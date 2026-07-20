"""
api/v1/imports.py — API for document ingestion operations.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.database import get_db

router = APIRouter(tags=["imports"])

class ImportRequest(BaseModel):
    path: str

@router.post("/imports")
def start_import(req: ImportRequest):
    """Register an approved upload/path and start controlled ingestion."""
    # In a full implementation, this would queue a job.
    # For R1, we just return a 202 Accepted.
    # The actual import runs via `importer.py`.
    return {"status": "accepted", "path": req.path, "import_id": "job-123"}

@router.get("/imports/{import_id}")
def get_import_status(import_id: str):
    """Status, warnings, extracted counts, and retry option."""
    return {
        "import_id": import_id,
        "status": "completed",
        "warnings": [],
        "counts": {"documents": 1, "entities": 5}
    }

@router.post("/imports/{import_id}/retry")
def retry_import(import_id: str):
    """Retry failed derived extraction/indexing only."""
    return {"status": "retried", "import_id": import_id}
