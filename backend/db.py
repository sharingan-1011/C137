"""SQLite session + message persistence (aiosqlite)."""
import json
import time
import uuid
import aiosqlite
from backend.config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id        TEXT PRIMARY KEY,
            title     TEXT NOT NULL DEFAULT 'New Chat',
            created   REAL NOT NULL,
            updated   REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id         TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            ts         REAL NOT NULL
        );
        """)
        await db.commit()


async def create_session(title: str = "New Chat") -> dict:
    sid = str(uuid.uuid4())
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sessions (id,title,created,updated) VALUES (?,?,?,?)",
            (sid, title, now, now),
        )
        await db.commit()
    return {"id": sid, "title": title, "created": now, "updated": now}


async def list_sessions() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sessions ORDER BY updated DESC"
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_session(sid: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM sessions WHERE id=?", (sid,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def update_session_title(sid: str, title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sessions SET title=?, updated=? WHERE id=?",
            (title, time.time(), sid),
        )
        await db.commit()


async def delete_session(sid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE id=?", (sid,))
        await db.commit()


async def append_message(session_id: str, role: str, content: str) -> str:
    mid = str(uuid.uuid4())
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (id,session_id,role,content,ts) VALUES (?,?,?,?,?)",
            (mid, session_id, role, content, now),
        )
        await db.execute(
            "UPDATE sessions SET updated=? WHERE id=?", (now, session_id)
        )
        await db.commit()
    return mid


async def get_history(session_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM messages WHERE session_id=? ORDER BY ts",
            (session_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_history_for_llm(session_id: str) -> list[dict]:
    """Return history in OpenAI message format."""
    rows = await get_history(session_id)
    return [{"role": r["role"], "content": r["content"]} for r in rows]
