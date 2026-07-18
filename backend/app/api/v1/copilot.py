"""
api/v1/copilot.py — Expert Knowledge Copilot API endpoints.

Endpoints (all under /api/v1):
  POST /copilot/conversations                  — create a new conversation
  POST /copilot/conversations/{id}/messages    — ask a question
  GET  /copilot/conversations/{id}             — retrieve conversation history
  POST /copilot/feedback                       — submit feedback on an answer

The copilot: retrieves evidence → verifies citations → generates or abstains.
Never modifies source, review state, or audit records.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.config import settings
from app.services import answer_service, retrieval_service
from app.services import qdrant_service, neo4j_service
from app.services.ollama_client import health_check as ollama_health

log = structlog.get_logger(__name__)
router = APIRouter(tags=["copilot"])


# ── Request / Response models ────────────────────────────────────────────────

class CreateConversationRequest(BaseModel):
    title: str = Field(default="", max_length=200)
    selected_asset_tag: str | None = Field(default=None)
    metadata: dict = Field(default_factory=dict)


class MessageFilters(BaseModel):
    include_ai_proposed: bool = True
    include_synthetic_demo: bool = True
    document_types: list[str] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=2, max_length=2000)
    selected_asset_tag: str | None = Field(default=None)
    filters: MessageFilters = Field(default_factory=MessageFilters)


class FeedbackRequest(BaseModel):
    conversation_id: str
    message_id: str
    rating: str = Field(..., pattern="^(helpful|not_helpful)$")
    issue: str | None = Field(default=None)
    comment: str = Field(default="", max_length=1000)


# ── POST /copilot/conversations ──────────────────────────────────────────────

@router.post("/copilot/conversations")
def create_conversation(body: CreateConversationRequest):
    """Create a new copilot conversation session."""
    db = get_db()
    conversation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "conversation_id": conversation_id,
        "title": body.title or "New conversation",
        "selected_asset_tag": body.selected_asset_tag,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
        "metadata": body.metadata,
    }
    db.conversations.insert_one(record)
    return {
        "conversation_id": conversation_id,
        "title": record["title"],
        "selected_asset_tag": body.selected_asset_tag,
        "created_at": now,
    }


# ── POST /copilot/conversations/{id}/messages ────────────────────────────────

@router.post("/copilot/conversations/{conversation_id}/messages")
def send_message(conversation_id: str, body: SendMessageRequest):
    """
    Ask a plant knowledge question in the context of a conversation.
    Runs: safety gate → retrieval → answer generation → citation verification.
    """
    db = get_db()
    t_start = time.monotonic()

    # Verify conversation exists
    convo = db.conversations.find_one({"conversation_id": conversation_id})
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Store user message
    user_msg_id = str(uuid.uuid4())
    user_msg = {
        "message_id": user_msg_id,
        "conversation_id": conversation_id,
        "role": "user",
        "content": body.message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.messages.insert_one(user_msg)

    # ── Safety gate ──────────────────────────────────────────────────────────
    safety_response = answer_service.check_safety_gate(body.message)
    if safety_response:
        asst_msg_id = str(uuid.uuid4())
        latency_ms = (time.monotonic() - t_start) * 1000
        asst_msg = {
            "message_id": asst_msg_id,
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": safety_response["answer"],
            "answer_status": "safety_boundary",
            "latency_ms": round(latency_ms),
            "created_at": datetime.now(timezone.utc).isoformat(),
            **{k: v for k, v in safety_response.items() if k != "answer"},
        }
        db.messages.insert_one(asst_msg)
        db.conversations.update_one(
            {"conversation_id": conversation_id},
            {"$inc": {"message_count": 2}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {**safety_response, "content": safety_response["answer"], "message_id": asst_msg_id, "conversation_id": conversation_id}

    # ── Retrieval ────────────────────────────────────────────────────────────
    retrieval_result = retrieval_service.retrieve(
        query=body.message,
        selected_asset_tag=body.selected_asset_tag or convo.get("selected_asset_tag"),
        include_ai_proposed=body.filters.include_ai_proposed,
        include_synthetic_demo=body.filters.include_synthetic_demo,
        db=db,
    )

    chunks = retrieval_result["chunks"]
    tags_found = retrieval_result["tags_found"]
    evidence_pack = answer_service.build_evidence_pack(chunks)

    # ── Answer generation ────────────────────────────────────────────────────
    answer = answer_service.generate_answer(
        query=body.message,
        evidence_pack=evidence_pack,
        tags_found=tags_found,
        retrieval_info=retrieval_result,
    )

    latency_ms = (time.monotonic() - t_start) * 1000

    # Store assistant message
    asst_msg_id = str(uuid.uuid4())
    asst_msg = {
        "message_id": asst_msg_id,
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": answer["answer"],
        "answer_status": answer["answer_status"],
        "support_label": answer["answer_confidence"]["label"],
        "retrieval_score": answer["answer_confidence"]["retrieval_score"],
        "evidence_count": answer["answer_confidence"]["evidence_count"],
        "citations": answer["citations"],
        "suggested_followups": answer["suggested_followups"],
        "retrieval_info": answer.get("retrieval_info", {}),
        "request_id": answer.get("request_id", ""),
        "latency_ms": round(latency_ms),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.messages.insert_one(asst_msg)
    db.conversations.update_one(
        {"conversation_id": conversation_id},
        {"$inc": {"message_count": 2}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    # Persist retrieval metric
    db.retrieval_metrics.insert_one({
        "conversation_id": conversation_id,
        "message_id": asst_msg_id,
        "query": body.message,
        "asset_tag": body.selected_asset_tag,
        "mongo_hits": len(chunks),
        "qdrant_used": retrieval_result.get("used_qdrant", False),
        "graph_used": retrieval_result.get("used_graph", False),
        "mongo_fallback": retrieval_result.get("used_mongo_fallback", False),
        "final_chunks": len(evidence_pack),
        "answer_status": answer["answer_status"],
        "support_label": answer["answer_confidence"]["label"],
        "latency_ms": round(latency_ms),
        "latency_breakdown": retrieval_result.get("latency", {}),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        **answer,
        "content": answer["answer"],
        "message_id": asst_msg_id,
        "conversation_id": conversation_id,
        "latency_ms": round(latency_ms),
    }


# ── GET /copilot/conversations/{id} ─────────────────────────────────────────

@router.get("/copilot/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    """Return conversation metadata and all message turns."""
    db = get_db()
    convo = db.conversations.find_one({"conversation_id": conversation_id}, {"_id": 0})
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = list(db.messages.find(
        {"conversation_id": conversation_id},
        {"_id": 0},
    ).sort("created_at", 1))
    return {**convo, "messages": messages}


# ── POST /copilot/feedback ────────────────────────────────────────────────────

@router.post("/copilot/feedback")
def submit_feedback(body: FeedbackRequest):
    """Record user feedback on a copilot answer. Does not modify source or review state."""
    db = get_db()
    # Validate message exists
    msg = db.messages.find_one({"message_id": body.message_id, "conversation_id": body.conversation_id})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    feedback_id = str(uuid.uuid4())
    record = {
        "feedback_id": feedback_id,
        "conversation_id": body.conversation_id,
        "message_id": body.message_id,
        "rating": body.rating,
        "issue": body.issue,
        "comment": body.comment,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.feedback.insert_one(record)
    return {"feedback_id": feedback_id, "status": "recorded"}


# ── GET /copilot/status ────────────────────────────────────────────────────────

@router.get("/copilot/status")
def copilot_status():
    """Return health status of all RAG components."""
    db = get_db()
    chunk_count = db.document_chunks.count_documents({})
    indexed_count = db.document_chunks.count_documents({"indexed_at": {"$ne": None}})

    return {
        "ollama": {
            "available": ollama_health(),
            "chat_model": settings.qdrant_collection and settings.ollama_chat_model,
            "embedding_model": settings.ollama_embedding_model,
        },
        "qdrant": qdrant_service.get_collection_info(),
        "neo4j": {"available": neo4j_service.health_check()},
        "mongodb": {
            "available": True,
            "chunk_count": chunk_count,
            "indexed_chunk_count": indexed_count,
        },
        "feature_flags": {
            "rag_vector_enabled": settings.rag_vector_enabled,
            "rag_graph_enabled": settings.rag_graph_enabled,
        },
    }


# ── GET /copilot/index ─────────────────────────────────────────────────────────

@router.post("/copilot/index")
def trigger_index(force: bool = Query(False, description="Force re-index all chunks")):
    """Trigger a full corpus index run (async-style: returns immediately with job_id)."""
    # Run synchronously for simplicity — for large corpora use a background task
    from app.services.indexer import run_full_index
    summary = run_full_index(force=force)
    return summary
