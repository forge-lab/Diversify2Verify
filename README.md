# Diversify2Verify Artifact Bundle

This repository contains artifacts from the paper ***Diversifying to Verify: When Task-Equivalent Programs Differ in Verifiability***.

## Abstract

Program verification is crucial for software correctness, but producing fully verified programs remains difficult in practice.  
This paper studies whether implementation structure affects automated verifiability when multiple generated programs are intended to satisfy the same task-level semantics.
Diversify2Verify presents a staged LLM-based pipeline for Why3 that infers representation-specific contracts, generates and tests diverse recursive and imperative array/list implementations, and attempts verification with bounded verifier-guided annotation repair.
We also construct a verification-oriented benchmark of 73 tasks over integers, arrays, and lists, yielding 292 implementation variants. Diversify2Verify verifies 96 artifacts initially and 154 after two repair passes, improving artifact-level verification from 32.9% to 52.7%. At the task level, at least one variant verifies for 49 of 73 tasks, a 67.1% success rate. These results show that task-equivalent implementations can differ substantially in verifiability and that implementation diversity helps find verification-friendly artifacts.

## Contents

- `README.md` — this guide.
- `diversify2verify.html` — high-level run report with task/implementation statistics.
- `dataset/` — benchmark archive with 73 tasks.
  - `description/` — task definitions.
  - `contracts/` — representation-specific contract files (`list` and `array`).
  - `implementations/` — generated recursive and imperative array/list solutions.
  - `verification/` — initial and repaired artifacts (`initial`, `repair1`, `repair2`) with verification logs and results.
- `LICENSE` — MIT license.

## Quick start

1. Open one of the HTML reports to view summary and per-benchmark results.
2. Browse `dataset/` task directories to inspect generated `.mlw` programs, logs, and contracts for each repair stage.
3. Inspect `verification/` folders for `.verify.log` files and repaired outputs that show verification outcomes per representation.

## Public release notes

This repository is intended for sharing benchmark outputs and report artifacts.  
Code and data are provided under the MIT license.

## License

See [LICENSE](LICENSE).
