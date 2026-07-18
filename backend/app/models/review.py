"""
models/review.py — Pydantic schema for review tasks.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReviewTaskRecord(BaseModel):
    """
    Human review task. Stored in MongoDB `review_tasks` collection.
    Sourced from Data/derived/ocr/work-orders-001/review_queue.json.
    """

    task_id: str
    task_type: str = Field(..., description="ocr_page_review | field_review | asset_link_review")
    source_id: str
    source_hash: str
    source_page: Optional[int] = None
    source_region_id: Optional[str] = None
    source_artifact: Optional[str] = None
    field: Optional[str] = None
    proposed_value: Optional[str] = None
    proposed_asset_tag: Optional[str] = None
    confidence: Optional[float] = None
    state: str = Field("pending_review", description="pending_review | verified | rejected | unreadable")
    allowed_decisions: list[str] = Field(default_factory=list)
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    imported_at: datetime = Field(default_factory=datetime.utcnow)
