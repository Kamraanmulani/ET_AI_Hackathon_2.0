"""
app/models/copilot.py — Conversation, message, and feedback models for the RAG copilot.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ConversationRecord:
    """A copilot conversation session."""
    conversation_id: str
    title: str = ""
    selected_asset_tag: str | None = None
    created_at: str = ""
    updated_at: str = ""
    message_count: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "conversation_id": self.conversation_id,
            "title": self.title,
            "selected_asset_tag": self.selected_asset_tag,
            "created_at": self.created_at or now,
            "updated_at": self.updated_at or now,
            "message_count": self.message_count,
            "metadata": self.metadata,
        }


@dataclass
class CitationRecord:
    """A single evidence citation attached to a copilot answer."""
    citation_id: str                         # e.g. "C1", "C2"
    chunk_id: str
    document_id: str
    source_id: str
    title: str
    provenance: str                          # original | synthetic_demo | derived_ocr
    review_state: str                        # verified | AI proposed | pending_review
    asset_tags: list[str] = field(default_factory=list)
    drawing_ids: list[str] = field(default_factory=list)
    page: int | None = None
    source_region: dict | None = None
    excerpt: str = ""
    open_target: str = ""                    # URL to navigate to in the frontend
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "citation_id": self.citation_id,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "title": self.title,
            "provenance": self.provenance,
            "review_state": self.review_state,
            "asset_tags": self.asset_tags,
            "drawing_ids": self.drawing_ids,
            "page": self.page,
            "source_region": self.source_region,
            "excerpt": self.excerpt,
            "open_target": self.open_target,
            "score": self.score,
        }


@dataclass
class MessageRecord:
    """One turn in a conversation (user message + assistant answer)."""
    message_id: str
    conversation_id: str
    role: str                                # user | assistant
    content: str
    # Answer-specific fields (populated for role=assistant)
    answer_status: str = ""                  # supported | insufficient_evidence | safety_boundary
    support_label: str = ""                  # high_support | partial_support | insufficient
    retrieval_score: float = 0.0
    evidence_count: int = 0
    citations: list[dict] = field(default_factory=list)
    suggested_followups: list[str] = field(default_factory=list)
    retrieval_explanation: str = ""
    graph_path_used: bool = False
    qdrant_used: bool = False
    mongo_fallback: bool = False
    request_id: str = ""
    latency_ms: float = 0.0
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "answer_status": self.answer_status,
            "support_label": self.support_label,
            "retrieval_score": self.retrieval_score,
            "evidence_count": self.evidence_count,
            "citations": self.citations,
            "suggested_followups": self.suggested_followups,
            "retrieval_explanation": self.retrieval_explanation,
            "graph_path_used": self.graph_path_used,
            "qdrant_used": self.qdrant_used,
            "mongo_fallback": self.mongo_fallback,
            "request_id": self.request_id,
            "latency_ms": self.latency_ms,
            "created_at": self.created_at or datetime.now(timezone.utc).isoformat(),
        }


@dataclass
class FeedbackRecord:
    """User feedback on a copilot answer."""
    feedback_id: str
    conversation_id: str
    message_id: str
    rating: str                              # helpful | not_helpful
    issue: str | None = None                 # citation_wrong | missing_evidence | incorrect_answer | other
    comment: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "feedback_id": self.feedback_id,
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "rating": self.rating,
            "issue": self.issue,
            "comment": self.comment,
            "created_at": self.created_at or datetime.now(timezone.utc).isoformat(),
        }
