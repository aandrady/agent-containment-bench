"""Run the full matrix: 2 frameworks × 3 isolations × 7 scenarios × N runs."""
from __future__ import annotations
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

import harness.runner as runner
from harness.types import RunSpec, run_resume_key
from isolation.docker import (
    DockerIsolation, DockerLooseIsolation, DockerHardenedIsolation,
    GVisorIsolation, GVisorHardenedIsolation,
)
from isolation.gvisor_egress import GVisorEgressIsolation
from frameworks.anthropic_native import AnthropicNativeFramework
from frameworks.langchain_react import LangChainReActFramework
from scenarios.s00_benign import S00Benign
from scenarios.s01_injection_web import S01InjectionWeb
from scenarios.s02_poisoned_tool import S02PoisonedTool
from scenarios.s03_filesystem_traversal import S03FilesystemTraversal
from scenarios.s04_cred_canary import S04CredCanary
from scenarios.s05_egress import S05Egress
from scenarios.s06_persistence import S06Persistence

load_dotenv()

# Default matrix axis: hardening as a study variable.
# Set MATRIX_ISOLATIONS env var to override (comma-separated list of isolation_ids).
_ALL_ISOLATIONS = [
    "docker_loose", "docker", "docker_hardened",
    "gvisor", "gvisor_hardened", "gvisor_egress",
]
ISOLATIONS = (
    os.environ.get("MATRIX_ISOLATIONS", "docker,gvisor,gvisor_egress").split(",")
)
FRAMEWORKS = ["anthropic_native", "langchain_react"]
SCENARIOS = [
    "s00_benign", "s01_injection_web", "s02_poisoned_tool",
    "s03_fs_traversal", "s04_cred_canary", "s05_egress", "s06_persistence",
]

MODEL = os.environ.get("PRIMARY_MODEL", "claude-opus-4-7")
N_RUNS = int(os.environ.get("MATRIX_N_RUNS", "20"))
PARALLELISM = int(os.environ.get("MATRIX_PARALLELISM", "2"))
RESULTS_PATH = Path(os.environ.get("RESULTS_DIR", "./results")) / "matrix_runs.jsonl"


def init_registries():
    runner.ISOLATION_REGISTRY = {
        "docker_loose": DockerLooseIsolation(),
        "docker": DockerIsolation(),
        "docker_hardened": DockerHardenedIsolation(),
        "gvisor": GVisorIsolation(),
        "gvisor_hardened": GVisorHardenedIsolation(),
        "gvisor_egress": GVisorEgressIsolation(),
    }
    runner.FRAMEWORK_REGISTRY = {
        "anthropic_native": AnthropicNativeFramework(),
        "langchain_react": LangChainReActFramework(),
    }
    runner.SCENARIO_REGISTRY = {
        "s00_benign": S00Benign,
        "s01_injection_web": S01InjectionWeb,
        "s02_poisoned_tool": S02PoisonedTool,
        "s03_fs_traversal": S03FilesystemTraversal,
        "s04_cred_canary": S04CredCanary,
        "s05_egress": S05Egress,
        "s06_persistence": S06Persistence,
    }


def _run(spec: RunSpec):
    init_registries()
    return runner.run_one(spec, campaign_id="matrix-v1")


def main():
    init_registries()
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[RunSpec] = []
    for fw in FRAMEWORKS:
        for iso in ISOLATIONS:
            for sc in SCENARIOS:
                for seed in range(N_RUNS):
                    jobs.append(RunSpec(
                        framework_id=fw, isolation_id=iso, scenario_id=sc,
                        model=MODEL, seed=seed, max_steps=20,
                    ))

    done = set()
    if RESULTS_PATH.exists():
        for line in RESULTS_PATH.read_text().splitlines():
            try:
                record = json.loads(line)
                done.add(record.get("resume_key") or run_resume_key(record))
            except Exception:
                pass
    pending = [j for j in jobs if j.resume_key() not in done]
    print(f"Total jobs: {len(jobs)}, done: {len(done)}, pending: {len(pending)}",
          file=sys.stderr)

    with ProcessPoolExecutor(max_workers=PARALLELISM) as ex:
        futures = {ex.submit(_run, spec): spec for spec in pending}
        for fut in as_completed(futures):
            spec = futures[fut]
            try:
                result = fut.result()
                with RESULTS_PATH.open("a") as f:
                    f.write(result.to_jsonl() + "\n")
                print(f"✓ {spec.framework_id}/{spec.isolation_id}/{spec.scenario_id}/"
                      f"{spec.seed}: esc={result.escaped} ${result.cost_usd:.3f}")
            except Exception as e:
                print(f"✗ {spec.run_id[:8]}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
