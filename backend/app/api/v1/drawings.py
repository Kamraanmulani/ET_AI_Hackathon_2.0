"""
api/v1/drawings.py — P&ID drawing catalogue and overlay endpoints.

GET /api/v1/drawings              → list all 5 P&ID drawings
GET /api/v1/drawings/{drawing_id} → drawing metadata + asset overlay positions
"""
from fastapi import APIRouter, HTTPException
from app.core.database import get_db
from app.services.drawing_service import get_drawings_list, get_drawing_detail

router = APIRouter()


@router.get("/drawings", tags=["drawings"])
def list_drawings():
    """Return metadata for all 5 Pragyan P&ID drawings."""
    db = get_db()
    return {
        "drawings": get_drawings_list(db),
        "total": 5,
        "note": (
            "Overlay coordinates are manually estimated (coordinate_approximate). "
            "No automatic P&ID topology extraction is claimed."
        ),
    }


@router.get("/drawings/{drawing_id}", tags=["drawings"])
def get_drawing(drawing_id: str):
    """Return drawing metadata and all asset overlay positions."""
    db = get_db()
    detail = get_drawing_detail(db, drawing_id.upper())
    if not detail:
        raise HTTPException(
            status_code=404,
            detail=f"Drawing '{drawing_id}' not found. Valid IDs: PCP-PID-001 through PCP-PID-005.",
        )
    return detail
