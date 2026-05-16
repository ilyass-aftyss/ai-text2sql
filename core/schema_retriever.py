"""
Couche 1 — Schema Retrieval avec RAG.
Récupère les tables/colonnes pertinentes via recherche vectorielle ChromaDB.
"""

from __future__ import annotations

from app.utils import get_logger
from vectorstore.indexer import VectorStoreIndexer

logger = get_logger("core.schema_retriever")


class SchemaRetriever:
    """
    Couche RAG pour la récupération du schéma pertinent.
    À chaque requête, retourne uniquement les tables/colonnes utiles.
    """

    def __init__(self, indexer: VectorStoreIndexer) -> None:
        self._indexer = indexer

    def retrieve(self, question: str, n_results: int = 5) -> str:
        """
        Retrouve les chunks de schéma les plus pertinents pour une question.

        Args:
            question: La question en langage naturel de l'utilisateur.
            n_results: Nombre de chunks à retourner.

        Returns:
            Texte du schéma pertinent, prêt à injecter dans le prompt.
        """
        chunks = self._indexer.search_schema(question, n_results=n_results)

        if not chunks:
            logger.warning("Aucun chunk de schéma trouvé — le schéma n'est peut-être pas indexé")
            return "Schéma non disponible."

        schema_text = "\n\n".join(chunks)
        logger.debug(f"📋 {len(chunks)} chunks de schéma récupérés pour : {question[:60]}...")
        return schema_text
