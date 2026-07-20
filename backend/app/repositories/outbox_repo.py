"""
app/repositories/outbox_repo.py — Outbox repository
"""
from pymongo.database import Database
from app.models.outbox import OutboxEventRecord

class OutboxRepository:
    def __init__(self, db: Database):
        self.collection = db["index_outbox"]

    def append(self, record: OutboxEventRecord) -> tuple[OutboxEventRecord, bool]:
        data = record.model_dump(by_alias=True)
        result = self.collection.update_one(
            {"event_id": record.event_id},
            {"$set": data},
            upsert=True
        )
        was_inserted = result.upserted_id is not None
        return record, was_inserted
