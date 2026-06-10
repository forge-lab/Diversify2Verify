---
name: why3_contract_audit_repair
description: Audit and repair Stage 1A Why3 contract/specification files for array or list benchmarks using the normalized benchmark, generated .mlw file, and type-check or verifier logs.
---

# Why3 Contract Audit and Repair Skill

Use this skill to repair Stage 1A contract/specification outputs in the Diversify2Verify pipeline.

This skill is for fixing generated specifications and specification-test lemmas. It is not for Stage 3 final verification repair.

## Inputs

Use this skill when the user provides or points to some combination of:

- a normalized Diversify2Verify benchmark JSON,
- a Stage 1A `.mlw` specification file,
- a type-check log,
- a verification log,
- a Codex stdout JSONL log,
- a previous repair attempt.

The Stage 1A file usually contains:

- helper predicates/functions,
- a `val` declaration for the target function,
- semantic postconditions,
- concrete proof-style test lemmas.

## Outputs

Produce a repaired Stage 1A `.mlw` file and, when requested by the caller or script, a concise repair report.

Use exact output paths provided by the user, driver script, or orchestration layer. Do not write outside the requested output root.

If no output path is specified, use a clear name such as:

```text
<task_slug>_stage1a_repaired.mlw
<task_slug>_stage1a_repair_report.md
```

## Goal

Repair the contract file while preserving the intended benchmark semantics.

The repaired file should:

- type-check with `why3 prove --type-only`,
- keep a strong mathematical specification,
- avoid overfitting to selected tests,
- include useful concrete test lemmas,
- avoid known Why3 anti-patterns from previous Codex runs.

Full verification is not required unless explicitly requested.

## Workflow

1. Read the normalized benchmark JSON when available.
2. Read the current Stage 1A `.mlw` file.
3. Read the provided type-check, verification, or Codex log.
4. Determine whether the task is array-based or list-based.
5. Consult the corresponding generation skill when present:
   - `why3_array_contract_generation`
   - `why3_list_contract_generation`
6. Consult relevant references under `.agents/references/why3/`.
7. Classify the issue:
   - syntax error,
   - import/use warning or error,
   - type error,
   - predicate used in non-ghost executable context,
   - fragile quantified `if` guard,
   - malformed helper function,
   - malformed test lemma,
   - wrong expected value in a concrete test,
   - underspecified or incorrect semantic contract,
   - verification weakness rather than specification bug.
8. Apply the smallest semantics-preserving repair when possible.
9. Run type-checking:

```bash
why3 prove --type-only <repaired-file>.mlw
```

10. Repeat bounded repairs until the file type-checks or the repair budget is exhausted.

## Repair budget

Use one audit pass plus up to 3 repair iterations unless the caller specifies a different budget.

If the file still does not type-check after the budget is exhausted, report:

- the latest file path,
- the exact command that failed,
- the relevant error output,
- the likely remaining cause.

Do not keep trying indefinitely.

## Specification discipline

Keep specifications strong and faithful to the benchmark.

Do not weaken a contract merely to make test lemmas or verification succeed.

Do not turn a semantic specification into a test-specific specification.

For LeetCode-style total functions, use `requires` only for real input-domain assumptions from the benchmark, not merely to simplify proof obligations.

If the Stage 1A specification is clearly wrong relative to the normalized benchmark, repair it and explicitly document the semantic change in the repair report.

If the benchmark is ambiguous, document the assumption made and prefer the strongest reasonable interpretation consistent with the problem statement and normalized tests.

## Common Stage 1A problems and repairs

### Redundant `use import`

Prefer:

```why3
use int.Int
use array.Array
use array.Init
use list.List
```

instead of:

```why3
use import int.Int
use import array.Array
use import array.Init
use import list.List
```

unless imported unqualified names are necessary.

Before finalizing, grep the repaired file for `use import`. Remove it unless justified.

### Logical predicate used as an executable guard

Why3 may reject this pattern:

```why3
predicate p (a: array int) (i: int) = ...

let rec function count_from (a: array int) (i: int) : int =
  if p a i then 1 else 0
```

with an error like:

```text
Logical symbol p is used in a non-ghost context
```

For array counting, prefer `array.NumOf` or a recursive function whose executable guards are simple comparisons.

For list counting, prefer structural recursion with executable pattern matching and simple comparisons.

### Quantified formula inside `if`

Avoid:

```why3
if forall j: int. P j then ...
```

and avoid large logical conjunctions as executable conditions.

Prefer:

- a transparent predicate used in specifications and assertions,
- direct logical postconditions,
- `array.NumOf` or a structurally recursive list function for counting,
- executable guards that are simple comparisons or Boolean variables.

### Wrong or fragile test lemmas

Concrete test lemmas should help validate the specification, not replace it.

Repair test lemmas by:

- constructing arrays with `array.Init.init` or `make 0 0` for empty arrays,
- asserting lengths immediately,
- asserting concrete element facts,
- enumerating finite domains before proving universal facts,
- asserting contributing and non-contributing cases before aggregate counts,
- correcting expected values only when the normalized tests show they are wrong.

Do not delete difficult tests solely to make the file pass. If a test is redundant, keep enough representative coverage.

### Incorrect helper functions

Do not duplicate standard-library concepts without a reason.

For arrays, check whether the helper should use:

```why3
use array.NumOf
use array.NumOfEq
use array.ArrayEq
use array.IntArraySorted
```

For lists, check whether a structural recursive helper is clearer and easier to verify.

### Bad stdlib probing or filesystem assumptions

Do not hardcode Why3 stdlib paths such as `/Users/.../.opam/.../stdlib/*.mlw`.

If a standard-library detail is needed and local references are insufficient, locate the stdlib with:

```bash
why3 --print-datadir
```

Then inspect only the directly relevant file.

Before searching optional directories such as `generated`, `output`, or example folders, check that they exist. Treat `rg` exit code `1` as “no matches found,” not as a fatal command failure.

## Array-specific repair guidance

Use array-native specifications:

- `length a`
- explicit index bounds,
- universal/existential quantification over indices,
- pairwise quantification for pair problems,
- `array.NumOf` for counting elements satisfying a predicate,
- `array.NumOfEq` for counting occurrences equal to a value.

For a predicate that depends on another array, define a transparent predicate and count values with `array.NumOf`:

```why3
use array.NumOf

predicate good (a2: array int) (x: int) =
  forall j: int. 0 <= j < length a2 -> <condition involving x and a2[j]>

function count_good (a1: array int) (a2: array int) : int =
  numof (fun _ v -> good a2 v) a1 0 (length a1)
```

Do not call `good` as an executable `if` guard in a recursive function.

For pair-counting problems, use a transparent pair predicate for specifications, but keep executable/logical counting definitions free of predicate calls in program-like branches.

## List-specific repair guidance

Use structural recursion over lists:

```why3
let rec function f (l: list int) : int
  variant { l }
=
  match l with
  | Nil -> ...
  | Cons x xs -> ...
  end
```

Avoid array-style index encodings for list tasks unless the benchmark explicitly requires index-like behavior.

Do not invent behavior for `Nil` when the benchmark requires a non-empty list. Preserve real preconditions.

## Validation

Default validation is type-checking only:

```bash
why3 prove --type-only <repaired-file>.mlw
```

If full verification is explicitly requested, use the repository script:

```bash
./scripts/why3-verify.sh <repaired-file>.mlw
```

When wrapping shell commands, do not use `status` as a zsh variable name. Use `exit_code`, `why3_status`, or similar.

If writing a report path, derive the path once, create its parent directory, and reuse the exact same path for writing and reading.

## Repair report format

When a repair report is requested, use this compact format:

```markdown
# Stage 1A Contract Repair Report

## Inputs

- Benchmark JSON:
- Original spec:
- Log:
- Repaired spec:

## Diagnosis

- Classification:
- Root cause:
- Why this is a contract/spec issue rather than final-verification issue:

## Changes

- Semantic changes:
- Non-semantic cleanup:
- Test lemma changes:

## Validation

```bash
why3 prove --type-only <repaired-file>.mlw
```

Result:
```

If semantics changed, make that explicit. If semantics did not change, say so.

## What to avoid

- Do not repair Stage 3 final verification files with this skill.
- Do not weaken specs merely to prove tests.
- Do not delete meaningful normalized-test coverage without explanation.
- Do not add axioms unless explicitly requested and justified.
- Do not silently change benchmark semantics.
