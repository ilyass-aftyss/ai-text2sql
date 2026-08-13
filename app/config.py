"""
Configuration globale du projet Text-to-SQL.
Chargement depuis les variables d'environnement (.env).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres centralisés de l'application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Base de données ---
    database_url: str = Field(
        default="sqlite:///./demo.sqlite",
        description="URI de connexion SQLAlchemy",
    )
    database_ssl_enabled: bool = Field(
        default=False,
        description="Active TLS pour la connexion à la base de données",
    )
    database_ssl_mode: str = Field(
        default="verify-full",
        description="Mode SSL PostgreSQL (require, verify-ca ou verify-full)",
    )
    database_ssl_ca_cert_path: str | None = Field(
        default=None,
        description="Chemin vers le certificat CA PEM de la base de données",
    )
    database_ssl_ca_cert_content: str | None = Field(
        default=None,
        description="Contenu PEM du certificat CA (à utiliser via un secret)",
    )
    database_ssl_verify_identity: bool = Field(
        default=True,
        description="Vérifie le nom d'hôte pour les connexions MySQL TLS",
    )

    # --- LLM (Ollama) ---
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.1")
    ollama_embed_model: str = Field(default="nomic-embed-text")

    # --- Embeddings (Sentence Transformers) ---
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    embedding_device: Literal["cpu", "cuda", "mps"] = Field(default="cpu")

    # --- ChromaDB ---
    chroma_persist_dir: str = Field(default="./data/chroma_db")
    chroma_collection_schema: str = Field(default="schema_chunks")
    chroma_collection_fewshot: str = Field(default="few_shot_examples")

    # --- Self-correction ---
    max_correction_attempts: int = Field(default=3, ge=1, le=5)

    # --- Sécurité ---
    sql_read_only: bool = Field(default=True)

    # --- FastAPI ---
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # --- Application ---
    app_title: str = Field(default="Text-to-SQL Intelligent")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retourne l'instance singleton des paramètres."""
    return Settings()


settings = get_settings()
