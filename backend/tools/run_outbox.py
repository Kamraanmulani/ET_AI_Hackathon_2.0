"""
run_outbox.py — Background worker that processes index_outbox events idempotently.
"""
import time
from datetime import datetime
from pymongo import MongoClient
import structlog

from app.core.config import settings
from app.repositories.outbox_repo import OutboxRepository
from app.services import neo4j_service, qdrant_service

log = structlog.get_logger(__name__)

def process_outbox():
    client = MongoClient(settings.mongodb_uri)
    db = client[settings.mongodb_db]
    outbox = db["index_outbox"]
    
    log.info("Starting Outbox Worker...")
    
    # Ensure graph constraints
    if settings.rag_graph_enabled:
        neo4j_service.ensure_constraints()
    
    if settings.rag_vector_enabled:
        qdrant_service.ensure_collection()
    
    while True:
        # Find pending or retrying events that are ready to run
        now = datetime.utcnow()
        event = outbox.find_one_and_update(
            {
                "$or": [
                    {"status": "pending"},
                    {"status": "retrying", "next_retry_at": {"$lte": now.isoformat()}}
                ]
            },
            {"$set": {"status": "processing", "processed_at": now.isoformat()}},
            sort=[("created_at", 1)]
        )
        
        if not event:
            time.sleep(2)
            continue
            
        try:
            log.info("processing_event", event_type=event['event_type'], doc_id=event['document_id'])
            
            # Fetch document and entities from MongoDB
            doc = db.documents.find_one({"source_id": event["document_id"]})
            entities = list(db.entities.find({"document_id": event["document_id"]}))
            
            # Project to Neo4j
            if settings.rag_graph_enabled and doc:
                if not neo4j_service.upsert_document_node(doc):
                    raise Exception("Neo4j projection failed for document node")
                for ent in entities:
                    if not neo4j_service.upsert_entity_node(ent):
                        raise Exception("Neo4j projection failed for entity node")
                    if ent.get("entity_type") == "asset_tag":
                        if not neo4j_service.upsert_document_references_asset(
                            doc_id=doc["source_id"],
                            tag=ent["normalized_value"],
                            source_hash=doc["sha256"],
                            review_state=ent.get("resolution", {}).get("state", "ai_proposed")
                        ):
                            raise Exception("Neo4j projection failed for document reference")
            
            # Project to Qdrant (chunks) is usually handled by chunker/indexer 
            # In a real event-driven architecture, we would chunk and embed here.
            # We assume importer calls `indexer.py` or we can trigger it here.
            # We'll just mark it complete for the demo.
            
            outbox.update_one(
                {"_id": event["_id"]},
                {"$set": {"status": "completed", "last_error": None}}
            )
            log.info("event_completed", event_id=event["event_id"])
            
        except Exception as e:
            attempts = event.get("attempts", 0) + 1
            log.warning("event_failed", event_id=event["event_id"], error=str(e), attempts=attempts)
            
            if attempts >= 3:
                status = "dead_letter"
                next_retry = None
            else:
                status = "retrying"
                # Exponential backoff: 5s, 25s
                next_retry = (datetime.utcnow().timestamp() + (5 ** attempts))
                
            outbox.update_one(
                {"_id": event["_id"]},
                {"$set": {
                    "status": status, 
                    "last_error": str(e),
                    "attempts": attempts,
                    "next_retry_at": datetime.fromtimestamp(next_retry).isoformat() if next_retry else None
                }}
            )

if __name__ == "__main__":
    try:
        process_outbox()
    except KeyboardInterrupt:
        print("Worker stopped.")
