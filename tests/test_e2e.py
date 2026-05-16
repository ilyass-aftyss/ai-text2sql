"""
Tests d'intégration End-to-End — Pipeline complet sur SQLite de démo.
Ces tests requièrent Ollama en cours d'exécution.
Passez la variable SKIP_E2E=1 pour les ignorer en CI.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# Skip si Ollama n'est pas disponible ou SKIP_E2E=1
SKIP_E2E = os.getenv("SKIP_E2E", "0") == "1"


@pytest.fixture(scope="module")
def demo_db_url() -> str:
    """Crée une base SQLite temporaire pour les tests E2E."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT,
            stock INTEGER DEFAULT 0
        );
        INSERT INTO products (name, price, category, stock) VALUES
            ('Laptop', 999.99, 'Electronics', 10),
            ('Mouse', 29.99, 'Electronics', 50),
            ('Desk', 299.99, 'Furniture', 5),
            ('Chair', 199.99, 'Furniture', 8),
            ('Monitor', 449.99, 'Electronics', 15);

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            product_id INTEGER REFERENCES products(id),
            quantity INTEGER DEFAULT 1,
            total_price REAL,
            order_date TEXT DEFAULT CURRENT_DATE
        );
        INSERT INTO orders (product_id, quantity, total_price) VALUES
            (1, 2, 1999.98),
            (2, 5, 149.95),
            (3, 1, 299.99),
            (1, 1, 999.99);
    """)
    conn.commit()
    conn.close()
    return f"sqlite:///{db_path}"


@pytest.mark.skipif(SKIP_E2E, reason="E2E tests skipped (SKIP_E2E=1 or Ollama unavailable)")
class TestSecurityE2E:
    """Tests de sécurité qui ne nécessitent pas Ollama."""

    def test_security_blocks_drop(self, demo_db_url: str) -> None:
        from core.security import SecurityGuard

        guard = SecurityGuard()
        ok, msg = guard.validate("DROP TABLE products")
        assert ok is False

    def test_security_allows_select(self, demo_db_url: str) -> None:
        from core.security import SecurityGuard

        guard = SecurityGuard()
        ok, msg = guard.validate("SELECT * FROM products")
        assert ok is True


@pytest.mark.skipif(SKIP_E2E, reason="E2E tests skipped (SKIP_E2E=1 or Ollama unavailable)")
class TestDatabaseE2E:
    """Tests d'intégration base de données."""

    def test_connector_sqlite(self, demo_db_url: str) -> None:
        from database.connector import DatabaseConnector

        connector = DatabaseConnector(demo_db_url)
        ok, msg = connector.test_connection()
        assert ok is True

    def test_schema_extraction(self, demo_db_url: str) -> None:
        from database.connector import DatabaseConnector
        from database.schema_extractor import SchemaExtractor

        connector = DatabaseConnector(demo_db_url)
        extractor = SchemaExtractor(connector.connect())
        schema = extractor.extract()

        assert len(schema.tables) == 2
        table_names = [t.name for t in schema.tables]
        assert "products" in table_names
        assert "orders" in table_names

    def test_safe_execution_select(self, demo_db_url: str) -> None:
        from database.connector import DatabaseConnector
        from database.executor import SafeExecutor

        connector = DatabaseConnector(demo_db_url)
        executor = SafeExecutor(connector)
        result = executor.execute("SELECT COUNT(*) AS total FROM products")

        assert result.success is True
        assert result.row_count == 1
        assert result.data.iloc[0]["total"] == 5

    def test_safe_execution_blocks_delete(self, demo_db_url: str) -> None:
        from database.connector import DatabaseConnector
        from database.executor import SafeExecutor

        connector = DatabaseConnector(demo_db_url)
        executor = SafeExecutor(connector)
        result = executor.execute("DELETE FROM products WHERE id = 1")

        assert result.success is False
        assert "SÉCURITÉ" in result.error_message


@pytest.mark.skipif(SKIP_E2E, reason="E2E tests skipped (SKIP_E2E=1 or Ollama unavailable)")
class TestVectorStoreE2E:
    """Tests d'intégration ChromaDB + Sentence Transformers."""

    def test_index_and_search_schema(self, demo_db_url: str, tmp_path: Path) -> None:
        import os

        os.environ["CHROMA_PERSIST_DIR"] = str(tmp_path / "chroma")

        from database.connector import DatabaseConnector
        from database.schema_extractor import SchemaExtractor
        from vectorstore.indexer import VectorStoreIndexer

        connector = DatabaseConnector(demo_db_url)
        extractor = SchemaExtractor(connector.connect())
        schema = extractor.extract()
        chunks = schema.to_chunks()

        indexer = VectorStoreIndexer()
        indexer.index_schema(chunks)

        results = indexer.search_schema("products price", n_results=2)
        assert len(results) > 0
        assert any("products" in r.lower() for r in results)
