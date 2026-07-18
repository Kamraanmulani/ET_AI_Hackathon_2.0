"""
models/ocr.py — Pydantic schemas for OCR jobs, pages, and regions.

All OCR-derived records land with review_state='pending_review' and
state='AI proposed'. No auto-verification is permitted.
Every record retains source_hash and source_id to link back to the
original scanned PDF.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Raw bounding box from PaddleOCR (list of four [x, y] points)."""

    points: list[list[float]]


class OcrRegionRecord(BaseModel):
    """
    One detected text region from OCR.
    Stored in MongoDB `ocr_regions` collection.
    """

    region_id: str = Field(..., description="Unique region ID, e.g. 'p001-r007'")
    job_id: str
    source_id: str = "work-orders-001"
    source_hash: str
    source_page: int
    text: str
    confidence: float
    bounding_box: Optional[Any] = None  # raw coordinates from engine
    words: Optional[list[dict]] = None
    state: str = Field("AI proposed", description="Always 'AI proposed' until reviewed")
    review_state: str = Field("pending_review", description="pending_review | verified | rejected | unreadable")
    imported_at: datetime = Field(default_factory=datetime.utcnow)


class OcrPageRecord(BaseModel):
    """
    Summary record for one rendered page.
    Stored in MongoDB `ocr_pages` collection.
    """

    page_id: str = Field(..., description="Unique page ID, e.g. 'ocr-C7B4-page-1'")
    job_id: str
    source_id: str = "work-orders-001"
    source_hash: str
    source_page: int
    region_count: int
    mean_confidence: float
    duration_ms: float
    review_state: str = "pending_review"
    artifact_path: Optional[str] = None
    imported_at: datetime = Field(default_factory=datetime.utcnow)


class OcrJobRecord(BaseModel):
    """
    Top-level OCR job record.
    Stored in MongoDB `ocr_jobs` collection.
    """

    job_id: str
    source_id: str = "work-orders-001"
    source_hash: str
    cache_key: str
    configuration: dict
    status: str
    review_state: str = "pending_review"
    page_count: int
    started_at: Optional[str] = None
    imported_at: datetime = Field(default_factory=datetime.utcnow)
