"""
repositories/document_repo.py — MongoDB CRUD for the `documents` collection.
"""
from __future__ import annotations

from typing import Optional

import structlog
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from app.models.document import DocumentRecord

log = structlog.get_logger(__name__)


class DocumentRepository:
    def __init__(self, db):
        self.col: Collection = db.documents

    def upsert(self, record: DocumentRecord) -> tuple[str, bool]:
        """
        Insert or update a document by source_id.
        Returns (source_id, was_inserted).
        Never modifies source files.
        """
        doc = record.model_dump(by_alias=True, exclude_none=False)
        doc.pop("_id", None)

        # Attach a visible synthetic label to the stored record
        if record.provenance == "synthetic_demo":
            doc["synthetic_label"] = "Synthetic demo data"

        result = self.col.update_one(
            {"source_id": record.source_id},
            {"$set": doc},
            upsert=True,
        )
        inserted = result.upserted_id is not None
        log.info(
            "document_upserted",
            source_id=record.source_id,
            inserted=inserted,
        )
        return record.source_id, inserted

    def find_all(self) -> list[dict]:
        return list(self.col.find({}, {"_id": 0}))

    def find_by_source_id(self, source_id: str) -> Optional[dict]:
        return self.col.find_one({"source_id": source_id}, {"_id": 0})

    def count(self) -> int:
        return self.col.count_documents({})
