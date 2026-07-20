"""
services/review_service.py — Human review decision processing.

A reviewer decision:
1. Updates review_tasks.state to the decided outcome.
2. Updates the linked work_order_links or work_order_fields record.
3. Appends an append-only audit_event.

NEVER auto-verifies anything. Every state change requires an explicit decision.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

import structlog

log = structlog.get_logger(__name__)

VALID_DECISIONS = {"verify", "reject", "correct", "mark_unreadable"}

DECISION_STATE_MAP = {
    "verify": "verified",
    "reject": "rejected",
    "correct": "corrected",
    "mark_unreadable": "unreadable",
}


def process_review_decision(
    db,
    task_id: str,
    decision: str,
    corrected_value: str | None = None,
    reviewer_id: str = "reviewer",
) -> dict:
    """
    Apply a reviewer decision to a review task.
    Returns the updated task or raises ValueError on invalid input.
    """
    if decision not in VALID_DECISIONS:
        raise ValueError(f"Invalid decision '{decision}'. Must be one of: {VALID_DECISIONS}")

    task = db.review_tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not task:
        raise LookupError(f"Review task '{task_id}' not found.")

    if task.get("state") not in ("pending_review",):
        raise ValueError(
            f"Task '{task_id}' has already been decided (state='{task.get('state')}'). "
            "Decisions are final in this prototype."
        )

    new_state = DECISION_STATE_MAP[decision]
    now = datetime.utcnow()

    # 1. Update the review task
    update_fields = {
        "state": new_state,
        "reviewer_id": reviewer_id,
        "reviewed_at": now,
    }
    if corrected_value and decision == "correct":
        update_fields["corrected_value"] = corrected_value

    db.review_tasks.update_one(
        {"task_id": task_id},
        {"$set": update_fields},
    )

    # 2. Propagate state to the linked evidence record
    task_type = task.get("task_type", "")

    if task_type == "asset_link_review":
        # Find and update the matching work_order_link
        region_id = task.get("source_region_id")
        asset_tag = task.get("proposed_asset_tag")
        if region_id and asset_tag:
            db.work_order_links.update_many(
                {"task_id": task_id},
                {"$set": {"review_state": new_state, "state": new_state}},
            )

    elif task_type in ("ocr_field_review", "field_review"):
        # Find and update the matching work_order_field
        db.work_order_fields.update_many(
            {"source_region_id": task.get("source_region_id"),
             "field": task.get("field")},
            {"$set": {
                "review_state": new_state,
                "state": new_state,
                **({"corrected_value": corrected_value} if corrected_value else {}),
            }},
        )

    elif task_type == "ocr_page_review":
        # Mark the OCR region
        db.ocr_regions.update_many(
            {"source_page": task.get("source_page"),
             "job_id": {"$exists": True}},
            {"$set": {"review_state": new_state}},
        )

    # 3. Append audit event (append-only, never update or delete)
    audit_doc = {
        "event_type": "review_decision",
        "entity_type": "review_task",
        "entity_id": task_id,
        "actor": reviewer_id,
        "detail": {
            "decision": decision,
            "task_type": task_type,
            "new_state": new_state,
            "corrected_value": corrected_value,
            "proposed_value": task.get("proposed_value") or task.get("proposed_asset_tag"),
            "source_id": task.get("source_id"),
            "source_page": task.get("source_page"),
        },
        "timestamp": now,
    }
    db.audit_events.insert_one(audit_doc)

    # Also append an event for the asset tag if this is an asset link review
    if task_type == "asset_link_review" and task.get("proposed_asset_tag"):
        asset_audit = {
            "event_type": "review_decision",
            "entity_type": "asset",
            "entity_id": task.get("proposed_asset_tag"),
            "actor": reviewer_id,
            "detail": {
                "decision": decision,
                "task_id": task_id,
                "new_state": new_state,
                "source_id": task.get("source_id"),
                "source_page": task.get("source_page"),
            },
            "timestamp": now,
        }
        db.audit_events.insert_one(asset_audit)

    log.info(
        "review_decision_applied",
        task_id=task_id,
        decision=decision,
        new_state=new_state,
        reviewer=reviewer_id,
    )

    updated_task = db.review_tasks.find_one({"task_id": task_id}, {"_id": 0})
    return updated_task


def get_review_tasks_paginated(
    db,
    page: int = 1,
    limit: int = 20,
    task_type: str | None = None,
    state: str | None = None,
) -> dict:
    """Return paginated review tasks with optional type/state filter."""
    query: dict = {}
    if task_type:
        query["task_type"] = task_type
    if state:
        query["state"] = state

    skip = (page - 1) * limit
    total = db.review_tasks.count_documents(query)
    tasks = list(
        db.review_tasks.find(query, {"_id": 0})
        .sort("imported_at", 1)
        .skip(skip)
        .limit(limit)
    )

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit,
        "tasks": tasks,
    }


def get_review_task_detail(db, task_id: str) -> dict | None:
    """Return a single task with its linked OCR region data."""
    task = db.review_tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not task:
        return None

    # Attach OCR region if available
    region_id = task.get("source_region_id")
    if region_id:
        region = db.ocr_regions.find_one({"region_id": region_id}, {"_id": 0})
        if region:
            task["ocr_region"] = region

    # Attach page image URL
    source_page = task.get("source_page")
    if source_page:
        task["page_image_url"] = f"/static/ocr-pages/page-{source_page:03d}.png"

    return task
