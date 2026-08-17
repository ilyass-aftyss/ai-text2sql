"""
Couche de connexion à la base de données via SQLAlchemy.
Support PostgreSQL, MySQL et SQLite.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.utils import get_logger

logger = get_logger("database.connector")


@dataclass(frozen=True)
class DatabaseSSLConfig:
    """Options TLS utilisées pour une connexion à une base distante."""

    enabled: bool = False
    mode: str = "verify-full"
    ca_cert_path: str | None = None
    ca_cert_content: str | None = None
    verify_identity: bool = True


class DatabaseConnector:
    """
    Gestionnaire de connexion SQLAlchemy.
    Applique automatiquement le mode lecture seule si configuré.
    """

    def __init__(
        self,
        database_url: str | None = None,
        ssl_config: DatabaseSSLConfig | None = None,
    ) -> None:
        self._url = database_url or settings.database_url
        self._ssl_config = ssl_config or DatabaseSSLConfig(
            enabled=settings.database_ssl_enabled,
            mode=settings.database_ssl_mode,
            ca_cert_path=settings.database_ssl_ca_cert_path,
            ca_cert_content=settings.database_ssl_ca_cert_content,
            verify_identity=settings.database_ssl_verify_identity,
        )
        self._engine: Engine | None = None
        self._temporary_ca_path: str | None = None

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
        elif self._ssl_config.enabled:
            kwargs["connect_args"] = self._ssl_connect_args()

        try:
            self._engine = create_engine(self._url, **kwargs)
        except Exception:
            self._remove_temporary_ca()
            raise

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
        self._remove_temporary_ca()

    def __del__(self) -> None:
        """Nettoie le certificat temporaire si le connecteur est libéré."""
        self._remove_temporary_ca()

    # ─── Tests de connexion ─────────────────────────────────────────────────

    def test_connection(self) -> tuple[bool, str]:
        """Teste la connexion. Retourne (succès, message)."""
        try:
            engine = self.connect()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True, "Connexion réussie ✅"
        except (SQLAlchemyError, ValueError) as exc:
            self.disconnect()
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

    def _ssl_connect_args(self) -> dict[str, Any]:
        """Construit les options TLS propres au dialecte SQLAlchemy."""
        if self.dialect not in {"postgresql", "mysql"}:
            raise ValueError(
                "SSL avec certificat CA est pris en charge pour PostgreSQL et MySQL uniquement."
            )

        ca_path = self._resolve_ca_path()
        if not ca_path:
            raise ValueError(
                "Un certificat CA est requis lorsque SSL est activé. "
                "Définissez DATABASE_SSL_CA_CERT_PATH ou fournissez le certificat."
            )

        if self.dialect == "postgresql":
            mode = self._ssl_config.mode.lower()
            valid_modes = {"require", "verify-ca", "verify-full"}
            if mode not in valid_modes:
                self._remove_temporary_ca()
                raise ValueError(
                    f"Mode SSL PostgreSQL invalide : {mode}. "
                    f"Valeurs acceptées : {', '.join(sorted(valid_modes))}."
                )
            return {"sslmode": mode, "sslrootcert": ca_path}

        # PyMySQL (mysql+pymysql) reçoit les paramètres TLS via `ssl`.
        return {
            "ssl": {
                "ca": ca_path,
                "check_hostname": self._ssl_config.verify_identity,
            }
        }

    def _resolve_ca_path(self) -> str | None:
        """Retourne un chemin CA existant, ou matérialise le contenu PEM en fichier privé."""
        if self._ssl_config.ca_cert_path:
            path = Path(self._ssl_config.ca_cert_path).expanduser()
            if not path.is_file():
                raise ValueError(f"Certificat CA introuvable : {path}")
            return str(path)

        if self._ssl_config.ca_cert_content:
            pem_content = self._normalise_pem(self._ssl_config.ca_cert_content)
            if "BEGIN CERTIFICATE" not in pem_content:
                raise ValueError("Le certificat CA doit être au format PEM.")
            if self._temporary_ca_path is None:
                fd, path = tempfile.mkstemp(prefix="text2sql-ca-", suffix=".pem")
                try:
                    # newline="\n" prevents Python on Windows from converting
                    # LF to CRLF, which libpq can reject as "bad end line".
                    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as cert_file:
                        cert_file.write(pem_content)
                    os.chmod(path, 0o600)
                except Exception:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    try:
                        os.unlink(path)
                    except FileNotFoundError:
                        pass
                    raise
                self._temporary_ca_path = path
            return self._temporary_ca_path

        return None

    @staticmethod
    def _normalise_pem(content: str) -> str:
        """Normalise un certificat PEM collé depuis Windows, navigateur ou JSON."""
        normalised = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
        # Also accept a PEM copied from a JSON/env representation containing literal
        # ``\n`` sequences instead of actual line breaks.
        if "\\n" in normalised and "\n" not in normalised:
            normalised = normalised.replace("\\n", "\n")

        # Keep only complete certificate blocks. This tolerates surrounding quotes,
        # Markdown fences, labels, and whitespace copied from a provider dashboard.
        blocks = re.findall(
            r"-----BEGIN CERTIFICATE-----\s*(.*?)\s*-----END CERTIFICATE-----",
            normalised,
            flags=re.DOTALL,
        )
        if not blocks:
            return normalised.strip() + "\n"

        canonical_blocks: list[str] = []
        for body in blocks:
            encoded_body = re.sub(r"\s+", "", body)
            wrapped_body = "\n".join(
                encoded_body[index : index + 64] for index in range(0, len(encoded_body), 64)
            )
            canonical_blocks.append(
                "-----BEGIN CERTIFICATE-----\n"
                f"{wrapped_body}\n"
                "-----END CERTIFICATE-----"
            )
        return "\n".join(canonical_blocks) + "\n"

    def _remove_temporary_ca(self) -> None:
        """Supprime le fichier CA temporaire créé depuis un contenu PEM."""
        if self._temporary_ca_path:
            try:
                os.unlink(self._temporary_ca_path)
            except FileNotFoundError:
                pass
            self._temporary_ca_path = None

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
