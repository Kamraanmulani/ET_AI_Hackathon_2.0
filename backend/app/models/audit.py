"""
models/audit.py — Pydantic schema for append-only audit events.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AuditEventRecord(BaseModel):
    """
    Append-only audit event. Stored in MongoDB `audit_events` collection.
    Used for import, review, and API activity.
    """

    event_type: str = Field(..., description="import | review_decision | api_request | export")
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    actor: str = "system"
    detail: Optional[dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
