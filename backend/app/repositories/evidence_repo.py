"""
app/repositories/evidence_repo.py — Evidence repository
"""
from pymongo.database import Database
from app.models.evidence import EvidenceRecord

class EvidenceRepository:
    def __init__(self, db: Database):
        self.collection = db["evidence"]

    def upsert(self, record: EvidenceRecord) -> tuple[EvidenceRecord, bool]:
        data = record.model_dump(by_alias=True)
        # Handle datetime serialization if necessary or rely on pymongo depending on how models are structured.
        # But wait, pydantic models to dict doesn't convert datetime to strings, pymongo handles datetime objects natively.
        
        result = self.collection.update_one(
            {"evidence_id": record.evidence_id},
            {"$set": data},
            upsert=True
        )
        was_inserted = result.upserted_id is not None
        return record, was_inserted
