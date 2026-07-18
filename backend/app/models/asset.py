"""
models/asset.py — Pydantic schemas for P&ID assets and relationships.

Assets are seeded from the reviewed pid_asset_registry.json (31 verified tags).
Relationships are seeded from pid_relationships.json (16 verified links).
Both collections use 'verified' state because they come from the manual review.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AssetRecord(BaseModel):
    """Canonical asset record stored in MongoDB `assets` collection."""

    tag: str = Field(..., description="Canonical P&ID tag, e.g. 'ETP-601'")
    asset_type: str = Field(..., description="Equipment type from registry, e.g. 'effluent_treatment_tank'")
    area: str = Field(..., description="Process area: reactor | distillation | storage | utilities | effluent_treatment")
    source_id: str = Field(..., description="Source document ID, e.g. 'pid-005-etp'")
    drawing_id: Optional[str] = None
    state: str = Field("verified", description="'verified' | 'AI proposed'")
    aliases: list[str] = Field(default_factory=list)
    imported_at: datetime = Field(default_factory=datetime.utcnow)


class AssetResponse(BaseModel):
    """API response shape for /api/v1/assets."""

    tag: str
    asset_type: str
    area: str
    source_id: str
    drawing_id: Optional[str] = None
    state: str
    aliases: list[str] = []
    relationships: list[dict] = []


class RelationshipRecord(BaseModel):
    """P&ID process relationship stored in MongoDB `relationships` collection."""

    from_tag: str
    relationship_type: str
    to_tag: str
    source_id: str = Field(..., description="P&ID source_id that evidences this relationship")
    state: str = "verified"
    imported_at: datetime = Field(default_factory=datetime.utcnow)
