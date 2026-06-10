---
name: why3_array_verification
description: Combine a Stage 1A Why3 array specification and a Stage 2A array implementation into a final verified Why3 file with the original semantic contract, the same implementation style, and proof support such as contracts, invariants, variants, assertions, and small helper lemmas.
---

# Why3 Array Verification Skill

Use this skill for Stage 3 of the Diversify2Verify pipeline when the inputs are:

```text
Stage 1A array specification .mlw
Stage 2A array implementation .mlw
  -> final verified Why3 .mlw with implementation + contract + proof support
```

The goal is to produce one final `.mlw` file that verifies against the Stage 1A semantic contract while preserving the Stage 2A implementation style. Add the proof scaffolding needed for verification: preconditions/postconditions, recursive variants, loop invariants, targeted assertions, and small helper lemmas when necessary.

The user may run full verification offline. If full verification is explicitly requested by the user, inspect and reuse `scripts/why3-verify.sh` rather than replacing it or hardcoding all Why3 prover commands.

## Required inputs

Use this skill when the user provides or points to:

- a Stage 1A array specification file,
- a Stage 2A recursive or imperative array implementation file,
- optionally, the original benchmark JSON,
- optionally, verifier output from a failed Stage 3 attempt.

The Stage 1A file usually contains:

- predicates/functions describing the intended behavior,
- a `val` declaration for the target function,
- proof-style lemma tests.

The Stage 2A file usually contains:

- an executable `let` implementation,
- executable tests,
- no full correctness contract.

## Required output

Generate one final `.mlw` file. If the user, driver script, or orchestration layer provides a requested output path, use it exactly. Otherwise choose a clear name such as:

```text
<task_slug>_stage3_array_recursive.mlw
<task_slug>_stage3_array_imperative.mlw
```

For examples inside this skill, use this layout:

```text
.agents/skills/why3_array_verification/examples/<task_slug>/stage1a_spec.mlw
.agents/skills/why3_array_verification/examples/<task_slug>/stage2a_impl.mlw
.agents/skills/why3_array_verification/examples/<task_slug>/stage3_verified.mlw
```

## Core preservation rules

Stage 3 is verification repair, not specification repair and not implementation redesign.

Do not change the Stage 1A semantic specification. Preserve:

- the target function name,
- the original signature,
- the original preconditions,
- the original semantic postcondition,
- the meaning of Stage 1A helper predicates/functions.

Do not change the implementation style from Stage 2A:

- recursive implementations must remain recursive,
- imperative implementations must remain imperative,
- do not replace an imperative loop with a recursive helper,
- do not replace recursive code with refs/loops,
- do not switch arrays to lists.

Preserve the Stage 2A algorithm as much as possible. You may make proof-oriented local edits such as:

- adding contracts to helper functions,
- adding recursive `variant` clauses,
- adding loop invariants and loop variants,
- adding assertions before/after branches or loops,
- introducing ghost variables only when useful for proof,
- introducing small proof helper predicates or lemmas.

Do not substantially redesign the algorithm just because a different algorithm would be easier to prove. If the Stage 2A implementation appears fundamentally inconsistent with the Stage 1A spec, report that as an implementation repair issue rather than silently replacing it.

If the original benchmark and logs suggest that the Stage 1A specification may be wrong, stop and report that as a separate contract/spec repair issue. Do not silently change the specification as part of Stage 3.

## What to include and omit

The final file should include:

- the Stage 1A semantic helper predicates/functions needed by the contract,
- the target implementation from Stage 2A with the Stage 1A contract attached,
- helper predicates/functions introduced only for proof clarity,
- small helper lemmas only when assertions/invariants are not enough,
- recursive variants for recursive functions,
- loop invariants and loop variants for imperative loops,
- targeted assertions to expose definitions and instantiate quantifiers.

The final file should usually omit:

- Stage 1A concrete lemma tests,
- Stage 2A executable tests,
- `run_tests ()`,
- duplicate or unused predicates/functions,
- proof artifacts unrelated to the final contract,
- axioms.

Never use axioms unless the user explicitly requests them and the output clearly marks the file as relying on an axiom.

## Workflow

1. Read the Stage 1A specification file.
2. Read the Stage 2A implementation file.
3. If a benchmark JSON is provided, use it only for names/context; do not derive or alter the Stage 1A specification from tests.
4. Read relevant Why3 references from `.agents/references/why3/` when present, especially:
   - `stdlib_policy.md`
   - `stdlib_int.md`
   - `stdlib_bool.md`
   - `stdlib_array.md`
5. Inspect local examples in `.agents/skills/why3_array_verification/examples/` when present. Prefer examples matching the implementation style and proof shape:
   - recursive array traversal,
   - imperative array traversal,
   - counting,
   - min/max with witness facts,
   - sortedness/pairwise properties.
6. Identify:
   - module name,
   - target function name,
   - argument types,
   - return type,
   - original preconditions and postconditions,
   - helper predicates/functions from Stage 1A,
   - executable implementation structure from Stage 2A,
   - whether the implementation is recursive or imperative,
   - whether the postcondition requires a witness or existential fact,
   - whether the algorithm uses an improving accumulator such as max/min/best,
   - whether a nested-loop processed-outer/processed-inner invariant is needed.
7. Before writing the final module, choose proof-friendly initial values and invariants:
   - initialize from real witnesses when preconditions guarantee them,
   - avoid sentinel accumulators that force unnecessary disjunctions,
   - plan old/new accumulator facts for updates,
   - plan monotonicity lemmas for processed predicates parameterized by an improving accumulator.
8. Create a final module containing:
   - required imports,
   - preserved Stage 1A specification helpers,
   - derived proof helpers if needed,
   - helper lemmas if needed,
   - Stage 2A implementation with proof scaffolding,
   - the original Stage 1A semantic contract on the target function.
9. Validate the file:
   - always run `why3 prove --type-only <final-file>.mlw` when Why3 is available;
   - run `scripts/why3-verify.sh <final-file>.mlw` only when full verification is explicitly requested.
10. If validation fails, use the current verifier output to add generally useful assertions, invariants, variants, or lemmas. Avoid overfitting to one proof obligation.

## Generated file shape

Prefer this structure:

```why3
module <ModuleName>_Stage3_<RecursiveOrImperative>

  use int.Int
  use array.Array
  use array.Init

  (* additional imports only when needed *)

  (* Stage 1A specification helpers, preserved semantically *)

  (* derived predicates/functions for proof, if needed *)

  (* helper lemmas, only when needed *)

  let <target_function> ...
    requires { <original requires> }
    ensures  { <original ensures> }
  =
    <Stage 2A implementation with proof scaffolding>

end
```

Prefer `use` over `use import` unless importing unqualified names is necessary and justified.


## Proof-friendly first draft construction

Do not create the Stage 3 file by merely attaching the Stage 1A contract to the Stage 2A implementation and waiting for verifier failures. Before the first validation run, choose proof-friendly initial values, invariants, and helper predicates that make the final semantic postcondition easy to maintain.

A good Stage 3 first draft should already contain:

- accumulator invariants that mirror the Stage 1A semantic functions or predicates,
- witness invariants when the postcondition requires existence,
- processed-prefix or processed-suffix invariants for traversals,
- processed-outer and processed-inner invariants for nested loops,
- branch-local assertions that expose arithmetic, array bounds, and definition unfolding,
- small helper lemmas for monotonicity or induction when these are predictably needed.

Prefer a slightly verbose first verified file over a short but fragile file. Local assertions are useful proof breadcrumbs, not noise.

### Prefer real witnesses over sentinel values

If the Stage 1A postcondition requires an existential fact, a witness predicate, or a value known to come from the input array, initialize the accumulator from a real valid witness whenever the precondition guarantees one.

Prefer this shape:

```why3
requires { 1 <= length a }

let best = ref a[0] in
invariant { exists k: int. 0 <= k < !i /\ !best = a[k] }
```

over this weaker shape:

```why3
let best = ref 0 in
invariant { !i = 0 \/ exists k: int. 0 <= k < !i /\ !best = a[k] }
```

For pairwise problems, if the precondition guarantees at least one valid pair, initialize from the first valid pair:

```why3
requires { 2 <= length a }

let best = ref (pair_value a 0 1) in
invariant { has_pair_value a !best }
```

Avoid sentinels such as `0`, `min_int`, or `max_int` when they force disjunctive invariants or make it hard to prove the result has a valid witness.

### Preserve strong invariants unconditionally when possible

Avoid conditional invariants such as:

```why3
invariant { !i = 0 \/ has_witness a !best }
```

when a proof-friendly initialization can establish:

```why3
invariant { has_witness a !best }
```

Conditional invariants are acceptable when no valid witness is available at initialization, for example on possibly empty arrays or search functions where no witness has been found yet.

### Use old/new accumulator facts after updates

When an accumulator may be updated, keep the old value around if previous invariants mention the accumulator:

```why3
let old_best = !best in
if candidate > !best then best := candidate;
assert { old_best <= !best };
```

Then use this monotonic relationship to preserve bounds about already-processed elements or pairs.

### Prefer proved `let lemma` helpers over unexplained bare lemmas

Bare `lemma` declarations are not axioms, but they create global proof obligations that may be difficult for SMT solvers to discharge without guidance. When the lemma is nontrivial, prefer a proved `let lemma` with local assertions:

```why3
let lemma processed_step (...)
  requires { ... }
  ensures  { ... }
=
  assert { ... };
  assert { ... }
```

Use bare `lemma` declarations only for very small facts that are expected to prove automatically.

### Do not delete proof support just because it looks redundant

When repairing a Stage 3 file, preserve useful proof structure unless the verifier confirms it is unnecessary. In particular, do not aggressively remove:

- helper lemma bodies,
- witness invariants,
- monotonicity lemmas,
- branch-local assertions,
- loop-bound assertions,
- assertions that instantiate quantified predicates.

A shorter file is not better if it produces weaker verification conditions.

## Array verification strategy

Prefer array-native reasoning:

- `length a`,
- explicit index bounds such as `0 <= i < length a`,
- prefix/suffix properties over index ranges,
- `array.NumOf` or `array.NumOfEq` when the Stage 1A spec already uses them,
- direct relational invariants over processed indices,
- small lemmas connecting implementation-friendly predicates with the Stage 1A predicate.

Do not imitate list-style membership or structural recursion for arrays when an index-based formulation is clearer.

## Imperative array loops

For loops over arrays, the core invariant is usually a prefix or suffix property that mirrors the already-processed part of the array.

For a traversal from left to right, use invariants like:

```why3
invariant { 0 <= !i <= length a }
invariant { <accumulator> = <specification over range 0..!i> }
variant   { length a - !i }
```

For a traversal from right to left, use invariants like:

```why3
invariant { 0 <= !i <= length a }
invariant { <accumulator> = <specification over range !i..length a> }
variant   { !i }
```

For Boolean scans, use a processed-prefix invariant:

```why3
invariant {
  !ok <->
    forall k: int. 0 <= k < !i -> <property at k>
}
```

For existential search, use:

```why3
invariant {
  not !found ->
    forall k: int. 0 <= k < !i -> not <candidate property at k>
}
invariant {
  !found ->
    exists k: int. 0 <= k < !i /\ <candidate property at k>
}
```

When the implementation stores a witness index, also maintain:

```why3
invariant { !found -> 0 <= !witness < !i }
invariant { !found -> <candidate property at !witness> }
```

For integer accumulators that count matching elements, prefer using the Stage 1A counting function if one exists:

```why3
invariant { !acc = count_matching_prefix a 0 !i }
```

If the Stage 1A spec uses `array.NumOf`, use the corresponding range invariant:

```why3
use array.NumOf

invariant { !acc = numof (fun i v -> <condition over i and v>) a 0 !i }
```

For output arrays, preserve length and per-index relationships:

```why3
invariant { length out = length a }
invariant {
  forall k: int. 0 <= k < !i -> out[k] = <expected value for k>
}
```

If the algorithm updates an output array in place, add invariants for unchanged or unprocessed ranges when needed.

## Recursive array implementations

For recursive implementations over array indices, use an explicit index and variant:

```why3
let rec aux (a: array int) (i: int) : <ret>
  requires { 0 <= i <= length a }
  ensures  { <result relates to suffix or prefix starting at i> }
  variant  { length a - i }
=
  if i = length a then ...
  else ...
```

Attach a contract to each recursive helper strong enough to prove the top-level function. The helper contract should usually describe a prefix or suffix of the Stage 1A specification rather than restating the full top-level contract.

Keep executable guards simple. Do not call logical predicates as executable branch conditions.

## Nested loops and pairwise properties

For pair-counting, pair-search, or pairwise ordering, use nested prefix invariants.

Typical outer-loop invariant:

```why3
invariant {
  acc = <number/result for all completed outer indices 0 <= p < !i>
}
```

Typical inner-loop invariant:

```why3
invariant {
  acc = <number/result for completed outer indices plus current pairs !i, j0..!j>
}
```

For sortedness, an implementation often checks adjacent pairs while the Stage 1A spec may quantify over all ordered pairs. Add lemmas connecting the two notions:

```why3
predicate adjacent_sorted (a: array int) =
  forall i: int. 0 <= i < length a - 1 -> a[i] <= a[i + 1]

let rec lemma adjacent_sorted_between (a: array int) (i: int) (j: int)
  requires { adjacent_sorted a }
  requires { 0 <= i <= j < length a }
  ensures  { a[i] <= a[j] }
  variant  { j - i }
= ...
```

Then prove only the directions needed by the target contract:

```why3
adjacent_sorted a -> sorted_array a
sorted_array a -> adjacent_sorted a
```


## Pairwise optimization pattern

For functions that compute a maximum or minimum over all valid pairs, maintain two kinds of facts:

1. The current best value is produced by some valid processed pair.
2. Every processed pair is bounded by the current best value.

For maximum-style problems, a useful helper shape is:

```why3
predicate processed_outer (a: array int) (best: int) (i: int) =
  forall p q: int.
    0 <= p < i -> p < q < length a -> pair_value a p q <= best

predicate processed_inner (a: array int) (best: int) (i: int) (j: int) =
  forall q: int.
    i < q < j -> pair_value a i q <= best
```

The outer loop should establish that all pairs for completed outer indices are processed. The inner loop should establish that pairs for the current outer index have been processed up to the current inner index.

At the end, add a small lemma or assertion bridge from the processed-loop predicate to the Stage 1A global upper-bound predicate:

```why3
processed_outer a best (length a - 1) -> area_upper_bound a best
```

or the corresponding benchmark-specific upper-bound predicate.

If the accumulator improves, use monotonicity lemmas to preserve processed facts:

```why3
let lemma processed_outer_mono (a: array int) (old new_: int) (i: int)
  requires { old <= new_ }
  requires { processed_outer a old i }
  ensures  { processed_outer a new_ i }
= ...

let lemma processed_inner_mono (a: array int) (old new_: int) (i j: int)
  requires { old <= new_ }
  requires { processed_inner a old i j }
  ensures  { processed_inner a new_ i j }
= ...
```

This pattern is especially useful for best-pair, maximum area, maximum distance, minimum distance, and pairwise scoring benchmarks.

## Maximum/minimum/witness properties

For maximum-like and minimum-like functions over non-empty arrays, maintain both bound and witness facts.

Example invariant shape:

```why3
invariant { 0 <= !best_idx < !i }
invariant { forall k: int. 0 <= k < !i -> a[k] <= a[!best_idx] }
```

If the Stage 1A spec requires a result value rather than an index, keep a witness fact:

```why3
invariant { exists k: int. 0 <= k < !i /\ !best = a[k] }
invariant { forall k: int. 0 <= k < !i -> a[k] <= !best }
```

## Logical/non-ghost separation

Do not use logical predicates as executable branch conditions unless they are executable WhyML functions.

Incorrect:

```why3
predicate good (a: array int) (i: int) = ...

if good a i then ...
```

Correct:

```why3
if <simple executable condition over a[i], i, and parameters> then ...
```

Then prove the relationship to `good` using assertions, lemmas, or the postcondition.

Also avoid quantified formulas directly inside executable `if` guards:

```why3
if forall j: int. P j then ...
```

Put quantified properties in predicates, postconditions, assertions, or lemmas instead.

## Assertions and quantifier instantiation

Add small assertions that expose the exact facts the prover needs.

Useful assertion patterns:

```why3
assert { 0 <= i < length a };
assert { a[i] = <known value> };
assert { <predicate definition instance> };
assert {
  forall k: int. 0 <= k < i + 1 ->
    k < i \/ k = i
};
```

For finite concrete tests or helper lemmas, enumerate small domains explicitly when needed.

For quantified postconditions, assert the quantified formula directly after establishing the pointwise property:

```why3
assert {
  forall k: int. 0 <= k < length a -> <property>
};
```


## First-pass assertion checklist

Before running full verification, add targeted assertions at known proof bottlenecks.

For array bounds:

```why3
assert { 0 <= i < length a };
assert { 0 <= j < length a };
assert { i < j };
```

For local variables that encode specification expressions:

```why3
assert { candidate = pair_value a i j };
assert { lower = min a[i] a[j] };
```

For `min`/`max` branches:

```why3
if x <= y then begin
  assert { min x y = x };
end else begin
  assert { min x y = y };
end
```

For accumulator updates:

```why3
let old_acc = !acc in
...
assert { old_acc <= !acc };  (* maximum-style accumulator *)
assert { !acc <= old_acc };  (* minimum-style accumulator *)
```

For loop exits:

```why3
assert { !i = length a };
assert { forall k: int. 0 <= k < length a -> <property> };
```

For quantified processed predicates, assert the exact instance needed immediately before using it:

```why3
assert { processed_prefix a !acc !i };
assert { 0 <= k < !i };
assert { <property at k follows from processed_prefix> };
```

## Common repair moves

When verification fails, prefer these changes before introducing large new lemmas:

1. Check whether the initial accumulator should come from a real witness instead of a sentinel value.
2. Strengthen loop invariants with bounds for every index used in the loop body.
3. Add accumulator invariants that exactly match the Stage 1A recursive/range function.
4. Add witness invariants for max/min/existential results.
5. Add old/new accumulator assertions after assignments.
6. Add monotonicity lemmas when processed facts must survive an improving accumulator.
7. Add branch-local assertions after assignments to re-establish invariants.
8. Add post-loop assertions that rewrite `!i = length a` or `!i = 0` into the final contract shape.
9. Add a small helper lemma only when the proof needs induction over an index range or a bridge between implementation-friendly and specification-friendly predicates.

Keep helper lemmas local, reusable, and specification-driven. Avoid large benchmark-specific lemmas that merely encode the final answer.

## What to avoid

- Do not switch the benchmark to lists.
- Do not change the Stage 1A semantic specification.
- Do not remove preconditions just to make proofs easier.
- Do not weaken the postcondition to match the implementation.
- Do not change recursive code to imperative code, or imperative code to recursive code.
- Do not substantially replace the Stage 2A algorithm with a different algorithm.
- Do not use logical predicates in non-ghost executable contexts.
- Do not introduce axioms unless explicitly requested and justified.
- Do not add large benchmark-specific lemmas when a small invariant or assertion is enough.
- Do not keep trying indefinitely; report the latest proof failure if the repair budget is exhausted.

## Validation

Always type-check the final file when Why3 is available:

```bash
why3 prove --type-only <final-file>.mlw
```

When deeper verification is requested by the user, driver, or prompt, use the repository validation script if it exists:

```bash
./scripts/why3-verify.sh <final-file>.mlw
```

When running `./scripts/why3-verify.sh`:

1. Capture the output of the current run into a fresh log file.
2. Use the process exit code as the primary success/failure signal.
3. If the current run's log contains `VERIFY_*` summary markers, use the last occurrence of each marker from the current log.
4. Do not reuse `VERIFY_*` markers from previous runs or other files.
5. Do not infer final verification failure from intermediate prover messages alone.
6. If the process exit code and `VERIFY_RESULT` disagree, report the inconsistency.

## If verification remains incomplete

If the file type-checks but full verification does not finish:

- preserve the strongest current file,
- report the unproved obligations,
- explain the likely missing invariant/lemma,
- do not weaken the Stage 1A specification,
- do not replace the Stage 2A algorithm,
- mark the case for manual review if the repair budget is exhausted.
