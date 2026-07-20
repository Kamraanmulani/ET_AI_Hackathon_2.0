"""
app/adapters/spreadsheet.py — Spreadsheet adapter for ingestion.
"""
import csv
from pathlib import Path
from typing import List, Optional

import openpyxl

from app.adapters.base import DocumentAdapter, ExtractionResult, IngestionWarning
from app.core.identifiers import generate_id
from app.models.document import SourceMetadata
from app.models.evidence import EvidenceRecord, LocationMetadata, ExtractionMetadata
from app.models.entity import EntityRecord, ResolutionMetadata, ExtractorMetadata
from app.models.asset import RelationshipRecord


class SpreadsheetAdapter(DocumentAdapter):
    supported_extensions = {".xlsx", ".xlsm", ".csv", ".tsv"}

    def inspect(self, path: str) -> SourceMetadata:
        raise NotImplementedError("Use registry to construct SourceMetadata.")

    def extract(self, source: SourceMetadata) -> ExtractionResult:
        result = ExtractionResult()
        
        ext = Path(source.relative_path).suffix.lower()
        filepath = Path(source.relative_path)
        if not filepath.exists():
            # For testing/demo fallback to absolute if needed
            filepath = Path(__file__).parent.parent.parent.parent / source.relative_path
            
        if ext in {".xlsx", ".xlsm"}:
            self._extract_excel(filepath, source, result)
        elif ext in {".csv", ".tsv"}:
            self._extract_csv(filepath, source, result)
            
        return result

    def _extract_excel(self, filepath: Path, source: SourceMetadata, result: ExtractionResult):
        # Read-only, data_only=True to evaluate formulas as values
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.rows)
            if not rows:
                continue
                
            headers = [str(cell.value) if cell.value else f"Col{i}" for i, cell in enumerate(rows[0])]
            
            for row_idx, row in enumerate(rows[1:], start=2):
                row_values = [str(cell.value) if cell.value is not None else "" for cell in row]
                if not any(row_values):
                    continue
                
                # Combine headers and values into text
                row_text = " | ".join(f"{h}: {v}" for h, v in zip(headers, row_values) if v)
                
                evidence_id = generate_id(source.sha256, sheet_name, row_idx)
                
                evidence = EvidenceRecord(
                    evidence_id=evidence_id,
                    document_id=source.relative_path, # Ideally source_id
                    source_hash=source.sha256,
                    text=row_text,
                    location=LocationMetadata(kind="sheet", sheet=sheet_name, row=row_idx),
                    extraction=ExtractionMetadata(method="spreadsheet", confidence=1.0),
                    review_state="verified",
                    provenance=source.provenance
                )
                result.evidence.append(evidence)
                
                # Simple extraction for known columns
                self._extract_entities_from_row(headers, row_values, evidence_id, source, result)
                
        wb.close()

    def _extract_csv(self, filepath: Path, source: SourceMetadata, result: ExtractionResult):
        ext = filepath.suffix.lower()
        delimiter = "\t" if ext == ".tsv" else ","
        
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=delimiter)
            try:
                headers = next(reader)
            except StopIteration:
                return
            
            for row_idx, row in enumerate(reader, start=2):
                if not any(row):
                    continue
                    
                row_text = " | ".join(f"{h}: {v}" for h, v in zip(headers, row) if v)
                evidence_id = generate_id(source.sha256, "csv", row_idx)
                
                evidence = EvidenceRecord(
                    evidence_id=evidence_id,
                    document_id=source.relative_path,
                    source_hash=source.sha256,
                    text=row_text,
                    location=LocationMetadata(kind="sheet", sheet="csv", row=row_idx),
                    extraction=ExtractionMetadata(method="spreadsheet", confidence=1.0),
                    review_state="verified",
                    provenance=source.provenance
                )
                result.evidence.append(evidence)
                self._extract_entities_from_row(headers, row, evidence_id, source, result)

    def _extract_entities_from_row(self, headers: List[str], row: List[str], evidence_id: str, source: SourceMetadata, result: ExtractionResult):
        # Minimal extraction matching the fixture for R1
        for header, val in zip(headers, row):
            val = val.strip()
            if not val:
                continue
                
            header_lower = header.lower()
            if "asset tag" in header_lower:
                entity = EntityRecord(
                    entity_id=generate_id(evidence_id, "asset_tag", val),
                    entity_type="asset_tag",
                    value=val,
                    normalized_value=val.upper(),
                    evidence_id=evidence_id,
                    document_id=source.relative_path,
                    resolution=ResolutionMetadata(state="verified", canonical_id=f"asset:{val.upper()}"),
                    extractor=ExtractorMetadata(name="spreadsheet_column", version="1.0", confidence=1.0)
                )
                result.entities.append(entity)
            elif "work order id" in header_lower:
                entity = EntityRecord(
                    entity_id=generate_id(evidence_id, "work_order_id", val),
                    entity_type="work_order_id",
                    value=val,
                    normalized_value=val.upper(),
                    evidence_id=evidence_id,
                    document_id=source.relative_path,
                    resolution=ResolutionMetadata(state="verified"),
                    extractor=ExtractorMetadata(name="spreadsheet_column", version="1.0", confidence=1.0)
                )
                result.entities.append(entity)
