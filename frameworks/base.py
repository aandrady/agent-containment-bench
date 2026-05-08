"""Abstract framework — drives one agent through a scenario."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass

from harness.types import ToolCall
from isolation.base import SandboxHandle
from tools.standard import ToolSpec


@dataclass
class AgentRun:
    transcript: list[ToolCall]
    final_message: str
    steps_taken: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    error: str | None


class Framework(ABC):
    framework_id: str = "abstract"

    @abstractmethod
    def run_agent(
        self,
        sandbox: SandboxHandle,
        system_prompt: str,
        user_message: str,
        tools: list[ToolSpec],
        model: str,
        max_steps: int,
        temperature: float,
    ) -> AgentRun: ...
