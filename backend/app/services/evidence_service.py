"""
services/evidence_service.py — Retrieve evidence for Asset 360.

Assembles verified P&ID relationships, candidate work-order links,
and linked OCR regions for a given asset tag.
All evidence is labelled with its source_id, page, region, and review_state.
Nothing is auto-verified here.
"""
from __future__ import annotations

from datetime import datetime

import structlog

log = structlog.get_logger(__name__)


def get_asset_evidence(db, tag: str) -> dict:
    """
    Return all evidence for an asset tag:
    - Asset canonical record
    - Verified P&ID relationships
    - Candidate work-order links (with source OCR region)
    - Linked OCR candidate fields
    - Audit timeline
    """
    tag_upper = tag.upper()

    # Asset record
    asset = db.assets.find_one({"tag": tag_upper}, {"_id": 0})
    if not asset:
        return None

    # P&ID relationships (verified from registry)
    relationships = list(db.relationships.find(
        {"$or": [{"from_tag": tag_upper}, {"to_tag": tag_upper}]},
        {"_id": 0}
    ))

    # Candidate work-order links mentioning this tag
    links = list(db.work_order_links.find(
        {"asset_tag": tag_upper},
        {"_id": 0}
    ).sort("imported_at", -1))

    # Enrich links with their OCR region text (if available)
    for link in links:
        region_id = link.get("source_region_id")
        if region_id:
            region = db.ocr_regions.find_one(
                {"region_id": region_id},
                {"_id": 0, "text": 1, "confidence": 1, "source_page": 1, "review_state": 1}
            )
            if region:
                link["ocr_region"] = region

    # Candidate work-order fields mentioning this tag (via field value matching)
    fields = list(db.work_order_fields.find(
        {"value": {"$regex": tag_upper, "$options": "i"}},
        {"_id": 0}
    ).limit(20))

    # Related OCR regions containing the tag text
    ocr_regions = list(db.ocr_regions.find(
        {"text": {"$regex": tag_upper, "$options": "i"}},
        {"_id": 0}
    ).limit(20))

    # Audit events for this asset
    audit = list(db.audit_events.find(
        {"entity_id": tag_upper},
        {"_id": 0}
    ).sort("timestamp", -1).limit(50))

    return {
        "asset": asset,
        "relationships": relationships,
        "work_order_links": links,
        "candidate_fields": fields,
        "ocr_regions": ocr_regions,
        "audit_events": audit,
        "evidence_summary": {
            "relationship_count": len(relationships),
            "link_count": len(links),
            "verified_links": sum(1 for l in links if l.get("review_state") == "verified"),
            "pending_links": sum(1 for l in links if l.get("review_state") == "pending_review"),
            "region_count": len(ocr_regions),
        }
    }


def get_asset_audit(db, tag: str) -> list[dict]:
    """Return audit timeline for a tag, newest first."""
    return list(db.audit_events.find(
        {"entity_id": tag.upper()},
        {"_id": 0}
    ).sort("timestamp", -1))


def get_asset_evidence_graph(db, tag: str) -> dict:
    """Return the asset-centric evidence graph for a tag (nodes and edges)."""
    tag_upper = tag.upper()
    nodes = []
    edges = []

    # 1. Central Asset Node
    asset = db.assets.find_one({"tag": tag_upper}, {"_id": 0})
    if not asset:
        return {"nodes": [], "edges": []}
    
    nodes.append({
        "id": tag_upper,
        "type": "asset",
        "label": tag_upper,
        "provenance": "original",
        "review_state": asset.get("state", "verified"),
        "source_id": asset.get("source_id", ""),
        "open_target": f"/assets/{tag_upper}"
    })

    # 2. P&ID Relationships (1-hop)
    rels = list(db.relationships.find({"$or": [{"from_tag": tag_upper}, {"to_tag": tag_upper}]}, {"_id": 0}))
    for r in rels:
        other_tag = r["to_tag"] if r["from_tag"] == tag_upper else r["from_tag"]
        other_asset = db.assets.find_one({"tag": other_tag}, {"_id": 0})
        if other_asset and not any(n["id"] == other_tag for n in nodes):
            nodes.append({
                "id": other_tag,
                "type": "asset",
                "label": other_tag,
                "provenance": "original",
                "review_state": other_asset.get("state", "verified"),
                "source_id": other_asset.get("source_id", ""),
                "open_target": f"/assets/{other_tag}"
            })
        
        edges.append({
            "id": f"rel_{r['from_tag']}_{r['to_tag']}",
            "source": r["from_tag"],
            "target": r["to_tag"],
            "relationship_type": r.get("relationship_type", "connected"),
            "evidence_basis": "Verified P&ID relationship",
            "state": "verified",
            "source_citation": r.get("source_id", "")
        })

    # 3. Work Order / OCR Links
    links = list(db.work_order_links.find({"asset_tag": tag_upper}, {"_id": 0}))
    for i, link in enumerate(links):
        doc_id = f"doc_{link.get('source_id')}_{i}"
        
        # Determine provenance
        prov = "derived_ocr"
        if "synthetic" in str(link.get("source_id", "")).lower() or "demo" in str(link.get("source_id", "")).lower():
            prov = "synthetic_demo"

        nodes.append({
            "id": doc_id,
            "type": "document",
            "label": f"{link.get('source_id', 'Unknown')} p.{link.get('source_page', '1')}",
            "provenance": prov,
            "review_state": link.get("review_state", "pending_review"),
            "source_id": link.get("source_id", ""),
            "open_target": f"/catalogue?source={link.get('source_id')}" + (f"&page={link.get('source_page')}" if link.get("source_page") else "")
        })
        
        is_verified = link.get("review_state") == "verified"
        basis = "Reviewer-approved link" if is_verified else "AI proposed OCR tag match"
        if prov == "synthetic_demo":
            basis = "Synthetic-demo document reference"

        edges.append({
            "id": f"link_{tag_upper}_{doc_id}",
            "source": tag_upper,
            "target": doc_id,
            "relationship_type": "mentions",
            "evidence_basis": basis,
            "state": link.get("review_state", "pending_review"),
            "source_citation": link.get("source_id", "")
        })

    return {"nodes": nodes, "edges": edges}
