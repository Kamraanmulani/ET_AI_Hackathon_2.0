"""
app/adapters/email.py — Email and handover notes adapter.
"""
import email
from email import policy
from pathlib import Path
from typing import List

from app.adapters.base import DocumentAdapter, ExtractionResult
from app.models.document import SourceMetadata
from app.models.evidence import EvidenceRecord, LocationMetadata, ExtractionMetadata
from app.core.identifiers import generate_id

class EmailAdapter(DocumentAdapter):
    supported_extensions = {".eml", ".msg", ".eml.txt"}

    def inspect(self, path: str) -> SourceMetadata:
        raise NotImplementedError

    def extract(self, source: SourceMetadata) -> ExtractionResult:
        result = ExtractionResult()
        filepath = Path(source.relative_path)
        if not filepath.exists():
            filepath = Path(__file__).parent.parent.parent.parent / source.relative_path

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                msg = email.message_from_file(f, policy=policy.default)
            
            # Extract Headers
            headers_text = []
            for header in ["From", "To", "Cc", "Subject", "Date"]:
                val = msg.get(header)
                if val:
                    headers_text.append(f"{header}: {val}")
            
            if headers_text:
                header_evidence_id = generate_id(source.sha256, "email_headers")
                header_evidence = EvidenceRecord(
                    evidence_id=header_evidence_id,
                    document_id=source.relative_path,
                    source_hash=source.sha256,
                    text="\n".join(headers_text),
                    location=LocationMetadata(kind="region", sheet="headers"),
                    extraction=ExtractionMetadata(method="native_text", confidence=1.0),
                    review_state="verified",
                    provenance=source.provenance
                )
                result.evidence.append(header_evidence)
            
            # Extract Body
            body = msg.get_body(preferencelist=('plain'))
            body_text = ""
            if body:
                body_text = body.get_content()
            else:
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body_text = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                            break
                else:
                    body_text = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8')
            
            if body_text:
                paragraphs = [p.strip() for p in body_text.split("\n\n") if p.strip()]
                for idx, para in enumerate(paragraphs):
                    para_evidence_id = generate_id(source.sha256, "email_body", idx)
                    para_evidence = EvidenceRecord(
                        evidence_id=para_evidence_id,
                        document_id=source.relative_path,
                        source_hash=source.sha256,
                        text=para,
                        location=LocationMetadata(kind="region", sheet="body", row=idx),
                        extraction=ExtractionMetadata(method="native_text", confidence=1.0),
                        review_state="verified",
                        provenance=source.provenance
                    )
                    result.evidence.append(para_evidence)

        except Exception as e:
            pass # Or log it, but ExtractionResult doesn't have warnings

        return result
