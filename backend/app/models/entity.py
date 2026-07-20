"""
app/models/entity.py — Pydantic schema for canonical entity candidates.

Entities are deterministic extractions from Evidence records.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ResolutionMetadata(BaseModel):
    state: Literal["verified", "ai_proposed", "unresolved", "rejected"] = Field(...)
    canonical_id: Optional[str] = Field(None, description="e.g. 'asset:ETP-601'")


class ExtractorMetadata(BaseModel):
    name: str = Field(...)
    version: str = Field(...)
    confidence: float = Field(1.0)


class EntityRecord(BaseModel):
    """
    Stored in `entities` MongoDB collection.
    """
    entity_id: str = Field(..., description="Deterministic ID")
    entity_type: Literal[
        "asset_tag", "work_order_id", "drawing_id", "document_id",
        "date", "role", "regulatory_reference", "process_reference"
    ] = Field(...)
    
    value: str = Field(..., description="Raw extracted value")
    normalized_value: str = Field(..., description="Normalized value for matching")
    
    evidence_id: str = Field(...)
    document_id: str = Field(...)
    
    resolution: ResolutionMetadata = Field(...)
    extractor: ExtractorMetadata = Field(...)
    
    imported_at: datetime = Field(default_factory=datetime.utcnow)
