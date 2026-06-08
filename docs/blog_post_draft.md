# How often do agents escape their sandbox? A benchmark across Docker, gVisor, and egress-filtered configurations

*Published [DATE]. Code & data: [github.com/.../agent-containment-bench](#)*

---

## tl;dr

We built `agent-containment-bench`, an open-source benchmark that measures sandbox escape behavior of agent frameworks. Across 7 scenarios mapped to OWASP Agentic Top 10, 2 agent frameworks (Anthropic native tool use, LangChain ReAct), and 3 isolation configurations (plain Docker, Docker+gVisor, Docker+gVisor+egress firewall), we ran 840 trials with N=20 per cell.

Three findings:

1. **[FINDING 1 — fill from `results/cell_summary.csv` after matrix run]** — e.g. "Plain Docker hosts allow indirect-injection escape in 65% [CI 41–85%] of runs; egress filtering drops this to 5%."
2. **[FINDING 2]** — e.g. "Framework choice matters more than isolation type for poisoned-tool-description scenarios — both isolations leak at the same rate."
3. **[FINDING 3]** — e.g. "Cost per successful escape ranged from $0.02 (poisoned tool description) to $1.40 (persistence)."

Full data, methodology, and reproducibility instructions in the linked repo.

## Why this exists

[200 words framing — start with the Mythos incident as a hook. Then SandboxEscapeBench as prior art. Then the gap this benchmark fills: it's the first to systematically compare *isolation configurations* with quantitative cost numbers.]

## What we built

[400 words — the architecture, the abstractions, what we held constant, what we varied. Reference the repo for code. End with the components list:
- 7 scenarios (incl. 1 negative control)
- 2 frameworks
- 3 isolation configs
- 1 model (claude-opus-4-7), with secondary sweep on claude-sonnet-4-6
- N=20 per cell, total 840 runs]

## Findings

### Finding 1: [headline]

[3 paragraphs. Lead with the heatmap image (`results/heatmap_anthropic_native.png`). State the numerical claim with CIs. Discuss what's surprising or expected. Connect to the threat model.]

### Finding 2: [headline]

[3 paragraphs. Same shape.]

### Finding 3: [headline]

[3 paragraphs. The cost-per-escape framing is the unique angle — make it concrete. Reference `results/cost_per_escape.csv`.]

### What surprised us

[300 words — pick the single most counterintuitive cell from the matrix. Be honest about what the initial hypothesis was and why the data didn't match.]

## Limitations

- One model family, one model snapshot.
- N=20 → wide CIs on rare-event cells.
- Adversarial scenarios are based on public threat reports; novel attacks not covered.
- Detection mechanisms (canaries, tripwires) are conservative — actual production deployments would need stronger telemetry.
- "Escape" is defined narrowly; a model that *attempts* but fails to invoke a canary tool isn't counted.
- gVisor/runsc has known weaknesses we didn't probe (e.g. /proc surface).
- Single-agent attack surfaces; multi-agent is out of scope.

## Related work

[Pull from `docs/related-work.md`.]

## Reproducing

```
git clone github.com/.../agent-containment-bench
cd agent-containment-bench
cp .env.example .env  # add your ANTHROPIC_API_KEY
make setup
make docker-build
make smoke   # ~30 minutes, ~$2 of API spend
```

Full methodology in `docs/methodology.md`. Threat model in `docs/threat-model.md`.

## What's next

v2 directions:
- Add Firecracker microVM as 4th isolation
- Add OpenAI Assistants or smolagents as 3rd framework
- Expand to scenarios 07–08 (capability escalation, DNS exfil)
- Test on a wider model panel

If you're working in this space, DM me — happy to hear what you'd want from v2.

## Acknowledgments

[Names of reviewers.]

## Appendix A — full results table

[Embed `results/cell_summary.csv`.]

## Appendix B — methodology details

See `docs/methodology.md`.
