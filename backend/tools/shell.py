"""
tools/shell.py — shell_exec: run a subprocess, capture stdout + stderr.
"""
from __future__ import annotations
import asyncio
import os


async def shell_exec(
    cmd: str,
    cwd: str | None = None,
    timeout: int = 30,
) -> dict:
    """
    Run `cmd` in a shell subprocess.

    Returns:
        {
            "stdout": str,
            "stderr": str,
            "returncode": int,
            "error": str | None   # set only on Python-level exception
        }
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd or os.getcwd(),
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {
                "stdout": "",
                "stderr": "",
                "returncode": -1,
                "error": f"Command timed out after {timeout}s",
            }

        return {
            "stdout":     stdout.decode(errors="replace"),
            "stderr":     stderr.decode(errors="replace"),
            "returncode": proc.returncode,
            "error":      None,
        }
    except Exception as exc:
        return {
            "stdout":     "",
            "stderr":     "",
            "returncode": -1,
            "error":      str(exc),
        }
