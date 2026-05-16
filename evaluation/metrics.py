"""
Métriques d'évaluation NL2SQL.
Exact Match (EM) et Execution Match (EX) — conformes au benchmark Spider.
"""

from __future__ import annotations

import re

import sqlparse


def normalize_sql(sql: str) -> str:
    """
    Normalise une requête SQL pour la comparaison (Exact Match).
    - Met en minuscule
    - Supprime les espaces superflus
    - Supprime les points-virgules finaux
    """
    sql = sql.lower().strip().rstrip(";").strip()
    sql = re.sub(r"\s+", " ", sql)
    parsed = sqlparse.parse(sql)
    if parsed:
        sql = str(parsed[0]).strip()
    return sql


def exact_match(predicted: str, reference: str) -> bool:
    """Vérifie si deux requêtes SQL sont syntaxiquement identiques après normalisation."""
    return normalize_sql(predicted) == normalize_sql(reference)


def execution_match(
    predicted_result: list[dict],
    reference_result: list[dict],
) -> bool:
    """
    Vérifie si deux jeux de résultats sont identiques.
    Insensible à l'ordre des colonnes et des lignes.
    """
    if predicted_result is None or reference_result is None:
        return False

    def normalize_row(row: dict) -> frozenset:
        return frozenset((k, str(v)) for k, v in row.items())

    predicted_set = {normalize_row(r) for r in predicted_result}
    reference_set = {normalize_row(r) for r in reference_result}
    return predicted_set == reference_set


class EvaluationReport:
    """Rapport d'évaluation agrégé."""

    def __init__(self) -> None:
        self.total = 0
        self.exact_matches = 0
        self.execution_matches = 0
        self.valid_sql = 0
        self.corrections_needed = 0
        self.latencies: list[float] = []

    def add_result(
        self,
        is_exact_match: bool,
        is_execution_match: bool,
        is_valid_sql: bool,
        needed_correction: bool,
        latency_ms: float,
    ) -> None:
        self.total += 1
        if is_exact_match:
            self.exact_matches += 1
        if is_execution_match:
            self.execution_matches += 1
        if is_valid_sql:
            self.valid_sql += 1
        if needed_correction:
            self.corrections_needed += 1
        self.latencies.append(latency_ms)

    @property
    def exact_match_rate(self) -> float:
        return self.exact_matches / self.total if self.total > 0 else 0.0

    @property
    def execution_match_rate(self) -> float:
        return self.execution_matches / self.total if self.total > 0 else 0.0

    @property
    def valid_sql_rate(self) -> float:
        return self.valid_sql / self.total if self.total > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0.0

    def summary(self) -> dict[str, float | int]:
        return {
            "total": self.total,
            "exact_match": round(self.exact_match_rate * 100, 2),
            "execution_match": round(self.execution_match_rate * 100, 2),
            "valid_sql_rate": round(self.valid_sql_rate * 100, 2),
            "corrections_rate": round(self.corrections_needed / self.total * 100, 2) if self.total else 0,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
        }
