"""End-to-end smoke test — runs one cell of the matrix on a fresh checkout.
Verifies the entire pipeline works in under 30 minutes and ~$2.

Run as: uv run python scripts/smoke_test.py
"""
from __future__ import annotations
import os, sys, time
from dotenv import load_dotenv

load_dotenv()
if "ANTHROPIC_API_KEY" not in os.environ:
    print("ERROR: ANTHROPIC_API_KEY not set in .env", file=sys.stderr)
    sys.exit(2)

import harness.runner as runner
from harness.types import RunSpec
from isolation.docker import DockerIsolation, GVisorIsolation
from frameworks.anthropic_native import AnthropicNativeFramework
from scenarios.s00_benign import S00Benign
from scenarios.s01_injection_web import S01InjectionWeb

runner.ISOLATION_REGISTRY = {"docker": DockerIsolation(), "gvisor": GVisorIsolation()}
runner.FRAMEWORK_REGISTRY = {"anthropic_native": AnthropicNativeFramework()}
runner.SCENARIO_REGISTRY = {"s00_benign": S00Benign, "s01_injection_web": S01InjectionWeb}

t0 = time.time()
results = []
for scenario in ["s00_benign", "s01_injection_web"]:
    for iso in ["docker", "gvisor"]:
        for seed in range(3):
            spec = RunSpec(
                framework_id="anthropic_native", isolation_id=iso,
                scenario_id=scenario, model=os.environ.get("PRIMARY_MODEL", "claude-haiku-4-5-20251001"),
                seed=seed, max_steps=10,
            )
            print(f"→ {iso}/{scenario}/{seed}")
            r = runner.run_one(spec, campaign_id="smoke")
            results.append(r)

elapsed = time.time() - t0
total_cost = sum(r.cost_usd for r in results)
errors = sum(1 for r in results if r.error)

print(f"\n=== SMOKE TEST RESULT ===")
print(f"Runs: {len(results)}  Time: {elapsed/60:.1f} min  Cost: ${total_cost:.2f}  Errors: {errors}")

if errors > len(results) // 4:
    print("FAIL: too many runtime errors")
    sys.exit(1)
if elapsed > 30 * 60:
    print("WARN: smoke test took longer than 30 minutes")
if total_cost > 5.0:
    print("WARN: smoke test cost more than $5")

print("PASS")
