"""
Couche 2 — Few-Shot Dynamique.
Sélectionne les 3 exemples NL→SQL les plus proches sémantiquement.
"""

from __future__ import annotations

from app.utils import get_logger
from prompts.generation import format_few_shot_examples
from vectorstore.indexer import VectorStoreIndexer

logger = get_logger("core.few_shot_selector")


class FewShotSelector:
    """
    Sélection dynamique des exemples few-shot par similarité sémantique.
    Améliore la précision syntaxique et structurelle des requêtes générées.
    """

    def __init__(self, indexer: VectorStoreIndexer, n_examples: int = 3) -> None:
        self._indexer = indexer
        self._n_examples = n_examples

    def select(self, question: str) -> str:
        """
        Sélectionne et formate les exemples few-shot pour une question donnée.

        Args:
            question: La question en langage naturel.

        Returns:
            Texte formaté des exemples, prêt à injecter dans le prompt.
        """
        examples = self._indexer.search_few_shot(question, n_results=self._n_examples)

        if not examples:
            logger.debug("Aucun exemple few-shot disponible")
            return "Aucun exemple disponible."

        logger.debug(f"💡 {len(examples)} exemples few-shot sélectionnés")
        return format_few_shot_examples(examples)
