# Examples for `why3_final_verification_repair`

These examples are intentionally small. They show the repair *pattern* expected during final verification repair:

- preserve the semantic contract;
- preserve recursive vs. imperative style;
- repair proof scaffolding, not the benchmark meaning;
- report the decision in a machine-readable way.

Each example contains:

- `failing_stage3.mlw` — a representative failing final-verification candidate;
- `verifier.log` — a shortened verifier log showing the root failure;
- `repaired_stage3.mlw` — a proof-oriented repair candidate;
- `repair_report.md` — the expected diagnosis style;
- `repair_decision.json` — the expected classification style.
