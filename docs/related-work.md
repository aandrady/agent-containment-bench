# Related Work

This project sits at the intersection of agent security evaluation, prompt-injection research, and sandbox/isolation benchmarking.

## Agent and Prompt-Injection Benchmarks

Existing prompt-injection benchmarks typically measure whether a model follows malicious instructions embedded in untrusted content. This benchmark keeps that concern, but adds containment-specific signals: tool canaries, filesystem tripwires, credential use, network egress, and persistence writes.

## Sandbox and Isolation Systems

Docker, gVisor, Firecracker, and similar systems provide different tradeoffs between compatibility, performance, and isolation. `agent-containment-bench` treats isolation backend and hardening profile as experimental variables while holding model, tools, and scenario constant.

## Canary-Based Evaluation

Canaries are common in security testing because they make boundary crossings observable without using real secrets. This repo uses canary tools, canary files, canary credentials, and canary domains so each escape category has concrete evidence.

## How This Benchmark Differs

The goal is not to prove that a sandbox is secure in the formal sense. The goal is to compare practical escape rates and costs across framework and isolation choices under repeatable adversarial tasks.
