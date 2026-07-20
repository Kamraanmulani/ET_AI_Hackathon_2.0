"""
app/services/extractor.py — Deterministic entity extraction.
"""
import json
import re
from pathlib import Path
from typing import List

from app.models.entity import EntityRecord, ResolutionMetadata, ExtractorMetadata
from app.core.identifiers import generate_id

DATA_DIR = Path(__file__).parent.parent.parent.parent / "Data"
ALIASES_PATH = DATA_DIR / "config" / "asset_aliases.json"
ASSET_REGISTRY_PATH = DATA_DIR / "manifests" / "pid_asset_registry.json"
MANIFEST_PATH = DATA_DIR / "manifests" / "active_document_manifest.json"

class EntityExtractorService:
    def __init__(self):
        self.aliases = {}
        self.valid_assets = set()
        self.valid_documents = set()
        self.valid_drawings = set()
        self.valid_work_orders = set()
        
        self._load_config()
        
    def _load_config(self):
        if ALIASES_PATH.exists():
            data = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
            for item in data.get("aliases", []):
                self.aliases[item["alias"].upper()] = item["canonical_tag"]

        if ASSET_REGISTRY_PATH.exists():
            data = json.loads(ASSET_REGISTRY_PATH.read_text(encoding="utf-8"))
            for a in data.get("assets", []):
                self.valid_assets.add(a["tag"])

        if MANIFEST_PATH.exists():
            data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            for s in data.get("sources", []):
                self.valid_documents.add(s["source_id"])
                if s.get("drawing_id"):
                    self.valid_drawings.add(s["drawing_id"])
                # we don't have a strict work order manifest for the demo corpus
                # but we'll accept known patterns

    def extract_entities(self, text: str, evidence_id: str, document_id: str) -> List[EntityRecord]:
        entities = []

        # 1. Asset Tags (e.g. ETP-601, P-601, AIT-601 or without dash)
        tag_pattern = re.compile(r'\b([A-Za-z]{1,4})-?(\d{3,4})\b')
        for match in tag_pattern.finditer(text):
            prefix, num = match.groups()
            norm = f"{prefix.upper()}-{num}"
            val = match.group(0)
            
            # Resolve
            state = "ai_proposed"
            canonical_id = None
            
            # Check direct match
            if norm in self.valid_assets:
                state = "verified"
                canonical_id = f"asset:{norm}"
            # Check aliases
            elif val.upper() in self.aliases:
                state = "verified"
                canonical_id = f"asset:{self.aliases[val.upper()]}"
            
            entities.append(EntityRecord(
                entity_id=generate_id(evidence_id, "asset_tag", norm),
                entity_type="asset_tag",
                value=val,
                normalized_value=norm,
                evidence_id=evidence_id,
                document_id=document_id,
                resolution=ResolutionMetadata(state=state, canonical_id=canonical_id),
                extractor=ExtractorMetadata(name="regex_tag", version="1.1", confidence=1.0)
            ))

        # 2. Document IDs (e.g. INS-PRG-ETP601-001)
        doc_pattern = re.compile(r'\b(?:INS|SOP|NMR|EMAIL)-PRG-[A-Z0-9-]+(?:-00\d)?\b')
        for match in doc_pattern.finditer(text):
            val = match.group(0)
            norm = val.upper()
            state = "verified" if norm in self.valid_documents else "ai_proposed"
            
            entities.append(EntityRecord(
                entity_id=generate_id(evidence_id, "document_id", norm),
                entity_type="document_id",
                value=val,
                normalized_value=norm,
                evidence_id=evidence_id,
                document_id=document_id,
                resolution=ResolutionMetadata(state=state, canonical_id=f"document:{norm}" if state=="verified" else None),
                extractor=ExtractorMetadata(name="regex_doc", version="1.0", confidence=1.0)
            ))

        # 3. Work Order IDs (e.g. WO-2026-...)
        wo_pattern = re.compile(r'\bWO-\d{4}-\d+\b', re.IGNORECASE)
        for match in wo_pattern.finditer(text):
            val = match.group(0)
            norm = val.upper()
            entities.append(EntityRecord(
                entity_id=generate_id(evidence_id, "work_order_id", norm),
                entity_type="work_order_id",
                value=val,
                normalized_value=norm,
                evidence_id=evidence_id,
                document_id=document_id,
                resolution=ResolutionMetadata(state="ai_proposed", canonical_id=None),
                extractor=ExtractorMetadata(name="regex_wo", version="1.0", confidence=1.0)
            ))

        # 4. Dates (YYYY-MM-DD or simple variations)
        date_pattern = re.compile(r'\b(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b')
        for match in date_pattern.finditer(text):
            val = match.group(0)
            norm = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
            entities.append(EntityRecord(
                entity_id=generate_id(evidence_id, "date", norm),
                entity_type="date",
                value=val,
                normalized_value=norm,
                evidence_id=evidence_id,
                document_id=document_id,
                resolution=ResolutionMetadata(state="verified"),
                extractor=ExtractorMetadata(name="regex_date", version="1.0", confidence=1.0)
            ))

        # 5. Regulatory references (e.g. OISD-116, PESO)
        reg_pattern = re.compile(r'\b(?:OISD-\d+|PESO|Factories Act)\b', re.IGNORECASE)
        for match in reg_pattern.finditer(text):
            val = match.group(0)
            norm = val.upper()
            entities.append(EntityRecord(
                entity_id=generate_id(evidence_id, "regulatory_reference", norm),
                entity_type="regulatory_reference",
                value=val,
                normalized_value=norm,
                evidence_id=evidence_id,
                document_id=document_id,
                resolution=ResolutionMetadata(state="verified", canonical_id=f"reg:{norm}"),
                extractor=ExtractorMetadata(name="regex_reg", version="1.0", confidence=1.0)
            ))
            
        # Deduplicate
        seen = set()
        deduped = []
        for ent in entities:
            if ent.entity_id not in seen:
                seen.add(ent.entity_id)
                deduped.append(ent)

        return deduped
