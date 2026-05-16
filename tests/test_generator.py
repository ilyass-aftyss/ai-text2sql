"""
Tests unitaires — Utilitaires et nettoyage SQL.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.utils import clean_sql, detect_chart_type, sanitize_user_input


class TestCleanSQL:
    def test_remove_markdown_block(self) -> None:
        raw = "```sql\nSELECT * FROM users\n```"
        assert clean_sql(raw) == "SELECT * FROM users"

    def test_remove_sql_prefix(self) -> None:
        raw = "SQL : SELECT id FROM users"
        assert clean_sql(raw) == "SELECT id FROM users"

    def test_strip_semicolon(self) -> None:
        raw = "SELECT * FROM users;"
        assert clean_sql(raw) == "SELECT * FROM users"

    def test_strip_whitespace(self) -> None:
        raw = "  SELECT * FROM users  "
        assert clean_sql(raw) == "SELECT * FROM users"

    def test_plain_sql_unchanged(self) -> None:
        raw = "SELECT id, name FROM products WHERE price > 100"
        assert clean_sql(raw) == raw

    def test_empty_string(self) -> None:
        assert clean_sql("") == ""

    def test_multiline_markdown(self) -> None:
        raw = "```sql\nSELECT\n  id,\n  name\nFROM users\n```"
        result = clean_sql(raw)
        assert "SELECT" in result
        assert "```" not in result


class TestSanitizeInput:
    def test_truncate_long_input(self) -> None:
        long_input = "A" * 5000
        result = sanitize_user_input(long_input, max_length=2000)
        assert len(result) <= 2000

    def test_remove_control_chars(self) -> None:
        raw = "SELECT\x00 * FROM\x01 users"
        result = sanitize_user_input(raw)
        assert "\x00" not in result
        assert "\x01" not in result

    def test_normal_input_unchanged(self) -> None:
        normal = "Quels sont les 10 meilleurs clients ?"
        assert sanitize_user_input(normal) == normal


class TestDetectChartType:
    def test_bar_chart_for_small_categorical(self) -> None:
        import pandas as pd
        df = pd.DataFrame({"category": ["A", "B", "C"], "count": [10, 20, 30]})
        assert detect_chart_type(df) == "bar"

    def test_pie_for_very_few_categories(self) -> None:
        import pandas as pd
        df = pd.DataFrame({"label": ["X", "Y"], "value": [60, 40]})
        chart_type = detect_chart_type(df)
        assert chart_type in ("bar", "pie")

    def test_none_for_empty_df(self) -> None:
        import pandas as pd
        assert detect_chart_type(pd.DataFrame()) is None

    def test_none_for_single_column(self) -> None:
        import pandas as pd
        df = pd.DataFrame({"name": ["Alice", "Bob"]})
        assert detect_chart_type(df) is None
