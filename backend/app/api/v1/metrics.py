"""
api/v1/metrics.py — GET /api/v1/metrics

Returns extraction, link, and review counts from MongoDB.
No fabricated values; if MongoDB is unavailable the endpoint returns 503.
"""
from fastapi import APIRouter, Response
from app.core.database import get_db, ping_db
from app.repositories.document_repo import DocumentRepository
from app.repositories.asset_repo import AssetRepository
from app.repositories.ocr_repo import OcrRepository
from app.repositories.review_repo import ReviewRepository

router = APIRouter()


@router.get("/metrics", tags=["metrics"])
def get_metrics(response: Response):
    if not ping_db():
        response.status_code = 503
        return {"error": "MongoDB unavailable. See GET /api/v1/health for details."}

    db = get_db()
    doc_repo = DocumentRepository(db)
    asset_repo = AssetRepository(db)
    ocr_repo = OcrRepository(db)
    review_repo = ReviewRepository(db)

    all_docs = doc_repo.find_all()
    original_count = sum(1 for d in all_docs if d.get("provenance") == "original")
    synthetic_count = sum(1 for d in all_docs if d.get("provenance") == "synthetic_demo")

    return {
        "documents": {
            "total": doc_repo.count(),
            "original": original_count,
            "synthetic_demo": synthetic_count,
        },
        "assets": {
            "total": asset_repo.count_assets(),
            "relationships": asset_repo.count_relationships(),
        },
        "ocr": {
            "total_regions": ocr_repo.count_regions(),
            "pending_review_regions": ocr_repo.count_pending_regions(),
            "candidate_fields": ocr_repo.count_fields(),
            "candidate_links": ocr_repo.count_links(),
        },
        "review": {
            "total_tasks": review_repo.count_tasks(),
            "pending_tasks": review_repo.count_pending(),
            "audit_events": review_repo.count_events(),
        },
    }
