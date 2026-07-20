"""
app/services/extractor.py — Deterministic entity extraction.
"""
import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

from app.models.entity import EntityRecord, ResolutionMetadata, ExtractorMetadata

ALIASES_PATH = Path(__file__).parent.parent.parent.parent / "Data" / "config" / "asset_aliases.json"

class EntityExtractorService:
    def __init__(self):
        self.aliases = {}
        self._load_aliases()
        
    def _load_aliases(self):
        if ALIASES_PATH.exists():
            data = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
            for item in data.get("aliases", []):
                self.aliases[item["alias"].upper()] = item["canonical_tag"]

    def extract_entities(self, text: str, evidence_id: str, document_id: str) -> List[EntityRecord]:
        entities = []
        
        # Simple extraction for demo: tags like ETP-601 or aliases
        # This is a basic deterministic extractor as requested by R1.3
        
        # 1. Asset Tags
        tag_pattern = re.compile(r'\b([A-Z]{1,4}-\d{3})\b')
        for match in tag_pattern.finditer(text):
            val = match.group(1)
            norm = val.upper()
            
            # Resolve against aliases
            state = "verified"
            canonical_id = f"asset:{norm}"
            
            if norm in self.aliases:
                canonical_id = f"asset:{self.aliases[norm]}"
            else:
                # In a real app we'd verify against registry, if not found, it's proposed
                state = "ai_proposed" # For R1, assume not in registry unless alias match or explicit
                canonical_id = None
                
            entities.append(EntityRecord(
                entity_id=f"{evidence_id}::asset_tag::{norm}",
                entity_type="asset_tag",
                value=val,
                normalized_value=norm,
                evidence_id=evidence_id,
                document_id=document_id,
                resolution=ResolutionMetadata(state=state, canonical_id=canonical_id),
                extractor=ExtractorMetadata(name="regex_tag_extractor", version="1.0", confidence=1.0)
            ))
            
        return entities
