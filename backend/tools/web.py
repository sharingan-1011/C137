"""
tools/web.py — web_fetch and web_search (no external dependencies beyond requests).

web_fetch  — HTTP GET, strips HTML tags, returns plain text.
web_search — DuckDuckGo Instant Answer API (no API key required).
"""
from __future__ import annotations
import asyncio
import html
import re
import urllib.parse
from typing import Any

import requests


# ── HTML stripper ────────────────────────────────────────────────────────────

_TAG_RE  = re.compile(r"<[^>]+>")
_WS_RE   = re.compile(r"\s{2,}")

def _strip_html(raw: str) -> str:
    text = html.unescape(raw)
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


# ── web_fetch ────────────────────────────────────────────────────────────────

def _fetch_sync(url: str, timeout: int, raw_html: bool) -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        body = r.text
        content = body if raw_html else _strip_html(body)
        # Truncate very large pages
        if len(content) > 20_000:
            content = content[:20_000] + "\n\n[... truncated at 20 000 chars ...]"
        return {
            "ok":          True,
            "url":         r.url,
            "status_code": r.status_code,
            "content":     content,
            "content_type": r.headers.get("content-type", ""),
        }
    except requests.HTTPError as exc:
        return {"ok": False, "url": url, "error": f"HTTP {exc.response.status_code}: {exc}"}
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}


async def web_fetch(
    url: str,
    timeout: int = 15,
    raw_html: bool = False,
) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_sync, url, timeout, raw_html)


# ── web_search ───────────────────────────────────────────────────────────────

def _search_sync(query: str, max_results: int) -> dict:
    """
    DuckDuckGo HTML scrape — no API key, no rate-limit headers.
    Falls back gracefully if DDG changes its markup.
    """
    encoded = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()

        # Parse result blocks: <div class="result__body">
        results: list[dict[str, Any]] = []
        # Regex-based extraction (avoids BS4 dependency)
        blocks = re.findall(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</span>',
            r.text,
            re.DOTALL,
        )
        for href, title_raw, snippet_raw in blocks[:max_results]:
            # DDG wraps URLs in a redirect; extract uddg param
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            real_url = qs.get("uddg", [href])[0]
            results.append({
                "title":   _strip_html(title_raw),
                "url":     urllib.parse.unquote(real_url),
                "snippet": _strip_html(snippet_raw),
            })

        if not results:
            # Fallback: return the page text so the model can try to parse
            return {
                "ok":      True,
                "query":   query,
                "results": [],
                "warning": "No structured results parsed — DDG markup may have changed.",
            }

        return {"ok": True, "query": query, "results": results}
    except Exception as exc:
        return {"ok": False, "query": query, "error": str(exc), "results": []}


async def web_search(query: str, max_results: int = 5) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search_sync, query, max_results)
