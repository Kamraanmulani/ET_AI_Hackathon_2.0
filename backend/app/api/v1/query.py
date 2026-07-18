"""
api/v1/query.py — Grounded search/query workspace.

GET /api/v1/query?q=...&asset_tag=...

Returns cited OCR evidence matching the query.
Uses MongoDB text/regex search only — no external LLM, no Qdrant.
Returns "insufficient_evidence" when nothing matches.

Every result shows:
- source_id, source_page, source_region_id (provenance)
- text excerpt
- confidence
- review_state (pending_review | verified | rejected | unreadable)
- asset_tag mentions found in the text (if any)
"""
from fastapi import APIRouter, Query
from app.core.database import get_db
import re

router = APIRouter()

# Tags from the reviewed P&ID registry (for mention detection)
KNOWN_TAGS = {
    "R-201", "P-101", "P-102", "PSV-201", "TIC-201", "XV-101", "XV-102", "XV-201",
    "C-301", "E-301", "E-302", "P-301", "LIC-301", "TIC-301", "PIC-301",
    "V-401", "V-402", "P-401", "LAH-401", "LAL-401", "LIT-402",
    "B-501", "P-501", "PSV-501", "FIC-501", "PIC-501", "LIC-501",
    "ETP-601", "P-601", "AIT-601", "AAH-601", "LIC-601", "LV-601", "XV-603",
}


def _find_tag_mentions(text: str) -> list[str]:
    found = []
    for tag in KNOWN_TAGS:
        if re.search(re.escape(tag), text, re.IGNORECASE):
            found.append(tag)
    return found


@router.get("/query", tags=["query"])
def grounded_query(
    q: str = Query(..., min_length=2, description="Search query"),
    asset_tag: str | None = Query(None, description="Optional: filter by asset tag"),
    limit: int = Query(20, ge=1, le=50),
):
    """
    Search OCR regions and work-order fields for the query string.
    Returns cited evidence or 'insufficient_evidence'.
    No LLM calls, no Qdrant, no external data.
    """
    db = get_db()

    # Build MongoDB filter
    text_filter: dict = {"text": {"$regex": re.escape(q), "$options": "i"}}
    if asset_tag:
        text_filter["text"]["$regex"] = "|".join([
            re.escape(q), re.escape(asset_tag.upper())
        ])

    # Search OCR regions
    regions = list(db.ocr_regions.find(text_filter, {"_id": 0}).limit(limit))

    # If asset_tag given, also pull work_order_links directly
    link_results = []
    if asset_tag:
        links = list(db.work_order_links.find(
            {"asset_tag": asset_tag.upper()},
            {"_id": 0}
        ).limit(limit))
        for link in links:
            # Enrich with region text
            region_id = link.get("source_region_id")
            if region_id:
                region = db.ocr_regions.find_one({"region_id": region_id}, {"_id": 0})
                if region:
                    link["text"] = region.get("text", "")
                    link["confidence"] = region.get("confidence")
            link_results.append(link)

    # Build citation list
    citations = []
    for region in regions:
        text = region.get("text", "")
        citations.append({
            "citation_type": "ocr_region",
            "source_id": region.get("source_id", "work-orders-001"),
            "source_page": region.get("source_page"),
            "source_region_id": region.get("region_id"),
            "text": text,
            "confidence": region.get("confidence"),
            "review_state": region.get("review_state", "pending_review"),
            "state": region.get("state", "AI proposed"),
            "asset_tag_mentions": _find_tag_mentions(text),
            "page_image_url": (
                f"/static/ocr-pages/page-{region.get('source_page', 0):03d}.png"
                if region.get("source_page") else None
            ),
        })

    for link in link_results:
        text = link.get("text", "")
        citations.append({
            "citation_type": "asset_link",
            "source_id": link.get("source_id"),
            "source_page": link.get("source_page"),
            "source_region_id": link.get("source_region_id"),
            "text": text,
            "confidence": link.get("confidence"),
            "review_state": link.get("review_state", "pending_review"),
            "state": link.get("state", "AI proposed"),
            "asset_tag": link.get("asset_tag"),
            "page_image_url": (
                f"/static/ocr-pages/page-{link.get('source_page', 0):03d}.png"
                if link.get("source_page") else None
            ),
        })

    # Deduplicate by region_id
    seen = set()
    unique_citations = []
    for c in citations:
        key = c.get("source_region_id") or id(c)
        if key not in seen:
            seen.add(key)
            unique_citations.append(c)

    if not unique_citations:
        return {
            "result": "insufficient_evidence",
            "query": q,
            "asset_tag": asset_tag,
            "message": (
                "No matching records found in the active corpus. "
                "The corpus contains only the five Pragyan P&IDs and the scanned work-order PDF. "
                "OCR extraction may be incomplete; 98 review tasks are pending human verification."
            ),
            "citations": [],
        }

    return {
        "result": "evidence_found",
        "query": q,
        "asset_tag": asset_tag,
        "citation_count": len(unique_citations),
        "citations": unique_citations,
        "provenance_note": (
            "All results are OCR-extracted text (AI proposed) unless a reviewer has verified them. "
            "Review state is shown on each citation."
        ),
    }
