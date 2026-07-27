"""Helpers to extract grounded context from OpenAI-compatible payloads."""

from __future__ import annotations

from typing import Any


def extract_grounded_context(body: dict[str, Any]) -> str:
    """Pull retrieval context from common OpenAI extension fields."""
    extra = body.get("extra_body")
    if isinstance(extra, dict):
        ctx = extra.get("grounded_context") or extra.get("context")
        if isinstance(ctx, str) and ctx.strip():
            return ctx

    for key in ("grounded_context", "context"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            return val

    # Chat message content marked as system grounding (optional convention)
    messages = body.get("messages")
    if isinstance(messages, list):
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") == "grounding" and isinstance(msg.get("content"), str):
                return msg["content"]
    return ""


def assistant_text_from_chat_completion(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    msg = (choices[0] or {}).get("message") or {}
    content = msg.get("content")
    return content if isinstance(content, str) else ""


def assistant_text_from_completion(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    text = (choices[0] or {}).get("text")
    return text if isinstance(text, str) else ""


def stream_delta_text(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices") or []
    if not choices:
        return ""
    choice = choices[0] or {}
    delta = choice.get("delta") or {}
    if isinstance(delta, dict) and isinstance(delta.get("content"), str):
        return delta["content"]
    text = choice.get("text")
    return text if isinstance(text, str) else ""
