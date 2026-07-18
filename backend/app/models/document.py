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


class DocumentRecord(BaseModel):
    """Canonical document record stored in MongoDB `documents` collection."""

    source_id: str = Field(..., description="Stable source identifier from the manifest")
    path: str = Field(..., description="Original relative path (never modified)")
    document_type: str = Field(..., description="pid_image | scanned_work_order_pdf | sop_excerpt_pdf | inspection_report_pdf | near_miss_report_pdf | email_export")
    provenance: Literal["original", "synthetic_demo"] = Field(
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
