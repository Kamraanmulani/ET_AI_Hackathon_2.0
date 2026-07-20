"""
api/v1/documents.py — GET /api/v1/documents

Returns all 30 active documents with provenance and extraction state.
Synthetic-demo documents always include the 'Synthetic demo data' label.
"""
from fastapi import APIRouter, HTTPException
from app.core.database import get_db
from app.repositories.document_repo import DocumentRepository

router = APIRouter()


@router.get("/documents", tags=["documents"])
def list_documents():
    db = get_db()
    repo = DocumentRepository(db)
    docs = repo.find_all()
    # Ensure synthetic label is always present in the response
    for doc in docs:
        if doc.get("provenance") == "synthetic_demo":
            doc.setdefault("synthetic_label", "Synthetic demo data")
    return {
        "total": len(docs),
        "documents": docs,
    }

TYPE_MAP = {
    "pid_drawing": ("drawings", "P&ID Drawing"),
    "pid_image": ("drawings", "P&ID Image"),
    "work_order_pdf": ("maintenance", "Work Order"),
    "scanned_work_order_pdf": ("maintenance", "Scanned Work Order"),
    "sop": ("safety_procedures", "SOP"),
    "sop_excerpt_pdf": ("safety_procedures", "SOP"),
    "inspection": ("inspections", "Inspection Report"),
    "inspection_report_pdf": ("inspections", "Inspection Report"),
    "incident": ("incidents", "Incident Report"),
    "near_miss_report_pdf": ("incidents", "Near Miss Report"),
    "email": ("communications", "Email"),
    "email_export": ("communications", "Email Export"),
    "spreadsheet": ("maintenance", "Spreadsheet"),
}

def _map_readiness(doc: dict, pending_reviews: int) -> str:
    if pending_reviews > 0:
        return "needs_review"
        
    ingestion = doc.get("ingestion") or {}
    state = ingestion.get("state") or doc.get("extraction_state", "pending")
    
    if state == "failed":
        return "attention_needed"
    if state in ("registered", "extracted", "pending"):
        return "processing"
    if state == "review_required":
        return "needs_review"
        
    doc_type = doc.get("document_type", "")
    if "drawing" in doc_type or "pid" in doc_type:
        return "available"
        
    return "ready"

@router.get("/documents/catalogue", tags=["documents"])
def list_catalogue_documents():
    """Redacted view for the Plant Information Catalogue."""
    db = get_db()
    repo = DocumentRepository(db)
    docs = repo.find_all()
    
    results = []
    for doc in docs:
        doc_id = doc["source_id"]
        doc_type = doc.get("document_type", "unknown")
        category, display_type = TYPE_MAP.get(doc_type, ("other", doc_type.replace("_", " ").title()))
        
        # Resolve assets and drawings from entities
        entities = list(db.entities.find({"document_id": doc_id}, {"_id": 0}))
        asset_tags = []
        drawing_ids = []
        for ent in entities:
            res = ent.get("resolution", {})
            if res.get("state") in ("verified", "ai_proposed"):
                val = ent.get("normalized_value")
                if val:
                    if ent.get("entity_type") == "asset_tag" and val not in asset_tags:
                        asset_tags.append(val)
                    elif ent.get("entity_type") == "drawing_id" and val not in drawing_ids:
                        drawing_ids.append(val)
                        
        # Resolve from P&ID assets
        for a in db.assets.find({"source_id": doc_id, "state": "verified"}):
            if a["tag"] not in asset_tags:
                asset_tags.append(a["tag"])
                
        # Resolve from work order links
        for link in db.work_order_links.find({"source_id": doc_id, "state": "verified"}):
            if link["asset_tag"] not in asset_tags:
                asset_tags.append(link["asset_tag"])
                        
        pending_count = db.review_tasks.count_documents({"document_id": doc_id, "state": "pending_review"})
        
        # Fallback date
        date_str = "Not recorded"
        if "source" in doc and doc["source"] and doc["source"].get("document_date"):
            date_str = doc["source"]["document_date"]
        elif "manifest" in doc and doc["manifest"] and doc["manifest"].get("date"):
            date_str = doc["manifest"]["date"]
        elif "imported_at" in doc and doc["imported_at"]:
            date_str = doc["imported_at"].strftime("%Y-%m-%d")
            
        results.append({
            "record_id": doc_id,
            "document_type": doc_type,
            "display_type": display_type,
            "category": category,
            "asset_tags": asset_tags,
            "drawing_ids": drawing_ids,
            "document_date": date_str,
            "readiness": _map_readiness(doc, pending_count),
            "review_summary": {
                "has_pending_review": pending_count > 0,
                "pending_count": pending_count
            },
            "open_target": f"/documents/{doc_id}"
        })
        
    return {"total": len(results), "documents": results}


@router.get("/documents/{document_id}/entities", tags=["documents"])
def get_document_entities(document_id: str):
    """Return verified entities extracted from a specific document."""
    db = get_db()
    entities = list(db.entities.find({"document_id": document_id}, {"_id": 0}))
    return {"document_id": document_id, "entities": entities}

@router.get("/documents/{document_id}", tags=["documents"])
def get_document(document_id: str):
    """Return redacted document detail."""
    db = get_db()
    doc = db.documents.find_one({"source_id": document_id}, {"_id": 0, "provenance": 0, "sha256": 0, "path": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    doc_type = doc.get("document_type", "unknown")
    category, display_type = TYPE_MAP.get(doc_type, ("other", doc_type.replace("_", " ").title()))
    
    entities = list(db.entities.find({"document_id": document_id}, {"_id": 0}))
    asset_tags = []
    for ent in entities:
        res = ent.get("resolution", {})
        if res.get("state") in ("verified", "ai_proposed") and ent.get("entity_type") == "asset_tag":
            val = ent.get("normalized_value")
            if val and val not in asset_tags:
                asset_tags.append(val)
                
    for a in db.assets.find({"source_id": document_id, "state": "verified"}):
        if a["tag"] not in asset_tags:
            asset_tags.append(a["tag"])
            
    for link in db.work_order_links.find({"source_id": document_id, "state": "verified"}):
        if link["asset_tag"] not in asset_tags:
            asset_tags.append(link["asset_tag"])
                
    pending_count = db.review_tasks.count_documents({"document_id": document_id, "state": "pending_review"})
    
    date_str = "Not recorded"
    if "source" in doc and doc["source"] and doc["source"].get("document_date"):
        date_str = doc["source"]["document_date"]
    elif "manifest" in doc and doc["manifest"] and doc["manifest"].get("date"):
        date_str = doc["manifest"]["date"]
    elif "imported_at" in doc and doc["imported_at"]:
        date_str = doc["imported_at"].strftime("%Y-%m-%d")
        
    return {
        "record_id": document_id,
        "display_type": display_type,
        "category": category,
        "document_date": date_str,
        "asset_tags": asset_tags,
        "readiness": _map_readiness(doc, pending_count),
        "source": doc.get("source", {}), # Omit provenance from source
        "ingestion": {
            "state": doc.get("ingestion", {}).get("state", doc.get("extraction_state", "pending"))
        }
    }
