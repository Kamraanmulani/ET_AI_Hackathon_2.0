"""
repositories/asset_repo.py — MongoDB CRUD for `assets` and `relationships` collections.
"""
from __future__ import annotations

from typing import Optional

import structlog
from pymongo.collection import Collection

from app.models.asset import AssetRecord, RelationshipRecord

log = structlog.get_logger(__name__)


class AssetRepository:
    def __init__(self, db):
        self.assets: Collection = db.assets
        self.relationships: Collection = db.relationships

    # ---- Assets ----

    def upsert_asset(self, record: AssetRecord) -> tuple[str, bool]:
        """Upsert by tag. Returns (tag, was_inserted)."""
        doc = record.model_dump()
        doc.pop("_id", None)
        result = self.assets.update_one(
            {"tag": record.tag},
            {"$set": doc},
            upsert=True,
        )
        inserted = result.upserted_id is not None
        log.debug("asset_upserted", tag=record.tag, inserted=inserted)
        return record.tag, inserted

    def find_all_assets(self) -> list[dict]:
        return list(self.assets.find({}, {"_id": 0}))

    def find_asset_by_tag(self, tag: str) -> Optional[dict]:
        return self.assets.find_one({"tag": tag}, {"_id": 0})

    def count_assets(self) -> int:
        return self.assets.count_documents({})

    # ---- Relationships ----

    def upsert_relationship(self, record: RelationshipRecord) -> bool:
        """Upsert by (from_tag, to_tag, relationship_type). Returns was_inserted."""
        doc = record.model_dump()
        doc.pop("_id", None)
        result = self.relationships.update_one(
            {
                "from_tag": record.from_tag,
                "to_tag": record.to_tag,
                "relationship_type": record.relationship_type,
            },
            {"$set": doc},
            upsert=True,
        )
        return result.upserted_id is not None

    def find_relationships_for_tag(self, tag: str) -> list[dict]:
        """Return all relationships where the tag appears as from or to."""
        return list(
            self.relationships.find(
                {"$or": [{"from_tag": tag}, {"to_tag": tag}]},
                {"_id": 0},
            )
        )

    def count_relationships(self) -> int:
        return self.relationships.count_documents({})
