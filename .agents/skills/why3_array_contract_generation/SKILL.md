---
name: why3_array_contract_generation
description: Generate a Why3 array specification file and a small set of concrete specification test lemmas from a normalized Diversify2Verify array benchmark JSON.
---

# Why3 Array Contract Generation

Use this skill for Stage 1A of the Diversify2Verify pipeline:

```text
normalized array JSON
  -> PLAN
  -> Why3 array specification file
  -> 5-10 concrete specification test lemmas
  -> Why3 type-check only
```

This skill generates one Why3 `.mlw` specification file for one normalized benchmark whose `target.name` is `"array"`.

The generated file should specify the intended behavior of the target function and include a small number of concrete test lemmas that validate the generated specification. The test lemmas should use intermediate `assert` statements to help Why3 instantiate quantifiers, unfold transparent specification functions, and expose concrete array facts.

Full verification is not part of this skill by default.

## Required input

The input must be a normalized Diversify2Verify JSON file. It should contain:

```text
task.task_id
task.question_id
task.difficulty
target.name
target.language
target.module_name
target.output_file
target.signature.raw
target.signature.function_name
target.signature.parameters
target.signature.return
problem.description
tests
normalization
```

Require:

```json
"target": {
  "name": "array",
  "language": "why3"
}
```

If `target.name` is not `"array"`, stop and report that this skill only handles array benchmarks.

Use only the normalized `tests` array. Do not parse the original raw Python `test` string.

## Required outputs

Generate:

```text
generated/plans/array/<task_id>.array.plan.md
<target.output_file>
```

Use `target.output_file` when no caller-specific output path is provided.

If the user prompt, driver script, or orchestration layer provides explicit output paths or an explicit output root, follow those exact paths. In that case, it is acceptable for the generated `.mlw` path to be the requested output root plus `target.output_file`.

Do not write Stage 1A outputs outside the requested output root when one is provided.

## Reference files

Before generating imports or helper functions, read these references when present:

```text
.agents/references/why3/stdlib_policy.md
.agents/references/why3/stdlib_int.md
.agents/references/why3/stdlib_bool.md
.agents/references/why3/stdlib_array.md
```

Read additional references only when needed:

```text
.agents/references/why3/stdlib_list.md
.agents/references/why3/stdlib_map.md
.agents/references/why3/stdlib_set.md
```

Prefer Why3 standard-library functions and predicates when available. Do not define local helpers for generic concepts such as absolute value, min, max, array equality, sortedness, occurrence counting, or sums unless justified in the PLAN.

Useful examples for this skill should be stored in:

```text
.agents/skills/why3_array_contract_generation/examples/
```

Expected examples:

```text
.agents/skills/why3_array_contract_generation/examples/count_occurrences_array.mlw
.agents/skills/why3_array_contract_generation/examples/max_array.mlw
.agents/skills/why3_array_contract_generation/examples/sorted_array.mlw
```

Use these examples as style guides:

- `count_occurrences_array.mlw`: recursive specification functions and suffix assertions.
- `max_array.mlw`: existential witnesses, universal bounds, and finite-domain enumeration assertions.
- `sorted_array.mlw`: pairwise quantified predicates, pair assertions, and negative counterexample lemmas.

Do not copy benchmark-specific names from the examples unless they match the current benchmark.

## Workflow

1. Read the normalized JSON.
2. Confirm `target.name = "array"` and `target.language = "why3"`.
3. Read the relevant Why3 reference files.
4. Inspect the array examples if available.
5. Before using optional directories such as `generated`, `output`, or example folders, check that they exist. Treat `rg` exit code `1` as “no matches,” not as a fatal error.
6. Extract:
   - task id from `task.task_id`;
   - module name from `target.module_name`;
   - output path from `target.output_file`;
   - function name from `target.signature.function_name`;
   - raw signature from `target.signature.raw`;
   - parameters from `target.signature.parameters`;
   - return type from `target.signature.return`;
   - problem description from `problem.description`;
   - normalized tests from `tests`.
7. Select 5-10 tests deterministically, defaulting to 7.
8. Write a compact PLAN.
9. Generate the Why3 `.mlw` file.
10. Run type-checking only:

```bash
why3 prove --type-only <generated-file>.mlw
```

11. Fix syntax, import, and type errors if needed.
12. Re-run the same type-check command after each fix.
13. Before finalizing, grep the generated file for `use import`, predicate calls inside `if` guards, and quantified formulas inside `if` guards.
14. Do not run full verification unless explicitly requested.

## PLAN format

Before writing the Why3 file, create a concise plan:

```markdown
# PLAN: <task_id> / array

## Target

- Module: <target.module_name>
- Output file: <resolved output path>
- Function: <target.signature.function_name>
- Signature: <target.signature.raw>

## Semantic summary

Summarize the intended behavior from the problem description in 2-5 sentences.

## Why3 library usage

Used references:
- stdlib_policy.md
- stdlib_int.md
- stdlib_array.md
- stdlib_bool.md, if used
- any additional reference files used

Used theories:
- int.Int
- array.Array
- array.Init
- any additional theories, such as int.Abs, int.NumOf, int.MinMax, array.ArrayEq, array.NumOf, array.NumOfEq, or array.IntArraySorted

Local helpers:
- list each local helper and explain why it is needed
- explicitly justify any helper that duplicates a standard-library concept

## Contract design

List the helper predicates/functions and the final postcondition.

## Selected test lemmas

List the selected test ids and explain the coverage briefly.

## Test lemma proof strategy

For the selected tests, identify the main proof style:
- recursive computation;
- library counting function;
- existential witness plus universal bound;
- finite-domain universal enumeration;
- pairwise enumeration;
- negative counterexample;
- direct semantic predicate assertion;
- expected-array equality assertion.

## Type-check command

```bash
why3 prove --type-only <resolved output path>
```

## Known-risk patterns checked

Record whether the generated file contains:
- `use import`
- `if <user-defined predicate> then`
- `if forall ... then` or `if exists ... then`
- recursive counting helpers over array indices where `array.NumOf` would be clearer
- custom definitions duplicating standard-library notions
```

Do not include long hidden reasoning traces in the PLAN.

## Generated file shape

Prefer this module structure:

```why3
module <ModuleName>

  use int.Int
  use array.Array
  use array.Init

  (* additional imports only when needed *)

  (* transparent helper predicates/functions *)

  val <target_function> ...
    ensures { ... }

  let lemma test_... () =
    ...

end
```

Hard rule: use `use`, not `use import`, unless importing names is necessary and the PLAN explicitly justifies it.

Before finalizing the `.mlw` file, scan for `use import`. If any occurrence remains without justification, replace it with `use`. In many Why3 modules, `use import` produces a harmless but noisy warning that `import` is redundant.



## Common failure patterns from recent Codex runs

Recent array-spec generation logs showed that most final files eventually type-check, but several avoidable patterns caused repair iterations. Treat these as high-priority checks:

1. Use `use`, not `use import`, unless explicitly justified in the PLAN.
2. Never call a user-defined `predicate` as the condition of an `if` expression inside `let function` or `let rec function`.
3. Do not repair predicate-in-`if` errors by inserting large conjunctive, quantified, or bound-heavy formulas directly into the `if` guard.
4. Prefer `array.NumOf` or `array.NumOfEq` for array counting when they match the semantics.
5. Keep recursive counting helpers only when they express benchmark-specific structure and do not call logical predicates in executable guards.
6. Do not hardcode local Why3 stdlib paths such as `/Users/.../.opam/.../stdlib/*.mlw`; use references or `why3 --print-datadir`.
7. In shell wrappers, do not use `status` as a variable name under zsh; it is read-only.
8. Derive report paths once, create parent directories, and reuse the same variable for writing and reading reports.

## Predicate vs Boolean guards

A Why3 `predicate` is a logical symbol. It is appropriate in postconditions, assertions, quantified formulas, and other ghost/specification contexts. It should not be used as an executable Boolean condition in a recursive function body.

Avoid this pattern:

```why3
predicate good_pair (a: array int) (i: int) (j: int) (target: int) =
  0 <= i < j < length a /\ a[i] + a[j] < target

let rec function count_from (a: array int) (i: int) (j: int) (target: int) : int =
  if good_pair a i j target then 1 else 0
```

Why3 may reject it with:

```text
Logical symbol good_pair is used in a non-ghost context
```

Preferred patterns:

- Use the predicate only in the final contract and concrete test assertions.
- When a recursive helper is necessary, put index bounds in `requires` clauses and recursion structure, then keep the executable `if` guard to a simple comparison such as `a[i] + a[j] < target`.
- When counting array elements satisfying a semantic condition, prefer `array.NumOf.numof` with a transparent predicate.
- When counting equal values, prefer `array.NumOfEq.numof`.

When repairing a non-ghost predicate error, do not replace it with this kind of fragile guard:

```why3
if 0 <= i < j < length a /\ a[i] + a[j] < target then 1 else 0
```

Instead, restructure the helper so the bounds are guaranteed outside the guard, or move the full condition back into a ghost predicate used by the specification.

## Specification philosophy

Prefer direct mathematical specifications.

Use:
- quantified formulas over indices
- explicit bounds
- explicit length constraints
- direct characterizations of the result
- small transparent logical predicates only when they improve readability
- standard-library functions when they directly match the intended property

Avoid:
- opaque pure helper functions that replace the actual contract
- executable-looking specification helpers when a direct formula is clearer
- axioms except as a last resort
- weakening the postcondition just to make test lemmas easier
- overfitting the contract to the selected normalized tests

Prefer branch-free logical specifications.

When writing Why3 preconditions, postconditions, predicates, logical functions, loop invariants, and helper specifications:
- avoid if-then-else expressions whenever possible
- rewrite conditionals using implication, conjunction, and disjunction
- prefer guarded formulas of the form `C -> P`
- when a conditional defines a value, rewrite it as `(C -> R = T) /\ (not C -> R = E)` when this is clearer
- avoid putting conditionals inside quantified formulas unless unavoidable
- for optimization/objective definitions, prefer min/max or relational characterizations over if-then-else
- do not use if-then-else in specifications unless there is no clean logical reformulation

## Expected array reasoning style

Prefer array-native reasoning.

Use:
- `length a`
- explicit index bounds such as `0 <= i < length a`
- universal or existential quantification over indices
- direct position-based properties
- standard array-library modules for common concepts

Examples:
- membership-like properties should usually use an existential quantifier over indices
- pairwise properties should usually quantify over valid index pairs
- optimization properties should usually define valid candidates through indices and bounds
- counting properties should use `array.NumOf` or `array.NumOfEq` when they directly match the meaning

Do not imitate list-style membership or list-native abstractions for arrays when an index-based formulation is clearer.

## Array counting specifications

For array-counting problems, first check whether the intended count is one of these standard forms:

```why3
use array.NumOf
use array.NumOfEq
```

Use `array.NumOf.numof` when counting elements satisfying a predicate over the index and value:

```why3
use array.NumOf

function count_matching (a: array int) : int =
  numof (fun i v -> <condition over i and v>) a 0 (length a)
```

Use `array.NumOfEq.numof` when counting occurrences equal to one value:

```why3
use array.NumOfEq

function count_eq (a: array int) (x: int) : int =
  numof a x 0 (length a)
```

This is usually preferable to defining a recursive `let rec function` over array indices. Recursive counting functions are still acceptable when they express a benchmark-specific recursive decomposition and are easier to prove with suffix assertions, but they should not reimplement generic occurrence counting without a reason.

For predicates that depend on another array, define a transparent predicate for the semantic condition and count values using `array.NumOf`:

```why3
use int.Abs
use array.NumOf

predicate far_from_all (arr2: array int) (x: int) (d: int) =
  forall j: int. 0 <= j < length arr2 -> abs (x - arr2[j]) > d

function distance_value (arr1: array int) (arr2: array int) (d: int) : int =
  numof (fun _ v -> far_from_all arr2 v d) arr1 0 (length arr1)
```

Do not write a recursive count whose `if` guard calls a user-defined logical predicate, for example:

```why3
let rec function count_from (a: array int) (i: int) : int =
  if i = length a then 0
  else (if some_predicate a i then 1 else 0) + count_from a (i + 1)
```

Why3 may reject this pattern with an error such as:

```text
Logical symbol <predicate> is used in a non-ghost context
```

Also avoid putting a quantified formula directly as an `if` guard:

```why3
if forall j: int. P j then 1 else 0
```

This is fragile in Why3 and often leads to syntax/type errors. Prefer `array.NumOf` plus a transparent predicate.


## Pair counting and nested-index specifications

For pair-counting problems, prefer a semantic predicate plus a relational count characterization.

A good semantic predicate is:

```why3
predicate good_pair (nums: array int) (target: int) (i: int) (j: int) =
  0 <= i < j < length nums /\ nums[i] + nums[j] < target
```

Use this predicate in:
- the postcondition;
- helper predicates describing the result;
- assertions inside concrete test lemmas.

Do not use this predicate as an `if` guard in a recursive helper.

If a numeric pair count is needed and there is no direct two-dimensional `array.NumOf` pattern, use a transparent recursive helper only if its guards are simple and its preconditions guarantee bounds. For example, the recursive structure may ensure `0 <= i <= length nums` and `i < j <= length nums`; the branch condition should then be only the benchmark-specific comparison.

For output arrays that enumerate indices or values:
- specify `length result` precisely;
- characterize every valid result position;
- state that every output index points to a valid input index when applicable;
- state ordering or uniqueness constraints when the problem requires them;
- state coverage: every valid input candidate appears somewhere in the output.

## Constraints

Extract explicit constraints from `problem.description` and encode them as:
- `requires` clauses when they are required for the function's intended domain
- explicit validity predicates if useful
- direct mathematical side conditions in the postcondition when appropriate

Examples:
- array length bounds
- element bounds
- valid index ranges
- sortedness
- distinctness
- compatibility between multiple arrays

For LeetCode-style total functions, use `requires` only for real input-domain assumptions from the benchmark, not for facts that merely simplify proofs.

## Concrete test lemmas

Generate 5-10 concrete test lemmas, defaulting to 7 when enough normalized tests are available.

Test lemmas are specification checks, not algorithm implementations. They should:
- construct concrete arrays using `array.Init`
- assert lengths immediately after construction
- assert concrete element facts when useful
- enumerate finite index domains before proving universal facts over small arrays
- assert semantic helper predicates at concrete indices before asserting aggregate predicates
- assert final expected specification facts, such as `result_predicate arr expected` or `count arr = expected`

For concrete arrays, prefer this style:

```why3
let lemma test_000_example () =
  let a = init 3 [|4; 5; 8|] in
  assert { length a = 3 };
  assert { a[0] = 4 };
  assert { a[1] = 5 };
  assert { a[2] = 8 };
  ...
```

For small finite universal claims, add enumeration assertions before the universal property:

```why3
assert {
  forall i: int. 0 <= i < length a ->
    i = 0 \/ i = 1 \/ i = 2
};
```

When a test lemma proves a count, assert the contributing and non-contributing cases explicitly before the aggregate count assertion.

For pair-counting tests, enumerate the finite pair domain explicitly. For an array of length 3, assert facts for `(0,1)`, `(0,2)`, and `(1,2)` before asserting the final count or pair predicate. This helps avoid fragile quantifier instantiation.

Do not add negative tests whose only purpose is to make verification fail. Negative counterexample lemmas are useful only when they prove a positive logical fact, such as `not property concrete_input`.

## Validation

Only type-checking is required by this skill unless the caller explicitly requests deeper verification.

Before running validation:
- create the parent directory of the generated `.mlw` file;
- if writing a report, derive the report path once, create its parent directory, and reuse that exact path;
- do not use `status` as a shell variable name in zsh scripts; use `exit_code` or `why3_status`.

Run:

```bash
why3 prove --type-only <generated-file>.mlw
```

If Why3 reports a syntax, import, or type error:
1. identify the smallest failing pattern;
2. check whether it matches a known failure pattern from this skill;
3. repair the `.mlw` file without weakening the intended semantics;
4. rerun the exact same type-check command;
5. repeat until the file type-checks or the retry budget is exhausted.

If `why3` is unavailable, still produce the PLAN and `.mlw` file and write a type-check report that records that Why3 was unavailable.

## Optional deeper verification

Do not run deeper verification unless explicitly requested by the user, driver script, or orchestration layer.

If deeper verification is requested, use the repository validation script rather than direct custom prover invocations:

```bash
./scripts/why3-verify.sh <filename>
```

When running `./scripts/why3-verify.sh`:

1. Capture the output of the current run into a fresh log file and parse only that log.
2. Use the process exit code as the primary success/failure signal for the current run.
3. If the current run's log contains any of:
   - `VERIFY_RESULT:`
   - `VERIFY_REASON:`
   - `VERIFY_STAGE:`
   - `VERIFY_ROOT_TOTAL:`
   - `VERIFY_ROOT_PROVED:`
   - `VERIFY_ROOT_REMAINING:`
   then treat the last occurrence of each field in that current log as the canonical verification summary.
4. Do not reuse `VERIFY_*` markers from previous runs, previous files, or other logs.
5. Do not infer final verification failure from intermediate prover messages alone.
6. If the process exit code and `VERIFY_RESULT` disagree, explicitly report the inconsistency instead of guessing.

Intermediate `Unknown`, `Timeout`, `Failure`, `HighFailure`, socket issues, or partial subgoal failures do not override a final `VERIFY_RESULT: SUCCESS` from the current run.

## Important note on verification outcomes

Verification is a useful sanity check, but it is not the sole criterion for correctness of the specification.

In particular:
- failure to prove small sanity-check examples does not necessarily mean the specification is wrong
- the prover may be too weak for the generated obligations
- the verification script configuration may be insufficient for that benchmark
- failed proof attempts should be recorded, but they should not automatically be treated as specification errors

If deeper verification fails but the specification remains mathematically sound and faithful to the benchmark, mark it for manual review rather than weakening the specification.

If validation clearly reveals a specification bug or a wrong concrete assertion, repair the specification/test while preserving strong semantics.

## Troubleshooting Why3 and stdlib usage

If a standard-library detail is needed and the local references are insufficient, locate the installed Why3 stdlib with:

```bash
why3 --print-datadir
```

Then inspect only the directly relevant stdlib file, for example:

```bash
sed -n '348,390p' "$(why3 --print-datadir)/stdlib/array.mlw"
```

Do not use:

```bash
why3 config --print-libdir
```

That command is not accepted by some Why3 versions. Also do not run broad searches over unrelated filesystem locations.

Common type-check failures and preferred repairs:

- `Logical symbol <p> is used in a non-ghost context`: look for a program-style `if` whose condition calls a logical predicate. For array-counting specs, replace the recursive helper with `array.NumOf.numof` when applicable.
- `syntax error` near `if forall`: do not use a quantified formula directly as an `if` guard. Rewrite with a predicate and use a direct logical formula or `array.NumOf`.
- syntax errors after expanding an `if` guard with `/\`, `\/`, chained inequalities, or quantifiers: move bounds to `requires`, assertions, or predicates; keep program guards simple.
- redundant `import` warning: remove `import` and keep `use <module>` unless importing is actually needed.
- `rg` exit code `1`: treat as “no matches found,” not as a fatal command failure, unless the match was required.
- `zsh: read-only variable: status`: rename the shell variable to `exit_code`, `why3_status`, or another non-reserved name.
- missing report or stale report contents: ensure the script writes and reads the same freshly-created report path, and never parse a previous run's report as if it belonged to the current file.

## Acceptance criteria

A good array contract file:
- is syntactically valid Why3
- type-checks with `why3 prove --type-only <file>`
- uses array-specific reasoning
- encodes stated constraints
- has strong mathematical postconditions
- uses standard-library notions such as `array.NumOf` when they directly match the intended semantics
- avoids opaque pure-function-based specifications
- avoids axioms unless absolutely necessary
- includes concrete test lemmas that validate representative normalized tests
- keeps test lemmas constructive and proof-oriented, with helpful intermediate assertions
- contains no unjustified `use import`
- avoids predicate calls and quantified formulas inside executable `if` guards

## If the benchmark is ambiguous

If the benchmark is ambiguous:
- infer the strongest reasonable array-side meaning from the description
- use examples only as supporting evidence
- prefer direct mathematical characterization
- avoid underspecification

If no satisfactory array specification can be produced, mark it for manual review.

## Output discipline

When asked to generate files, write exactly the requested PLAN, `.mlw`, and type-check report paths.

Do not generate the list file here.
Do not write outside the requested output root.
Do not include long hidden reasoning traces in generated files.
