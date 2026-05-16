"""
Tests unitaires — Validation syntaxique SQL.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.sql_validator import SQLValidator


class TestSyntaxValidation:
    """Tests de la validation syntaxique sans exécution."""

    @pytest.fixture
    def validator_stub(self) -> SQLValidator:
        """Validator avec executor simulé."""
        from unittest.mock import MagicMock

        mock_executor = MagicMock()
        mock_executor.execute.return_value = MagicMock(
            success=True,
            data=__import__("pandas").DataFrame(),
            row_count=0,
            execution_time_ms=0.0,
        )
        return SQLValidator(mock_executor)

    def test_valid_select_syntax(self, validator_stub: SQLValidator) -> None:
        ok, msg = validator_stub.validate_syntax("SELECT * FROM users")
        assert ok is True

    def test_valid_complex_query(self, validator_stub: SQLValidator) -> None:
        sql = """
            SELECT u.name, COUNT(o.id) AS orders
            FROM users u
            LEFT JOIN orders o ON u.id = o.user_id
            GROUP BY u.id, u.name
            HAVING COUNT(o.id) > 2
            ORDER BY orders DESC
        """
        ok, msg = validator_stub.validate_syntax(sql)
        assert ok is True

    def test_empty_query_invalid(self, validator_stub: SQLValidator) -> None:
        ok, msg = validator_stub.validate_syntax("")
        assert ok is False


class TestMetrics:
    """Tests des métriques d'évaluation."""

    def test_exact_match_identical(self) -> None:
        from evaluation.metrics import exact_match
        assert exact_match("SELECT * FROM users", "SELECT * FROM users") is True

    def test_exact_match_case_insensitive(self) -> None:
        from evaluation.metrics import exact_match
        assert exact_match("select * from users", "SELECT * FROM users") is True

    def test_exact_match_different(self) -> None:
        from evaluation.metrics import exact_match
        assert exact_match("SELECT id FROM users", "SELECT * FROM users") is False

    def test_execution_match_same_data(self) -> None:
        from evaluation.metrics import execution_match
        predicted = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        reference = [{"id": 2, "name": "Bob"}, {"id": 1, "name": "Alice"}]
        assert execution_match(predicted, reference) is True

    def test_execution_match_different_data(self) -> None:
        from evaluation.metrics import execution_match
        predicted = [{"id": 1, "name": "Alice"}]
        reference = [{"id": 1, "name": "Bob"}]
        assert execution_match(predicted, reference) is False

    def test_execution_match_empty(self) -> None:
        from evaluation.metrics import execution_match
        assert execution_match([], []) is True
        assert execution_match(None, []) is False
