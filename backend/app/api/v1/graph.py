"""
api/v1/graph.py — Asset evidence graph API endpoint.

GET /api/v1/assets/{tag}/evidence-graph
Returns nodes and edges for the asset evidence graph (from Neo4j).
Falls back to MongoDB relationships if Neo4j is unavailable.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Path

from app.core.database import get_db
from app.core.config import settings
from app.services import neo4j_service

log = structlog.get_logger(__name__)
router = APIRouter(tags=["graph"])


@router.get("/assets/{tag}/evidence-graph")
def get_evidence_graph(tag: str = Path(..., description="Asset tag, e.g. ETP-601")):
    """
    Return the asset evidence graph for a given tag.
    Uses Neo4j for graph traversal; falls back to MongoDB relationships if Neo4j is unavailable.
    """
    tag = tag.upper()
    db = get_db()

    # Try Neo4j first
    graph = neo4j_service.get_asset_evidence_graph(tag)

    if not graph.get("available") or graph.get("fallback"):
        # MongoDB fallback: build a simple graph from canonical records
        graph = _mongo_graph_fallback(tag, db)
        graph["fallback"] = True
        graph["fallback_reason"] = "Neo4j unavailable — using MongoDB relationship data"

    return graph


def _mongo_graph_fallback(tag: str, db) -> dict:
    """Build a basic graph from MongoDB assets and relationships."""
    nodes = []
    edges = []

    asset = db.assets.find_one({"tag": tag}, {"_id": 0})
    if asset:
        nodes.append({"id": f"asset:{tag}", "type": "Asset", "data": asset})

        drawing_id = asset.get("drawing_id", "")
        if drawing_id:
            drawing = db.documents.find_one({"drawing_id": drawing_id}, {"_id": 0})
            d_data = drawing or {"drawing_id": drawing_id}
            nodes.append({"id": f"drawing:{drawing_id}", "type": "Drawing", "data": d_data})
            edges.append({
                "source": f"asset:{tag}",
                "target": f"drawing:{drawing_id}",
                "type": "APPEARS_ON",
                "data": {"review_state": "verified"},
            })

    # Related assets via P&ID relationships
    for rel in db.relationships.find(
        {"$or": [{"from_tag": tag}, {"to_tag": tag}]},
        {"_id": 0}
    ).limit(10):
        other_tag = rel["to_tag"] if rel["from_tag"] == tag else rel["from_tag"]
        other_asset = db.assets.find_one({"tag": other_tag}, {"_id": 0})
        if other_asset:
            nodes.append({"id": f"asset:{other_tag}", "type": "Asset", "data": other_asset})
            edges.append({
                "source": f"asset:{tag}",
                "target": f"asset:{other_tag}",
                "type": "RELATED_TO",
                "data": {
                    "rel_type": rel.get("relationship_type", ""),
                    "review_state": rel.get("state", "verified"),
                },
            })

    # OCR chunks that mention this tag
    for chunk in db.document_chunks.find(
        {"asset_tags": tag, "review_state": {"$nin": ["rejected", "unreadable"]}},
        {"_id": 0}
    ).limit(5):
        cid = chunk.get("chunk_id", "")
        nodes.append({"id": f"chunk:{cid}", "type": "Chunk", "data": {
            "chunk_id": cid,
            "source_id": chunk.get("source_id", ""),
            "review_state": chunk.get("review_state", ""),
            "provenance": chunk.get("provenance", ""),
            "text_excerpt": chunk.get("text", "")[:200],
        }})
        edges.append({
            "source": f"chunk:{cid}",
            "target": f"asset:{tag}",
            "type": "MENTIONS",
            "data": {"review_state": chunk.get("review_state", "")},
        })

    # Deduplicate nodes
    seen = set()
    deduped = []
    for n in nodes:
        if n["id"] not in seen:
            seen.add(n["id"])
            deduped.append(n)

    return {
        "available": True,
        "tag": tag,
        "nodes": deduped,
        "edges": edges,
        "fallback": False,
    }

@router.get("/health")
def graph_health():
    """Verify Neo4j connectivity and schema."""
    available = neo4j_service.check_health()
    return {"status": "ok" if available else "unavailable", "neo4j_available": available}

@router.post("/reconcile")
def graph_reconcile():
    """Reconcile index counts."""
    db = get_db()
    
    mongo_docs = db.documents.count_documents({})
    mongo_assets = db.assets.count_documents({})
    mongo_entities = db.entities.count_documents({})
    
    neo4j_docs = 0
    neo4j_assets = 0
    neo4j_entities = 0
    
    driver = neo4j_service._get_driver()
    neo4j_available = driver is not None
    error_msg = None
    if neo4j_available:
        try:
            with driver.session(database=settings.neo4j_database) as session:
                neo4j_docs = session.run("MATCH (n:Document) RETURN count(n) AS c").single()["c"]
                neo4j_assets = session.run("MATCH (n:Asset) RETURN count(n) AS c").single()["c"]
                neo4j_entities = session.run("MATCH (n:Entity) RETURN count(n) AS c").single()["c"]
        except Exception as e:
            neo4j_available = False
            error_msg = str(e)
            log.warning("reconcile_neo4j_failed", error=str(e))
            
    outbox_pending = db.index_outbox.count_documents({"status": "pending"})
    outbox_failed = db.index_outbox.count_documents({"status": "failed"})
    outbox_dead_letter = db.index_outbox.count_documents({"status": "dead_letter"})
    
    # Calculate Parity
    doc_parity = (mongo_docs == neo4j_docs)
    asset_parity = (mongo_assets == neo4j_assets)
    entity_parity = (mongo_entities == neo4j_entities)
    
    status = "green" if neo4j_available and doc_parity and asset_parity and entity_parity and outbox_pending == 0 else "red"
    if not neo4j_available:
        status = "degraded (neo4j offline)"
        
    return {
        "status": status,
        "error": error_msg,
        "mongodb": {
            "documents": mongo_docs,
            "assets": mongo_assets,
            "entities": mongo_entities
        },
        "neo4j": {
            "available": neo4j_available,
            "documents": neo4j_docs,
            "assets": neo4j_assets,
            "entities": neo4j_entities
        },
        "outbox": {
            "pending": outbox_pending,
            "failed": outbox_failed,
            "dead_letter": outbox_dead_letter
        },
        "parity": {
            "documents": doc_parity,
            "assets": asset_parity,
            "entities": entity_parity
        }
    }
