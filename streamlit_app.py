"""
streamlit_app.py — C137 FORGE · Streamlit UI
Connects to the FastAPI backend at FORGE_API_URL (default http://localhost:8000).

Run:
    streamlit run streamlit_app.py
"""
from __future__ import annotations

import json
import os
import time

import requests
import sseclient
import streamlit as st

# ── config ────────────────────────────────────────────────────────────────────

API_URL = os.getenv("FORGE_API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="C137 FORGE",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── minimal dark styling ──────────────────────────────────────────────────────
st.markdown("""
<style>
/* Hide Streamlit branding */
#MainMenu, footer { visibility: hidden; }

/* Dark base */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0a0a0a;
    color: #e8e8e8;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #111111;
    border-right: 2px solid #3d0000;
}

/* Chat bubbles */
.user-bubble {
    background: #1a0000;
    border: 1px solid #8b0000;
    border-radius: 4px;
    padding: 10px 14px;
    margin: 6px 0;
    white-space: pre-wrap;
    word-wrap: break-word;
}
.assistant-bubble {
    background: #0f0f0f;
    border: 1px solid #3d0000;
    border-radius: 4px;
    padding: 10px 14px;
    margin: 6px 0;
    white-space: pre-wrap;
    word-wrap: break-word;
}
.thinking-box {
    background: #050505;
    border: 1px dashed #8b0000;
    border-radius: 4px;
    padding: 8px 12px;
    margin: 4px 0 10px 0;
    color: #666;
    font-size: 0.85em;
    white-space: pre-wrap;
}
.tag-user     { color: #e53935; font-weight: bold; font-size: 0.78em; }
.tag-agent    { color: #8b0000; font-weight: bold; font-size: 0.78em; }
.tag-thinking { color: #444;    font-weight: bold; font-size: 0.78em; }

/* Buttons */
div.stButton > button {
    background-color: #e53935;
    color: #000;
    border: none;
    border-radius: 3px;
    font-weight: bold;
}
div.stButton > button:hover {
    background-color: #ff5252;
    color: #000;
}
</style>
""", unsafe_allow_html=True)


# ── helpers ───────────────────────────────────────────────────────────────────

def _api(method: str, path: str, **kwargs):
    """Thin wrapper around requests; raises on HTTP error."""
    resp = requests.request(method, f"{API_URL}{path}", timeout=30, **kwargs)
    resp.raise_for_status()
    return resp


def _sse_stream(path: str, payload: dict):
    """
    POST to path with payload, return sseclient.SSEClient.
    Caller iterates over events.
    """
    resp = requests.post(
        f"{API_URL}{path}",
        json=payload,
        stream=True,
        timeout=120,
    )
    resp.raise_for_status()
    return sseclient.SSEClient(resp)


def _check_backend() -> bool:
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


# ── session state init ────────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "session_id": None,
        "messages": [],           # [{role, content, thinking}]
        "thinking_mode": True,
        "pending_plan": None,     # plan text waiting for approval
        "pending_message": None,  # user message that triggered the plan
        "sessions_list": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ── sidebar ───────────────────────────────────────────────────────────────────

def _load_sessions():
    try:
        st.session_state.sessions_list = _api("GET", "/sessions").json()
    except Exception:
        st.session_state.sessions_list = []


def _new_session():
    try:
        resp = _api("POST", "/sessions", json={})
        sid = resp.json()["id"]
        st.session_state.session_id = sid
        st.session_state.messages = []
        st.session_state.pending_plan = None
        st.session_state.pending_message = None
        _load_sessions()
    except Exception as e:
        st.error(f"Could not create session: {e}")


def _load_session(sid: str):
    try:
        msgs = _api("GET", f"/sessions/{sid}/messages").json()
        st.session_state.session_id = sid
        st.session_state.messages = [
            {"role": m["role"], "content": m["content"], "thinking": m.get("thinking")}
            for m in msgs
        ]
        st.session_state.pending_plan = None
        st.session_state.pending_message = None
    except Exception as e:
        st.error(f"Could not load session: {e}")


with st.sidebar:
    st.markdown("## 🤖 C137 FORGE")
    st.markdown("---")

    backend_ok = _check_backend()
    if backend_ok:
        st.success("Backend ● online")
    else:
        st.error("Backend ✗ offline")
        st.caption(f"Expected at {API_URL}")

    st.markdown("---")

    # Thinking toggle
    st.session_state.thinking_mode = st.toggle(
        "Thinking mode",
        value=st.session_state.thinking_mode,
        help="When ON, C137 shows a plan for approval before answering.",
    )

    st.markdown("---")

    if st.button("＋ New chat", use_container_width=True):
        _new_session()

    # Session list
    _load_sessions()
    if st.session_state.sessions_list:
        st.markdown("**Recent sessions**")
        for s in st.session_state.sessions_list:
            label = s["title"][:40] + ("…" if len(s["title"]) > 40 else "")
            is_active = s["id"] == st.session_state.session_id
            btn_label = f"▶ {label}" if is_active else label
            if st.button(btn_label, key=f"sess_{s['id']}", use_container_width=True):
                _load_session(s["id"])
                st.rerun()

    st.markdown("---")
    st.caption(f"Model: Groot-19B-A3B-261023")
    st.caption(f"API: {API_URL}")


# ── main chat area ────────────────────────────────────────────────────────────

st.markdown("## C137")

if not st.session_state.session_id:
    st.info("Start a new chat from the sidebar, or select an existing session.")
    st.stop()

if not backend_ok:
    st.error("Backend is offline. Start the FastAPI server first.")
    st.stop()

# ── render message history ────────────────────────────────────────────────────

chat_area = st.container()

with chat_area:
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f'<p class="tag-user">YOU</p>'
                        f'<div class="user-bubble">{msg["content"]}</div>',
                        unsafe_allow_html=True)
        elif msg["role"] == "assistant":
            if msg.get("thinking") and not msg.get("content"):
                # thinking-only row (pre-confirm)
                pass
            else:
                thinking_html = ""
                if msg.get("thinking"):
                    thinking_html = (
                        f'<p class="tag-thinking">THINK</p>'
                        f'<div class="thinking-box">{msg["thinking"]}</div>'
                    )
                st.markdown(
                    f'{thinking_html}'
                    f'<p class="tag-agent">C137</p>'
                    f'<div class="assistant-bubble">{msg["content"]}</div>',
                    unsafe_allow_html=True,
                )


# ── pending plan approval ─────────────────────────────────────────────────────

if st.session_state.pending_plan:
    st.markdown("---")
    st.markdown("### 🔍 C137's Plan — review before executing")
    st.markdown(
        f'<div class="thinking-box">{st.session_state.pending_plan}</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Approve & Run", use_container_width=True):
            plan = st.session_state.pending_plan
            st.session_state.pending_plan = None
            st.session_state.pending_message = None

            # stream final response
            response_placeholder = st.empty()
            full_response = ""
            try:
                client = _sse_stream(
                    "/chat/confirm",
                    {"session_id": st.session_state.session_id, "approved_plan": plan},
                )
                for event in client.events():
                    data = json.loads(event.data)
                    if data["type"] == "delta":
                        full_response += data["text"]
                        response_placeholder.markdown(
                            f'<div class="assistant-bubble">{full_response}▌</div>',
                            unsafe_allow_html=True,
                        )
                    elif data["type"] == "done":
                        response_placeholder.empty()
                        break
                    elif data["type"] == "error":
                        st.error(data["detail"])
                        break
            except Exception as e:
                st.error(f"Stream error: {e}")

            if full_response:
                st.session_state.messages.append(
                    {"role": "assistant", "content": full_response, "thinking": plan}
                )
            st.rerun()

    with col2:
        if st.button("✏️ Edit plan (re-run)", use_container_width=True):
            st.session_state.pending_plan = None
            st.rerun()

    st.stop()   # don't render input bar while plan is pending


# ── input bar ─────────────────────────────────────────────────────────────────

st.markdown("---")
with st.form("input_form", clear_on_submit=True):
    col_input, col_send = st.columns([9, 1])
    with col_input:
        user_input = st.text_area(
            "Message",
            placeholder="Ask C137 anything…",
            label_visibility="collapsed",
            height=80,
        )
    with col_send:
        submitted = st.form_submit_button("Send", use_container_width=True)

if submitted and user_input.strip():
    user_msg = user_input.strip()

    # Show user message immediately
    st.session_state.messages.append({"role": "user", "content": user_msg, "thinking": None})

    # ── thinking mode ON → two-round-trip ─────────────────────────────────
    if st.session_state.thinking_mode:
        thinking_placeholder = st.empty()
        thinking_text = ""

        try:
            client = _sse_stream(
                "/chat",
                {"session_id": st.session_state.session_id, "message": user_msg},
            )
            for event in client.events():
                data = json.loads(event.data)
                if data["type"] == "thinking":
                    thinking_text += data["text"]
                    thinking_placeholder.markdown(
                        f'<p class="tag-thinking">THINKING…</p>'
                        f'<div class="thinking-box">{thinking_text}▌</div>',
                        unsafe_allow_html=True,
                    )
                elif data["type"] == "done":
                    thinking_placeholder.empty()
                    break
                elif data["type"] == "error":
                    st.error(data["detail"])
                    break
        except Exception as e:
            st.error(f"Stream error: {e}")

        if thinking_text:
            st.session_state.pending_plan = thinking_text
            st.session_state.pending_message = user_msg
        st.rerun()

    # ── thinking mode OFF → single pass ───────────────────────────────────
    else:
        response_placeholder = st.empty()
        full_response = ""
        try:
            client = _sse_stream(
                "/chat/direct",
                {"session_id": st.session_state.session_id, "message": user_msg},
            )
            for event in client.events():
                data = json.loads(event.data)
                if data["type"] == "delta":
                    full_response += data["text"]
                    response_placeholder.markdown(
                        f'<div class="assistant-bubble">{full_response}▌</div>',
                        unsafe_allow_html=True,
                    )
                elif data["type"] == "done":
                    response_placeholder.empty()
                    break
                elif data["type"] == "error":
                    st.error(data["detail"])
                    break
        except Exception as e:
            st.error(f"Stream error: {e}")

        if full_response:
            st.session_state.messages.append(
                {"role": "assistant", "content": full_response, "thinking": None}
            )
        st.rerun()
