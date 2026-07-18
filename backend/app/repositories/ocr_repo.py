"""
repositories/ocr_repo.py — MongoDB CRUD for OCR collections.
Collections: ocr_jobs, ocr_pages, ocr_regions, work_order_fields, work_order_links.
All records land with review_state='pending_review' / state='AI proposed'.
"""
from __future__ import annotations

import structlog
from pymongo.collection import Collection

from app.models.ocr import OcrJobRecord, OcrPageRecord, OcrRegionRecord
from app.models.work_order import WorkOrderFieldRecord, WorkOrderLinkRecord

log = structlog.get_logger(__name__)


class OcrRepository:
    def __init__(self, db):
        self.jobs: Collection = db.ocr_jobs
        self.pages: Collection = db.ocr_pages
        self.regions: Collection = db.ocr_regions
        self.fields: Collection = db.work_order_fields
        self.links: Collection = db.work_order_links

    # ---- Jobs ----
    def upsert_job(self, record: OcrJobRecord) -> bool:
        doc = record.model_dump()
        doc.pop("_id", None)
        result = self.jobs.update_one(
            {"job_id": record.job_id}, {"$set": doc}, upsert=True
        )
        return result.upserted_id is not None

    def find_job(self, job_id: str):
        return self.jobs.find_one({"job_id": job_id}, {"_id": 0})

    # ---- Pages ----
    def upsert_page(self, record: OcrPageRecord) -> bool:
        doc = record.model_dump()
        doc.pop("_id", None)
        result = self.pages.update_one(
            {"page_id": record.page_id}, {"$set": doc}, upsert=True
        )
        return result.upserted_id is not None

    # ---- Regions ----
    def upsert_region(self, record: OcrRegionRecord) -> bool:
        doc = record.model_dump()
        doc.pop("_id", None)
        result = self.regions.update_one(
            {"region_id": record.region_id}, {"$set": doc}, upsert=True
        )
        return result.upserted_id is not None

    def count_regions(self) -> int:
        return self.regions.count_documents({})

    def count_pending_regions(self) -> int:
        return self.regions.count_documents({"review_state": "pending_review"})

    # ---- Work-order candidate fields ----
    def upsert_field(self, record: WorkOrderFieldRecord) -> bool:
        doc = record.model_dump()
        doc.pop("_id", None)
        result = self.fields.update_one(
            {"field_id": record.field_id}, {"$set": doc}, upsert=True
        )
        return result.upserted_id is not None

    def count_fields(self) -> int:
        return self.fields.count_documents({})

    # ---- Candidate asset links ----
    def upsert_link(self, record: WorkOrderLinkRecord) -> bool:
        doc = record.model_dump()
        doc.pop("_id", None)
        result = self.links.update_one(
            {"link_id": record.link_id}, {"$set": doc}, upsert=True
        )
        return result.upserted_id is not None

    def count_links(self) -> int:
        return self.links.count_documents({})
