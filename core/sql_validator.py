"""
Couche 4 — Validation syntaxique et self-correction SQL.
Boucle LangGraph : génération → validation → correction (max N tentatives).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

import sqlparse
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from app.config import settings
from app.utils import clean_sql, get_logger
from core.security import SecurityGuard
from database.executor import ExecutionResult, SafeExecutor
from prompts.correction import build_correction_prompt

logger = get_logger("core.sql_validator")


# ─── État LangGraph ──────────────────────────────────────────────────────────


class ValidationState(TypedDict):
    """État partagé dans le graphe LangGraph."""
    question: str
    schema: str
    sql: str
    error: str | None
    attempt: int
    max_attempts: int
    final_sql: str
    execution_result: dict[str, Any]
    success: bool
    messages: Annotated[list, add_messages]


@dataclass
class ValidationResult:
    """Résultat complet de la validation + correction."""
    sql: str
    is_valid_syntax: bool
    execution_result: ExecutionResult | None = None
    attempts: int = 1
    errors: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.execution_result is not None and self.execution_result.success


# ─── Validateur principal ─────────────────────────────────────────────────────


class SQLValidator:
    """
    Pipeline de validation et self-correction SQL basé sur LangGraph.
    Boucle : exécution → erreur → correction LLM (jusqu'à max_attempts).
    """

    def __init__(self, executor: SafeExecutor) -> None:
        self._executor = executor
        self._security = SecurityGuard()
        self._llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.0,
            num_predict=256,
        )
        self._correction_prompt = build_correction_prompt()
        self._correction_chain = self._correction_prompt | self._llm
        self._graph = self._build_graph()

    # ─── Validation syntaxique ───────────────────────────────────────────────

    def validate_syntax(self, sql: str) -> tuple[bool, str]:
        """Valide la syntaxe SQL avec sqlparse."""
        try:
            statements = sqlparse.parse(sql)
            if not statements or not any(s.get_type() for s in statements):
                return False, "Aucune instruction SQL valide détectée"
            return True, ""
        except Exception as exc:
            return False, str(exc)

    # ─── LangGraph ───────────────────────────────────────────────────────────

    def _build_graph(self) -> Any:
        """Construit le graphe LangGraph de validation/correction."""
        graph = StateGraph(ValidationState)

        graph.add_node("validate_and_execute", self._node_validate)
        graph.add_node("correct_sql", self._node_correct)

        graph.set_entry_point("validate_and_execute")

        graph.add_conditional_edges(
            "validate_and_execute",
            self._should_correct,
            {"correct": "correct_sql", "done": END},
        )
        graph.add_conditional_edges(
            "correct_sql",
            self._should_retry,
            {"retry": "validate_and_execute", "done": END},
        )

        return graph.compile()

    def _node_validate(self, state: ValidationState) -> dict[str, Any]:
        """Nœud : validation sécurité + syntaxe + exécution."""
        sql = state["sql"]
        attempt = state["attempt"]

        logger.info(f"🔍 Tentative {attempt}/{state['max_attempts']} — validation : {sql[:60]}...")

        is_safe, security_msg = self._security.validate(sql)
        if not is_safe:
            return {
                "success": False,
                "error": security_msg,
                "final_sql": sql,
            }

        is_valid, syntax_msg = self.validate_syntax(sql)
        if not is_valid:
            return {
                "success": False,
                "error": f"Syntaxe invalide : {syntax_msg}",
                "final_sql": sql,
            }

        result = self._executor.execute(sql)
        if result.success:
            return {
                "success": True,
                "error": None,
                "final_sql": sql,
                "execution_result": {
                    "rows": result.data.to_dict(orient="records"),
                    "row_count": result.row_count,
                    "execution_time_ms": result.execution_time_ms,
                },
            }
        else:
            return {
                "success": False,
                "error": result.error_message,
                "final_sql": sql,
            }

    def _node_correct(self, state: ValidationState) -> dict[str, Any]:
        """Nœud : correction SQL via LLM avec le message d'erreur."""
        logger.info(f"🔧 Correction SQL — erreur : {state['error']}")

        response = self._correction_chain.invoke(
            {
                "schema": state["schema"],
                "question": state["question"],
                "sql_invalide": state["sql"],
                "message_erreur": state["error"],
                "attempt": state["attempt"],
                "max_attempts": state["max_attempts"],
            }
        )

        raw = response.content if hasattr(response, "content") else str(response)
        corrected_sql = clean_sql(raw)

        return {
            "sql": corrected_sql,
            "attempt": state["attempt"] + 1,
        }

    def _should_correct(self, state: ValidationState) -> str:
        """Décision : corriger ou terminer."""
        if state["success"]:
            return "done"
        if state["attempt"] >= state["max_attempts"]:
            logger.warning(f"❌ Limite de {state['max_attempts']} tentatives atteinte")
            return "done"
        return "correct"

    def _should_retry(self, state: ValidationState) -> str:
        """Après correction, recommencer la validation."""
        if state["attempt"] >= state["max_attempts"]:
            return "done"
        return "retry"

    # ─── Point d'entrée public ───────────────────────────────────────────────

    def validate_and_correct(
        self,
        sql: str,
        question: str,
        schema: str,
    ) -> ValidationResult:
        """
        Lance le pipeline complet de validation et self-correction.

        Args:
            sql: La requête SQL générée.
            question: La question originale de l'utilisateur.
            schema: Le schéma pertinent (pour le prompt de correction).

        Returns:
            ValidationResult avec le SQL final et les résultats d'exécution.
        """
        initial_state: ValidationState = {
            "question": question,
            "schema": schema,
            "sql": sql,
            "error": None,
            "attempt": 1,
            "max_attempts": settings.max_correction_attempts,
            "final_sql": sql,
            "execution_result": {},
            "success": False,
            "messages": [],
        }

        final_state = self._graph.invoke(initial_state)

        result = ValidationResult(
            sql=final_state["final_sql"],
            is_valid_syntax=True,
            attempts=final_state["attempt"],
        )

        if final_state["success"] and final_state.get("execution_result"):
            import pandas as pd

            rows = final_state["execution_result"].get("rows", [])
            exec_result = ExecutionResult(
                success=True,
                data=pd.DataFrame(rows),
                row_count=final_state["execution_result"].get("row_count", len(rows)),
                execution_time_ms=final_state["execution_result"].get("execution_time_ms", 0),
            )
            result.execution_result = exec_result
        else:
            error_msg = final_state.get("error", "Erreur inconnue")
            result.errors.append(error_msg or "Erreur inconnue")

        return result
