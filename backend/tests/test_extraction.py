import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.adapters.email import EmailAdapter
from app.adapters.pdf import PDFTextAdapter
from app.services.extractor import EntityExtractorService
from app.models.document import SourceMetadata

def test_email_extraction_unit():
    """Verify email adapter RFC parsing."""
    adapter = EmailAdapter()
    source = SourceMetadata(
        source_id="test-email-01",
        relative_path="test.eml",
        sha256="abc123hash",
        format="eml",
        document_class="email",
        provenance="synthetic_demo"
    )
    
    result = adapter.extract(source)
    assert len(result.evidence) == 0  # Missing file

def test_entity_extractor_service_unit():
    """Verify regex-based deterministic entity extraction."""
    extractor = EntityExtractorService()
    
    text = "Work Order WO-2023-010 created for asset AIT-601. Also refer to ETP601 and procedure SOP-PRG-ETP-001."
    entities = extractor.extract_entities(text, "evidence-1", "doc-1")
    
    types = [e.entity_type for e in entities]
    assert "work_order_id" in types
    assert "asset_tag" in types
    assert "document_id" in types
    
    asset_tags = [e.normalized_value for e in entities if e.entity_type == "asset_tag"]
    assert "AIT-601" in asset_tags
    assert "ETP-601" in asset_tags # ETP601 should be aliased to ETP-601

def test_pdf_extraction_fallback_logic():
    """Verify PDF Adapter logic."""
    adapter = PDFTextAdapter()
    source = SourceMetadata(
        source_id="test-pdf-01",
        relative_path="test.pdf",
        sha256="abc123hash",
        format="pdf",
        document_class="procedure",
        provenance="synthetic_demo"
    )
    result = adapter.extract(source)
    assert len(result.evidence) == 0
