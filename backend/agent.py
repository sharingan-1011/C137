"""
agent.py — ReAct agent loop with live token streaming.

Improvements over previous version
────────────────────────────────────
- A2: Tokens stream live. <think> tags are detected incrementally so
      thinking and response text both appear word-by-word.
- C4: Accepts an asyncio.Event (cancel_event) — set it to stop the loop
      cleanly; the generator yields a final done/cancelled event.

SSE event shapes
────────────────
{ "type": "thinking",    "text": "…" }   ← incremental tokens inside <think>
{ "type": "delta",       "text": "…" }   ← incremental response tokens
{ "type": "tool_start",  "call_id": "…", "name": "…", "args": {…} }
{ "type": "tool_result", "call_id": "…", "name": "…", "output": "…" }
{ "type": "done" }
{ "type": "cancelled" }
{ "type": "error",       "detail": "…" }
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from backend.config import MODEL_NAME
from backend.llm import get_client
from backend.tools import TOOL_REGISTRY, TOOL_SCHEMAS

SYSTEM_PROMPT = """You are C137, a capable agentic AI assistant with access to tools.

When you need to reason before acting, wrap your thoughts in <think>…</think>.
After reasoning, either call a tool or respond directly to the user.

Guidelines:
- Use tools only when needed — don't call tools for things you already know.
- For computation or data analysis, prefer repl_run.
- For research, use web_search then web_fetch for full content.
- Never guess file contents — use fs_read.
- Format responses clearly using markdown — use headers, bullet lists, bold, and code blocks where appropriate.
- Be concise and direct in your final response.
"""

# ── incremental <think> tag parser ────────────────────────────────────────────
# Tracks streaming state across token chunks so we can emit thinking vs
# response events live without waiting for the full buffer.

class _ThinkParser:
    """
    Feed tokens one at a time; get back labelled segments.
    States: RESPONSE | IN_THINK | DRAINING_CLOSE
    """
    def __init__(self):
        self._state   = "RESPONSE"   # "RESPONSE" | "IN_THINK"
        self._partial = ""           # accumulates partial tag chars

    def feed(self, token: str) -> list[tuple[str, str]]:
        """
        Returns list of (label, text) where label ∈ {"thinking","delta"}.
        """
        out: list[tuple[str, str]] = []
        i = 0
        while i < len(token):
            ch = token[i]
            if self._state == "RESPONSE":
                if ch == "<":
                    self._partial = "<"
                    i += 1
                    # consume ahead to see if this is <think>
                    while i < len(token) and len(self._partial) < 7:
                        self._partial += token[i]
                        i += 1
                    if self._partial == "<think>":
                        self._state   = "IN_THINK"
                        self._partial = ""
                    elif "<think>".startswith(self._partial):
                        pass  # still accumulating — will resolve next chunk
                    else:
                        out.append(("delta", self._partial))
                        self._partial = ""
                else:
                    out.append(("delta", ch))
                    i += 1
            else:  # IN_THINK
                if ch == "<":
                    self._partial = "<"
                    i += 1
                    while i < len(token) and len(self._partial) < 7:
                        self._partial += token[i]
                        i += 1
                    if self._partial == "</think>":
                        self._state   = "RESPONSE"
                        self._partial = ""
                    elif "</think>".startswith(self._partial):
                        pass  # still accumulating
                    else:
                        out.append(("thinking", self._partial))
                        self._partial = ""
                else:
                    out.append(("thinking", ch))
                    i += 1
        return out

    def flush(self) -> list[tuple[str, str]]:
        """Emit any leftover partial tag as the appropriate type."""
        if self._partial:
            label = "thinking" if self._state == "IN_THINK" else "delta"
            out = [(label, self._partial)]
            self._partial = ""
            return out
        return []


# ── main streaming entry point ────────────────────────────────────────────────

async def stream_agent(
    session_id: str,
    history: list[dict],
    max_iterations: int = 12,
    cancel_event: asyncio.Event | None = None,
) -> AsyncGenerator[str, None]:
    """
    Run the ReAct loop and yield SSE-formatted strings.
    Tokens are emitted live — no full-buffer wait.
    Pass cancel_event and set() it to abort mid-stream.
    """

    def sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def cancelled() -> bool:
        return cancel_event is not None and cancel_event.is_set()

    client   = get_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]

    try:
        for _iteration in range(max_iterations):
            if cancelled():
                yield sse({"type": "cancelled"})
                return

            parser         = _ThinkParser()
            full_text_buf  = ""          # for the assistant message record
            tool_calls_buf: dict[int, dict] = {}

            # ── live-stream one LLM call ──────────────────────────────────────
            stream = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                stream=True,
                max_tokens=4096,
                temperature=0.6,
            )

            async for chunk in stream:
                if cancelled():
                    yield sse({"type": "cancelled"})
                    return

                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue
                delta = choice.delta

                # ── text tokens ───────────────────────────────────────────────
                if delta.content:
                    token = delta.content
                    full_text_buf += token
                    for label, text in parser.feed(token):
                        if text:
                            yield sse({"type": label, "text": text})

                # ── tool call deltas ──────────────────────────────────────────
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_buf:
                            tool_calls_buf[idx] = {"id": "", "name": "", "args_str": ""}
                        if tc.id:
                            tool_calls_buf[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_buf[idx]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls_buf[idx]["args_str"] += tc.function.arguments

                await asyncio.sleep(0)

            # flush partial tag buffer
            for label, text in parser.flush():
                if text:
                    yield sse({"type": label, "text": text})

            # ── no tool calls → turn complete ─────────────────────────────────
            if not tool_calls_buf:
                break

            # ── build assistant message with tool_calls ───────────────────────
            tool_call_objs: list[dict] = []
            parsed_calls:   list[dict] = []

            for idx in sorted(tool_calls_buf):
                tc = tool_calls_buf[idx]
                try:
                    args = json.loads(tc["args_str"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                parsed_calls.append({
                    "id": tc["id"], "name": tc["name"],
                    "args": args, "args_str": tc["args_str"],
                })
                tool_call_objs.append({
                    "id":       tc["id"],
                    "type":     "function",
                    "function": {"name": tc["name"], "arguments": tc["args_str"]},
                })

            messages.append({
                "role":       "assistant",
                "content":    full_text_buf,
                "tool_calls": tool_call_objs,
            })

            # ── execute each tool ─────────────────────────────────────────────
            for tc in parsed_calls:
                if cancelled():
                    yield sse({"type": "cancelled"})
                    return

                call_id = tc["id"]
                name    = tc["name"]
                args    = tc["args"]

                yield sse({"type": "tool_start", "call_id": call_id, "name": name, "args": args})

                fn = TOOL_REGISTRY.get(name)
                if fn is None:
                    output = json.dumps({"error": f"Unknown tool: {name}"})
                else:
                    try:
                        result = await fn(**args)
                        output = json.dumps(result, ensure_ascii=False)
                    except Exception as exc:
                        output = json.dumps({"error": str(exc)})

                yield sse({"type": "tool_result", "call_id": call_id, "name": name, "output": output})

                messages.append({
                    "role":         "tool",
                    "tool_call_id": call_id,
                    "content":      output,
                })

            # loop → next LLM call with tool results in context

        yield sse({"type": "done"})

    except Exception as exc:
        yield sse({"type": "error", "detail": str(exc)})