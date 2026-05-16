"""
Extraction des métadonnées du schéma SQL (tables, colonnes, types, FK).
Produit des chunks textuels sémantiques pour la couche RAG.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.utils import get_logger

logger = get_logger("database.schema_extractor")


@dataclass
class ColumnInfo:
    name: str
    type: str
    nullable: bool
    primary_key: bool
    comment: str | None = None


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    foreign_keys: list[dict[str, str]] = field(default_factory=list)
    comment: str | None = None


@dataclass
class SchemaInfo:
    tables: list[TableInfo] = field(default_factory=list)

    def to_text(self) -> str:
        """Représentation textuelle complète du schéma."""
        lines: list[str] = []
        for table in self.tables:
            lines.append(f"Table: {table.name}")
            if table.comment:
                lines.append(f"  Description: {table.comment}")
            for col in table.columns:
                pk_marker = " [PK]" if col.primary_key else ""
                null_marker = " NOT NULL" if not col.nullable else ""
                comment = f" -- {col.comment}" if col.comment else ""
                lines.append(f"  - {col.name}: {col.type}{pk_marker}{null_marker}{comment}")
            for fk in table.foreign_keys:
                lines.append(
                    f"  FK: {fk['column']} → {fk['referred_table']}.{fk['referred_column']}"
                )
            lines.append("")
        return "\n".join(lines)

    def to_chunks(self) -> list[dict[str, str]]:
        """
        Découpe le schéma en chunks sémantiques (une entrée par table).
        Chaque chunk contient l'id, le texte, et les métadonnées.
        """
        chunks: list[dict[str, str]] = []
        for table in self.tables:
            text_parts: list[str] = [f"Table: {table.name}"]
            if table.comment:
                text_parts.append(f"Description: {table.comment}")
            col_parts = []
            for col in table.columns:
                pk = " [PK]" if col.primary_key else ""
                col_parts.append(f"{col.name} ({col.type}){pk}")
            text_parts.append("Colonnes: " + ", ".join(col_parts))
            for fk in table.foreign_keys:
                text_parts.append(
                    f"Relation: {fk['column']} référence {fk['referred_table']}({fk['referred_column']})"
                )
            chunks.append(
                {
                    "id": f"table_{table.name}",
                    "text": "\n".join(text_parts),
                    "table_name": table.name,
                }
            )
        return chunks


class SchemaExtractor:
    """Extrait et structure les métadonnées d'une base de données."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def extract(self) -> SchemaInfo:
        """Extrait le schéma complet de la base de données."""
        inspector = inspect(self._engine)
        schema_info = SchemaInfo()

        for table_name in inspector.get_table_names():
            table = self._extract_table(inspector, table_name)
            schema_info.tables.append(table)
            logger.debug(f"📋 Table extraite : {table_name} ({len(table.columns)} colonnes)")

        logger.info(f"✅ Schéma extrait : {len(schema_info.tables)} tables")
        return schema_info

    def _extract_table(self, inspector: object, table_name: str) -> TableInfo:
        """Extrait les informations d'une table spécifique."""
        raw_cols = inspector.get_columns(table_name)
        pk_cols = set(inspector.get_pk_constraint(table_name).get("constrained_columns", []))
        raw_fks = inspector.get_foreign_keys(table_name)

        columns = [
            ColumnInfo(
                name=col["name"],
                type=str(col["type"]),
                nullable=col.get("nullable", True),
                primary_key=col["name"] in pk_cols,
                comment=col.get("comment"),
            )
            for col in raw_cols
        ]

        foreign_keys = [
            {
                "column": fk["constrained_columns"][0] if fk["constrained_columns"] else "",
                "referred_table": fk["referred_table"],
                "referred_column": fk["referred_columns"][0] if fk["referred_columns"] else "",
            }
            for fk in raw_fks
            if fk.get("constrained_columns") and fk.get("referred_columns")
        ]

        return TableInfo(
            name=table_name,
            columns=columns,
            foreign_keys=foreign_keys,
        )
