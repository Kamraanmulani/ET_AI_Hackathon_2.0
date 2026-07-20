from pymongo import MongoClient
from app.models.entity import EntityRecord, ResolutionMetadata, ExtractorMetadata
from app.core.identifiers import generate_id
from datetime import datetime

import re

db = MongoClient('mongodb://localhost:27017/').pragyan_ppi

# Load all valid asset tags
valid_tags = set(db.assets.distinct("tag"))

# A regex to capture alpha and numeric parts (e.g. AIT601 or AIT-601)
pattern = re.compile(r'([A-Za-z]+)-?(\d+)')

docs = db.documents.find()

for doc in docs:
    source_id = doc["source_id"]
    # skip spreadsheets, they have a dedicated adapter
    if doc.get("document_type") == "spreadsheet":
        continue
        
    matches = pattern.findall(source_id)
    for prefix, number in matches:
        candidate_tag = f"{prefix.upper()}-{number}"
        if candidate_tag in valid_tags:
            # Create an entity record
            evidence_id = generate_id(doc["sha256"], "filename", candidate_tag)
            
            # Upsert entity
            db.entities.update_one(
                {"document_id": source_id, "entity_type": "asset_tag", "normalized_value": candidate_tag},
                {"$set": {
                    "entity_id": generate_id(evidence_id, "asset_tag", candidate_tag),
                    "document_id": source_id,
                    "entity_type": "asset_tag",
                    "value": candidate_tag,
                    "normalized_value": candidate_tag,
                    "evidence_id": evidence_id,
                    "resolution": {"state": "verified", "canonical_id": f"asset:{candidate_tag}"},
                    "extractor": {"name": "filename_heuristics", "version": "1.0", "confidence": 1.0},
                    "imported_at": datetime.utcnow()
                }},
                upsert=True
            )
            print(f"Added {candidate_tag} to {source_id}")

print("Entity extraction from filenames complete.")
