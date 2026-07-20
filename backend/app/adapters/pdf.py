"""
app/adapters/pdf.py — PDF and native text adapter.
"""
from typing import List
from pathlib import Path

from app.adapters.base import DocumentAdapter, ExtractionResult
from app.models.document import SourceMetadata

class PDFTextAdapter(DocumentAdapter):
    supported_extensions = {".pdf", ".txt"}

    def inspect(self, path: str) -> SourceMetadata:
        raise NotImplementedError

    def extract(self, source: SourceMetadata) -> ExtractionResult:
        result = ExtractionResult()
        # Stub: will implement pypdf/pymupdf extraction here in R1.3
        return result
