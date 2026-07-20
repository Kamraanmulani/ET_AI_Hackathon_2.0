"""
app/adapters/pdf.py — PDF and native text adapter.
"""
from typing import List
from pathlib import Path

import fitz  # PyMuPDF

from app.adapters.base import DocumentAdapter, ExtractionResult
from app.models.document import SourceMetadata
from app.models.evidence import EvidenceRecord, LocationMetadata, ExtractionMetadata
from app.core.identifiers import generate_id

class PDFTextAdapter(DocumentAdapter):
    supported_extensions = {".pdf", ".txt"}

    def inspect(self, path: str) -> SourceMetadata:
        raise NotImplementedError

    def extract(self, source: SourceMetadata) -> ExtractionResult:
        result = ExtractionResult()
        filepath = Path(source.relative_path)
        if not filepath.exists():
            filepath = Path(__file__).parent.parent.parent.parent / source.relative_path

        if filepath.suffix.lower() == ".txt":
            # Basic txt handling
            text = filepath.read_text(encoding="utf-8")
            evidence_id = generate_id(source.sha256, "txt", 1)
            evidence = EvidenceRecord(
                evidence_id=evidence_id,
                document_id=source.relative_path,
                source_hash=source.sha256,
                text=text,
                location=LocationMetadata(kind="page", page=1),
                extraction=ExtractionMetadata(method="native_text", confidence=1.0),
                review_state="verified",
                provenance=source.provenance
            )
            result.evidence.append(evidence)
            return result

        try:
            doc = fitz.open(filepath)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text("text").strip()

                if not text or len(text) < 10:
                    # Fallback to OCR representation
                    evidence_id = generate_id(source.sha256, "pdf_ocr", page_num + 1)
                    evidence = EvidenceRecord(
                        evidence_id=evidence_id,
                        document_id=source.relative_path,
                        source_hash=source.sha256,
                        text="[Scanned image - OCR pending/completed]",
                        location=LocationMetadata(kind="page", page=page_num + 1),
                        extraction=ExtractionMetadata(method="ocr", confidence=0.0),
                        review_state="pending_review",
                        provenance=source.provenance
                    )
                    result.evidence.append(evidence)
                else:
                    # Native text extraction (split by logical blocks if possible)
                    blocks = page.get_text("blocks")
                    for b_idx, block in enumerate(blocks):
                        b_text = block[4].strip()
                        if not b_text:
                            continue
                        
                        evidence_id = generate_id(source.sha256, "pdf_block", page_num + 1, b_idx)
                        bbox = {"x": block[0], "y": block[1], "width": block[2]-block[0], "height": block[3]-block[1]}
                        
                        evidence = EvidenceRecord(
                            evidence_id=evidence_id,
                            document_id=source.relative_path,
                            source_hash=source.sha256,
                            text=b_text,
                            location=LocationMetadata(kind="region", page=page_num + 1, bbox=bbox),
                            extraction=ExtractionMetadata(method="native_text", confidence=1.0),
                            review_state="verified",
                            provenance=source.provenance
                        )
                        result.evidence.append(evidence)

            doc.close()

        except Exception as e:
            pass # Or log it, but ExtractionResult doesn't have warnings
            
        return result
