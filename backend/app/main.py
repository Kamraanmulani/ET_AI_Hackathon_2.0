"""
app/main.py — FastAPI application factory.

Startup sequence:
1. Configure structured logging.
2. Attempt MongoDB connection, create indexes, seed drawing overlays.
3. Initialise Qdrant collection (if enabled and reachable).
4. Initialise Neo4j constraints (if enabled and reachable).
5. Mount API v1 router (including copilot and graph endpoints).
6. Mount static file routes for P&ID images and OCR page crops.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import close_client, ensure_indexes, get_db, ping_db
from app.core.logging import configure_logging
from app.api.v1 import health, documents, assets, review, metrics, drawings, query, copilot, graph, imports

configure_logging(settings.log_level)
log = structlog.get_logger(__name__)

# Paths relative to backend/ working directory
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_PID_DIR = _PROJECT_ROOT / "Data" / "P&IDs"
_OCR_PAGE_DIR = _PROJECT_ROOT / "Data" / "derived" / "ocr" / "work-orders-001" / "page_images"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: connect to MongoDB, Qdrant, Neo4j, then clean up."""
    log.info("ppi_startup", version=settings.app_version)

    if ping_db():
        db = get_db()
        ensure_indexes(db)
        # Seed drawing overlays if not already present
        from app.services.drawing_service import seed_drawing_overlays
        seed_drawing_overlays(db)
        log.info("mongodb_ready", db=settings.mongodb_db)
    else:
        log.warning(
            "mongodb_unavailable",
            hint=(
                "Start MongoDB Community (mongod) and set MONGODB_URI in .env. "
                "See infra/mongodb/README.md."
            ),
        )

    # Initialise Qdrant collection
    if settings.rag_vector_enabled:
        from app.services import qdrant_service
        ok = qdrant_service.ensure_collection()
        if ok:
            log.info("qdrant_ready", collection=settings.qdrant_collection)
        else:
            log.warning("qdrant_unavailable", hint="Start Qdrant: docker compose -f infra/rag-compose.yml up -d")

    # Initialise Neo4j constraints
    if settings.rag_graph_enabled:
        from app.services import neo4j_service
        ok = neo4j_service.ensure_constraints()
        if ok:
            log.info("neo4j_ready", uri=settings.neo4j_uri)
        else:
            log.warning("neo4j_unavailable", hint="Start Neo4j: docker compose -f infra/rag-compose.yml up -d")

    yield  # Application runs here

    # Cleanup
    from app.services import neo4j_service
    neo4j_service.reset_driver()
    close_client()
    log.info("ppi_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Pragyan Plant Intelligence — source-grounded asset knowledge workspace. "
            "Read-only plant knowledge support. Not a plant-control system."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — allow the Vite dev server (port 5173) during development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    # Static files: P&ID source images (read-only, originals never modified)
    if _PID_DIR.exists():
        app.mount("/static/pid", StaticFiles(directory=str(_PID_DIR)), name="pid_images")

    # Static files: OCR rendered page images
    if _OCR_PAGE_DIR.exists():
        app.mount("/static/ocr-pages", StaticFiles(directory=str(_OCR_PAGE_DIR)), name="ocr_pages")

    # Register API v1 routes
    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(health.router)
    api_router.include_router(documents.router)
    api_router.include_router(assets.router)
    api_router.include_router(review.router)
    api_router.include_router(metrics.router)
    api_router.include_router(drawings.router)
    api_router.include_router(query.router)
    api_router.include_router(copilot.router)
    api_router.include_router(graph.router)
    api_router.include_router(imports.router)
    app.include_router(api_router)

    return app


app = create_app()
