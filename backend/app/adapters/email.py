"""
app/adapters/email.py — Email and handover notes adapter.
"""
from typing import List

from app.adapters.base import DocumentAdapter, ExtractionResult
from app.models.document import SourceMetadata

class EmailAdapter(DocumentAdapter):
    supported_extensions = {".eml", ".msg"}

    def inspect(self, path: str) -> SourceMetadata:
        raise NotImplementedError

    def extract(self, source: SourceMetadata) -> ExtractionResult:
        result = ExtractionResult()
        # Stub: will implement email parsing here in R1.3
        return result
