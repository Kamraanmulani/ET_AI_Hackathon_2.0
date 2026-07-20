"""
app/repositories/entity_repo.py — Entity repository
"""
from pymongo.database import Database
from app.models.entity import EntityRecord

class EntityRepository:
    def __init__(self, db: Database):
        self.collection = db["entities"]

    def upsert(self, record: EntityRecord) -> tuple[EntityRecord, bool]:
        data = record.model_dump(by_alias=True)
        result = self.collection.update_one(
            {"entity_id": record.entity_id},
            {"$set": data},
            upsert=True
        )
        was_inserted = result.upserted_id is not None
        return record, was_inserted
