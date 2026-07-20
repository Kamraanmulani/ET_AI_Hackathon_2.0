"""
app/services/chunker.py — Deterministic source-structure-aware chunk builder.

Builds DocumentChunkRecord objects from MongoDB canonical records.
Every chunk has a stable chunk_id derived from source_hash + chunk_type + chunk_key,
ensuring idempotent upserts to Qdrant and Neo4j.

Chunk eligibility rules (from RAG_CC.md):
- Verified P&ID assets/relationships: always eligible
- Synthetic demo documents (SOPs, inspections, etc.): eligible with explicit label
- OCR work-order regions (AI proposed/pending): eligible with AI proposed label
- Rejected / unreadable: NEVER indexed for answers
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Iterator

from app.models.chunk import DocumentChunkRecord

# Verified P&ID asset tags from pid_asset_registry.json
KNOWN_TAGS: set[str] = {
    "R-201", "P-101", "P-102", "PSV-201", "TIC-201", "XV-101", "XV-102", "XV-201",
    "C-301", "E-301", "E-302", "P-301", "LIC-301", "TIC-301", "PIC-301",
    "XV-301", "XV-302", "XV-303",
    "V-401", "V-402", "P-401", "LAH-401", "LAL-401", "LIT-402",
    "XV-401", "XV-402", "XV-403",
    "B-501", "P-501", "PSV-501", "FIC-501", "PIC-501", "LIC-501",
    "XV-501", "XV-502",
    "ETP-601", "P-601", "AIT-601", "AAH-601", "LIC-601", "LV-601", "XV-603",
}


def _chunk_id(source_hash: str, chunk_type: str, chunk_key: str) -> str:
    """Generate a stable 32-char hex chunk ID from its canonical components."""
    raw = f"{source_hash}:{chunk_type}:{chunk_key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _extract_tags(text: str) -> list[str]:
    """Find known P&ID tags mentioned in text."""
    found = []
    for tag in KNOWN_TAGS:
        if re.search(r"(?<![A-Z0-9])" + re.escape(tag) + r"(?![A-Z0-9-])", text, re.IGNORECASE):
            found.append(tag)
    return found


def chunks_from_asset(asset_doc: dict, drawing_doc: dict | None = None) -> list[DocumentChunkRecord]:
    """
    Build one chunk per P&ID asset record.
    Assets from the verified registry are always eligible.
    """
    tag = asset_doc.get("tag", "")
    drawing_id = asset_doc.get("drawing_id", "")
    source_id = asset_doc.get("source_id", "")
    source_hash = asset_doc.get("source_hash", asset_doc.get("sha256", "unknown"))

    area = asset_doc.get("area", "")
    asset_type = asset_doc.get("asset_type", "")
    state = asset_doc.get("state", "verified")

    text_parts = [
        f"Asset tag: {tag}",
        f"Type: {asset_type}",
        f"Process area: {area}",
        f"Drawing: {drawing_id}",
        f"Review state: {state}",
    ]
    if drawing_doc:
        text_parts.append(f"Drawing title: {drawing_doc.get('title', '')}")

    text = "\n".join(p for p in text_parts if p)
    chunk_key = f"asset:{tag}"

    return [DocumentChunkRecord(
        chunk_id=_chunk_id(source_hash, "pid_asset", chunk_key),
        document_id=source_id,
        source_id=source_id,
        source_hash=source_hash,
        document_type="pid_asset",
        provenance="original",
        review_state=state,
        asset_tags=[tag],
        drawing_ids=[drawing_id] if drawing_id else [],
        page=None,
        source_region=None,
        text=text,
        chunk_type="pid_asset",
    )]


def chunks_from_relationship(rel_doc: dict) -> list[DocumentChunkRecord]:
    """One chunk per verified P&ID relationship."""
    from_tag = rel_doc.get("from_tag", "")
    to_tag = rel_doc.get("to_tag", "")
    rel_type = rel_doc.get("relationship_type", "")
    source_id = rel_doc.get("source_id", "")
    source_hash = rel_doc.get("source_hash", "unknown")
    state = rel_doc.get("state", "verified")

    text = (
        f"P&ID relationship: {from_tag} {rel_type} {to_tag}. "
        f"Source drawing: {source_id}. Review state: {state}."
    )
    chunk_key = f"rel:{from_tag}:{rel_type}:{to_tag}"

    return [DocumentChunkRecord(
        chunk_id=_chunk_id(source_hash, "pid_relationship", chunk_key),
        document_id=source_id,
        source_id=source_id,
        source_hash=source_hash,
        document_type="pid_relationship",
        provenance="original",
        review_state=state,
        asset_tags=[t for t in [from_tag, to_tag] if t],
        drawing_ids=[source_id] if source_id else [],
        page=None,
        source_region=None,
        text=text,
        chunk_type="pid_relationship",
    )]


def chunks_from_ocr_region(region_doc: dict, source_doc: dict | None = None) -> list[DocumentChunkRecord]:
    """
    One chunk per OCR region.
    Rejected and unreadable regions are NEVER indexed.
    """
    review_state = region_doc.get("review_state", "pending_review")
    state = region_doc.get("state", "AI proposed")

    # Hard filter: never index rejected or unreadable evidence
    if review_state in ("rejected", "unreadable") or state in ("rejected", "unreadable"):
        return []

    region_id = region_doc.get("region_id", "")
    source_id = region_doc.get("source_id", "work-orders-001")
    source_hash = region_doc.get("source_hash", "")
    page = region_doc.get("source_page")
    text = region_doc.get("text", "").strip()

    if not text:
        return []

    bbox = region_doc.get("bounding_box")
    asset_tags = _extract_tags(text)

    # Prefix OCR text with context
    full_text = f"[OCR work-order page {page}] {text}"
    if source_doc:
        full_text = f"[Source: {source_doc.get('source_id', source_id)}, Page {page}] {text}"

    chunk_key = f"ocr:{region_id}"

    return [DocumentChunkRecord(
        chunk_id=_chunk_id(source_hash, "ocr_region", chunk_key),
        document_id=source_id,
        source_id=source_id,
        source_hash=source_hash,
        document_type="work_order_ocr",
        provenance="derived_ocr",
        review_state=review_state,
        asset_tags=asset_tags,
        drawing_ids=[],
        page=page,
        source_region=bbox,
        text=full_text,
        chunk_type="ocr_region",
    )]


def chunks_from_synthetic_document(doc: dict) -> list[DocumentChunkRecord]:
    """
    One chunk per synthetic SOP / inspection / incident / email document.
    Only included with explicit 'Synthetic demo data' label.
    """
    source_id = doc.get("source_id", "")
    provenance = doc.get("provenance", "")

    # Must be explicitly synthetic_demo
    if provenance != "synthetic_demo":
        return []

    source_hash = doc.get("sha256", "")
    doc_type = doc.get("document_type", "synthetic")
    title = doc.get("title", source_id)
    synthetic_label = doc.get("synthetic_label", "Synthetic demo data")

    text = (
        f"[SYNTHETIC DEMO DATA — {synthetic_label}]\n"
        f"Document: {title}\n"
        f"Type: {doc_type}\n"
        f"Source: {source_id}"
    )

    # Synthetic docs may mention asset tags in their path/title
    asset_tags = _extract_tags(f"{source_id} {title}")
    chunk_key = f"synthetic:{source_id}"

    return [DocumentChunkRecord(
        chunk_id=_chunk_id(source_hash, "synthetic_doc", chunk_key),
        document_id=source_id,
        source_id=source_id,
        source_hash=source_hash,
        document_type=doc_type,
        provenance="synthetic_demo",
        review_state="verified",  # synthetic docs are pre-labelled but clearly marked
        asset_tags=asset_tags,
        drawing_ids=[],
        page=None,
        source_region=None,
        text=text,
        chunk_type="synthetic_doc",
    )]


def build_all_chunks(db) -> Iterator[DocumentChunkRecord]:
    """
    Generator that yields all eligible chunks from MongoDB canonical records.
    Does not write to MongoDB — call this then upsert results to Qdrant/Neo4j.
    """
    # 1. P&ID assets
    for asset in db.assets.find({}, {"_id": 0}):
        yield from chunks_from_asset(asset)

    # 2. P&ID relationships
    for rel in db.relationships.find({}, {"_id": 0}):
        yield from chunks_from_relationship(rel)

    # 3. OCR regions (work-order evidence)
    for region in db.ocr_regions.find({}, {"_id": 0}):
        yield from chunks_from_ocr_region(region)

    # 4. Synthetic demo documents
    for doc in db.documents.find({"provenance": "synthetic_demo"}, {"_id": 0}):
        yield from chunks_from_synthetic_document(doc)
