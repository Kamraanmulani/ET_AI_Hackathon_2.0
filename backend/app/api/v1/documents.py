"""
api/v1/documents.py — GET /api/v1/documents

Returns all 30 active documents with provenance and extraction state.
Synthetic-demo documents always include the 'Synthetic demo data' label.
"""
from fastapi import APIRouter, HTTPException
from app.core.database import get_db
from app.repositories.document_repo import DocumentRepository

router = APIRouter()


@router.get("/documents", tags=["documents"])
def list_documents():
    db = get_db()
    repo = DocumentRepository(db)
    docs = repo.find_all()
    # Ensure synthetic label is always present in the response
    for doc in docs:
        if doc.get("provenance") == "synthetic_demo":
            doc.setdefault("synthetic_label", "Synthetic demo data")
    return {
        "total": len(docs),
        "documents": docs,
    }
