"""
app/services/qdrant_service.py — Local Qdrant vector store client.

Handles collection initialization, idempotent chunk upsert, semantic search,
and chunk deletion. Always falls back safely to None/empty results when
Qdrant is unavailable — the caller must use MongoDB fallback in that case.
"""
from __future__ import annotations

import structlog
from typing import Any

from app.core.config import settings
from app.models.chunk import DocumentChunkRecord

log = structlog.get_logger(__name__)

_qdrant_client = None
_qdrant_available = None  # None = not yet checked


def _get_client():
    """Lazy singleton — import qdrant_client only when needed."""
    global _qdrant_client, _qdrant_available
    if _qdrant_available is False:
        return None
    if _qdrant_client is not None:
        return _qdrant_client
    try:
        from qdrant_client import QdrantClient  # type: ignore
        _qdrant_client = QdrantClient(url=settings.qdrant_url, timeout=5)
        _qdrant_available = True
        log.info("qdrant_connected", url=settings.qdrant_url)
        return _qdrant_client
    except Exception as e:
        log.warning("qdrant_unavailable", error=str(e))
        _qdrant_available = False
        return None


def reset_client() -> None:
    """Force reconnect on next call (used in tests)."""
    global _qdrant_client, _qdrant_available
    _qdrant_client = None
    _qdrant_available = None


def health_check() -> bool:
    """Return True if Qdrant is reachable."""
    client = _get_client()
    if client is None:
        return False
    try:
        client.get_collections()
        return True
    except Exception:
        return False


def ensure_collection() -> bool:
    """
    Create the Qdrant collection if it does not exist.
    Returns True on success, False if Qdrant is unavailable.
    """
    client = _get_client()
    if client is None:
        return False
    try:
        from qdrant_client.models import VectorParams, Distance  # type: ignore
        existing = [c.name for c in client.get_collections().collections]
        if settings.qdrant_collection not in existing:
            client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(
                    size=settings.qdrant_vector_size,
                    distance=Distance.COSINE,
                ),
            )
            log.info("qdrant_collection_created", collection=settings.qdrant_collection)
        return True
    except Exception as e:
        log.warning("qdrant_ensure_collection_failed", error=str(e))
        return False


def upsert_chunk(chunk: DocumentChunkRecord, vector: list[float]) -> bool:
    """
    Upsert one chunk with its embedding vector into Qdrant.
    Uses the chunk_id as a deterministic point ID (hashed to uint64).
    Returns True on success, False if Qdrant is unavailable.
    """
    client = _get_client()
    if client is None:
        return False
    try:
        from qdrant_client.models import PointStruct  # type: ignore
        # Deterministic point ID from chunk_id
        point_id = int(chunk.chunk_id[:16], 16)  # 64-bit int from hex prefix
        payload = {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "source_id": chunk.source_id,
            "source_hash": chunk.source_hash,
            "document_type": chunk.document_type,
            "provenance": chunk.provenance,
            "review_state": chunk.review_state,
            "asset_tags": chunk.asset_tags,
            "drawing_ids": chunk.drawing_ids,
            "page": chunk.page,
            "source_region": chunk.source_region,
            "text": chunk.text[:1000],  # store excerpt, not full text
            "chunk_type": chunk.chunk_type,
        }
        client.upsert(
            collection_name=settings.qdrant_collection,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        return True
    except Exception as e:
        log.warning("qdrant_upsert_failed", chunk_id=chunk.chunk_id, error=str(e))
        return False


def search(
    query_vector: list[float],
    top_k: int = 15,
    filter_conditions: dict | None = None,
) -> list[dict]:
    """
    Semantic search in Qdrant with optional metadata filters.
    Returns list of chunk payloads with scores, or [] if Qdrant is unavailable.
    """
    client = _get_client()
    if client is None:
        return []
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue  # type: ignore

        qdrant_filter = None
        if filter_conditions:
            must_clauses = []
            for field, value in filter_conditions.items():
                if isinstance(value, list):
                    # "review_state NOT IN [rejected, unreadable]"
                    for v in value:
                        must_clauses.append(FieldCondition(key=field, match=MatchValue(value=v)))
                else:
                    must_clauses.append(FieldCondition(key=field, match=MatchValue(value=value)))
            if must_clauses:
                qdrant_filter = Filter(must=must_clauses)

        response = client.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )
        return [
            {**r.payload, "qdrant_score": r.score}
            for r in response.points
            if r.score >= settings.rag_score_threshold
        ]
    except Exception as e:
        log.warning("qdrant_search_failed", error=str(e))
        return []


def delete_chunk(chunk_id: str) -> bool:
    """Delete a chunk from Qdrant (called when evidence is rejected/unreadable)."""
    client = _get_client()
    if client is None:
        return False
    try:
        point_id = int(chunk_id[:16], 16)
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=[point_id],
        )
        return True
    except Exception as e:
        log.warning("qdrant_delete_failed", chunk_id=chunk_id, error=str(e))
        return False


def get_collection_info() -> dict:
    """Return collection stats for the health endpoint."""
    client = _get_client()
    if client is None:
        return {"available": False}
    try:
        info = client.get_collection(settings.qdrant_collection)
        return {
            "available": True,
            "collection": settings.qdrant_collection,
            "vectors_count": getattr(info, "points_count", getattr(info, "vectors_count", 0)),
            "indexed_vectors_count": getattr(info, "indexed_vectors_count", 0),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}
