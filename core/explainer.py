"""
Couche 5 — Explication pédagogique du SQL généré.
Chain LangChain secondaire, explication en français pour non-techniciens.
"""

from __future__ import annotations

from langchain_ollama import ChatOllama

from app.config import settings
from app.utils import get_logger
from prompts.explanation import build_explanation_prompt

logger = get_logger("core.explainer")


class SQLExplainer:
    """
    Génère une explication pédagogique de la requête SQL en français.
    Chain LangChain indépendante de la chaîne de génération principale.
    """

    def __init__(self) -> None:
        self._llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.3,
            num_predict=256,
        )
        self._prompt = build_explanation_prompt()
        self._chain = self._prompt | self._llm

    def explain(self, question: str, sql: str) -> str:
        """
        Génère une explication en langage naturel du SQL.

        Args:
            question: La question posée par l'utilisateur.
            sql: La requête SQL validée.

        Returns:
            Explication pédagogique en français.
        """
        try:
            response = self._chain.invoke({"question": question, "sql": sql})
            explanation = response.content if hasattr(response, "content") else str(response)
            logger.debug("✅ Explication générée")
            return explanation.strip()
        except Exception as exc:
            logger.warning(f"Erreur lors de la génération de l'explication : {exc}")
            return "L'explication n'a pas pu être générée."
