"""
core/database.py — MongoDB connection management.

The client is created once via get_db() / get_client() helpers.
On connection failure the application starts but returns a 503
from the health endpoint, as specified in Rules.md.
"""
from __future__ import annotations

import structlog
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from app.core.config import settings

log = structlog.get_logger(__name__)

_client: MongoClient | None = None


def get_client(uri: str | None = None) -> MongoClient:
    """Return the shared MongoClient, creating it on first call."""
    global _client
    if _client is None:
        target_uri = uri or settings.mongodb_uri
        _client = MongoClient(
            target_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
        log.info("mongodb_client_created", uri=target_uri)
    return _client


def get_db(db_name: str | None = None, uri: str | None = None):
    """Return the application database."""
    name = db_name or settings.mongodb_db
    return get_client(uri=uri)[name]


def ping_db(db_name: str | None = None, uri: str | None = None) -> bool:
    """Ping MongoDB; return True if reachable, False otherwise."""
    try:
        db = get_db(db_name=db_name, uri=uri)
        db.command("ping")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        log.warning("mongodb_unreachable", error=str(exc))
        return False


def close_client() -> None:
    """Close the shared client (call on application shutdown)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        log.info("mongodb_client_closed")


def ensure_indexes(db) -> None:
    """Create indexes required for efficient queries."""
    # documents: unique on source_id
    db.documents.create_index("source_id", unique=True)
    db.documents.create_index("document_type")
    db.documents.create_index("provenance")

    # assets: unique on tag
    db.assets.create_index("tag", unique=True)
    db.assets.create_index("source_id")
    db.assets.create_index("area")

    # relationships: compound index
    db.relationships.create_index([("from_tag", 1), ("to_tag", 1)])
    db.relationships.create_index("source_id")

    # ocr_jobs: unique on job_id
    db.ocr_jobs.create_index("job_id", unique=True)
    db.ocr_jobs.create_index("source_id")

    # ocr_pages: compound
    db.ocr_pages.create_index([("job_id", 1), ("source_page", 1)], unique=True)

    # ocr_regions: region_id unique within job
    db.ocr_regions.create_index("region_id", unique=True)
    db.ocr_regions.create_index([("job_id", 1), ("source_page", 1)])
    db.ocr_regions.create_index("review_state")

    # work_order_fields: unique on field_id
    db.work_order_fields.create_index("field_id", unique=True)
    db.work_order_fields.create_index("source_id")
    db.work_order_fields.create_index("review_state")

    # work_order_links: unique on link_id
    db.work_order_links.create_index("link_id", unique=True)
    db.work_order_links.create_index("asset_tag")
    db.work_order_links.create_index("review_state")

    # review_tasks: unique on task_id
    db.review_tasks.create_index("task_id", unique=True)
    db.review_tasks.create_index("state")
    db.review_tasks.create_index("task_type")

    # audit_events: append-only; index by timestamp
    db.audit_events.create_index("timestamp")
    db.audit_events.create_index("entity_id")

    # drawing_overlays: compound unique on (drawing_id, tag)
    db.drawing_overlays.create_index([("drawing_id", 1), ("tag", 1)], unique=True)

    # RAG collections
    db.document_chunks.create_index("chunk_id", unique=True)
    db.document_chunks.create_index("source_id")
    db.document_chunks.create_index("asset_tags")
    db.index_jobs.create_index("job_id", unique=True)
    
    # Copilot collections
    db.conversations.create_index("conversation_id", unique=True)
    db.messages.create_index("message_id", unique=True)
    db.messages.create_index("conversation_id")
    db.feedback.create_index("feedback_id", unique=True)
    db.retrieval_metrics.create_index("conversation_id")

    log.info("mongodb_indexes_ensured")