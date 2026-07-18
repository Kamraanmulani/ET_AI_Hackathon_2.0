"""
models/work_order.py — Pydantic schemas for work-order candidate fields
and candidate asset links extracted by OCR.

All values are 'AI proposed' / 'pending_review' until a human reviewer
confirms them. Source page and region coordinates are always retained.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WorkOrderFieldRecord(BaseModel):
    """
    One candidate extracted field (work-order ID, date, asset tag, etc.).
    Stored in MongoDB `work_order_fields` collection.
    """

    field_id: str = Field(..., description="Stable unique ID: '{job_id}::{page}::{region_id}::{field}'")
    job_id: str
    source_id: str = "work-orders-001"
    source_hash: str
    source_page: int
    source_region_id: str
    source_text: str = Field(..., description="Verbatim OCR text from the source region")
    field: str = Field(..., description="work_order_id | date_raw | asset_tag")
    value: str = Field(..., description="Extracted candidate value — never treated as verified")
    confidence: float
    state: str = Field("AI proposed", description="Always 'AI proposed' until reviewed")
    review_state: str = Field("pending_review", description="pending_review | verified | rejected | unreadable")
    imported_at: datetime = Field(default_factory=datetime.utcnow)


class WorkOrderLinkRecord(BaseModel):
    """
    Candidate link between a work-order asset tag mention and a registry asset.
    Stored in MongoDB `work_order_links` collection.
    """

    link_id: str = Field(..., description="Stable unique ID: '{job_id}::{page}::{region_id}::{tag}'")
    task_id: str = Field(..., description="Corresponding review_queue task_id")
    job_id: str
    source_id: str = "work-orders-001"
    source_hash: str
    source_page: int
    source_region_id: str
    asset_tag: str
    registry_matched: bool = True
    confidence: Optional[float] = None
    state: str = Field("AI proposed", description="Always 'AI proposed' until a reviewer approves")
    review_state: str = Field("pending_review", description="pending_review | verified | rejected")
    imported_at: datetime = Field(default_factory=datetime.utcnow)
