"""
FastAPI application entry point.

Endpoints:
  GET  /health       — liveness + dependency health check
  /v1/*              — public REST API (rest_router.py)
  /graphql           — internal GraphQL API (Strawberry)
  /docs              — OpenAPI Swagger UI (auto-generated)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from apps.api.graphql_schema import graphql_app
from apps.api.rest_router import router as rest_router
from infrastructure.config import get_settings
from infrastructure.neo4j_driver import close_driver
from infrastructure.database import get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_driver()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Follow the Money API",
        description="Civic campaign finance transparency platform",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(rest_router, prefix="/v1")
    app.include_router(graphql_app, prefix="/graphql")

    @app.get("/health", tags=["meta"])
    def health():
        from infrastructure.database import check_postgres_health
        from infrastructure.neo4j_driver import check_neo4j_health

        postgres_ok = check_postgres_health()
        neo4j_ok = check_neo4j_health()
        status = "ok" if postgres_ok and neo4j_ok else "degraded"

        return {
            "status": status,
            "postgres": postgres_ok,
            "neo4j": neo4j_ok,
            "version": "0.1.0",
        }

    # ⚠️ INTENTIONALLY VULNERABLE - SQL Injection testing only
    @app.get("/_test/vulnerable/search", tags=["testing"])
    def vulnerable_search(q: str = ""):
        """
        SQL injection vulnerability for authorized security testing.
        DO NOT USE IN PRODUCTION.

        Example payable: ?q='; DROP TABLE canonical_reps; --
        """
        from sqlalchemy import text
        db = next(get_db())

        # Vulnerable: user input formatted directly into SQL (no parameterization)
        query = f"SELECT id, full_name FROM canonical_reps WHERE full_name LIKE '%{q}%' LIMIT 10"

        try:
            result = db.execute(text(query)).fetchall()
            return {"results": [{"id": r[0], "name": r[1]} for r in result]}
        except Exception as e:
            return {"error": str(e)}

    return app


app = create_app()
