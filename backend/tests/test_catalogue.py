import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_catalogue_redaction():
    # Insert a synthetic document with sensitive fields
    response = client.get("/api/v1/documents/catalogue")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "documents" in data
    
    for doc in data["documents"]:
        assert "provenance" not in doc
        assert "sha256" not in doc
        assert "path" not in doc
        assert "synthetic_demo" not in str(doc)
        assert "synthetic_label" not in doc
        
        # Verify readiness
        assert doc["readiness"] in ("ready", "available", "needs_review", "processing", "attention_needed")
        
        # Verify category
        assert doc["category"] in ("all", "drawings", "maintenance", "inspections", "safety_procedures", "incidents", "communications", "other")
        
        # Date should be a string
        assert isinstance(doc["document_date"], str)

def test_document_detail_redaction():
    # Fetch first document to test detail
    cat_resp = client.get("/api/v1/documents/catalogue")
    docs = cat_resp.json()["documents"]
    if docs:
        doc_id = docs[0]["record_id"]
        response = client.get(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 200
        doc = response.json()
        
        assert "provenance" not in doc
        assert "sha256" not in doc
        assert "path" not in doc
        assert "source" in doc
        assert "provenance" not in doc["source"]

def test_missing_document_detail():
    response = client.get("/api/v1/documents/invalid_missing_id_999")
    assert response.status_code == 404
