# Reproducing

## Prerequisites

- Docker with permission to build and run containers.
- `uv` for Python environment management.
- `ANTHROPIC_API_KEY` and `GOOGLE_API_KEY` in `.env` for the current framework adapters.
- `runsc` installed and configured as a Docker runtime for gVisor cells.

## Setup

```bash
make setup
make docker-build
```

For the gVisor+egress backend, also build the dnsmasq helper image:

```bash
docker build -t acb-dnsmasq:latest -f sandbox/Dockerfile.dnsmasq sandbox/
```

## Smoke Test

```bash
make smoke
```

The smoke test runs a small Docker/gVisor slice and is intended to catch broken Docker, API, image, or framework wiring before a larger spend.

## MVP Matrix

```bash
MVP_N_RUNS=2 make mvp
```

This writes `results/mvp_runs.jsonl`. Increase `MVP_N_RUNS` when the local environment is stable.

## Full Matrix

```bash
MATRIX_N_RUNS=20 make matrix
```

By default the full matrix uses `docker,gvisor,gvisor_egress` and the Anthropic/LangChain frameworks. Override with comma-separated lists:

```bash
MATRIX_ISOLATIONS=docker_loose,docker,docker_hardened,gvisor,gvisor_hardened,gvisor_egress make matrix
```

Each result row includes a random `run_id` and a deterministic `resume_key` derived from framework, isolation, scenario, model, seed, max steps, and temperature. Re-running the same matrix skips rows whose `resume_key` is already present.

To run only the Google adapter, set `MATRIX_FRAMEWORKS=google_gemini` and `GEMINI_MODEL=gemini-3.5-flash`.

## Analysis Artifacts

```bash
make analysis
```

The analysis step reads `results/matrix_runs.jsonl`, keeps model snapshots separate in grouped outputs, and regenerates:

- `results/matrix_runs.parquet`
- `results/cell_summary.csv`
- `results/cost_per_escape.csv`
- `results/category_breakdown.csv`
- `results/significance_tests.csv`
- `results/heatmap_*.png`
- `results/cost_per_run.png`

Use a different input file with `RESULTS_JSONL=/path/to/runs.jsonl make analysis`.
