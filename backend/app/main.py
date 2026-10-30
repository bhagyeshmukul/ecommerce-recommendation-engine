"""FastAPI lifecycle: verify the offline bundle and database before serving."""

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.recommendation_routes import router
from app.db.session import SessionLocal
from app.services.recommendation_service import load_bundle, verify_snapshot
from src.train_model import BUNDLE_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bundle = load_bundle(Path(os.getenv("MODEL_BUNDLE_DIR", str(BUNDLE_DIR))))
    with SessionLocal() as session:
        verify_snapshot(session, app.state.bundle)
    yield


app = FastAPI(
    title="Retail Recommendation Lab",
    version="2.0.0",
    description="Purchase-based collaborative filtering with reproducible offline evaluation.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(SQLAlchemyError)
async def database_failure(request: Request, exc: SQLAlchemyError):
    logging.getLogger(__name__).error(
        "Database operation failed: %s", type(exc).__name__
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable. Please retry."},
    )


@app.get("/health")
def health():
    """Liveness is distinct from readiness: a process can be alive with a failed DB."""
    return {"status": "ok"}


@app.get("/ready")
def ready(request: Request):
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
            verify_snapshot(session, request.app.state.bundle)
        return {
            "status": "ready",
            "model_version": request.app.state.bundle.model.model_version,
        }
    except (SQLAlchemyError, RuntimeError):
        return JSONResponse(status_code=503, content={"status": "not_ready"})
