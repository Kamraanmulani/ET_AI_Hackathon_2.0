"""
app/adapters/base.py — Adapter framework for Document extraction
"""
from typing import List, Set
from pydantic import BaseModel

from app.models.document import SourceMetadata
from app.models.evidence import EvidenceRecord
from app.models.entity import EntityRecord
from app.models.asset import RelationshipRecord

class IngestionWarning(BaseModel):
    message: str
    phase: str

class ExtractionResult(BaseModel):
    evidence: List[EvidenceRecord] = []
    entities: List[EntityRecord] = []
    relationships: List[RelationshipRecord] = []

class DocumentAdapter:
    supported_extensions: Set[str] = set()

    def inspect(self, path: str) -> SourceMetadata:
        """Inspect the file and return SourceMetadata."""
        raise NotImplementedError

    def extract(self, source: SourceMetadata) -> ExtractionResult:
        """Extract evidence, entities, and relationships."""
        raise NotImplementedError

    def validate(self, result: ExtractionResult) -> List[IngestionWarning]:
        """Validate extraction result and return warnings."""
        return []
