"""
app/services/ollama_client.py — Local Ollama HTTP client for embeddings and chat.

Uses httpx for async-ready HTTP. Runs against Ollama at localhost:11434 on Windows host.
Never sends data externally. Falls back gracefully when Ollama is unavailable.
"""
from __future__ import annotations

import json
import time
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings

import structlog
log = structlog.get_logger(__name__)

_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0, write=30.0, pool=5.0)


class OllamaUnavailableError(Exception):
    """Raised when Ollama is not reachable or no model is loaded."""


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.ollama_base_url, timeout=_TIMEOUT)


def health_check() -> bool:
    """Return True if Ollama is running and reachable."""
    try:
        with _client() as c:
            r = c.get("/api/tags", timeout=3.0)
            return r.status_code == 200
    except Exception:
        return False


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    reraise=True,
)
def embed(text: str) -> list[float]:
    """
    Generate an embedding vector using mxbai-embed-large via Ollama.
    Returns a list of floats (1024 dimensions for mxbai-embed-large).
    Raises OllamaUnavailableError if Ollama is down.
    """
    try:
        with _client() as c:
            payload = {
                "model": settings.ollama_embedding_model,
                "input": text,
            }
            r = c.post("/api/embed", json=payload)
            r.raise_for_status()
            data = r.json()
            # Ollama /api/embed returns {"embeddings": [[...]], ...}
            embeddings = data.get("embeddings") or data.get("embedding")
            if not embeddings:
                raise OllamaUnavailableError("Empty embedding response from Ollama")
            # Handle both [[...]] and [...] shapes
            vec = embeddings[0] if isinstance(embeddings[0], list) else embeddings
            return vec
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        raise OllamaUnavailableError(f"Ollama unreachable: {e}") from e
    except httpx.HTTPStatusError as e:
        raise OllamaUnavailableError(f"Ollama embed error {e.response.status_code}: {e.response.text}") from e


def generate(
    system_prompt: str,
    user_message: str,
    evidence_pack: list[dict],
    max_tokens: int = 512,
) -> str:
    """
    Generate an answer from the evidence pack using qwen3:8b via Ollama.

    The evidence pack is injected into the system context — NOT the whole document.
    Temperature is set low (0.1) for factual grounding.
    Returns the generated text string.
    Raises OllamaUnavailableError if Ollama is down.
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
        with _client() as c:
            payload = {
                "model": settings.ollama_chat_model,
                "messages": [
                    {"role": "system", "content": full_system},
                    {"role": "user", "content": user_message},
                ],
                "stream": False,
                "options": {
                    "temperature": settings.ollama_temperature,
                    "num_predict": max_tokens,
                    "num_ctx": settings.ollama_context_window,
                },
            }
            r = c.post("/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
            return data.get("message", {}).get("content", "").strip()
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        raise OllamaUnavailableError(f"Ollama unreachable during generation: {e}") from e
    except httpx.HTTPStatusError as e:
        raise OllamaUnavailableError(f"Ollama chat error {e.response.status_code}: {e.response.text}") from e
