"""End-to-end smoke test for a fresh checkout.

Runs a small matrix slice and verifies the whole pipeline works in under
30 minutes and about $2.
"""

from __future__ import annotations

import os
import sys
import time

from dotenv import load_dotenv

import harness.runner as runner
from frameworks.anthropic_native import AnthropicNativeFramework
from harness.types import RunSpec
from isolation.docker import DockerIsolation, GVisorIsolation
from scenarios.s00_benign import S00Benign
from scenarios.s01_injection_web import S01InjectionWeb


def main() -> int:
    load_dotenv()
    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ERROR: ANTHROPIC_API_KEY not set in .env", file=sys.stderr)
        return 2

    runner.ISOLATION_REGISTRY = {"docker": DockerIsolation(), "gvisor": GVisorIsolation()}
    runner.FRAMEWORK_REGISTRY = {"anthropic_native": AnthropicNativeFramework()}
    runner.SCENARIO_REGISTRY = {
        "s00_benign": S00Benign,
        "s01_injection_web": S01InjectionWeb,
    }

    t0 = time.time()
    results = []
    model = os.environ.get("PRIMARY_MODEL", "claude-haiku-4-5-20251001")
    for scenario in ["s00_benign", "s01_injection_web"]:
        for iso in ["docker", "gvisor"]:
            for seed in range(3):
                spec = RunSpec(
                    framework_id="anthropic_native",
                    isolation_id=iso,
                    scenario_id=scenario,
                    model=model,
                    seed=seed,
                    max_steps=10,
                )
                print(f"-> {iso}/{scenario}/{seed}")
                r = runner.run_one(spec, campaign_id="smoke")
                results.append(r)

    elapsed = time.time() - t0
    total_cost = sum(r.cost_usd for r in results)
    errors = sum(1 for r in results if r.error)

    print("\n=== SMOKE TEST RESULT ===")
    print(
        f"Runs: {len(results)}  Time: {elapsed / 60:.1f} min  "
        f"Cost: ${total_cost:.2f}  Errors: {errors}"
    )

    if errors > len(results) // 4:
        print("FAIL: too many runtime errors")
        return 1
    if elapsed > 30 * 60:
        print("WARN: smoke test took longer than 30 minutes")
    if total_cost > 5.0:
        print("WARN: smoke test cost more than $5")

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
