"""Standard tool definitions used by all frameworks.

Tool execution always happens *inside* the sandbox via SandboxHandle.exec().
Tool *definitions* (schemas) are framework-agnostic; per-framework adapters
translate them into Anthropic / OpenAI / LangChain shapes.

Tool routing precedence:
  1. Standard tools (shell, file_read, file_write, http_get)
  2. Scenario-registered tools (set per-run via set_scenario_tool_handlers)
  3. Canary tools (only the explicit names in canaries.tools.CANARY_TOOLS)
  4. Unknown → returns an error string (not a canary fire)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
import base64
import shlex
import time

from harness.types import ToolCall
from isolation.base import SandboxHandle


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


# ---- Standard agent tools ----

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
STANDARD_TOOL_NAMES = {t.name for t in STANDARD_TOOLS}


# ---- Scenario-registered tool handlers ----
# A handler takes (sandbox, args) and returns a string result.
ScenarioToolHandler = Callable[[SandboxHandle, dict[str, Any]], str]

_SCENARIO_HANDLERS: dict[str, ScenarioToolHandler] = {}


def set_scenario_tool_handlers(handlers: dict[str, ScenarioToolHandler]) -> None:
    """Replace the current scenario tool handler map. Called by the runner
    between runs so each scenario can register the tools it owns."""
    global _SCENARIO_HANDLERS
    _SCENARIO_HANDLERS = dict(handlers)


def clear_scenario_tool_handlers() -> None:
    global _SCENARIO_HANDLERS
    _SCENARIO_HANDLERS = {}


# ---- Standard tool implementations ----

def _exec_shell(handle: SandboxHandle, command: str) -> str:
    ec, out = handle.exec(["bash", "-lc", command], user="agent")
    return f"[exit={ec}] {out[:8000]}"


def _exec_file_read(handle: SandboxHandle, path: str) -> str:
    ec, out = handle.exec(["bash", "-lc", f"cat -- {shlex.quote(path)}"], user="agent")
    return out[:8000] if ec == 0 else f"[error] {out}"


def _exec_file_write(handle: SandboxHandle, path: str, content: str) -> str:
    """Write a file *as the unprivileged agent user*, so container permissions
    apply. Uses base64 to safely pass arbitrary bytes through bash."""
    b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    cmd = (
        f"mkdir -p -- {shlex.quote(str(__import__('os').path.dirname(path) or '/'))} "
        f"2>/dev/null; "
        f"echo {b64} | base64 -d > {shlex.quote(path)} && echo 'OK ({len(content)} bytes)'"
    )
    ec, out = handle.exec(["bash", "-lc", cmd], user="agent")
    return out.strip() if ec == 0 else f"[error] {out.strip()}"


def _exec_http_get(handle: SandboxHandle, url: str) -> str:
    ec, out = handle.exec(
        ["bash", "-lc", f"curl -sSL --max-time 10 {shlex.quote(url)} | head -c 8192"],
        user="agent",
    )
    return out if ec == 0 else f"[error] {out}"


# ---- Dispatcher ----

def execute_tool(
    handle: SandboxHandle, tool_name: str, args: dict[str, Any]
) -> ToolCall:
    """Execute a tool inside the sandbox; return a structured record."""
    started = time.time()

    if tool_name == "shell":
        result = _exec_shell(handle, args.get("command", ""))
    elif tool_name == "file_read":
        result = _exec_file_read(handle, args.get("path", ""))
    elif tool_name == "file_write":
        result = _exec_file_write(handle, args.get("path", ""), args.get("content", ""))
    elif tool_name == "http_get":
        result = _exec_http_get(handle, args.get("url", ""))
    elif tool_name in _SCENARIO_HANDLERS:
        # Scenario-owned tool (e.g. s02's weather_lookup)
        try:
            result = _SCENARIO_HANDLERS[tool_name](handle, args)
        except Exception as e:
            result = f"[error] scenario handler: {e}"
    else:
        # Canary tools — only fires if tool_name is an actual canary
        from canaries.tools import CANARY_TOOLS, handle_canary_tool
        canary_names = {t.name for t in CANARY_TOOLS}
        if tool_name in canary_names:
            result = handle_canary_tool(handle, tool_name, args)
        else:
            result = f"[error] unknown tool: {tool_name}"

    return ToolCall(
        tool_name=tool_name,
        arguments=args,
        result=result,
        timestamp=started,
        duration_s=time.time() - started,
    )
