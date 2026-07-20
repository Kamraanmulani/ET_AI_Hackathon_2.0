"""
run_outbox.py — Background worker that processes index_outbox events.
"""
import time
from datetime import datetime
from pymongo import MongoClient

from app.core.config import settings
from app.repositories.outbox_repo import OutboxRepository

def process_outbox():
    client = MongoClient(settings.mongodb_uri)
    db = client[settings.mongodb_db]
    outbox = db["index_outbox"]
    
    print("Starting Outbox Worker...")
    
    while True:
        # Find pending or failed events that are due for retry
        # For R1 demo, we just find "pending"
        event = outbox.find_one_and_update(
            {"status": "pending"},
            {"$set": {"status": "processing", "processed_at": datetime.utcnow()}},
            sort=[("created_at", 1)]
        )
        
        if not event:
            time.sleep(2)
            continue
            
        try:
            print(f"Processing event: {event['event_type']} for doc {event['document_id']}")
            # Here we would update Neo4j and Qdrant idempotently
            # (Neo4j projection logic is currently handled in run_indexer.py)
            
            # For this hackathon step, just mark completed
            outbox.update_one(
                {"_id": event["_id"]},
                {"$set": {"status": "completed", "last_error": None}}
            )
            print("Successfully processed event.")
            
        except Exception as e:
            print(f"Failed to process event: {e}")
            outbox.update_one(
                {"_id": event["_id"]},
                {"$set": {
                    "status": "failed", 
                    "last_error": str(e),
                    # Simple backoff would go here
                }}
            )

if __name__ == "__main__":
    try:
        process_outbox()
    except KeyboardInterrupt:
        print("Worker stopped.")
