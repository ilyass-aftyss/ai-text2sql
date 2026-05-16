"""
API REST FastAPI — Exposition du pipeline Text-to-SQL.
Permet l'intégration dans des applications tierces.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.utils import sanitize_user_input
from core.explainer import SQLExplainer
from core.few_shot_selector import FewShotSelector
from core.memory import ConversationMemory
from core.schema_retriever import SchemaRetriever
from core.sql_generator import SQLGenerator
from core.sql_validator import SQLValidator
from database.connector import DatabaseConnector
from database.executor import SafeExecutor
from database.schema_extractor import SchemaExtractor
from vectorstore.indexer import VectorStoreIndexer

# ─── Modèles Pydantic ────────────────────────────────────────────────────────


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000, description="Question en langage naturel")
    session_id: str = Field(default="default", description="Identifiant de session (pour la mémoire)")


class QueryResponse(BaseModel):
    question: str
    sql: str
    explanation: str
    success: bool
    row_count: int
    attempts: int
    data: list[dict[str, Any]]
    execution_time_ms: float


class ConnectRequest(BaseModel):
    database_url: str = Field(..., description="URI de connexion SQLAlchemy")


class HealthResponse(BaseModel):
    status: str
    version: str
    ollama_model: str


class SchemaResponse(BaseModel):
    tables: list[dict[str, Any]]


# ─── Application FastAPI ─────────────────────────────────────────────────────

app = FastAPI(
    title="Text-to-SQL Intelligent API",
    description="API REST pour interroger une base de données en langage naturel via Llama 3.1",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# État global (simplifié pour le mode API)
_pipeline: dict[str, Any] = {}
_sessions: dict[str, ConversationMemory] = {}


def _get_pipeline() -> dict[str, Any]:
    if not _pipeline:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de données non connectée. Appelez /connect d'abord.",
        )
    return _pipeline


def _get_session(session_id: str) -> ConversationMemory:
    if session_id not in _sessions:
        _sessions[session_id] = ConversationMemory()
    return _sessions[session_id]


# ─── Routes ──────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse, tags=["Système"])
async def health() -> HealthResponse:
    """Vérifie l'état de l'API."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        ollama_model=settings.ollama_model,
    )


@app.post("/connect", tags=["Base de données"])
async def connect(request: ConnectRequest) -> dict[str, str]:
    """Connecte la base de données et indexe son schéma."""
    try:
        connector = DatabaseConnector(request.database_url)
        ok, msg = connector.test_connection()
        if not ok:
            raise HTTPException(status_code=400, detail=msg)

        extractor = SchemaExtractor(connector.connect())
        schema_info = extractor.extract()

        indexer = VectorStoreIndexer()
        indexer.index_few_shot("data/few_shot/examples.json")
        indexer.reset_schema()
        indexer.index_schema(schema_info.to_chunks())

        executor = SafeExecutor(connector)
        schema_retriever = SchemaRetriever(indexer)
        few_shot_selector = FewShotSelector(indexer)

        _pipeline.clear()
        _pipeline.update(
            {
                "generator": SQLGenerator(
                    schema_retriever,
                    few_shot_selector,
                    dialect=connector.dialect,
                ),
                "validator": SQLValidator(executor),
                "explainer": SQLExplainer(),
                "schema_info": schema_info,
            }
        )

        return {"status": "connected", "tables": str(len(schema_info.tables))}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/query", response_model=QueryResponse, tags=["Requêtes"])
async def query(request: QueryRequest) -> QueryResponse:
    """Génère et exécute une requête SQL depuis une question en langage naturel."""
    pipeline = _get_pipeline()
    session = _get_session(request.session_id)

    question = sanitize_user_input(request.question)
    generator: SQLGenerator = pipeline["generator"]
    validator: SQLValidator = pipeline["validator"]
    explainer: SQLExplainer = pipeline["explainer"]

    try:
        sql = generator.generate(question, chat_history=session.get_history())
        schema_text = pipeline["schema_info"].to_text()
        validation_result = validator.validate_and_correct(sql, question, schema_text)
        explanation = explainer.explain(question, validation_result.sql)

        data: list[dict[str, Any]] = []
        row_count = 0
        execution_time_ms = 0.0

        if validation_result.execution_result and validation_result.execution_result.success:
            data = validation_result.execution_result.data.to_dict(orient="records")
            row_count = validation_result.execution_result.row_count
            execution_time_ms = validation_result.execution_result.execution_time_ms

        session.add_turn(
            question=question,
            sql=validation_result.sql,
            explanation=explanation,
            row_count=row_count,
            attempts=validation_result.attempts,
        )

        return QueryResponse(
            question=question,
            sql=validation_result.sql,
            explanation=explanation,
            success=validation_result.succeeded,
            row_count=row_count,
            attempts=validation_result.attempts,
            data=data,
            execution_time_ms=execution_time_ms,
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/schema", response_model=SchemaResponse, tags=["Base de données"])
async def get_schema() -> SchemaResponse:
    """Retourne le schéma de la base de données connectée."""
    pipeline = _get_pipeline()
    schema_info = pipeline["schema_info"]
    tables = [
        {
            "name": t.name,
            "columns": [
                {"name": c.name, "type": c.type, "primary_key": c.primary_key}
                for c in t.columns
            ],
            "foreign_keys": t.foreign_keys,
        }
        for t in schema_info.tables
    ]
    return SchemaResponse(tables=tables)


@app.delete("/session/{session_id}", tags=["Sessions"])
async def clear_session(session_id: str) -> dict[str, str]:
    """Vide la mémoire d'une session."""
    if session_id in _sessions:
        _sessions[session_id].clear()
    return {"status": "cleared", "session_id": session_id}


# ─── Point d'entrée ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
