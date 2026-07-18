"""
tests/conftest.py — Pytest fixtures for backend tests.

Tests use an isolated 'ppi_test' MongoDB database.
Each test that touches the DB gets a fresh set of collections,
dropped after the test completes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Point at the test database before importing app modules
os.environ.setdefault("MONGODB_DB", "ppi_test")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")

from app.core.database import get_db, ping_db, ensure_indexes
from app.core.config import settings
from app.main import create_app

TEST_DB_NAME = "ppi_test"

COLLECTIONS = [
    "documents",
    "assets",
    "relationships",
    "ocr_jobs",
    "ocr_pages",
    "ocr_regions",
    "work_order_fields",
    "work_order_links",
    "review_tasks",
    "audit_events",
]


@pytest.fixture(scope="session")
def mongodb_available():
    """Skip all DB tests if MongoDB is not reachable."""
    return ping_db(db_name=TEST_DB_NAME)


@pytest.fixture()
def test_db(mongodb_available):
    """
    Yield a fresh test database.
    Drops all test collections before and after each test.
    The client is intentionally NOT closed here — the app's lifespan
    may close it, so we catch InvalidOperation on teardown cleanup.
    """
    if not mongodb_available:
        pytest.skip("MongoDB not available — skipping DB test")
    db = get_db(db_name=TEST_DB_NAME)
    # Clean slate before test
    for col in COLLECTIONS:
        try:
            db[col].drop()
        except Exception:
            pass
    ensure_indexes(db)
    yield db
    # Clean up after test — client may have been closed by app lifespan
    for col in COLLECTIONS:
        try:
            db[col].drop()
        except Exception:
            pass
    # Reset the singleton so the next test gets a fresh client
    import app.core.database as db_module
    db_module._client = None


@pytest.fixture()
def api_client(test_db):
    """FastAPI TestClient wired to the test database."""
    # Override the DB used by the app
    import app.core.database as db_module
    original_get_db = db_module.get_db

    def _test_get_db(db_name=None, uri=None):
        return test_db

    db_module.get_db = _test_get_db

    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    db_module.get_db = original_get_db


@pytest.fixture()
def seeded_db(mongodb_available, project_root):
    """
    Yield a pre-seeded test database with corpus data imported.
    Used by Phase 4 tests that need real data to query against.
    Drops all collections after the test.
    """
    if not mongodb_available:
        pytest.skip("MongoDB not available — skipping DB test")

    db = get_db(db_name=TEST_DB_NAME)
    # Clean slate
    all_cols = COLLECTIONS + ["drawing_overlays", "work_order_links", "work_order_fields",
                               "ocr_jobs", "ocr_pages", "ocr_regions"]
    for col in all_cols:
        try:
            db[col].drop()
        except Exception:
            pass
    ensure_indexes(db)

    # Run the importer to seed data into the test DB
    from importer import run_import
    run_import(db_name=TEST_DB_NAME)

    yield db

    for col in all_cols:
        try:
            db[col].drop()
        except Exception:
            pass
    import app.core.database as db_module
    db_module._client = None


@pytest.fixture()
def seeded_api_client(seeded_db):
    """FastAPI TestClient wired to the seeded test database."""
    import app.core.database as db_module
    original_get_db = db_module.get_db

    def _test_get_db(db_name=None, uri=None):
        return seeded_db

    db_module.get_db = _test_get_db

    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    db_module.get_db = original_get_db



@pytest.fixture()
def project_root() -> Path:
    """Absolute path to the project root (ET AI 2/)."""
    return Path(__file__).parent.parent.parent


@pytest.fixture()
def manifests_dir(project_root) -> Path:
    return project_root / "Data" / "manifests"


@pytest.fixture()
def ocr_dir(project_root) -> Path:
    return project_root / "Data" / "derived" / "ocr" / "work-orders-001"


@pytest.fixture()
def active_manifest(manifests_dir) -> dict:
    path = manifests_dir / "active_document_manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def asset_registry(manifests_dir) -> dict:
    path = manifests_dir / "pid_asset_registry.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def pid_relationships(manifests_dir) -> dict:
    path = manifests_dir / "pid_relationships.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def ocr_job(ocr_dir) -> dict:
    path = ocr_dir / "job.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def review_queue(ocr_dir) -> dict:
    path = ocr_dir / "review_queue.json"
    return json.loads(path.read_text(encoding="utf-8"))
