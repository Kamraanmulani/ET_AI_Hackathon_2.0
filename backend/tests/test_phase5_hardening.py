"""
tests/test_phase5_hardening.py — Phase 5 validation tests for error boundaries,
reliability, and missing dependencies.
"""
import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from importer import run_import

client = TestClient(app)

def test_health_returns_503_when_mongodb_unavailable(monkeypatch):
    """If ping_db fails, the health endpoint must return 503."""
    import app.api.v1.health as health_module
    monkeypatch.setattr(health_module, "ping_db", lambda **kwargs: False)
    
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"]["connected"] is False

def test_importer_aborts_when_mongodb_unavailable(monkeypatch):
    """The importer must abort with SystemExit(1) if MongoDB is unreachable."""
    import importer
    monkeypatch.setattr(importer, "ping_db", lambda **kwargs: False)
    
    with pytest.raises(SystemExit) as exc:
        run_import(db_name="ppi_test", dry_run=True)
    assert exc.value.code == 1

def test_importer_aborts_when_source_file_missing(monkeypatch, test_db):
    """The importer must raise FileNotFoundError if a referenced source file is missing."""
    import importer
    
    # Let get_db and ping_db succeed/use mock
    import app.core.database as db_module
    monkeypatch.setattr(db_module, "get_db", lambda **kwargs: test_db)
    monkeypatch.setattr(importer, "ping_db", lambda **kwargs: True)

    # Patch Path.exists to simulate a missing source file
    _orig_exists = Path.exists
    def mock_exists(self):
        if "active_document_manifest.json" in str(self):
            return False
        return _orig_exists(self)
    
    monkeypatch.setattr(Path, "exists", mock_exists)

    with pytest.raises(FileNotFoundError, match="Required data file not found"):
        run_import(db_name="ppi_test", dry_run=True)
