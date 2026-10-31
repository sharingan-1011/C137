"""
tools/__init__.py — registry of all fundamental tools.

Each tool is a plain async Python function.
TOOL_REGISTRY maps tool name → callable, used by agent.py.
TOOL_SCHEMAS  is the OpenAI function-calling schema list passed to the model.
All tools auto-execute — no approval gate.
"""
from backend.tools.shell import shell_exec
from backend.tools.fs import fs_read, fs_write, fs_list, fs_delete
from backend.tools.repl import repl_run
from backend.tools.web import web_fetch, web_search

TOOL_REGISTRY: dict = {
    "shell_exec": shell_exec,
    "fs_read":    fs_read,
    "fs_write":   fs_write,
    "fs_list":    fs_list,
    "fs_delete":  fs_delete,
    "repl_run":   repl_run,
    "web_fetch":  web_fetch,
    "web_search": web_search,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "shell_exec",
            "description": "Run a shell command on the local machine. Returns stdout and stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd":     {"type": "string", "description": "Command to execute"},
                    "cwd":     {"type": "string", "description": "Working directory (optional)"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
                },
                "required": ["cmd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fs_read",
            "description": "Read a file and return its contents as text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":     {"type": "string", "description": "Absolute or relative file path"},
                    "encoding": {"type": "string", "description": "File encoding (default utf-8)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fs_write",
            "description": "Write or overwrite a file with the given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                    "mode":    {"type": "string", "description": "'w' (overwrite) or 'a' (append), default 'w'"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fs_list",
            "description": "List files and directories at a path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":      {"type": "string", "description": "Directory path"},
                    "recursive": {"type": "boolean", "description": "List recursively (default false)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fs_delete",
            "description": "Delete a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":      {"type": "string", "description": "Path to delete"},
                    "recursive": {"type": "boolean", "description": "Delete directory recursively (default false)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "repl_run",
            "description": "Execute Python code in a persistent REPL session. Variables persist between calls within the same session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code":       {"type": "string", "description": "Python code to execute"},
                    "session_id": {"type": "string", "description": "REPL session ID to maintain state (optional)"},
                    "timeout":    {"type": "integer", "description": "Timeout in seconds (default 60)"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch a URL and return the page content as plain text (HTML stripped).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url":      {"type": "string", "description": "URL to fetch"},
                    "timeout":  {"type": "integer", "description": "Timeout in seconds (default 15)"},
                    "raw_html": {"type": "boolean", "description": "Return raw HTML instead of stripped text (default false)"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using DuckDuckGo. Returns top N results with title, URL, and snippet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":       {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results to return (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
]