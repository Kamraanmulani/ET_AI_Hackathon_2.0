"""
app/models/evidence.py — Pydantic schema for canonical evidence records.

Evidence is tied to a specific location in a source document.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, Any

from pydantic import BaseModel, Field


class LocationMetadata(BaseModel):
    page: Optional[int] = None
    sheet: Optional[str] = None
    row: Optional[int] = None
    bbox: Optional[dict[str, float]] = None


class ExtractionMetadata(BaseModel):
    method: Literal["native_text", "OCR", "spreadsheet"] = Field(...)
    confidence: float = Field(0.0)


class EvidenceRecord(BaseModel):
    """
    Stored in `evidence` MongoDB collection.
    """
    evidence_id: str = Field(..., description="Deterministic ID")
    document_id: str = Field(...)
    source_hash: str = Field(...)
    
    text: str = Field(..., description="Exact extracted excerpt")
    location: LocationMetadata = Field(default_factory=LocationMetadata)
    extraction: ExtractionMetadata = Field(...)
    
    review_state: Literal["verified", "ai_proposed", "pending_review", "rejected", "unreadable"] = Field("pending_review")
    provenance: Literal["original", "synthetic_demo", "derived_ocr"] = Field(...)
    
    imported_at: datetime = Field(default_factory=datetime.utcnow)
