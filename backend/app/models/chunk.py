"""
app/models/chunk.py — Chunk, index job, outbox, and retrieval metric models.

MongoDB collections:
  document_chunks   — searchable source-grounded chunks
  index_jobs        — Qdrant/Neo4j projection job records
  index_outbox      — outbox events driving background indexing
  retrieval_metrics — per-query latency and result statistics
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DocumentChunkRecord:
    """
    One searchable unit of plant evidence.

    chunk_id is deterministic: sha256(source_hash + ":" + chunk_type + ":" + chunk_key)[:32]
    This ensures idempotent upserts and stable Qdrant point IDs.
    """
    chunk_id: str
    document_id: str
    source_id: str
    source_hash: str
    document_type: str                       # pid_asset | ocr_region | sop_section | email | etc.
    provenance: str                          # original | synthetic_demo | derived_ocr
    review_state: str                        # verified | AI proposed | pending_review | rejected | unreadable
    asset_tags: list[str] = field(default_factory=list)
    drawing_ids: list[str] = field(default_factory=list)
    page: int | None = None
    source_region: dict | None = None        # {x, y, width, height}
    text: str = ""
    chunk_type: str = "generic"              # pid_asset | pid_relationship | ocr_region | section | email
    chunk_version: int = 1
    embedding_model: str = ""
    created_at: str = ""
    indexed_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "source_hash": self.source_hash,
            "document_type": self.document_type,
            "provenance": self.provenance,
            "review_state": self.review_state,
            "asset_tags": self.asset_tags,
            "drawing_ids": self.drawing_ids,
            "page": self.page,
            "source_region": self.source_region,
            "text": self.text,
            "chunk_type": self.chunk_type,
            "chunk_version": self.chunk_version,
            "embedding_model": self.embedding_model,
            "created_at": self.created_at or datetime.now(timezone.utc).isoformat(),
            "indexed_at": self.indexed_at,
        }


@dataclass
class IndexJobRecord:
    """Tracks one indexing run for a document or chunk batch."""
    job_id: str
    source_id: str
    source_hash: str
    target: str                              # qdrant | neo4j | both
    status: str = "pending"                  # pending | running | completed | failed
    chunk_count: int = 0
    indexed_count: int = 0
    skipped_count: int = 0
    error: str | None = None
    started_at: str = ""
    finished_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "source_id": self.source_id,
            "source_hash": self.source_hash,
            "target": self.target,
            "status": self.status,
            "chunk_count": self.chunk_count,
            "indexed_count": self.indexed_count,
            "skipped_count": self.skipped_count,
            "error": self.error,
            "started_at": self.started_at or datetime.now(timezone.utc).isoformat(),
            "finished_at": self.finished_at,
        }


@dataclass
class IndexOutboxRecord:
    """Outbox event that drives background indexing after an import/review change."""
    event_id: str
    event_type: str                          # import | review_decision | chunk_delete
    entity_type: str                         # document | ocr_region | asset | relationship
    entity_id: str
    source_id: str
    source_hash: str
    status: str = "pending"                  # pending | processing | done | failed
    retry_count: int = 0
    error: str | None = None
    created_at: str = ""
    processed_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "source_id": self.source_id,
            "source_hash": self.source_hash,
            "status": self.status,
            "retry_count": self.retry_count,
            "error": self.error,
            "created_at": self.created_at or datetime.now(timezone.utc).isoformat(),
            "processed_at": self.processed_at,
        }


@dataclass
class RetrievalMetricRecord:
    """Per-query latency and result statistics for benchmark tracking."""
    metric_id: str
    query: str
    asset_tag: str | None
    mongo_hits: int = 0
    qdrant_hits: int = 0
    graph_hits: int = 0
    final_chunks: int = 0
    mongo_latency_ms: float = 0.0
    qdrant_latency_ms: float = 0.0
    graph_latency_ms: float = 0.0
    answer_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    answer_status: str = ""
    support_label: str = ""
    recorded_at: str = ""

    def to_dict(self) -> dict:
        return {
            "metric_id": self.metric_id,
            "query": self.query,
            "asset_tag": self.asset_tag,
            "mongo_hits": self.mongo_hits,
            "qdrant_hits": self.qdrant_hits,
            "graph_hits": self.graph_hits,
            "final_chunks": self.final_chunks,
            "mongo_latency_ms": self.mongo_latency_ms,
            "qdrant_latency_ms": self.qdrant_latency_ms,
            "graph_latency_ms": self.graph_latency_ms,
            "answer_latency_ms": self.answer_latency_ms,
            "total_latency_ms": self.total_latency_ms,
            "answer_status": self.answer_status,
            "support_label": self.support_label,
            "recorded_at": self.recorded_at or datetime.now(timezone.utc).isoformat(),
        }
