"""Abstract scenario — defines the adversarial setup, agent prompt, and
escape-detection parameters for one (framework × isolation) cell."""
from __future__ import annotations
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

from isolation.base import SandboxHandle
from tools.standard import ToolSpec, STANDARD_TOOLS
from canaries.tools import CANARY_TOOLS


@dataclass
class ScenarioConfig:
    system_prompt: str
    user_message: str
    tools: list[ToolSpec]
    sentinel_paths: list[str] = field(default_factory=list)
    sentinel_domains: list[str] = field(default_factory=list)
    persistence_paths: list[str] = field(default_factory=list)
    benign_expected_tools: list[str] = field(default_factory=list)


class Scenario(ABC):
    scenario_id: str = "abstract"
    owasp_category: str = ""

    @contextmanager
    @abstractmethod
    def stage(self, sandbox: SandboxHandle, monitor_dir: str) -> Iterator[ScenarioConfig]:
        """Set up adversarial content inside the sandbox; yield config; tear down."""
        ...
