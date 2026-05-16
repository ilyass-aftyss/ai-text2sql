"""
Exécution sécurisée des requêtes SQL.
Applique les contrôles de sécurité avant toute exécution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.utils import get_logger, results_to_dataframe, timer
from core.security import SecurityGuard
from database.connector import DatabaseConnector

import pandas as pd

logger = get_logger("database.executor")


@dataclass
class ExecutionResult:
    """Résultat d'une exécution de requête SQL."""

    success: bool
    data: pd.DataFrame
    error_message: str | None = None
    row_count: int = 0
    execution_time_ms: float = 0.0

    @property
    def has_data(self) -> bool:
        return self.success and not self.data.empty


class SafeExecutor:
    """
    Exécute les requêtes SQL avec validation sécurité préalable.
    Bloque toute requête DML/DDL.
    """

    def __init__(self, connector: DatabaseConnector) -> None:
        self._connector = connector
        self._security = SecurityGuard()

    def execute(self, sql: str) -> ExecutionResult:
        """
        Exécute une requête SQL de manière sécurisée.

        Args:
            sql: La requête SQL à exécuter.

        Returns:
            ExecutionResult contenant les données ou l'erreur.
        """
        import time

        # ── 1. Validation sécurité ──────────────────────────────────────────
        is_safe, security_msg = self._security.validate(sql)
        if not is_safe:
            logger.warning(f"🚫 Requête bloquée : {security_msg}")
            return ExecutionResult(
                success=False,
                data=pd.DataFrame(),
                error_message=f"SÉCURITÉ : {security_msg}",
            )

        # ── 2. Exécution ────────────────────────────────────────────────────
        start = time.perf_counter()
        try:
            with timer("Exécution SQL"):
                raw_results = self._connector.execute_query(sql)

            elapsed_ms = (time.perf_counter() - start) * 1000
            df = results_to_dataframe(raw_results)

            logger.info(f"✅ {len(df)} lignes retournées en {elapsed_ms:.0f}ms")
            return ExecutionResult(
                success=True,
                data=df,
                row_count=len(df),
                execution_time_ms=elapsed_ms,
            )

        except SQLAlchemyError as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            error_msg = str(exc).split("\n")[0]
            logger.warning(f"❌ Erreur SQL : {error_msg}")
            return ExecutionResult(
                success=False,
                data=pd.DataFrame(),
                error_message=error_msg,
                execution_time_ms=elapsed_ms,
            )
