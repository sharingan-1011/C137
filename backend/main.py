"""
main.py — FastAPI application entry point. v2.2.0
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from backend.agent import stream_agent
from backend.db import (
    append_message,
    create_session,
    delete_session,
    get_history_for_llm,
    get_session,
    init_db,
    list_sessions,
    update_session_title,
)
from backend.tools.repl import clear_repl



@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="FORGE", version="2.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── sessions ──────────────────────────────────────────────────

@app.get("/sessions")
async def get_sessions():
    return await list_sessions()


@app.post("/sessions")
async def new_session():
    session = await create_session()
    return {"session_id": session["id"]}


@app.get("/sessions/{session_id}")
async def get_session_endpoint(session_id: str):
    session = await get_session(session_id)
    if not session:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return session


class RenameRequest(BaseModel):
    title: str


@app.patch("/sessions/{session_id}")
async def rename_session(session_id: str, req: RenameRequest):
    await update_session_title(session_id, req.title)
    return {"ok": True}


@app.delete("/sessions/{session_id}")
async def del_session(session_id: str):
    await delete_session(session_id)
    clear_repl(session_id)
    return {"ok": True}


# ── chat ──────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message:    str


@app.post("/chat")
async def chat(req: Request, body: ChatRequest = Body(...)):
    session_id = body.session_id
    user_msg   = body.message

    await append_message(session_id, "user", user_msg)
    history = await get_history_for_llm(session_id)

    cancel_event   = asyncio.Event()
    response_parts: list[str] = []

    async def generate():
        async def _watch_disconnect():
            while not cancel_event.is_set():
                if await req.is_disconnected():
                    cancel_event.set()
                    return
                await asyncio.sleep(0.3)

        watcher = asyncio.create_task(_watch_disconnect())

        try:
            async for chunk in stream_agent(session_id, history, cancel_event=cancel_event):
                yield chunk
                try:
                    payload = json.loads(chunk.removeprefix("data: ").strip())
                    if payload.get("type") == "delta":
                        response_parts.append(payload.get("text", ""))
                except Exception:
                    pass
        finally:
            cancel_event.set()
            watcher.cancel()

            full_response = "".join(response_parts)
            if full_response.strip():
                await append_message(session_id, "assistant", full_response)
                session = await get_session(session_id)
                if session and session.get("title", "").startswith("New Chat"):
                    title = user_msg[:48] + ("…" if len(user_msg) > 48 else "")
                    await update_session_title(session_id, title)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ── upload ────────────────────────────────────────────────────

UPLOAD_DIR = Path(tempfile.gettempdir()) / "forge_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/upload")
async def upload_file(file: UploadFile):
    safe_name = Path(file.filename).name
    dest      = UPLOAD_DIR / safe_name
    counter   = 1
    stem, suffix = dest.stem, dest.suffix
    while dest.exists():
        dest = UPLOAD_DIR / f"{stem}_{counter}{suffix}"
        counter += 1
    contents = await file.read()
    dest.write_bytes(contents)
    return {"path": str(dest), "name": dest.name, "size": len(contents)}