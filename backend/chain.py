"""
chain.py — higher-level LangChain wrappers.

Phase 1: plain async generator helpers on top of llm.py.
Phase 3+: swap internals to LangGraph without changing the API surface.
"""
from __future__ import annotations

from typing import AsyncGenerator

from backend import llm


# ── thinking phase ────────────────────────────────────────────────────────────

async def think(
    history: list[dict[str, str]],
) -> AsyncGenerator[str, None]:
    """
    Streams the planning/reasoning text.
    Yields raw string chunks (caller joins them for storage).
    """
    async for chunk in llm.stream_thinking(history):
        yield chunk


# ── response phase ────────────────────────────────────────────────────────────

async def respond(
    history: list[dict[str, str]],
    approved_plan: str,
) -> AsyncGenerator[str, None]:
    """
    Streams the final answer given the user-approved plan.
    """
    async for chunk in llm.stream_response(history, approved_plan):
        yield chunk


# ── direct phase (thinking OFF) ───────────────────────────────────────────────

async def direct(
    history: list[dict[str, str]],
) -> AsyncGenerator[str, None]:
    """Single-pass response when thinking mode is disabled."""
    async for chunk in llm.stream_direct(history):
        yield chunk
