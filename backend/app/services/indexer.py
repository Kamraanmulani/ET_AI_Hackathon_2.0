"""
app/services/indexer.py — Full corpus indexer for Qdrant and Neo4j.

Run this script to build/rebuild the vector and graph indexes from MongoDB.
It is idempotent: chunks with unchanged source_hash + chunk_version are skipped.

Usage:
    cd backend
    python -c "from app.services.indexer import run_full_index; run_full_index()"

Or via the tools/run_indexer.py helper script.
"""
from __future__ import annotations

import uuid
import time
from datetime import datetime, timezone

import structlog

from app.core.config import settings
from app.core.database import get_db
from app.models.chunk import DocumentChunkRecord, IndexJobRecord
from app.services.chunker import build_all_chunks
from app.services import qdrant_service, neo4j_service
from app.services.ollama_client import embed, OllamaUnavailableError

log = structlog.get_logger(__name__)

CHUNK_VERSION = 1  # Bump to force re-embed all chunks
EMBEDDING_MODEL = "mxbai-embed-large"


def _already_indexed(db, chunk: DocumentChunkRecord) -> bool:
    """True if chunk has been indexed with the same version and embedding model."""
    existing = db.document_chunks.find_one(
        {
            "chunk_id": chunk.chunk_id,
            "chunk_version": CHUNK_VERSION,
            "embedding_model": EMBEDDING_MODEL,
            "indexed_at": {"$ne": None},
        },
        {"_id": 0, "chunk_id": 1},
    )
    return existing is not None


def run_full_index(force: bool = False) -> dict:
    """
    Build chunks from all eligible MongoDB sources, embed, and upsert to Qdrant/Neo4j.
    
    Args:
        force: if True, re-index all chunks even if already indexed.
    
    Returns summary dict with counts and errors.
    """
    db = get_db()
    job_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    log.info("indexer_started", job_id=job_id, force=force)

    # Ensure Qdrant collection
    if settings.rag_vector_enabled:
        qdrant_service.ensure_collection()

    # Ensure Neo4j constraints
    if settings.rag_graph_enabled:
        neo4j_service.ensure_constraints()
        # Project drawing nodes
        for doc in db.documents.find({"document_type": "pid_drawing"}, {"_id": 0}):
            neo4j_service.upsert_drawing_node({
                "drawing_id": doc.get("drawing_id", doc.get("source_id", "")),
                "title": doc.get("title", ""),
                "source_id": doc.get("source_id", ""),
            })
        # Project asset nodes and APPEARS_ON edges
        for asset in db.assets.find({}, {"_id": 0}):
            neo4j_service.upsert_asset_node(asset)
            drawing_id = asset.get("drawing_id", "")
            if drawing_id:
                neo4j_service.upsert_asset_on_drawing(
                    tag=asset.get("tag", ""),
                    drawing_id=drawing_id,
                    source_id=asset.get("source_id", ""),
                    source_hash=asset.get("source_hash", "unknown"),
                )
        # Project P&ID relationships
        for rel in db.relationships.find({}, {"_id": 0}):
            neo4j_service.upsert_asset_relationship(rel)

    total = 0
    indexed = 0
    skipped = 0
    failed = 0
    errors = []

    for chunk in build_all_chunks(db):
        total += 1

        # Skip ineligible review states
        if chunk.review_state in ("rejected", "unreadable"):
            skipped += 1
            continue

        # Skip if already indexed (unless force)
        if not force and _already_indexed(db, chunk):
            skipped += 1
            continue

        # Store chunk record in MongoDB (upsert)
        chunk.chunk_version = CHUNK_VERSION
        chunk.embedding_model = EMBEDDING_MODEL
        chunk_dict = chunk.to_dict()
        db.document_chunks.update_one(
            {"chunk_id": chunk.chunk_id},
            {"$set": chunk_dict},
            upsert=True,
        )

        # Qdrant embedding and upsert
        if settings.rag_vector_enabled:
            try:
                vector = embed(chunk.text)
                success = qdrant_service.upsert_chunk(chunk, vector)
                if success:
                    db.document_chunks.update_one(
                        {"chunk_id": chunk.chunk_id},
                        {"$set": {"indexed_at": datetime.now(timezone.utc).isoformat()}},
                    )
                    indexed += 1
                else:
                    failed += 1
                    errors.append(f"Qdrant upsert failed: {chunk.chunk_id}")
            except OllamaUnavailableError as e:
                log.warning("ollama_embed_failed", chunk_id=chunk.chunk_id, error=str(e))
                failed += 1
                errors.append(f"Ollama unavailable: {chunk.chunk_id}")
                # Don't abort — try next chunk
        else:
            indexed += 1  # count as done if vector disabled

        # Neo4j chunk node + MENTIONS edges
        if settings.rag_graph_enabled:
            neo4j_service.upsert_chunk_node(chunk.to_dict())
            for tag in chunk.asset_tags:
                neo4j_service.upsert_chunk_mentions_asset(
                    chunk.chunk_id, tag, chunk.source_hash, chunk.review_state
                )

    finished_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "job_id": job_id,
        "total": total,
        "indexed": indexed,
        "skipped": skipped,
        "failed": failed,
        "errors": errors[:20],
        "started_at": started_at,
        "finished_at": finished_at,
    }
    log.info("indexer_finished", **summary)

    # Save job record
    db.index_jobs.insert_one({**summary, "target": "qdrant+neo4j"})
    return summary


def delete_chunk_from_indexes(chunk_id: str, db=None) -> None:
    """Called when OCR region is rejected. Removes chunk from Qdrant and marks MongoDB."""
    if db is None:
        db = get_db()
    qdrant_service.delete_chunk(chunk_id)
    db.document_chunks.update_one(
        {"chunk_id": chunk_id},
        {"$set": {"review_state": "rejected", "indexed_at": None}},
    )
