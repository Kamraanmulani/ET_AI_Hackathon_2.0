"""
api/v1/review.py — Review queue endpoints.

GET  /api/v1/review                        → summary counts
GET  /api/v1/review/tasks                  → paginated task list
GET  /api/v1/review/tasks/{task_id}        → single task detail with OCR region
POST /api/v1/review/tasks/{task_id}/decide → submit reviewer decision
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator
from app.core.database import get_db
from app.repositories.review_repo import ReviewRepository
from app.services.review_service import (
    process_review_decision,
    get_review_tasks_paginated,
    get_review_task_detail,
    VALID_DECISIONS,
)

router = APIRouter()


class DecisionRequest(BaseModel):
    decision: str
    corrected_value: Optional[str] = None
    reviewer_id: Optional[str] = "reviewer"

    @field_validator("decision")
    @classmethod
    def decision_must_be_valid(cls, v):
        if v not in VALID_DECISIONS:
            raise ValueError(f"decision must be one of: {sorted(VALID_DECISIONS)}")
        return v


@router.get("/review", tags=["review"])
def get_review_summary():
    """Return review queue summary counts."""
    db = get_db()
    repo = ReviewRepository(db)
    pending_count = repo.count_pending()
    total = repo.count_tasks()
    sample = repo.find_pending(limit=10)
    return {
        "total_tasks": total,
        "pending_tasks": pending_count,
        "sample_pending": sample,
    }


@router.get("/review/tasks", tags=["review"])
def list_review_tasks(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    task_type: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
):
    """Return paginated review tasks with optional type/state filter."""
    db = get_db()
    return get_review_tasks_paginated(db, page=page, limit=limit, task_type=task_type, state=state)


@router.get("/review/tasks/{task_id}", tags=["review"])
def get_task_detail(task_id: str):
    """Return a single review task with OCR region and page image URL."""
    db = get_db()
    task = get_review_task_detail(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return task


@router.post("/review/tasks/{task_id}/decide", tags=["review"])
def decide_task(task_id: str, body: DecisionRequest):
    """
    Submit a reviewer decision for a review task.
    Allowed decisions: verify, reject, correct, mark_unreadable.
    Every decision creates an append-only audit event.
    """
    db = get_db()
    try:
        updated = process_review_decision(
            db=db,
            task_id=task_id,
            decision=body.decision,
            corrected_value=body.corrected_value,
            reviewer_id=body.reviewer_id or "reviewer",
        )
        return {
            "status": "decision_recorded",
            "task_id": task_id,
            "new_state": updated.get("state"),
            "decision": body.decision,
        }
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
