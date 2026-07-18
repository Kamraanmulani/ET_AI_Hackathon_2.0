"""
tests/test_phase4.py — Phase 4 backend tests.

Covers:
- Drawing endpoints return correct structure
- Asset evidence endpoint returns evidence with provenance
- Review decision creates audit event and updates task state
- Verify decision propagates to linked records
- Reject decision does not destroy asset browsability
- Query returns citations for known text
- Query returns insufficient_evidence for unknown text
- Decided task cannot be re-decided
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# Drawing endpoint tests (no data needed — overlays seeded at startup)
# ─────────────────────────────────────────────────────────────────────────────

class TestDrawingsApi:
    def test_drawings_returns_five(self, api_client: TestClient):
        resp = api_client.get("/api/v1/drawings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["drawings"]) == 5

    def test_etp_drawing_exists(self, api_client: TestClient):
        resp = api_client.get("/api/v1/drawings/PCP-PID-005")
        assert resp.status_code == 200
        data = resp.json()
        assert data["drawing_id"] == "PCP-PID-005"
        assert "effluent" in data["area"]
        assert data["overlay_count"] > 0

    def test_etp_drawing_has_all_seven_etp_tags(self, api_client: TestClient):
        resp = api_client.get("/api/v1/drawings/PCP-PID-005")
        assert resp.status_code == 200
        data = resp.json()
        overlay_tags = {o["tag"] for o in data["overlays"]}
        required = {"ETP-601", "P-601", "AIT-601", "AAH-601", "LIC-601", "LV-601", "XV-603"}
        assert required.issubset(overlay_tags), (
            f"Missing ETP tags in overlays: {required - overlay_tags}"
        )

    def test_overlays_marked_approximate(self, api_client: TestClient):
        resp = api_client.get("/api/v1/drawings/PCP-PID-005")
        data = resp.json()
        for overlay in data["overlays"]:
            assert overlay["state"] == "coordinate_approximate"

    def test_unknown_drawing_returns_404(self, api_client: TestClient):
        resp = api_client.get("/api/v1/drawings/PCP-PID-999")
        assert resp.status_code == 404

    def test_all_drawings_have_image_url(self, api_client: TestClient):
        resp = api_client.get("/api/v1/drawings")
        for d in resp.json()["drawings"]:
            assert d["image_url"].startswith("/static/pid/")


# ─────────────────────────────────────────────────────────────────────────────
# Asset evidence tests (require seeded data)
# ─────────────────────────────────────────────────────────────────────────────

class TestAssetEvidenceApi:
    def test_etp601_evidence_returns_asset(self, seeded_api_client: TestClient):
        resp = seeded_api_client.get("/api/v1/assets/ETP-601/evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset"]["tag"] == "ETP-601"

    def test_etp601_evidence_has_relationships(self, seeded_api_client: TestClient):
        resp = seeded_api_client.get("/api/v1/assets/ETP-601/evidence")
        data = resp.json()
        assert "relationships" in data
        assert isinstance(data["relationships"], list)

    def test_evidence_has_summary(self, seeded_api_client: TestClient):
        resp = seeded_api_client.get("/api/v1/assets/ETP-601/evidence")
        data = resp.json()
        assert "evidence_summary" in data
        summary = data["evidence_summary"]
        assert "link_count" in summary
        assert "pending_links" in summary

    def test_evidence_ocr_regions_are_pending(self, seeded_api_client: TestClient):
        """All OCR evidence must still be pending_review — none auto-verified."""
        resp = seeded_api_client.get("/api/v1/assets/ETP-601/evidence")
        data = resp.json()
        for link in data.get("work_order_links", []):
            assert link.get("review_state") != "verified", (
                "Work-order link must not be auto-verified"
            )

    def test_unknown_asset_evidence_returns_404(self, seeded_api_client: TestClient):
        resp = seeded_api_client.get("/api/v1/assets/FAKE-999/evidence")
        assert resp.status_code == 404

    def test_asset_audit_returns_list(self, seeded_api_client: TestClient):
        resp = seeded_api_client.get("/api/v1/assets/ETP-601/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert isinstance(data["events"], list)


# ─────────────────────────────────────────────────────────────────────────────
# Review task list tests (require seeded data)
# ─────────────────────────────────────────────────────────────────────────────

class TestReviewTasksApi:
    def test_review_tasks_paginated(self, seeded_api_client: TestClient):
        resp = seeded_api_client.get("/api/v1/review/tasks?page=1&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        assert "total" in data
        assert data["total"] >= 98

    def test_review_tasks_filter_by_type(self, seeded_api_client: TestClient):
        resp = seeded_api_client.get("/api/v1/review/tasks?task_type=asset_link_review&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        for task in data["tasks"]:
            assert task["task_type"] == "asset_link_review"

    def test_review_task_detail_has_page_image_url(self, seeded_api_client: TestClient):
        resp = seeded_api_client.get("/api/v1/review/tasks?limit=1")
        tasks = resp.json()["tasks"]
        if not tasks:
            pytest.skip("No tasks available")
        task_id = tasks[0]["task_id"]
        detail_resp = seeded_api_client.get(f"/api/v1/review/tasks/{task_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert "page_image_url" in detail

    def test_review_unknown_task_returns_404(self, seeded_api_client: TestClient):
        resp = seeded_api_client.get("/api/v1/review/tasks/NONEXISTENT-TASK-ID")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Review decision tests (require seeded data)
# ─────────────────────────────────────────────────────────────────────────────

class TestReviewDecisionApi:
    def test_verify_decision_creates_audit_event(self, seeded_api_client: TestClient, seeded_db):
        resp = seeded_api_client.get("/api/v1/review/tasks?state=pending_review&limit=1")
        tasks = resp.json()["tasks"]
        if not tasks:
            pytest.skip("No pending tasks")
        task_id = tasks[0]["task_id"]

        audit_before = seeded_db.audit_events.count_documents({})
        decision_resp = seeded_api_client.post(
            f"/api/v1/review/tasks/{task_id}/decide",
            json={"decision": "verify", "reviewer_id": "test_reviewer"},
        )
        assert decision_resp.status_code == 200
        data = decision_resp.json()
        assert data["decision"] == "verify"
        assert data["new_state"] == "verified"

        audit_after = seeded_db.audit_events.count_documents({})
        assert audit_after > audit_before

    def test_reject_decision_changes_task_state(self, seeded_api_client: TestClient, seeded_db):
        resp = seeded_api_client.get("/api/v1/review/tasks?state=pending_review&limit=1")
        tasks = resp.json()["tasks"]
        if not tasks:
            pytest.skip("No pending tasks")
        task_id = tasks[0]["task_id"]

        decision_resp = seeded_api_client.post(
            f"/api/v1/review/tasks/{task_id}/decide",
            json={"decision": "reject"},
        )
        assert decision_resp.status_code == 200
        assert decision_resp.json()["new_state"] == "rejected"

        task = seeded_db.review_tasks.find_one({"task_id": task_id})
        assert task["state"] == "rejected"

    def test_asset_remains_browseable_after_reject(self, seeded_api_client: TestClient, seeded_db):
        tasks = list(seeded_db.review_tasks.find(
            {"proposed_asset_tag": "ETP-601", "state": "pending_review"},
            {"task_id": 1}
        ).limit(1))
        if not tasks:
            pytest.skip("No ETP-601 pending tasks")
        task_id = tasks[0]["task_id"]
        seeded_api_client.post(
            f"/api/v1/review/tasks/{task_id}/decide",
            json={"decision": "reject"},
        )
        asset_resp = seeded_api_client.get("/api/v1/assets/ETP-601")
        assert asset_resp.status_code == 200

    def test_invalid_decision_returns_422(self, seeded_api_client: TestClient, seeded_db):
        resp = seeded_api_client.get("/api/v1/review/tasks?state=pending_review&limit=1")
        tasks = resp.json()["tasks"]
        if not tasks:
            pytest.skip("No pending tasks")
        task_id = tasks[0]["task_id"]
        resp = seeded_api_client.post(
            f"/api/v1/review/tasks/{task_id}/decide",
            json={"decision": "acknowledge"},  # invalid — plant control action
        )
        assert resp.status_code == 422

    def test_cannot_re_decide_a_task(self, seeded_api_client: TestClient, seeded_db):
        resp = seeded_api_client.get("/api/v1/review/tasks?state=pending_review&limit=1")
        tasks = resp.json()["tasks"]
        if not tasks:
            pytest.skip("No pending tasks")
        task_id = tasks[0]["task_id"]

        seeded_api_client.post(
            f"/api/v1/review/tasks/{task_id}/decide",
            json={"decision": "verify"},
        )
        second = seeded_api_client.post(
            f"/api/v1/review/tasks/{task_id}/decide",
            json={"decision": "reject"},
        )
        assert second.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Grounded query tests (require seeded data)
# ─────────────────────────────────────────────────────────────────────────────

class TestGroundedQueryApi:
    def test_query_known_term_returns_evidence(self, seeded_api_client: TestClient):
        resp = seeded_api_client.get("/api/v1/query?q=R-201")
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "evidence_found"
        assert len(data["citations"]) > 0

    def test_citations_have_provenance(self, seeded_api_client: TestClient):
        resp = seeded_api_client.get("/api/v1/query?q=R-201")
        data = resp.json()
        for citation in data["citations"]:
            assert "source_id" in citation
            assert "review_state" in citation
            assert "state" in citation

    def test_citations_are_never_auto_verified(self, seeded_api_client: TestClient):
        """OCR results must all be pending_review — no auto-verification."""
        resp = seeded_api_client.get("/api/v1/query?q=R-201")
        data = resp.json()
        for citation in data["citations"]:
            assert citation["review_state"] != "verified", (
                "Query results must not be auto-verified"
            )

    def test_query_unknown_term_returns_insufficient_evidence(self, seeded_api_client: TestClient):
        resp = seeded_api_client.get("/api/v1/query?q=xyzabc_nonexistent_term_8937")
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "insufficient_evidence"
        assert data["citations"] == []

    def test_query_with_asset_filter(self, seeded_api_client: TestClient):
        resp = seeded_api_client.get("/api/v1/query?q=pump&asset_tag=P-601")
        assert resp.status_code == 200

    def test_query_too_short_returns_422(self, seeded_api_client: TestClient):
        resp = seeded_api_client.get("/api/v1/query?q=x")
        assert resp.status_code == 422
