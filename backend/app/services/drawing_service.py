"""
services/drawing_service.py — Drawing metadata and overlay seed for the P&ID Explorer.

Drawing overlays are approximate percentage-based positions for each verified asset tag.
They are seeded once into MongoDB `drawing_overlays` collection and served through the
/api/v1/drawings endpoints.

IMPORTANT: These coordinates are manually estimated, NOT extracted from the P&ID images.
Every overlay record carries state='coordinate_approximate' so the UI can label them clearly.
We never claim automatic P&ID topology extraction.
"""
from __future__ import annotations

from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

# Map drawing_id → actual P&ID filename (original, never modified)
DRAWING_FILES = {
    "PCP-PID-001": "Refractor unit.png",
    "PCP-PID-002": "Distilation_Seperation unit.png",
    "PCP-PID-003": "Storage and tank farm.png",
    "PCP-PID-004": "Utilities_boiler_house.png",
    "PCP-PID-005": "Effluent treatment plant.png",
}

DRAWING_AREAS = {
    "PCP-PID-001": "reactor",
    "PCP-PID-002": "distillation",
    "PCP-PID-003": "storage",
    "PCP-PID-004": "utilities",
    "PCP-PID-005": "effluent_treatment",
}

DRAWING_LABELS = {
    "PCP-PID-001": "Reactor Unit",
    "PCP-PID-002": "Distillation / Separation Unit",
    "PCP-PID-003": "Storage & Tank Farm",
    "PCP-PID-004": "Utilities / Boiler House",
    "PCP-PID-005": "Effluent Treatment Plant",
}

# Approximate percentage-based overlay positions for each tag.
# Format: { tag: (x_pct, y_pct) } — origin top-left of the image.
# These are manually estimated and marked 'coordinate_approximate'.
OVERLAY_POSITIONS: dict[str, tuple[float, float]] = {
    # PCP-PID-001 Reactor
    "R-201":   (0.48, 0.42),
    "P-101":   (0.22, 0.70),
    "P-102":   (0.35, 0.70),
    "PSV-201": (0.62, 0.28),
    "TIC-201": (0.55, 0.38),
    "XV-101":  (0.18, 0.55),
    "XV-102":  (0.28, 0.55),
    "XV-201":  (0.48, 0.22),
    # PCP-PID-002 Distillation
    "C-301":   (0.45, 0.40),
    "E-301":   (0.45, 0.72),
    "E-302":   (0.70, 0.28),
    "P-301":   (0.72, 0.65),
    "LIC-301": (0.32, 0.50),
    "TIC-301": (0.55, 0.55),
    "PIC-301": (0.60, 0.32),
    "XV-301":  (0.25, 0.35),
    "XV-302":  (0.25, 0.48),
    "XV-303":  (0.25, 0.62),
    # PCP-PID-003 Storage
    "V-401":   (0.32, 0.45),
    "V-402":   (0.62, 0.45),
    "P-401":   (0.48, 0.72),
    "LAH-401": (0.28, 0.30),
    "LAL-401": (0.28, 0.60),
    "LIT-402": (0.65, 0.30),
    "XV-401":  (0.20, 0.55),
    "XV-402":  (0.48, 0.55),
    "XV-403":  (0.75, 0.55),
    # PCP-PID-004 Boiler
    "B-501":   (0.45, 0.42),
    "P-501":   (0.25, 0.70),
    "PSV-501": (0.58, 0.22),
    "FIC-501": (0.35, 0.35),
    "PIC-501": (0.55, 0.35),
    "LIC-501": (0.45, 0.60),
    "XV-501":  (0.20, 0.50),
    "XV-502":  (0.72, 0.50),
    # PCP-PID-005 ETP — lead demo drawing
    "ETP-601": (0.42, 0.48),
    "P-601":   (0.28, 0.72),
    "AIT-601": (0.65, 0.38),
    "AAH-601": (0.72, 0.30),
    "LIC-601": (0.38, 0.30),
    "LV-601":  (0.38, 0.68),
    "XV-603":  (0.58, 0.68),
}

# Map tag → drawing_id
TAG_TO_DRAWING = {
    "R-201": "PCP-PID-001", "P-101": "PCP-PID-001", "P-102": "PCP-PID-001",
    "PSV-201": "PCP-PID-001", "TIC-201": "PCP-PID-001",
    "XV-101": "PCP-PID-001", "XV-102": "PCP-PID-001", "XV-201": "PCP-PID-001",
    "C-301": "PCP-PID-002", "E-301": "PCP-PID-002", "E-302": "PCP-PID-002",
    "P-301": "PCP-PID-002", "LIC-301": "PCP-PID-002", "TIC-301": "PCP-PID-002",
    "PIC-301": "PCP-PID-002", "XV-301": "PCP-PID-002", "XV-302": "PCP-PID-002",
    "XV-303": "PCP-PID-002",
    "V-401": "PCP-PID-003", "V-402": "PCP-PID-003", "P-401": "PCP-PID-003",
    "LAH-401": "PCP-PID-003", "LAL-401": "PCP-PID-003", "LIT-402": "PCP-PID-003",
    "XV-401": "PCP-PID-003", "XV-402": "PCP-PID-003", "XV-403": "PCP-PID-003",
    "B-501": "PCP-PID-004", "P-501": "PCP-PID-004", "PSV-501": "PCP-PID-004",
    "FIC-501": "PCP-PID-004", "PIC-501": "PCP-PID-004", "LIC-501": "PCP-PID-004",
    "XV-501": "PCP-PID-004", "XV-502": "PCP-PID-004",
    "ETP-601": "PCP-PID-005", "P-601": "PCP-PID-005", "AIT-601": "PCP-PID-005",
    "AAH-601": "PCP-PID-005", "LIC-601": "PCP-PID-005", "LV-601": "PCP-PID-005",
    "XV-603": "PCP-PID-005",
}


def seed_drawing_overlays(db) -> None:
    """
    Seed the `drawing_overlays` collection with approximate tag positions.
    Idempotent: uses upsert on (drawing_id, tag) compound key.
    """
    col = db.drawing_overlays
    # Ensure index
    col.create_index([("drawing_id", 1), ("tag", 1)], unique=True)

    count = 0
    for tag, (x_pct, y_pct) in OVERLAY_POSITIONS.items():
        drawing_id = TAG_TO_DRAWING.get(tag)
        if not drawing_id:
            continue
        doc = {
            "drawing_id": drawing_id,
            "tag": tag,
            "x_pct": x_pct,
            "y_pct": y_pct,
            "state": "coordinate_approximate",
            "note": "Manually estimated position — not extracted from drawing.",
        }
        col.update_one(
            {"drawing_id": drawing_id, "tag": tag},
            {"$set": doc},
            upsert=True,
        )
        count += 1

    log.info("drawing_overlays_seeded", count=count)


def get_drawings_list(db) -> list[dict]:
    """Return metadata for all 5 P&ID drawings."""
    result = []
    for drawing_id, filename in DRAWING_FILES.items():
        overlay_count = db.drawing_overlays.count_documents({"drawing_id": drawing_id})
        result.append({
            "drawing_id": drawing_id,
            "label": DRAWING_LABELS[drawing_id],
            "area": DRAWING_AREAS[drawing_id],
            "filename": filename,
            "image_url": f"/static/pid/{filename}",
            "overlay_count": overlay_count,
        })
    return result


def get_drawing_detail(db, drawing_id: str) -> dict | None:
    """Return drawing metadata plus all overlay positions for a drawing."""
    filename = DRAWING_FILES.get(drawing_id)
    if not filename:
        return None
    overlays = list(db.drawing_overlays.find({"drawing_id": drawing_id}, {"_id": 0}))
    return {
        "drawing_id": drawing_id,
        "label": DRAWING_LABELS.get(drawing_id, drawing_id),
        "area": DRAWING_AREAS.get(drawing_id, ""),
        "filename": filename,
        "image_url": f"/static/pid/{filename}",
        "overlays": overlays,
        "overlay_count": len(overlays),
        "coordinate_note": (
            "Overlay coordinates are manually estimated percentages of image dimensions, "
            "not extracted from the drawing. Each tag is marked 'coordinate_approximate'."
        ),
    }
