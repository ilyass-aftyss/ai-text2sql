"""
Indexation ChromaDB — schéma SQL et exemples few-shot.
Utilise Sentence Transformers (open-source, 100% local).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.utils import get_logger

logger = get_logger("vectorstore.indexer")


class VectorStoreIndexer:
    """
    Gère l'indexation dans ChromaDB avec Sentence Transformers.
    Deux collections : schéma SQL et exemples few-shot.
    """

    def __init__(self) -> None:
        self._client: chromadb.PersistentClient | None = None
        self._model: SentenceTransformer | None = None

    # ─── Initialisation ─────────────────────────────────────────────────────

    def _get_client(self) -> chromadb.PersistentClient:
        if self._client is None:
            Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=settings.chroma_persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            logger.info(f"📦 ChromaDB initialisé : {settings.chroma_persist_dir}")
        return self._client

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info(f"🔄 Chargement du modèle d'embedding : {settings.embedding_model}")
            self._model = SentenceTransformer(
                settings.embedding_model,
                device=settings.embedding_device,
            )
            logger.info("✅ Modèle d'embedding chargé")
        return self._model

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Génère les embeddings pour une liste de textes."""
        model = self._get_model()
        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return embeddings.tolist()

    # ─── Schéma SQL ─────────────────────────────────────────────────────────

    def index_schema(self, chunks: list[dict[str, str]]) -> None:
        """
        Indexe les chunks du schéma SQL dans ChromaDB.

        Args:
            chunks: Liste de dicts avec 'id', 'text', 'table_name'
        """
        if not chunks:
            logger.warning("Aucun chunk de schéma à indexer")
            return

        client = self._get_client()
        collection = client.get_or_create_collection(
            name=settings.chroma_collection_schema,
            metadata={"hnsw:space": "cosine"},
        )

        ids = [c["id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        metadatas = [{"table_name": c.get("table_name", "")} for c in chunks]
        embeddings = self._embed(texts)

        collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.info(f"✅ {len(chunks)} chunks de schéma indexés")

    def reset_schema(self) -> None:
        """Supprime et recrée la collection schéma (lors d'un changement de BDD)."""
        client = self._get_client()
        try:
            client.delete_collection(settings.chroma_collection_schema)
        except Exception:
            pass
        logger.info("🗑  Collection schéma réinitialisée")

    # ─── Exemples Few-Shot ──────────────────────────────────────────────────

    def index_few_shot(self, examples_path: str | Path | None = None) -> None:
        """
        Indexe les exemples few-shot depuis un fichier JSON.
        Format attendu : [{"question": "...", "sql": "...", "domain": "..."}]
        """
        path = Path(examples_path or "data/few_shot/examples.json")
        if not path.exists():
            logger.warning(f"Fichier few-shot introuvable : {path}")
            return

        with path.open(encoding="utf-8") as f:
            examples: list[dict[str, str]] = json.load(f)

        if not examples:
            return

        client = self._get_client()
        collection = client.get_or_create_collection(
            name=settings.chroma_collection_fewshot,
            metadata={"hnsw:space": "cosine"},
        )

        ids = [f"example_{i}" for i in range(len(examples))]
        texts = [ex["question"] for ex in examples]
        metadatas = [
            {"sql": ex["sql"], "domain": ex.get("domain", "general")}
            for ex in examples
        ]
        embeddings = self._embed(texts)

        collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.info(f"✅ {len(examples)} exemples few-shot indexés")

    # ─── Recherche ──────────────────────────────────────────────────────────

    def search_schema(self, query: str, n_results: int = 5) -> list[str]:
        """Recherche les chunks de schéma les plus pertinents pour une question."""
        client = self._get_client()
        try:
            collection = client.get_collection(settings.chroma_collection_schema)
        except Exception:
            return []

        embedding = self._embed([query])[0]
        results = collection.query(
            query_embeddings=[embedding],
            n_results=min(n_results, collection.count()),
        )
        return results["documents"][0] if results["documents"] else []

    def search_few_shot(self, query: str, n_results: int = 3) -> list[dict[str, str]]:
        """Recherche les exemples few-shot les plus proches sémantiquement."""
        client = self._get_client()
        try:
            collection = client.get_collection(settings.chroma_collection_fewshot)
        except Exception:
            return []

        embedding = self._embed([query])[0]
        results = collection.query(
            query_embeddings=[embedding],
            n_results=min(n_results, collection.count()),
        )

        examples: list[dict[str, str]] = []
        if results["documents"] and results["metadatas"]:
            for question, meta in zip(results["documents"][0], results["metadatas"][0]):
                examples.append({"question": question, "sql": meta.get("sql", "")})
        return examples

    def schema_collection_count(self) -> int:
        """Retourne le nombre de chunks dans la collection schéma."""
        try:
            client = self._get_client()
            col = client.get_collection(settings.chroma_collection_schema)
            return col.count()
        except Exception:
            return 0
