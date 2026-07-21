"""
app/services/retrieval_service.py — Hybrid retrieval pipeline for the RAG copilot.

Sequence (from RAG_CC.md §3):
1. Exact tag/document match in MongoDB
2. Neo4j graph expansion (2-hop, verified-first)
3. Qdrant metadata-filtered semantic search
4. MongoDB keyword/text fallback when Qdrant or Neo4j is unavailable
5. Reciprocal rank fusion + deduplication
6. Fetch canonical source records and apply provenance/review filters
7. Return top-N deduplicated, ranked chunks

Returns chunk dicts — never raw LLM output.
"""
from __future__ import annotations

import re
import time
from typing import Any

import structlog

from app.core.config import settings
from app.services import qdrant_service, neo4j_service
from app.services.ollama_client import embed, OllamaUnavailableError

log = structlog.get_logger(__name__)

# P&ID asset tags vocabulary (same as chunker.py)
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

# Review states that must never be returned as evidence
EXCLUDED_STATES = {"rejected", "unreadable"}


def extract_tags(text: str) -> list[str]:
    """Extract known P&ID tags from the query string."""
    found = []
    for tag in KNOWN_TAGS:
        if re.search(r"(?<![A-Z0-9])" + re.escape(tag) + r"(?![A-Z0-9-])", text, re.IGNORECASE):
            found.append(tag)
    return found


def _normalize_chunk(raw: dict, score: float, source: str) -> dict:
    """Normalise a raw MongoDB or Qdrant result into a standard chunk dict."""
    return {
        "chunk_id": raw.get("chunk_id", ""),
        "document_id": raw.get("document_id", raw.get("source_id", "")),
        "source_id": raw.get("source_id", ""),
        "source_hash": raw.get("source_hash", ""),
        "document_type": raw.get("document_type", ""),
        "provenance": raw.get("provenance", "unknown"),
        "review_state": raw.get("review_state", "pending_review"),
        "asset_tags": raw.get("asset_tags", []),
        "drawing_ids": raw.get("drawing_ids", []),
        "page": raw.get("page"),
        "source_region": raw.get("source_region") or raw.get("bounding_box"),
        "text": raw.get("text", ""),
        "chunk_type": raw.get("chunk_type", "generic"),
        "_score": score,
        "_source": source,
    }


def _reciprocal_rank_fusion(ranked_lists: list[list[dict]], k: int = 60) -> list[dict]:
    """
    Merge multiple ranked result lists using Reciprocal Rank Fusion.
    Deduplicates by chunk_id; accumulates RRF score across lists.
    """
    scores: dict[str, float] = {}
    chunks: dict[str, dict] = {}

    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked, start=1):
            cid = chunk.get("chunk_id") or id(chunk)
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            if cid not in chunks:
                chunks[cid] = chunk

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [{**chunks[cid], "_rrf_score": scores[cid]} for cid in sorted_ids]


def _rank_order_key(chunk: dict) -> tuple:
    """
    Priority ordering (lower tuple = higher rank):
    1. Exact tag match
    2. Verified
    3. Original provenance
    4. Higher RRF / vector score
    """
    is_exact_tag = chunk.get("_source") == "exact_tag"
    is_verified = chunk.get("review_state") == "verified"
    is_original = chunk.get("provenance") == "original"
    score = chunk.get("_rrf_score", chunk.get("_score", 0.0))

    return (
        0 if is_exact_tag else 1,
        0 if is_verified else 1,
        0 if is_original else 1,
        -score,  # higher score = lower rank value
    )


def retrieve(
    query: str,
    selected_asset_tag: str | None = None,
    include_ai_proposed: bool = True,
    include_synthetic_demo: bool = True,
    db=None,
) -> dict:
    """
    Run the full hybrid retrieval pipeline for a given query.

    Returns:
        {
            "chunks": [...],          # top-N deduplicated ranked chunks
            "tags_found": [...],
            "used_qdrant": bool,
            "used_graph": bool,
            "used_mongo_fallback": bool,
            "latency": {...},
        }
    """
    from app.core.database import get_db as _get_db
    if db is None:
        db = _get_db()

    # Extract asset tags from query + selected_asset_tag
    tags_found = extract_tags(query)
    if selected_asset_tag and selected_asset_tag not in tags_found:
        tags_found.insert(0, selected_asset_tag)

    t_total = time.monotonic()
    latency: dict[str, float] = {}

    # ── 1. Exact tag/document match in MongoDB ───────────────────────────────
    t0 = time.monotonic()
    exact_chunks: list[dict] = []
    for tag in tags_found:
        asset = db.assets.find_one({"tag": tag}, {"_id": 0})
        if asset:
            source_hash = asset.get("source_hash", asset.get("sha256", "unknown"))
            text = (
                f"Asset tag: {asset.get('tag')}. "
                f"Type: {asset.get('asset_type')}. "
                f"Area: {asset.get('area')}. "
                f"Drawing: {asset.get('drawing_id')}. "
                f"Review state: {asset.get('state', 'verified')}."
            )
            exact_chunks.append(_normalize_chunk({
                "chunk_id": f"asset:{tag}",
                "source_id": asset.get("source_id", ""),
                "source_hash": source_hash,
                "document_type": "pid_asset",
                "provenance": "original",
                "review_state": asset.get("state", "verified"),
                "asset_tags": [tag],
                "drawing_ids": [asset.get("drawing_id", "")] if asset.get("drawing_id") else [],
                "text": text,
                "chunk_type": "pid_asset",
            }, score=1.0, source="exact_tag"))

        # Also pull work_order_links for this tag
        links = list(db.work_order_links.find({"asset_tag": tag}, {"_id": 0}).limit(5))
        for link in links:
            region_id = link.get("source_region_id")
            region = db.ocr_regions.find_one({"region_id": region_id}, {"_id": 0}) if region_id else None
            text = region.get("text", "") if region else link.get("notes", "")
            if text and link.get("review_state") not in EXCLUDED_STATES:
                exact_chunks.append(_normalize_chunk({
                    "chunk_id": f"link:{tag}:{region_id}",
                    "source_id": link.get("source_id", "work-orders-001"),
                    "source_hash": link.get("source_hash", ""),
                    "document_type": "work_order_ocr",
                    "provenance": "derived_ocr",
                    "review_state": link.get("review_state", "pending_review"),
                    "asset_tags": [tag],
                    "page": link.get("source_page"),
                    "text": text,
                    "chunk_type": "ocr_region",
                }, score=0.95, source="exact_tag"))

    latency["mongo_exact_ms"] = (time.monotonic() - t0) * 1000

    # ── 2. Neo4j graph expansion ─────────────────────────────────────────────
    t0 = time.monotonic()
    graph_chunk_ids: list[str] = []
    used_graph = False
    for tag in tags_found:
        cids = neo4j_service.get_connected_chunks(tag)
        graph_chunk_ids.extend(cids)
        if cids:
            used_graph = True

    graph_chunks: list[dict] = []
    if graph_chunk_ids:
        for cid in graph_chunk_ids[:20]:
            c = db.document_chunks.find_one({"chunk_id": cid}, {"_id": 0})
            if c and c.get("review_state") not in EXCLUDED_STATES:
                graph_chunks.append(_normalize_chunk(c, score=0.9, source="graph"))

    latency["graph_ms"] = (time.monotonic() - t0) * 1000

    # ── 3. Qdrant semantic search ────────────────────────────────────────────
    t0 = time.monotonic()
    qdrant_chunks: list[dict] = []
    used_qdrant = False
    used_mongo_fallback = False

    if settings.rag_vector_enabled:
        try:
            vec = embed(query)
            raw_results = qdrant_service.search(
                query_vector=vec,
                top_k=settings.rag_vector_top_k,
                exclude_conditions={"review_state": ["rejected", "unreadable"]},
            )
            for r in raw_results:
                qdrant_chunks.append(_normalize_chunk(r, score=r.get("qdrant_score", 0.0), source="qdrant"))
            used_qdrant = True
        except OllamaUnavailableError:
            log.warning("retrieval_ollama_unavailable_falling_back_to_mongo")
            used_qdrant = False

    latency["qdrant_ms"] = (time.monotonic() - t0) * 1000

    # ── 4. MongoDB keyword fallback ──────────────────────────────────────────
    t0 = time.monotonic()
    if not qdrant_chunks and not exact_chunks:
        used_mongo_fallback = True
        query_words = re.findall(r"\w{3,}", query)
        for word in query_words[:3]:
            for region in db.ocr_regions.find(
                {"text": {"$regex": re.escape(word), "$options": "i"}},
                {"_id": 0}
            ).limit(10):
                if region.get("review_state") not in EXCLUDED_STATES:
                    qdrant_chunks.append(_normalize_chunk(region, score=0.5, source="mongo_text"))

    latency["mongo_fallback_ms"] = (time.monotonic() - t0) * 1000

    # ── 5. Rank fusion ───────────────────────────────────────────────────────
    all_lists = [l for l in [exact_chunks, graph_chunks, qdrant_chunks] if l]
    if not all_lists:
        merged = []
    elif len(all_lists) == 1:
        merged = all_lists[0]
    else:
        merged = _reciprocal_rank_fusion(all_lists)

    # Apply provenance filters
    if not include_ai_proposed:
        merged = [c for c in merged if c.get("review_state") not in ("AI proposed", "pending_review")]
    if not include_synthetic_demo:
        merged = [c for c in merged if c.get("provenance") != "synthetic_demo"]

    # ── 6. Sort by priority order, cap at max_chunks ─────────────────────────
    merged.sort(key=_rank_order_key)
    final = merged[: settings.rag_max_chunks]

    latency["total_ms"] = (time.monotonic() - t_total) * 1000

    return {
        "chunks": final,
        "tags_found": tags_found,
        "used_qdrant": used_qdrant,
        "used_graph": used_graph,
        "used_mongo_fallback": used_mongo_fallback,
        "latency": latency,
    }
