"""
api/v1/assets.py — Asset registry endpoints.

GET /api/v1/assets              → list all 31 assets
GET /api/v1/assets/{tag}        → asset + relationships
GET /api/v1/assets/{tag}/evidence → full Asset 360 evidence
GET /api/v1/assets/{tag}/audit  → audit timeline
"""
from fastapi import APIRouter, HTTPException
from app.core.database import get_db
from app.repositories.asset_repo import AssetRepository
from app.services.evidence_service import get_asset_evidence, get_asset_audit, get_asset_evidence_graph

router = APIRouter()


@router.get("/assets/{tag}/evidence-graph", tags=["assets"])
def get_evidence_graph(tag: str):
    """Return Asset Evidence Graph (nodes and edges)."""
    db = get_db()
    result = get_asset_evidence_graph(db, tag)
    if not result or not result["nodes"]:
        raise HTTPException(
            status_code=404,
            detail=f"Asset '{tag.upper()}' not found for graph visualization.",
        )
    return result


@router.get("/assets", tags=["assets"])
def list_assets():
    db = get_db()
    repo = AssetRepository(db)
    assets = repo.find_all_assets()
    return {
        "total": len(assets),
        "assets": assets,
    }


@router.get("/assets/{tag}/evidence", tags=["assets"])
def get_evidence(tag: str):
    """Return full Asset 360 evidence: relationships, linked OCR, audit timeline."""
    db = get_db()
    result = get_asset_evidence(db, tag)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Asset '{tag.upper()}' not found in the P&ID registry.",
        )
    return result


@router.get("/assets/{tag}/audit", tags=["assets"])
def get_audit(tag: str):
    """Return audit timeline for an asset tag."""
    db = get_db()
    events = get_asset_audit(db, tag)
    return {
        "tag": tag.upper(),
        "event_count": len(events),
        "events": events,
    }


@router.get("/assets/{tag}", tags=["assets"])
def get_asset(tag: str):
    db = get_db()
    repo = AssetRepository(db)
    asset = repo.find_asset_by_tag(tag.upper())
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset '{tag}' not found in registry.")
    relationships = repo.find_relationships_for_tag(tag.upper())
    return {
        "asset": asset,
        "relationships": relationships,
    }
