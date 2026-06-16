"""Run the MVP matrix: 1 framework × 2 isolations × 4 scenarios × N runs."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

import harness.runner as runner
from frameworks.anthropic_native import AnthropicNativeFramework
from harness.types import RunSpec, run_resume_key
from isolation.docker import DockerIsolation, GVisorIsolation
from scenarios.s00_benign import S00Benign
from scenarios.s01_injection_web import S01InjectionWeb
from scenarios.s02_poisoned_tool import S02PoisonedTool
from scenarios.s04_cred_canary import S04CredCanary

load_dotenv()

runner.ISOLATION_REGISTRY = {
    "docker": DockerIsolation(),
    "gvisor": GVisorIsolation(),
}
runner.FRAMEWORK_REGISTRY = {
    "anthropic_native": AnthropicNativeFramework(),
}
runner.SCENARIO_REGISTRY = {
    "s00_benign": S00Benign,
    "s01_injection_web": S01InjectionWeb,
    "s02_poisoned_tool": S02PoisonedTool,
    "s04_cred_canary": S04CredCanary,
}

MODEL = os.environ.get("PRIMARY_MODEL", "claude-opus-4-7")
N_RUNS = int(os.environ.get("MVP_N_RUNS", "20"))
RESULTS_PATH = Path(os.environ.get("RESULTS_DIR", "./results")) / "mvp_runs.jsonl"


def main():
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    done = set()
    if RESULTS_PATH.exists():
        for line in RESULTS_PATH.read_text().splitlines():
            try:
                record = json.loads(line)
                done.add(record.get("resume_key") or run_resume_key(record))
            except (json.JSONDecodeError, KeyError):
                continue

    for framework_id in ["anthropic_native"]:
        for isolation_id in ["docker", "gvisor"]:
            for scenario_id in [
                "s00_benign",
                "s01_injection_web",
                "s02_poisoned_tool",
                "s04_cred_canary",
            ]:
                for seed in range(N_RUNS):
                    spec = RunSpec(
                        framework_id=framework_id,
                        isolation_id=isolation_id,
                        scenario_id=scenario_id,
                        model=MODEL,
                        seed=seed,
                        max_steps=20,
                    )
                    if spec.resume_key() in done:
                        continue
                    print(f"→ {framework_id} / {isolation_id} / {scenario_id} / seed={seed}")
                    result = runner.run_one(spec, campaign_id="mvp")
                    with RESULTS_PATH.open("a") as f:
                        f.write(result.to_jsonl() + "\n")
                    cats = [c.value for c in result.escape_categories]
                    print(f"  escaped={result.escaped} cats={cats} cost=${result.cost_usd:.3f}")


if __name__ == "__main__":
    main()
