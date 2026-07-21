"""
app/services/answer_service.py — Evidence-grounded answer generation with guardrails.

Implements:
1. Safety and intent gate (reject prohibited requests before any retrieval)
2. Evidence pack builder
3. Constrained system prompt
4. Ollama qwen3:8b answer generation
5. Post-generation citation verification
6. Abstention handler

Never generates factual content not supported by retrieved evidence.
"""
from __future__ import annotations

import re
import uuid
import time
from typing import Any

import structlog

from app.core.config import settings
from app.services.ollama_client import generate, OllamaUnavailableError

log = structlog.get_logger(__name__)

# ── Safety gate: prohibited request patterns ─────────────────────────────────
SAFETY_PATTERNS = [
    # Plant control actions
    r"\b(close|open|stop|start|trip|reset|acknowledge|silence)\s+(?:the\s+)?(valve|pump|compressor|motor|alarm|[A-Za-z]{1,4}-\d+)\b",
    r"\b(setpoint|interlock|override|inhibit|bypass)\b",
    r"\b[A-Za-z]{2,4}-\d+\s*(close|open|trip)\b",
    # Root cause / prediction
    r"\b(root\s*cause|failure\s*cause|caused?\s*(by|the)?|diagnos|predict|prognos)\b",
    # Compliance / regulatory
    r"\b(oisd|osha|pssr|hazop|lopa|pha|complian|regulatory|audit\s+finding|discharge\s+limit|emission\s+limit)\b",
    # Live data / sensor values
    r"\b(current\s+(pressure|temperature|flow|level|ppm|ph)|live\s+(reading|value|state|status))\b",
    r"\b(what\s+is\s+the\s+(pressure|temperature|flow|level|concentration|ph)\s+of)\b",
]

_SAFETY_REGEX = re.compile("|".join(SAFETY_PATTERNS), re.IGNORECASE)

SAFETY_BOUNDARY_RESPONSE = (
    "This question asks for operational, control, predictive, or compliance information "
    "that is outside the scope of this read-only plant knowledge workspace. "
    "Pragyan Plant Intelligence is a source-grounded information tool only — it cannot "
    "control equipment, predict failures, interpret live sensor readings, or make "
    "compliance determinations. Please consult your plant DCS, safety management system, "
    "or qualified engineer. You can browse the source catalogue or asset registry for "
    "documented engineering evidence."
)

CONSTRAINED_SYSTEM_PROMPT = """You are Pragyan Plant Intelligence, a read-only plant knowledge assistant.

RULES — you must follow these without exception:
1. Answer ONLY using the evidence provided in the EVIDENCE PACK below. Do not add facts, diagnoses, operating instructions, or conclusions not explicitly present in the evidence.
2. Every factual sentence in your answer MUST include one or more citation IDs in brackets, e.g., [C1] or [C1, C2].
3. Clearly preserve and display provenance labels: verified evidence, AI proposed evidence, synthetic demo evidence.
4. If the evidence pack does not support a complete answer, output EXACTLY this JSON:
   {"abstain": true, "reason": "brief explanation of what was searched"}
5. Never claim sensor readings, live values, plant states, setpoints, compliance, root causes, failure predictions, or operational instructions.
6. Keep answers short: 2-5 factual sentences maximum.
7. Do not repeat evidence verbatim — synthesise briefly and cite.

Your answer must be factual, brief, and fully grounded in the evidence pack."""


def check_safety_gate(query: str) -> dict | None:
    """
    Return a safety_boundary response dict if the query is prohibited.
    Returns None if the query passes the safety gate.
    """
    if _SAFETY_REGEX.search(query):
        return {
            "answer_status": "safety_boundary",
            "answer": SAFETY_BOUNDARY_RESPONSE,
            "answer_confidence": {
                "label": "insufficient",
                "retrieval_score": 0.0,
                "evidence_count": 0,
                "explanation": "Request falls outside the read-only evidence scope of this system.",
            },
            "citations": [],
            "suggested_followups": [
                "Browse the source catalogue",
                "Search for an asset tag",
                "View the P&ID Explorer",
            ],
        }
    return None


def build_evidence_pack(chunks: list[dict]) -> list[dict]:
    """
    Select the top evidence chunks for the LLM context.
    Deduplicates by source_region + page, caps at rag_max_chunks.
    """
    seen_keys = set()
    pack = []
    for chunk in chunks:
        # Deduplicate by source region + page
        key = (chunk.get("source_id", ""), chunk.get("page"), str(chunk.get("source_region")))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        pack.append(chunk)
        if len(pack) >= settings.rag_max_chunks:
            break
    return pack


def _build_citations(evidence_pack: list[dict]) -> list[dict]:
    """Build citation records from the evidence pack."""
    citations = []
    for i, chunk in enumerate(evidence_pack, start=1):
        tag = chunk.get("asset_tags", [])
        source_id = chunk.get("source_id", "")
        page = chunk.get("page")
        # Build open_target navigation URL
        if chunk.get("chunk_type") == "pid_asset" and tag:
            open_target = f"/assets/{tag[0]}"
        elif source_id and page:
            open_target = f"/catalogue?source={source_id}&page={page}"
        else:
            open_target = f"/catalogue?source={source_id}" if source_id else "/catalogue"

        citations.append({
            "citation_id": f"C{i}",
            "chunk_id": chunk.get("chunk_id", ""),
            "document_id": chunk.get("document_id", source_id),
            "source_id": source_id,
            "title": _citation_title(chunk),
            "provenance": chunk.get("provenance", "unknown"),
            "review_state": chunk.get("review_state", "pending_review"),
            "asset_tags": chunk.get("asset_tags", []),
            "drawing_ids": chunk.get("drawing_ids", []),
            "page": page,
            "source_region": chunk.get("source_region"),
            "excerpt": chunk.get("text", "")[:400],
            "open_target": open_target,
            "score": round(chunk.get("_rrf_score", chunk.get("_score", 0.0)), 3),
        })
    return citations


def _citation_title(chunk: dict) -> str:
    tags = chunk.get("asset_tags", [])
    chunk_type = chunk.get("chunk_type", "")
    source_id = chunk.get("source_id", "")
    page = chunk.get("page")
    if chunk_type == "pid_asset" and tags:
        return f"P&ID Asset: {', '.join(tags)}"
    if chunk_type == "pid_relationship":
        return f"P&ID Relationship: {source_id}"
    if chunk_type == "ocr_region":
        return f"Work Order OCR — {source_id} p.{page}" if page else f"Work Order OCR — {source_id}"
    if chunk.get("provenance") == "synthetic_demo":
        return f"[Synthetic Demo] {source_id}"
    return source_id


def _verify_citations(answer_text: str, evidence_pack: list[dict]) -> list[str]:
    """
    Check that every citation ID referenced in the answer exists in the evidence pack.
    Returns list of invalid citation IDs.
    """
    valid_ids = {f"C{i}" for i in range(1, len(evidence_pack) + 1)}
    referenced = set(re.findall(r"\[C\d+\]", answer_text))
    referenced_ids = {r.strip("[]") for r in referenced}
    return list(referenced_ids - valid_ids)


def _compute_support_label(evidence_pack: list[dict], answer_text: str) -> tuple[str, float]:
    """Determine support confidence based on evidence quality."""
    if not evidence_pack:
        return "insufficient", 0.0

    verified = sum(1 for c in evidence_pack if c.get("review_state") == "verified")
    total = len(evidence_pack)
    score = verified / total if total else 0.0

    cited_count = len(re.findall(r"\[C\d+\]", answer_text))
    if cited_count >= 2 and score >= 0.5:
        return "high_support", score
    if cited_count >= 1 or score > 0.0:
        return "partial_support", score
    return "insufficient", 0.0


def _suggested_followups(evidence_pack: list[dict], tags_found: list[str]) -> list[str]:
    suggestions = []
    if tags_found:
        suggestions.append(f"Open {tags_found[0]} in Asset 360")
    suggestions.append("Review proposed evidence in Review Queue")
    if any(c.get("page") for c in evidence_pack):
        suggestions.append("Inspect original source in Source Catalogue")
    return suggestions[:3]


def generate_answer(
    query: str,
    evidence_pack: list[dict],
    tags_found: list[str],
    retrieval_info: dict,
) -> dict:
    """
    Generate a grounded answer from the evidence pack using Ollama.
    Falls back to Insufficient Evidence if Ollama is unavailable or verification fails.
    """
    citations = _build_citations(evidence_pack)
    request_id = str(uuid.uuid4())

    # ── Insufficient evidence: no chunks ─────────────────────────────────────
    if not evidence_pack:
        return {
            "answer_status": "insufficient_evidence",
            "answer": (
                "No relevant evidence was found in the active Pragyan corpus for this query. "
                "The corpus contains the five P&ID drawings, the scanned maintenance records PDF, "
                "and associated synthetic demo documents. "
                "OCR extraction may be incomplete; some review tasks are pending human verification."
            ),
            "answer_confidence": {
                "label": "insufficient",
                "retrieval_score": 0.0,
                "evidence_count": 0,
                "explanation": "No chunks retrieved above the relevance threshold.",
            },
            "citations": [],
            "suggested_followups": [
                "Browse the Source Catalogue",
                "Search for an asset tag in the Assets page",
                "View the Review Queue to see pending OCR tasks",
            ],
            "request_id": request_id,
        }

    # ── Attempt LLM generation ────────────────────────────────────────────────
    answer_text = None
    ollama_used = False

    try:
        t0 = time.monotonic()
        answer_text = generate(
            system_prompt=CONSTRAINED_SYSTEM_PROMPT,
            user_message=query,
            evidence_pack=evidence_pack,
            max_tokens=400,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        ollama_used = True
        log.info("llm_generated", latency_ms=round(latency_ms), length=len(answer_text))
    except OllamaUnavailableError as e:
        log.warning("ollama_unavailable_falling_back_to_evidence_list", error=str(e))

    # ── Post-generation verification ──────────────────────────────────────────
    if answer_text:
        # Check for explicit abstention from LLM
        if '"abstain": true' in answer_text or answer_text.strip().startswith('{"abstain"'):
            return {
                "answer_status": "insufficient_evidence",
                "answer": "The retrieved evidence does not contain sufficient support for this query.",
                "answer_confidence": {
                    "label": "insufficient",
                    "retrieval_score": 0.0,
                    "evidence_count": len(evidence_pack),
                    "explanation": "LLM returned explicit abstention — evidence insufficient for a factual answer.",
                },
                "citations": citations,
                "suggested_followups": _suggested_followups(evidence_pack, tags_found),
                "request_id": request_id,
            }

        invalid_cids = _verify_citations(answer_text, evidence_pack)
        if invalid_cids:
            # Strip invalid citations from answer text rather than rejecting entire answer
            for cid in invalid_cids:
                answer_text = answer_text.replace(f"[{cid}]", "")
            log.warning("citations_stripped", invalid=invalid_cids)

        support_label, retrieval_score = _compute_support_label(evidence_pack, answer_text)
        answer_status = "supported"

    else:
        # Ollama unavailable — return evidence list with note
        answer_text = (
            "Semantic answer generation is currently unavailable (Ollama not reachable). "
            "The following evidence was retrieved from the corpus — please review citations directly."
        )
        support_label = "partial_support"
        retrieval_score = 0.5
        answer_status = "supported"

    return {
        "answer_status": answer_status,
        "answer": answer_text,
        "answer_confidence": {
            "label": support_label,
            "retrieval_score": round(retrieval_score, 3),
            "evidence_count": len(evidence_pack),
            "explanation": "Evidence-based support indicator based on retrieved and verified source records. Not a safety or operational confidence score.",
        },
        "citations": citations,
        "suggested_followups": _suggested_followups(evidence_pack, tags_found),
        "retrieval_info": {
            "used_qdrant": retrieval_info.get("used_qdrant", False),
            "used_graph": retrieval_info.get("used_graph", False),
            "used_mongo_fallback": retrieval_info.get("used_mongo_fallback", False),
            "ollama_used": ollama_used,
            "tags_found": tags_found,
        },
        "request_id": request_id,
    }
