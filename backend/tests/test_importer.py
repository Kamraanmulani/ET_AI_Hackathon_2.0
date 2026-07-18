"""
tests/test_importer.py — Focused backend tests for Phase 3.

Test categories:
1. Importer idempotency — two runs produce no duplicates
2. Source-hash provenance — every document record has sha256
3. Synthetic-demo labelling — every synthetic doc has provenance and label
4. Original vs derived data separation
5. OCR state preservation — all OCR records stay pending_review / AI proposed
6. API health
7. API documents
8. API assets
9. API asset by tag (ETP-601)

Tests are skipped (not failed) if MongoDB is unavailable.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Allow imports from backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("MONGODB_DB", "ppi_test")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")

from importer import run_import
from app.core.database import ping_db

# ---------------------------------------------------------------------------
# Helper: run the importer against the test DB
# ---------------------------------------------------------------------------


def do_import(test_db) -> dict:
    """Run importer.run_import() wired to the test DB."""
    import app.core.database as db_module
    _orig = db_module.get_db
    _orig_ping = db_module.ping_db

    # Patch get_db and ping_db for importer
    db_module.get_db = lambda db_name=None, uri=None: test_db

    def _mock_ping(db_name=None, uri=None):
        return True

    db_module.ping_db = _mock_ping

    try:
        summary = run_import(db_name="ppi_test", uri="mongodb://localhost:27017")
    finally:
        db_module.get_db = _orig
        db_module.ping_db = _orig_ping

    return summary


# ===========================================================================
# 1. Importer idempotency
# ===========================================================================


class TestImporterIdempotency:
    def test_double_import_no_duplicates_documents(self, test_db):
        """Running the importer twice must not create duplicate documents."""
        do_import(test_db)
        do_import(test_db)
        count = test_db.documents.count_documents({})
        # active_document_manifest has 30 sources
        assert count == 30, f"Expected 30 documents, got {count}"

    def test_double_import_no_duplicates_assets(self, test_db):
        """Running the importer twice must not create duplicate assets."""
        do_import(test_db)
        do_import(test_db)
        count = test_db.assets.count_documents({})
        assert count == 31, f"Expected 31 assets, got {count}"

    def test_double_import_no_duplicates_relationships(self, test_db):
        """Running the importer twice must not create duplicate relationships."""
        do_import(test_db)
        do_import(test_db)
        count = test_db.relationships.count_documents({})
        assert count == 16, f"Expected 16 relationships, got {count}"

    def test_double_import_no_duplicates_review_tasks(self, test_db):
        """Running the importer twice must not create duplicate review tasks."""
        do_import(test_db)
        do_import(test_db)
        count = test_db.review_tasks.count_documents({})
        assert count == 98, f"Expected 98 review tasks, got {count}"

    def test_double_import_no_duplicates_ocr_jobs(self, test_db):
        """Only one OCR job record should exist."""
        do_import(test_db)
        do_import(test_db)
        count = test_db.ocr_jobs.count_documents({})
        assert count == 1, f"Expected 1 OCR job, got {count}"


# ===========================================================================
# 2. Source-hash provenance
# ===========================================================================


class TestSourceHashProvenance:
    def test_all_documents_have_sha256(self, test_db):
        """Every document in MongoDB must have a non-empty sha256."""
        do_import(test_db)
        missing = list(
            test_db.documents.find(
                {"$or": [{"sha256": {"$exists": False}}, {"sha256": None}, {"sha256": ""}]},
                {"source_id": 1, "_id": 0},
            )
        )
        assert missing == [], f"Documents missing sha256: {missing}"

    def test_ocr_records_retain_source_hash(self, test_db, ocr_job):
        """Every OCR region must store the work-orders-001 source hash."""
        do_import(test_db)
        expected_hash = ocr_job["source_hash"]
        wrong = list(
            test_db.ocr_regions.find(
                {"source_hash": {"$ne": expected_hash}},
                {"region_id": 1, "source_hash": 1, "_id": 0},
            )
        )
        assert wrong == [], f"OCR regions with wrong/missing source_hash: {wrong}"

    def test_work_order_fields_retain_source_hash(self, test_db, ocr_job):
        """Every work-order candidate field must retain the source hash."""
        do_import(test_db)
        expected_hash = ocr_job["source_hash"]
        wrong = list(
            test_db.work_order_fields.find(
                {"source_hash": {"$ne": expected_hash}},
                {"field_id": 1, "_id": 0},
            )
        )
        assert wrong == [], f"Work-order fields with wrong hash: {wrong}"

    def test_assets_reference_original_source_ids(self, test_db):
        """P&ID assets must reference one of the five original pid-* source IDs."""
        do_import(test_db)
        valid_source_ids = {
            "pid-001-reactor",
            "pid-002-distillation",
            "pid-003-storage",
            "pid-004-boiler",
            "pid-005-etp",
        }
        invalid = list(
            test_db.assets.find(
                {"source_id": {"$nin": list(valid_source_ids)}},
                {"tag": 1, "source_id": 1, "_id": 0},
            )
        )
        assert invalid == [], f"Assets referencing invalid source_id: {invalid}"


# ===========================================================================
# 3. Synthetic-demo labelling
# ===========================================================================


class TestSyntheticDemoLabelling:
    def test_synthetic_documents_have_provenance_label(self, test_db, active_manifest):
        """Every synthetic_demo document in MongoDB must have synthetic_label set."""
        do_import(test_db)
        synthetic_source_ids = [
            s["source_id"]
            for s in active_manifest["sources"]
            if s["provenance"] == "synthetic_demo"
        ]
        for sid in synthetic_source_ids:
            doc = test_db.documents.find_one({"source_id": sid}, {"_id": 0})
            assert doc is not None, f"Synthetic document '{sid}' not found in DB"
            assert doc.get("provenance") == "synthetic_demo", (
                f"'{sid}' missing provenance field"
            )
            assert doc.get("synthetic_label") == "Synthetic demo data", (
                f"'{sid}' missing synthetic_label"
            )

    def test_original_documents_have_no_synthetic_label(self, test_db, active_manifest):
        """Original source documents must NOT have a synthetic_label."""
        do_import(test_db)
        original_source_ids = [
            s["source_id"]
            for s in active_manifest["sources"]
            if s["provenance"] == "original"
        ]
        for sid in original_source_ids:
            doc = test_db.documents.find_one({"source_id": sid}, {"_id": 0})
            assert doc is not None, f"Original document '{sid}' not found in DB"
            assert doc.get("provenance") == "original"
            assert not doc.get("synthetic_label"), (
                f"Original document '{sid}' incorrectly has synthetic_label"
            )

    def test_correct_synthetic_document_count(self, test_db, active_manifest):
        """There must be exactly 24 synthetic_demo documents."""
        do_import(test_db)
        count = test_db.documents.count_documents({"provenance": "synthetic_demo"})
        expected = sum(
            1
            for s in active_manifest["sources"]
            if s["provenance"] == "synthetic_demo"
        )
        assert count == expected, f"Expected {expected} synthetic docs, got {count}"


# ===========================================================================
# 4. Original vs derived data separation
# ===========================================================================


class TestOriginalVsDerivedSeparation:
    def test_ocr_records_reference_work_orders_source_id(self, test_db):
        """OCR regions must reference source_id='work-orders-001', not a P&ID."""
        do_import(test_db)
        wrong = list(
            test_db.ocr_regions.find(
                {"source_id": {"$ne": "work-orders-001"}},
                {"region_id": 1, "source_id": 1, "_id": 0},
            )
        )
        assert wrong == [], f"OCR regions with unexpected source_id: {wrong}"

    def test_pid_assets_do_not_reference_work_order_source(self, test_db):
        """P&ID assets must NOT reference 'work-orders-001' as their source_id."""
        do_import(test_db)
        wrong = list(
            test_db.assets.find(
                {"source_id": "work-orders-001"},
                {"tag": 1, "_id": 0},
            )
        )
        assert wrong == [], f"Assets wrongly referencing work-orders-001: {wrong}"

    def test_six_original_documents_present(self, test_db):
        """There must be exactly 6 original source documents."""
        do_import(test_db)
        count = test_db.documents.count_documents({"provenance": "original"})
        assert count == 6, f"Expected 6 original documents, got {count}"


# ===========================================================================
# 5. OCR state preservation
# ===========================================================================


class TestOcrStatePreservation:
    def test_all_ocr_regions_are_pending_review(self, test_db):
        """All OCR regions must start as pending_review (never auto-verified)."""
        do_import(test_db)
        not_pending = list(
            test_db.ocr_regions.find(
                {"review_state": {"$ne": "pending_review"}},
                {"region_id": 1, "review_state": 1, "_id": 0},
            )
        )
        assert not_pending == [], f"OCR regions not in pending_review: {not_pending}"

    def test_all_ocr_regions_are_ai_proposed(self, test_db):
        """All OCR regions must have state='AI proposed'."""
        do_import(test_db)
        wrong_state = list(
            test_db.ocr_regions.find(
                {"state": {"$ne": "AI proposed"}},
                {"region_id": 1, "state": 1, "_id": 0},
            )
        )
        assert wrong_state == [], f"OCR regions with wrong state: {wrong_state}"

    def test_all_candidate_fields_are_ai_proposed(self, test_db):
        """All work-order candidate fields must be AI proposed / pending_review."""
        do_import(test_db)
        total = test_db.work_order_fields.count_documents({})
        pending = test_db.work_order_fields.count_documents(
            {"review_state": "pending_review", "state": "AI proposed"}
        )
        assert total == pending, (
            f"Only {pending}/{total} work-order fields are correctly marked AI proposed/pending"
        )

    def test_all_review_tasks_pending(self, test_db):
        """All review tasks imported from the queue must start pending."""
        do_import(test_db)
        total = test_db.review_tasks.count_documents({})
        pending = test_db.review_tasks.count_documents({"state": "pending_review"})
        assert total == pending, (
            f"Only {pending}/{total} review tasks are pending_review"
        )


# ===========================================================================
# 6. API health
# ===========================================================================


class TestApiHealth:
    def test_health_returns_200(self, api_client):
        resp = api_client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"]["connected"] is True


# ===========================================================================
# 7. API documents
# ===========================================================================


class TestApiDocuments:
    def test_documents_returns_30(self, api_client, test_db):
        """After import, GET /api/v1/documents must return 30 documents."""
        do_import(test_db)
        resp = api_client.get("/api/v1/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 30, f"Expected 30, got {data['total']}"

    def test_synthetic_docs_have_label_in_response(self, api_client, test_db):
        """Synthetic documents in the API response must carry synthetic_label."""
        do_import(test_db)
        resp = api_client.get("/api/v1/documents")
        docs = resp.json()["documents"]
        for doc in docs:
            if doc.get("provenance") == "synthetic_demo":
                assert doc.get("synthetic_label") == "Synthetic demo data", (
                    f"Missing synthetic_label on {doc['source_id']}"
                )


# ===========================================================================
# 8. API assets
# ===========================================================================


class TestApiAssets:
    def test_assets_returns_31(self, api_client, test_db):
        """After import, GET /api/v1/assets must return 31 assets."""
        do_import(test_db)
        resp = api_client.get("/api/v1/assets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 31, f"Expected 31, got {data['total']}"

    def test_assets_are_verified_state(self, api_client, test_db):
        """All P&ID assets from the reviewed registry must have state='verified'."""
        do_import(test_db)
        resp = api_client.get("/api/v1/assets")
        assets = resp.json()["assets"]
        non_verified = [a for a in assets if a.get("state") != "verified"]
        assert non_verified == [], f"Assets not in verified state: {non_verified}"


# ===========================================================================
# 9. API asset by tag — ETP-601
# ===========================================================================


class TestApiAssetByTag:
    def test_etp601_found(self, api_client, test_db):
        """ETP-601 must be retrievable by tag."""
        do_import(test_db)
        resp = api_client.get("/api/v1/assets/ETP-601")
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset"]["tag"] == "ETP-601"
        assert data["asset"]["source_id"] == "pid-005-etp"

    def test_etp601_has_relationships(self, api_client, test_db):
        """ETP-601 must have at least one relationship from pid_relationships.json."""
        do_import(test_db)
        resp = api_client.get("/api/v1/assets/ETP-601")
        data = resp.json()
        assert len(data["relationships"]) >= 1, "ETP-601 has no relationships"

    def test_unknown_tag_returns_404(self, api_client, test_db):
        """A non-existent tag must return 404, not a fabricated result."""
        do_import(test_db)
        resp = api_client.get("/api/v1/assets/FAKE-999")
        assert resp.status_code == 404

    def test_etp601_drawing_id(self, api_client, test_db):
        """ETP-601 must reference drawing PCP-PID-005."""
        do_import(test_db)
        resp = api_client.get("/api/v1/assets/ETP-601")
        data = resp.json()
        assert data["asset"].get("drawing_id") == "PCP-PID-005"
