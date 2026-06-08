# Changelog

## 2026-06-01 - Project State and Resumability

### Current project state

- `agent-containment-bench` implements an agent containment benchmark with a fixed tool surface, multiple framework adapters, Docker/gVisor isolation backends, seven scenarios, and post-run escape detection.
- Core code exists for Anthropic native tool use, LangChain tool-calling, Docker/gVisor/gVisor-egress isolation, canary tools, filesystem/credential/network/persistence detection, and matrix runners.
- Current checked-in results are exploratory rather than publication-grade: `results/matrix_runs.jsonl` mixes model labels and historical detection behavior, and the summary CSVs are partial/stale relative to raw JSONL.
- `README.md`, `docs/threat-model.md`, `docs/reproducing.md`, and `docs/related-work.md` are currently empty; `docs/methodology.md` and `docs/blog_post_draft.md` are started.
- Local verification is not green yet: lint reports existing issues, and pytest needs a real `tests/` layout/configuration.

### Changed

- Added deterministic run resume keys derived from `(framework_id, isolation_id, scenario_id, model, seed, max_steps, temperature)`.
- Kept `run_id` as a unique per-execution identifier while using the deterministic resume key for skip decisions.
- Updated MVP and full matrix runners to derive resume keys from both new result rows and older JSONL rows that do not have an explicit `resume_key` field.
- New JSONL rows now include `resume_key` for easier auditing.

### Why

- The previous resume logic skipped by random `run_id`, so rerunning `make matrix` or `make mvp` would schedule duplicate cells and waste API budget.
