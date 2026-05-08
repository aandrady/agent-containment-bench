"""Standard tool definitions used by all frameworks.

Tool execution always happens *inside* the sandbox via SandboxHandle.exec().
Tool *definitions* (schemas) are framework-agnostic; per-framework adapters
translate them into Anthropic / OpenAI / LangChain shapes.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import shlex
import time

from harness.types import ToolCall
from isolation.base import SandboxHandle


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]   # JSON Schema (Anthropic-style)


SHELL_TOOL = ToolSpec(
    name="shell",
    description="Execute a bash command. Returns stdout+stderr.",
    input_schema={
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
)

FILE_READ_TOOL = ToolSpec(
    name="file_read",
    description="Read the contents of a text file.",
    input_schema={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
)

FILE_WRITE_TOOL = ToolSpec(
    name="file_write",
    description="Write content to a file. Creates parent dirs as needed.",
    input_schema={
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
    },
)

HTTP_GET_TOOL = ToolSpec(
    name="http_get",
    description="Fetch a URL with HTTP GET. Returns the response body (truncated to 8KB).",
    input_schema={
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
    },
)

STANDARD_TOOLS = [SHELL_TOOL, FILE_READ_TOOL, FILE_WRITE_TOOL, HTTP_GET_TOOL]


def execute_tool(
    handle: SandboxHandle, tool_name: str, args: dict[str, Any]
) -> ToolCall:
    """Execute a tool inside the sandbox; return a structured record."""
    started = time.time()
    if tool_name == "shell":
        cmd = args.get("command", "")
        ec, out = handle.exec(["bash", "-lc", cmd])
        result = f"[exit={ec}] {out[:8000]}"
    elif tool_name == "file_read":
        path = args.get("path", "")
        ec, out = handle.exec(["bash", "-lc", f"cat -- {shlex.quote(path)}"])
        result = out[:8000] if ec == 0 else f"[error] {out}"
    elif tool_name == "file_write":
        path = args.get("path", "")
        content = args.get("content", "")
        try:
            handle.write_file(path, content)
            result = f"wrote {len(content)} bytes to {path}"
        except Exception as e:
            result = f"[error] {e}"
    elif tool_name == "http_get":
        url = args.get("url", "")
        ec, out = handle.exec(
            ["bash", "-lc", f"curl -sSL --max-time 10 {shlex.quote(url)} | head -c 8192"]
        )
        result = out if ec == 0 else f"[error] {out}"
    else:
        from canaries.tools import handle_canary_tool
        result = handle_canary_tool(handle, tool_name, args)

    return ToolCall(
        tool_name=tool_name,
        arguments=args,
        result=result,
        timestamp=started,
        duration_s=time.time() - started,
    )
