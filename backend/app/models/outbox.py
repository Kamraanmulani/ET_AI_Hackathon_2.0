"""
app/models/outbox.py — Pydantic schema for the index_outbox collection.

Transactional outbox pattern for updating Qdrant and Neo4j derived indexes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class OutboxEventRecord(BaseModel):
    """
    Stored in `index_outbox` MongoDB collection.
    Processed by a background worker to ensure Qdrant and Neo4j updates are idempotent and resilient.
    """

    event_id: str = Field(..., description="Unique ID for the event, e.g. uuid4")
    event_type: Literal["document_imported", "entity_extracted", "review_decision_applied"] = Field(...)
    document_id: str = Field(..., description="Canonical document ID affected")
    source_hash: str = Field(..., description="Hash of the document at the time of this event")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event details (e.g., entity_id, decision)")
    
    status: Literal["pending", "processing", "completed", "failed"] = Field("pending")
    retry_count: int = Field(0)
    last_error: Optional[str] = None
    next_attempt_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
