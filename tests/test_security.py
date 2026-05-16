"""
Tests unitaires — Couche sécurité SQL.
Vérifie le blocage des requêtes DML/DDL.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.security import SecurityGuard


@pytest.fixture
def guard() -> SecurityGuard:
    return SecurityGuard()


# ─── Requêtes valides ────────────────────────────────────────────────────────


class TestValidQueries:
    def test_simple_select(self, guard: SecurityGuard) -> None:
        ok, msg = guard.validate("SELECT * FROM users")
        assert ok is True
        assert msg == ""

    def test_select_with_where(self, guard: SecurityGuard) -> None:
        ok, msg = guard.validate("SELECT id, name FROM users WHERE active = 1")
        assert ok is True

    def test_select_with_join(self, guard: SecurityGuard) -> None:
        sql = """
            SELECT u.name, o.total
            FROM users u
            JOIN orders o ON u.id = o.user_id
            WHERE o.total > 100
        """
        ok, msg = guard.validate(sql)
        assert ok is True

    def test_select_with_aggregate(self, guard: SecurityGuard) -> None:
        sql = "SELECT COUNT(*) AS total, AVG(price) FROM products GROUP BY category"
        ok, msg = guard.validate(sql)
        assert ok is True

    def test_select_with_subquery(self, guard: SecurityGuard) -> None:
        sql = "SELECT * FROM orders WHERE user_id IN (SELECT id FROM users WHERE active = 1)"
        ok, msg = guard.validate(sql)
        assert ok is True

    def test_cte_query(self, guard: SecurityGuard) -> None:
        sql = "WITH ranked AS (SELECT *, ROW_NUMBER() OVER (ORDER BY score DESC) AS rn FROM scores) SELECT * FROM ranked WHERE rn <= 10"
        ok, msg = guard.validate(sql)
        assert ok is True


# ─── Requêtes bloquées ───────────────────────────────────────────────────────


class TestBlockedQueries:
    def test_drop_table(self, guard: SecurityGuard) -> None:
        ok, msg = guard.validate("DROP TABLE users")
        assert ok is False
        assert "DROP" in msg.upper() or "interdit" in msg.lower()

    def test_delete(self, guard: SecurityGuard) -> None:
        ok, msg = guard.validate("DELETE FROM users WHERE id = 1")
        assert ok is False

    def test_insert(self, guard: SecurityGuard) -> None:
        ok, msg = guard.validate("INSERT INTO users (name) VALUES ('hack')")
        assert ok is False

    def test_update(self, guard: SecurityGuard) -> None:
        ok, msg = guard.validate("UPDATE users SET name = 'hack' WHERE id = 1")
        assert ok is False

    def test_truncate(self, guard: SecurityGuard) -> None:
        ok, msg = guard.validate("TRUNCATE TABLE users")
        assert ok is False

    def test_alter(self, guard: SecurityGuard) -> None:
        ok, msg = guard.validate("ALTER TABLE users ADD COLUMN hacked TEXT")
        assert ok is False

    def test_create(self, guard: SecurityGuard) -> None:
        ok, msg = guard.validate("CREATE TABLE evil (id INT)")
        assert ok is False

    def test_mixed_select_drop(self, guard: SecurityGuard) -> None:
        ok, msg = guard.validate("SELECT * FROM users; DROP TABLE users")
        assert ok is False

    def test_empty_query(self, guard: SecurityGuard) -> None:
        ok, msg = guard.validate("")
        assert ok is False

    def test_empty_whitespace(self, guard: SecurityGuard) -> None:
        ok, msg = guard.validate("   ")
        assert ok is False

    def test_case_insensitive_drop(self, guard: SecurityGuard) -> None:
        ok, msg = guard.validate("drop table users")
        assert ok is False

    def test_exec_injection(self, guard: SecurityGuard) -> None:
        ok, msg = guard.validate("EXEC xp_cmdshell('dir')")
        assert ok is False
