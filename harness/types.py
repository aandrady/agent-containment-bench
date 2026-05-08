"""Core types shared across the harness."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional
import json
import uuid


class EscapeCategory(str, Enum):
    NONE = "none"
    CANARY_FIRE = "canary_fire"
    TRIPWIRE_FS = "tripwire_fs"
    TRIPWIRE_NET = "tripwire_net"
    CRED_USE = "cred_use"
    SYSCALL_DENY = "syscall_deny"
    PERSISTENCE = "persistence"
    RUNTIME_ERROR = "runtime_error"


@dataclass
class ToolCall:
    tool_name: str
    arguments: dict[str, Any]
    result: str
    timestamp: float
    duration_s: float


@dataclass
class RunSpec:
    framework_id: str       # "anthropic_native" | "langchain_react"
    isolation_id: str       # "docker" | "gvisor" | "gvisor_egress"
    scenario_id: str        # "s00_benign" | "s01_injection_web" | ...
    model: str              # exact snapshot string, e.g. "claude-opus-4-7"
    seed: int
    max_steps: int = 30
    temperature: float = 1.0
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class RunResult:
    spec: RunSpec
    escaped: bool
    escape_categories: list[EscapeCategory]
    escape_evidence: list[str]
    steps_taken: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    wall_time_s: float
    transcript: list[ToolCall]
    final_message: str
    started_at: str
    ended_at: str
    error: Optional[str] = None

    def to_jsonl(self) -> str:
        return json.dumps({
            **asdict(self.spec),
            "run_id": self.spec.run_id,
            "escaped": self.escaped,
            "escape_categories": [c.value for c in self.escape_categories],
            "escape_evidence": self.escape_evidence,
            "steps_taken": self.steps_taken,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "wall_time_s": self.wall_time_s,
            "final_message": self.final_message,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "error": self.error,
            "transcript_summary": [
                {"tool": tc.tool_name, "ok": "error" not in tc.result.lower()}
                for tc in self.transcript
            ],
        })
