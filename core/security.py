"""
Couche 5 (partielle) — Sécurité SQL.
Bloque toute requête DML/DDL via regex + analyse AST sqlparse.
"""

from __future__ import annotations

import re

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import DDL, DML, Keyword

from app.utils import get_logger

logger = get_logger("core.security")

# Mots-clés destructifs interdits
_FORBIDDEN_KEYWORDS: frozenset[str] = frozenset(
    {
        "DROP", "DELETE", "INSERT", "UPDATE", "TRUNCATE",
        "ALTER", "CREATE", "REPLACE", "MERGE", "UPSERT",
        "EXEC", "EXECUTE", "GRANT", "REVOKE", "ATTACH",
    }
)

# Pattern regex de pré-filtre rapide
_FORBIDDEN_PATTERN = re.compile(
    r"\b(" + "|".join(_FORBIDDEN_KEYWORDS) + r")\b",
    flags=re.IGNORECASE,
)


class SecurityGuard:
    """
    Validateur de sécurité SQL à deux niveaux :
    1. Pré-filtre regex rapide
    2. Analyse AST sqlparse (précise)
    """

    def validate(self, sql: str) -> tuple[bool, str]:
        """
        Valide la sécurité d'une requête SQL.

        Returns:
            (True, "") si la requête est sûre
            (False, "raison") si elle est bloquée
        """
        if not sql or not sql.strip():
            return False, "Requête vide"

        # ── Niveau 1 : regex ────────────────────────────────────────────────
        match = _FORBIDDEN_PATTERN.search(sql)
        if match:
            keyword = match.group(0).upper()
            return False, f"Mot-clé interdit détecté : {keyword}"

        # ── Niveau 2 : analyse AST ──────────────────────────────────────────
        try:
            parsed = sqlparse.parse(sql)
            for statement in parsed:
                result = self._check_statement(statement)
                if result is not None:
                    return False, result
        except Exception as exc:
            logger.warning(f"Erreur lors de l'analyse AST : {exc}")

        # ── Niveau 3 : vérification SELECT ──────────────────────────────────
        if not self._is_select(sql):
            return False, "Seules les requêtes SELECT sont autorisées"

        return True, ""

    def _check_statement(self, statement: Statement) -> str | None:
        """Vérifie les tokens d'une instruction pour détecter les opérations interdites."""
        for token in statement.flatten():
            if token.ttype in (DDL, DML):
                val = token.normalized.upper()
                if val in _FORBIDDEN_KEYWORDS:
                    return f"Opération SQL interdite : {val}"
            if token.ttype is Keyword:
                val = token.normalized.upper()
                if val in _FORBIDDEN_KEYWORDS:
                    return f"Mot-clé interdit : {val}"
        return None

    def _is_select(self, sql: str) -> bool:
        """Vérifie que la requête commence par SELECT (ou WITH pour les CTE)."""
        cleaned = sql.strip().lstrip("(").upper()
        return cleaned.startswith("SELECT") or cleaned.startswith("WITH")
