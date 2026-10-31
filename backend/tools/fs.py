"""
tools/fs.py — file-system tools: read, write, list, delete.
"""
from __future__ import annotations
import os
import shutil
from pathlib import Path


async def fs_read(path: str, encoding: str = "utf-8") -> dict:
    """Read a file and return its text content."""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": f"File not found: {path}"}
        if not p.is_file():
            return {"ok": False, "error": f"Path is not a file: {path}"}
        content = p.read_text(encoding=encoding, errors="replace")
        return {"ok": True, "path": str(p), "content": content, "size_bytes": p.stat().st_size}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def fs_write(path: str, content: str, mode: str = "w") -> dict:
    """Write content to a file. mode='w' overwrites, mode='a' appends."""
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open(mode=mode, encoding="utf-8") as f:
            f.write(content)
        return {"ok": True, "path": str(p), "size_bytes": p.stat().st_size}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def fs_list(path: str, recursive: bool = False) -> dict:
    """List directory contents. Returns file names, sizes, types."""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": f"Path not found: {path}"}
        if not p.is_dir():
            return {"ok": False, "error": f"Path is not a directory: {path}"}

        entries = []
        if recursive:
            for item in sorted(p.rglob("*")):
                rel = item.relative_to(p)
                entries.append({
                    "name": str(rel),
                    "type": "file" if item.is_file() else "dir",
                    "size_bytes": item.stat().st_size if item.is_file() else None,
                })
        else:
            for item in sorted(p.iterdir()):
                entries.append({
                    "name": item.name,
                    "type": "file" if item.is_file() else "dir",
                    "size_bytes": item.stat().st_size if item.is_file() else None,
                })

        return {"ok": True, "path": str(p), "entries": entries, "count": len(entries)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def fs_delete(path: str, recursive: bool = False) -> dict:
    """Delete a file or directory."""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": f"Path not found: {path}"}
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            if recursive:
                shutil.rmtree(p)
            else:
                p.rmdir()  # fails if non-empty — intentional safety
        return {"ok": True, "path": str(p)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
