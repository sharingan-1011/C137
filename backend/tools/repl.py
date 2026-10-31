"""
tools/repl.py — repl_run: persistent Python REPL per chat session.

Uses a dict of `code.InteractiveInterpreter` instances keyed by session_id.
Variables persist across calls within the same session.
Stdout/stderr are captured via io.StringIO redirection.
"""
from __future__ import annotations
import asyncio
import code
import io
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from typing import Any

# In-process kernels: session_id → {"interp": InteractiveInterpreter, "locals": dict}
_kernels: dict[str, dict[str, Any]] = {}


def _get_kernel(session_id: str) -> tuple[code.InteractiveInterpreter, dict]:
    if session_id not in _kernels:
        local_ns: dict = {}
        interp = code.InteractiveInterpreter(locals=local_ns)
        _kernels[session_id] = {"interp": interp, "locals": local_ns}
    k = _kernels[session_id]
    return k["interp"], k["locals"]


def _run_sync(session_id: str, src: str) -> dict:
    interp, local_ns = _get_kernel(session_id)
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    try:
        compiled = compile(src, "<repl>", "exec")
    except SyntaxError:
        tb = traceback.format_exc()
        return {"ok": False, "stdout": "", "stderr": tb, "error": "SyntaxError"}

    with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        try:
            exec(compiled, local_ns)  # noqa: S102
            error = None
            ok = True
        except Exception:
            error = traceback.format_exc()
            ok = False

    stdout = stdout_buf.getvalue()
    stderr = stderr_buf.getvalue()
    if error:
        stderr = (stderr + "\n" + error).strip()

    return {"ok": ok, "stdout": stdout, "stderr": stderr, "error": error}


async def repl_run(
    code: str,
    session_id: str = "default",
    timeout: int = 60,
) -> dict:
    """
    Execute Python code in a persistent in-process REPL.

    Variables survive between calls within the same session_id.

    Returns:
        {
            "ok": bool,
            "stdout": str,
            "stderr": str,
            "error": str | None
        }
    """
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _run_sync, session_id, code),
            timeout=timeout,
        )
        return result
    except asyncio.TimeoutError:
        return {"ok": False, "stdout": "", "stderr": "", "error": f"Execution timed out after {timeout}s"}
    except Exception as exc:
        return {"ok": False, "stdout": "", "stderr": "", "error": str(exc)}


def clear_repl(session_id: str) -> None:
    """Clear the REPL state for a session (call on session delete)."""
    _kernels.pop(session_id, None)
