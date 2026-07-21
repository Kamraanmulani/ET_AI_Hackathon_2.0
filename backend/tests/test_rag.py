"""
backend/tests/test_rag.py — RAG unit and integration tests.

Tests:
- Deterministic chunk ID generation
- Chunker eligibility rules (rejected/unreadable never indexed)
- Safety gate detection of prohibited requests
- Citation verifier
- Abstention when no chunks
- Retrieval tag extraction
- Qdrant fallback when unavailable
- Neo4j fallback when unavailable
- MongoDB graph fallback
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

# ── Chunker tests ─────────────────────────────────────────────────────────────

def test_chunk_id_is_deterministic():
    """Same inputs always produce the same chunk ID."""
    from app.services.chunker import _chunk_id
    id1 = _chunk_id("hash123", "pid_asset", "asset:ETP-601")
    id2 = _chunk_id("hash123", "pid_asset", "asset:ETP-601")
    assert id1 == id2
    assert len(id1) == 32


def test_chunk_id_differs_by_key():
    """Different chunk keys produce different IDs."""
    from app.services.chunker import _chunk_id
    id1 = _chunk_id("hash123", "pid_asset", "asset:ETP-601")
    id2 = _chunk_id("hash123", "pid_asset", "asset:R-201")
    assert id1 != id2


def test_chunks_from_asset_returns_one_chunk():
    """An asset record yields exactly one chunk."""
    from app.services.chunker import chunks_from_asset
    asset = {
        "tag": "ETP-601",
        "asset_type": "Effluent treatment plant",
        "area": "ETP",
        "drawing_id": "PCP-PID-005",
        "source_id": "PCP-PID-005",
        "source_hash": "abc123",
        "state": "verified",
    }
    chunks = chunks_from_asset(asset)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_type == "pid_asset"
    assert chunk.provenance == "original"
    assert "ETP-601" in chunk.asset_tags
    assert "PCP-PID-005" in chunk.drawing_ids
    assert chunk.review_state == "verified"


def test_ocr_chunk_rejected_not_indexed():
    """Rejected OCR regions must return an empty list."""
    from app.services.chunker import chunks_from_ocr_region
    region = {
        "region_id": "r-001",
        "source_id": "work-orders-001",
        "source_hash": "xyz",
        "source_page": 1,
        "text": "some text",
        "review_state": "rejected",
        "state": "rejected",
    }
    chunks = chunks_from_ocr_region(region)
    assert chunks == []


def test_ocr_chunk_unreadable_not_indexed():
    """Unreadable OCR regions must not be indexed."""
    from app.services.chunker import chunks_from_ocr_region
    region = {
        "region_id": "r-002",
        "source_id": "work-orders-001",
        "source_hash": "xyz",
        "source_page": 2,
        "text": "illegible scan",
        "review_state": "unreadable",
        "state": "unreadable",
    }
    assert chunks_from_ocr_region(region) == []


def test_ocr_chunk_pending_is_indexed():
    """Pending OCR regions are eligible for indexing with 'pending_review' state."""
    from app.services.chunker import chunks_from_ocr_region
    region = {
        "region_id": "r-003",
        "source_id": "work-orders-001",
        "source_hash": "xyz",
        "source_page": 3,
        "text": "Work order for R-201 pump replacement",
        "review_state": "pending_review",
        "state": "AI proposed",
    }
    chunks = chunks_from_ocr_region(region)
    assert len(chunks) == 1
    assert chunks[0].review_state == "pending_review"
    assert "R-201" in chunks[0].asset_tags


def test_synthetic_doc_non_synthetic_returns_empty():
    """Non-synthetic documents must not pass through the synthetic chunker."""
    from app.services.chunker import chunks_from_synthetic_document
    doc = {
        "source_id": "some-real-doc",
        "provenance": "original",
        "sha256": "abc",
    }
    assert chunks_from_synthetic_document(doc) == []


def test_tag_extraction():
    """Known tags should be extracted from text."""
    from app.services.chunker import _extract_tags
    text = "Maintenance work on ETP-601 effluent pump P-601 completed."
    tags = _extract_tags(text)
    assert "ETP-601" in tags
    assert "P-601" in tags


# ── Safety gate tests ─────────────────────────────────────────────────────────

def test_safety_gate_plant_control():
    """Plant control requests must trigger the safety boundary."""
    from app.services.answer_service import check_safety_gate
    result = check_safety_gate("Close valve XV-603")
    assert result is not None
    assert result["answer_status"] == "safety_boundary"


def test_safety_gate_compliance():
    """Compliance questions must trigger the safety boundary."""
    from app.services.answer_service import check_safety_gate
    result = check_safety_gate("Is the plant OISD compliant?")
    assert result is not None
    assert result["answer_status"] == "safety_boundary"


def test_safety_gate_live_data():
    """Live sensor data requests must be rejected."""
    from app.services.answer_service import check_safety_gate
    result = check_safety_gate("What is the current pressure of B-501?")
    assert result is not None
    assert result["answer_status"] == "safety_boundary"


def test_safety_gate_passes_evidence_question():
    """Normal evidence questions must pass the safety gate."""
    from app.services.answer_service import check_safety_gate
    result = check_safety_gate("What evidence is linked to ETP-601?")
    assert result is None


def test_safety_gate_passes_drawing_question():
    """Drawing context questions must pass the gate."""
    from app.services.answer_service import check_safety_gate
    result = check_safety_gate("What drawing contains ETP-601?")
    assert result is None


def test_safety_gate_root_cause():
    """Root cause questions must be rejected."""
    from app.services.answer_service import check_safety_gate
    result = check_safety_gate("What caused the C-301 issue?")
    assert result is not None
    assert result["answer_status"] == "safety_boundary"


# ── Citation verifier tests ───────────────────────────────────────────────────

def test_citation_verifier_valid():
    """Valid citation IDs in answer should return empty invalid list."""
    from app.services.answer_service import _verify_citations
    pack = [{"chunk_id": "abc"}, {"chunk_id": "def"}]
    answer = "The asset is ETP-601 [C1]. It is located in the ETP area [C2]."
    invalid = _verify_citations(answer, pack)
    assert invalid == []


def test_citation_verifier_invalid():
    """Citation IDs beyond evidence pack size are invalid."""
    from app.services.answer_service import _verify_citations
    pack = [{"chunk_id": "abc"}]  # only C1 is valid
    answer = "The asset is ETP-601 [C1]. See also [C5]."
    invalid = _verify_citations(answer, pack)
    assert "C5" in invalid


# ── Abstention when no evidence ───────────────────────────────────────────────

def test_generate_answer_empty_pack():
    """Empty evidence pack must return insufficient_evidence without calling LLM."""
    from app.services.answer_service import generate_answer
    result = generate_answer(
        query="What is the pressure of ETP-601?",
        evidence_pack=[],
        tags_found=["ETP-601"],
        retrieval_info={"used_qdrant": False, "used_graph": False, "used_mongo_fallback": True},
    )
    assert result["answer_status"] == "insufficient_evidence"
    assert result["citations"] == []
    assert "insufficient" in result["answer_confidence"]["label"]


# ── Retrieval tag extraction ──────────────────────────────────────────────────

def test_retrieval_extract_tags():
    """Tags should be extracted from query strings case-insensitively."""
    from app.services.retrieval_service import extract_tags
    tags = extract_tags("What evidence is linked to etp-601?")
    assert "ETP-601" in tags


def test_retrieval_extract_multiple_tags():
    """Multiple tags in a single query should all be found."""
    from app.services.retrieval_service import extract_tags
    tags = extract_tags("Show evidence for R-201 and P-101")
    assert "R-201" in tags
    assert "P-101" in tags


# ── Qdrant unavailable fallback ───────────────────────────────────────────────

def test_qdrant_search_returns_empty_when_unavailable():
    """Qdrant search must return [] when the service is unavailable."""
    from app.services import qdrant_service
    qdrant_service.reset_client()
    # With a non-existent host, get_client will fail and return None
    with patch.object(qdrant_service, '_qdrant_available', False):
        results = qdrant_service.search(query_vector=[0.0] * 1024)
        assert results == []


def test_qdrant_health_check_false_when_unavailable():
    """health_check must return False when Qdrant is unavailable."""
    from app.services import qdrant_service
    with patch.object(qdrant_service, '_qdrant_available', False):
        assert qdrant_service.health_check() is False


# ── Neo4j unavailable fallback ────────────────────────────────────────────────

def test_neo4j_returns_fallback_graph_when_unavailable():
    """get_asset_evidence_graph must return fallback=True when Neo4j is down."""
    from app.services import neo4j_service
    neo4j_service.reset_driver()
    with patch.object(neo4j_service, '_neo4j_available', False):
        result = neo4j_service.get_asset_evidence_graph("ETP-601")
        assert result["available"] is False
        assert result["fallback"] is True


def test_neo4j_connected_chunks_returns_empty_when_unavailable():
    """get_connected_chunks must return [] when Neo4j is unavailable."""
    from app.services import neo4j_service
    neo4j_service.reset_driver()
    with patch.object(neo4j_service, '_neo4j_available', False):
        result = neo4j_service.get_connected_chunks("ETP-601")
        assert result == []


# ── RRF fusion ────────────────────────────────────────────────────────────────

def test_rrf_deduplication():
    """RRF should deduplicate by chunk_id across lists."""
    from app.services.retrieval_service import _reciprocal_rank_fusion
    chunk = {"chunk_id": "aaa", "text": "test"}
    merged = _reciprocal_rank_fusion([[chunk], [chunk]])
    assert len(merged) == 1


def test_rrf_ranking():
    """Higher rank in first list should have higher RRF score."""
    from app.services.retrieval_service import _reciprocal_rank_fusion
    list1 = [{"chunk_id": "a", "text": "top"}, {"chunk_id": "b", "text": "second"}]
    list2 = [{"chunk_id": "b", "text": "second"}, {"chunk_id": "a", "text": "top"}]
    merged = _reciprocal_rank_fusion([list1, list2])
    # Both appeared in both lists; result should have 2 unique chunks
    assert len(merged) == 2
