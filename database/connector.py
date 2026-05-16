"""
Couche de connexion à la base de données via SQLAlchemy.
Support PostgreSQL, MySQL et SQLite.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.utils import get_logger

logger = get_logger("database.connector")


class DatabaseConnector:
    """
    Gestionnaire de connexion SQLAlchemy.
    Applique automatiquement le mode lecture seule si configuré.
    """

    def __init__(self, database_url: str | None = None) -> None:
        self._url = database_url or settings.database_url
        self._engine: Engine | None = None

    # ─── Connexion ──────────────────────────────────────────────────────────

    def connect(self) -> Engine:
        """Crée et retourne le moteur SQLAlchemy."""
        if self._engine is not None:
            return self._engine

        kwargs: dict[str, Any] = {
            "echo": settings.debug,
        }

        if self._url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool

        self._engine = create_engine(self._url, **kwargs)

        if settings.sql_read_only and self._url.startswith("postgresql"):
            self._apply_readonly(self._engine)

        logger.info(f"✅ Connecté à : {self._safe_url()}")
        return self._engine

    def _apply_readonly(self, engine: Engine) -> None:
        """Force le mode READ ONLY sur PostgreSQL."""

        @event.listens_for(engine, "connect")
        def set_readonly(dbapi_connection: Any, connection_record: Any) -> None:
            dbapi_connection.set_session(readonly=True, autocommit=False)

        logger.info("🔒 Mode READ ONLY activé sur PostgreSQL")

    def disconnect(self) -> None:
        """Ferme proprement le moteur."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            logger.info("🔌 Connexion fermée")

    # ─── Tests de connexion ─────────────────────────────────────────────────

    def test_connection(self) -> tuple[bool, str]:
        """Teste la connexion. Retourne (succès, message)."""
        try:
            engine = self.connect()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True, "Connexion réussie ✅"
        except SQLAlchemyError as exc:
            return False, f"Erreur de connexion : {exc}"

    # ─── Exécution ──────────────────────────────────────────────────────────

    def execute_query(self, sql: str) -> list[dict[str, Any]]:
        """
        Exécute une requête SELECT et retourne les résultats sous forme de liste de dicts.
        Lève une exception en cas d'erreur SQL.
        """
        engine = self.connect()
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = result.fetchall()
            return [dict(zip(columns, row)) for row in rows]

    # ─── Helpers ────────────────────────────────────────────────────────────

    def _safe_url(self) -> str:
        """Masque le mot de passe dans l'URL pour les logs."""
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(self._url)
        if parsed.password:
            safe = parsed._replace(netloc=f"{parsed.username}:***@{parsed.hostname}:{parsed.port}")
            return urlunparse(safe)
        return self._url

    @property
    def dialect(self) -> str:
        """Retourne le dialecte SQL (postgresql, mysql, sqlite)."""
        return self._url.split("+")[0].split(":")[0].lower()
