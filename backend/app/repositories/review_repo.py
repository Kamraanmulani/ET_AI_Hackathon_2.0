"""
repositories/review_repo.py — MongoDB CRUD for review_tasks and audit_events.
"""
from __future__ import annotations

import structlog
from pymongo.collection import Collection

from app.models.audit import AuditEventRecord
from app.models.review import ReviewTaskRecord

log = structlog.get_logger(__name__)


class ReviewRepository:
    def __init__(self, db):
        self.tasks: Collection = db.review_tasks
        self.audit: Collection = db.audit_events

    # ---- Review tasks ----
    def upsert_task(self, record: ReviewTaskRecord) -> bool:
        doc = record.model_dump()
        doc.pop("_id", None)
        result = self.tasks.update_one(
            {"task_id": record.task_id}, {"$set": doc}, upsert=True
        )
        return result.upserted_id is not None

    def find_pending(self, limit: int = 20) -> list[dict]:
        return list(
            self.tasks.find({"state": "pending_review"}, {"_id": 0}).limit(limit)
        )

    def count_pending(self) -> int:
        return self.tasks.count_documents({"state": "pending_review"})

    def count_tasks(self) -> int:
        return self.tasks.count_documents({})

    # ---- Audit events (append-only) ----
    def append_event(self, record: AuditEventRecord) -> None:
        doc = record.model_dump()
        doc.pop("_id", None)
        self.audit.insert_one(doc)

    def count_events(self) -> int:
        return self.audit.count_documents({})
