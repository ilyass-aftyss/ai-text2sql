"""
Utilitaires communs — formatage, logging, helpers.
"""

from __future__ import annotations

import logging
import re
import time
from contextlib import contextmanager
from typing import Any, Generator

import pandas as pd
from rich.console import Console
from rich.logging import RichHandler

console = Console()

# ─── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)

logger = logging.getLogger("text2sql")


def get_logger(name: str) -> logging.Logger:
    """Retourne un logger nommé."""
    return logging.getLogger(f"text2sql.{name}")


# ─── Timer ──────────────────────────────────────────────────────────────────


@contextmanager
def timer(label: str = "Opération") -> Generator[None, None, None]:
    """Context manager pour mesurer le temps d'exécution."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info(f"⏱  {label} terminé en {elapsed:.2f}s")


# ─── Formatage SQL ──────────────────────────────────────────────────────────


def clean_sql(raw: str) -> str:
    """
    Nettoie le SQL brut retourné par le LLM.
    Supprime les blocs markdown, espaces superflus, etc.
    """
    sql = raw.strip()
    sql = re.sub(r"```sql\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"```\s*", "", sql)
    sql = re.sub(r"^SQL\s*:\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"^sql\s*:\s*", "", sql)
    sql = sql.strip().rstrip(";").strip()
    return sql


# ─── Résultats → DataFrame ──────────────────────────────────────────────────


def results_to_dataframe(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Convertit une liste de dictionnaires en DataFrame pandas."""
    if not results:
        return pd.DataFrame()
    return pd.DataFrame(results)


# ─── Sanitisation des entrées ───────────────────────────────────────────────


def sanitize_user_input(text: str, max_length: int = 2000) -> str:
    """
    Sanitise l'entrée utilisateur avant injection dans les prompts.
    - Tronque à max_length caractères
    - Supprime les caractères de contrôle dangereux
    """
    text = text[:max_length]
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()


# ─── Détection du type de graphique ─────────────────────────────────────────


def detect_chart_type(df: pd.DataFrame) -> str | None:
    """
    Détecte automatiquement le type de graphique adapté au DataFrame.
    Retourne : 'bar', 'line', 'pie', 'scatter', ou None.
    """
    if df.empty or len(df.columns) < 2:
        return None

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    text_cols = df.select_dtypes(exclude="number").columns.tolist()

    if len(df) <= 10 and len(numeric_cols) == 1 and len(text_cols) >= 1:
        return "bar"
    if len(numeric_cols) >= 2:
        return "scatter"
    if len(df) <= 7 and len(numeric_cols) == 1:
        return "pie"
    if len(numeric_cols) >= 1:
        return "line"
    return None


# ─── Export CSV ─────────────────────────────────────────────────────────────


def dataframe_to_csv(df: pd.DataFrame) -> bytes:
    """Convertit un DataFrame en bytes CSV (UTF-8 BOM pour Excel)."""
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
