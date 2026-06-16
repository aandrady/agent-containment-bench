"""Core types shared across the harness."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class EscapeCategory(StrEnum):
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
    success: bool = True
    step_index: int = -1


@dataclass
class RunSpec:
    framework_id: str  # "anthropic_native" | "langchain_react"
    isolation_id: str  # "docker" | "gvisor" | "gvisor_egress"
    scenario_id: str  # "s00_benign" | "s01_injection_web" | ...
    model: str  # exact snapshot string, e.g. "claude-opus-4-7"
    seed: int
    max_steps: int = 30
    temperature: float = 1.0
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def resume_key(self) -> str:
        return run_resume_key(asdict(self))


RESUME_KEY_FIELDS = (
    "framework_id",
    "isolation_id",
    "scenario_id",
    "model",
    "seed",
    "max_steps",
    "temperature",
)


def run_resume_key(record: dict[str, Any]) -> str:
    """Stable matrix-cell key used for resumability.

    `run_id` intentionally remains unique per execution. Resume decisions need
    the deterministic cell identity instead, otherwise rerunning the matrix
    schedules duplicate work.
    """
    return json.dumps(
        {field: record[field] for field in RESUME_KEY_FIELDS},
        sort_keys=True,
        separators=(",", ":"),
    )


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
    error: str | None = None
    image_digest: str = ""
    first_trigger_step: dict[str, int] = field(default_factory=dict)

    def to_jsonl(self) -> str:
        return json.dumps(
            {
                **asdict(self.spec),
                "run_id": self.spec.run_id,
                "resume_key": self.spec.resume_key(),
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
                "image_digest": self.image_digest,
                "first_trigger_step": self.first_trigger_step,
                "transcript_summary": [
                    {"tool": tc.tool_name, "ok": tc.success, "step": tc.step_index}
                    for tc in self.transcript
                ],
            }
        )
