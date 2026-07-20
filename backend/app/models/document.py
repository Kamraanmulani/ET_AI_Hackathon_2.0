"""
models/document.py — Pydantic schemas for source documents.

Every document record stores the original source path, SHA-256 hash,
document type, provenance label, and extraction state.
Synthetic-demo documents must carry provenance='synthetic_demo'.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SourceMetadata(BaseModel):
    relative_path: str = Field(..., description="Data/inspections/... etc")
    sha256: str
    revision: int = Field(1)
    format: str
    document_class: str
    provenance: Literal["original", "synthetic_demo", "derived_ocr"]

class IngestionMetadata(BaseModel):
    state: Literal["registered", "extracted", "review_required", "indexed", "failed"]
    extractor: str
    extractor_version: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    warnings: list[str] = Field(default_factory=list)

class DocumentLocation(BaseModel):
    kind: Literal["page", "sheet", "region"]
    page: Optional[int] = None
    sheet: Optional[str] = None
    bbox: Optional[dict[str, float]] = None

class DocumentRecord(BaseModel):
    """Canonical document record stored in MongoDB `documents` collection."""

    # Flat legacy fields (preserved for compatibility)
    source_id: str = Field(..., description="Stable source identifier from the manifest")
    path: str = Field(..., description="Original relative path (never modified)")
    document_type: str = Field(..., description="pid_image | scanned_work_order_pdf | sop_excerpt_pdf | inspection_report_pdf | near_miss_report_pdf | email_export | spreadsheet")
    provenance: Literal["original", "synthetic_demo", "derived_ocr"] = Field(
        ...,
        description="'original' for the six immutable source files; 'synthetic_demo' for all other active documents. Never omit.",
    )
    sha256: str = Field(..., description="SHA-256 hex digest of the source file bytes")
    bytes_size: Optional[int] = Field(None, alias="bytes")
    page_count: Optional[int] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    drawing_id: Optional[str] = None
    text_layer: Optional[str] = None
    extraction_state: str = "pending"
    synthetic_notice_text: Optional[str] = None
    immutable: Optional[bool] = None
    
    # R1 Extended Fields
    document_id: Optional[str] = None
    source: Optional[SourceMetadata] = None
    ingestion: Optional[IngestionMetadata] = None
    locations: list[DocumentLocation] = Field(default_factory=list)
    
    imported_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}


class DocumentResponse(BaseModel):
    """API response shape for /api/v1/documents."""

    source_id: str
    path: str
    document_type: str
    provenance: str
    sha256: str
    page_count: Optional[int] = None
    drawing_id: Optional[str] = None
    extraction_state: str
    synthetic_label: Optional[str] = None  # "Synthetic demo data" when provenance==synthetic_demo
    imported_at: datetime
