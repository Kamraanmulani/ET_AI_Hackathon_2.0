"""
app/services/llm_client.py — OpenAI client for embeddings and chat generation.

Embeddings use an OpenAI text-embedding-3 model, reduced to
settings.openai_embedding_dimensions (1024 by default) so vectors match the
Qdrant collection size. Chat generation uses settings.openai_chat_model.

Every failure (missing key, network error, API error) is raised as
LLMUnavailableError so callers can fall back gracefully.
"""
from __future__ import annotations

import time
from functools import lru_cache

import openai
from openai import OpenAI

from app.core.config import settings

import structlog
log = structlog.get_logger(__name__)

_TIMEOUT_SECONDS = 60.0
_HEALTH_TTL_SECONDS = 60.0
_health_cache: dict[str, float | bool] = {"checked_at": 0.0, "ok": False}


class LLMUnavailableError(Exception):
    """Raised when the OpenAI API is not configured, not reachable, or returns an error."""


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise LLMUnavailableError("OPENAI_API_KEY is not set in backend/.env")
    return OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        timeout=_TIMEOUT_SECONDS,
        max_retries=2,
    )


def health_check() -> bool:
    """Return True if the OpenAI API key is set and the API is reachable (cached for 60 s)."""
    now = time.monotonic()
    if now - float(_health_cache["checked_at"]) < _HEALTH_TTL_SECONDS:
        return bool(_health_cache["ok"])
    try:
        _client().models.retrieve(settings.openai_chat_model, timeout=5.0)
        ok = True
    except Exception as e:
        log.warning("openai_health_check_failed", error=str(e))
        ok = False
    _health_cache.update(checked_at=now, ok=ok)
    return ok


def embed(text: str) -> list[float]:
    """
    Generate an embedding vector with the configured OpenAI embedding model.
    Returns settings.openai_embedding_dimensions floats.
    Raises LLMUnavailableError on any failure.
    """
    try:
        resp = _client().embeddings.create(
            model=settings.openai_embedding_model,
            input=text,
            dimensions=settings.openai_embedding_dimensions,
        )
    except openai.OpenAIError as e:
        raise LLMUnavailableError(f"OpenAI embedding failed: {e}") from e
    if not resp.data:
        raise LLMUnavailableError("Empty embedding response from OpenAI")
    return list(resp.data[0].embedding)


def generate(
    system_prompt: str,
    user_message: str,
    evidence_pack: list[dict],
    max_tokens: int = 512,
) -> str:
    """
    Generate an answer from the evidence pack with the configured OpenAI chat model.

    The evidence pack is injected into the system context — NOT the whole document.
    Temperature is kept low for factual grounding.
    Raises LLMUnavailableError on any failure.
    """
    # Build evidence context string (compact, not full documents)
    evidence_lines = []
    for i, chunk in enumerate(evidence_pack, start=1):
        label = f"[C{i}]"
        provenance = chunk.get("provenance", "unknown")
        state = chunk.get("review_state", "unknown")
        excerpt = chunk.get("text", "")[:600]  # hard cap per chunk
        source = chunk.get("source_id", "")
        page = chunk.get("page", "")
        tags = ", ".join(chunk.get("asset_tags", []))
        evidence_lines.append(
            f"{label} Source={source} Page={page} Provenance={provenance} State={state} Tags={tags}\n{excerpt}"
        )

    evidence_text = "\n\n---\n".join(evidence_lines)

    full_system = (
        f"{system_prompt}\n\n"
        f"=== EVIDENCE PACK ===\n{evidence_text}\n=== END OF EVIDENCE ==="
    )

    try:
        resp = _client().chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": full_system},
                {"role": "user", "content": user_message},
            ],
            temperature=settings.openai_temperature,
            max_completion_tokens=max_tokens,
        )
    except openai.OpenAIError as e:
        raise LLMUnavailableError(f"OpenAI chat generation failed: {e}") from e
    if not resp.choices:
        raise LLMUnavailableError("Empty chat response from OpenAI")
    return (resp.choices[0].message.content or "").strip()
