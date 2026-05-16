"""
Couche 3 — Génération SQL via LLM (Llama 3.1 via Ollama).
Orchestration LangChain avec prompt structuré en 6 blocs.
"""

from __future__ import annotations

from langchain_ollama import ChatOllama

from app.config import settings
from app.utils import clean_sql, get_logger
from core.few_shot_selector import FewShotSelector
from core.schema_retriever import SchemaRetriever
from prompts.generation import build_generation_prompt, format_chat_history

logger = get_logger("core.sql_generator")


class SQLGenerator:
    """
    Génère des requêtes SQL depuis une question en langage naturel.
    Utilise Llama 3.1 via Ollama (100% local, pas d'API externe).
    """

    def __init__(
        self,
        schema_retriever: SchemaRetriever,
        few_shot_selector: FewShotSelector,
        dialect: str = "postgresql",
    ) -> None:
        self._schema_retriever = schema_retriever
        self._few_shot_selector = few_shot_selector
        self._dialect = dialect
        self._llm = self._build_llm()
        self._prompt = build_generation_prompt()
        self._chain = self._prompt | self._llm

    def _build_llm(self) -> ChatOllama:
        """Initialise le LLM Ollama (Llama 3.1)."""
        logger.info(
            f"🦙 Initialisation Ollama — modèle : {settings.ollama_model}"
        )
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.0,
            num_predict=512,
        )

    def generate(
        self,
        question: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> str:
        """
        Génère une requête SQL pour la question donnée.

        Args:
            question: La question en langage naturel.
            chat_history: Historique de conversation pour le contexte multi-tours.

        Returns:
            La requête SQL brute générée par le LLM.
        """
        logger.info(f"🔄 Génération SQL pour : {question[:80]}...")

        schema = self._schema_retriever.retrieve(question)
        few_shots = self._few_shot_selector.select(question)
        history_text = format_chat_history(chat_history or [])

        response = self._chain.invoke(
            {
                "dialect": self._dialect,
                "schema_retrieved": schema,
                "few_shot_examples": few_shots,
                "chat_history": history_text,
                "question": question,
                "messages": [],
            }
        )

        raw_sql = response.content if hasattr(response, "content") else str(response)
        sql = clean_sql(raw_sql)

        logger.info(f"✅ SQL généré : {sql[:100]}...")
        return sql
