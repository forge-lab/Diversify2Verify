---
name: why3_final_verification_repair
description: Repair a failing Stage 3 Why3 final-verification file using deeper proof-oriented changes while preserving Stage 1A semantics and the Stage 2A implementation style.
---

# Why3 Final Verification Repair

Use this skill when a Stage 3 Why3 final-verification candidate fails offline verification and the user provides the failing `.mlw` file plus a verifier log.

This is a **final verification repair** skill. It is not the initial Stage 3 generation skill and it is not a Stage 1A contract/spec repair skill.

The goal is to produce a stronger repaired Stage 3 `.mlw` file that is much more likely to verify. Prefer a complete proof-oriented repair over a tiny shallow patch when the verifier failure indicates that the file is missing a real proof story.

The repair may add substantial proof scaffolding:

- stronger contracts on internal helpers,
- recursive variants,
- loop invariants,
- branch-local assertions,
- post-loop bridge assertions,
- ghost variables,
- small proof predicates,
- small proved helper lemmas,
- monotonicity lemmas,
- witness-preservation facts,
- local expression reshaping that exposes proof facts.

The repair must still preserve:

- the Stage 1A semantic specification,
- the benchmark-facing public signature,
- the Stage 2A implementation family: recursive stays recursive; imperative stays imperative.

The user may run full verification offline. If full verification is explicitly requested, inspect and reuse `scripts/why3-verify.sh` rather than replacing it or hardcoding all Why3 prover commands.

## Expected inputs

Typical inputs are:

- failing Stage 3 `.mlw` file;
- verifier log from `scripts/why3-verify.sh` or an equivalent Why3 command;
- optional normalized benchmark JSON;
- optional Stage 1A semantic specification `.mlw`;
- optional Stage 2A implementation `.mlw`;
- optional relevant domain skill:
  - `.agents/skills/why3_array_verification/`
  - `.agents/skills/why3_list_verification/`

## Prompt priority

Follow this precedence order:

1. The explicit user/driver repair prompt.
2. This `why3_final_verification_repair` skill.
3. The relevant domain skill, if present:
   - arrays: `why3_array_verification`
   - lists: `why3_list_verification`
4. The examples in this skill and in the domain skill.
5. Repository-level `AGENTS.md`, if present.

If there is a conflict, preserve the Stage 1A semantic specification and Stage 2A implementation family.

## Repair stance

The repair should be **deeper than minimal patching** when needed.

Do not merely add one assertion next to the failing goal if the whole proof structure is weak. If the verifier log shows that invariants are too weak, a witness is not preserved, monotonic accumulator facts are missing, or processed-prefix/processed-suffix predicates are underspecified, rebuild that part of the proof scaffolding.

A good final repair may be longer than the failing file. That is acceptable when the added material is proof-oriented and does not change the benchmark semantics.

Prefer a verbose, proof-friendly, maintainable file over a short but fragile file.

## Non-negotiable constraints

### Do not change the Stage 1A semantic specification

Do **not** modify the semantic meaning of the Stage 1A spec during final verification repair.

This includes:

- public target contract semantics;
- public preconditions and postconditions that encode benchmark meaning;
- semantic predicates such as `sorted_array`, `max_container_area`, `distance_value_count`, `sorted_list`, etc.;
- semantic logical functions used by the public contract;
- benchmark-facing module/function signature;
- meaning of helper predicates/functions imported or copied from Stage 1A.

If the spec appears wrong, report this separately in `repair_report.md` and `repair_decision.json` using classification `spec_suspected_wrong_but_not_changed`, but do not silently repair the spec in this stage.

Allowed proof-only exception:

- Internal helper contracts may be strengthened when this does not alter benchmark semantics.
- Internal helper predicates may be added when they are proof summaries over the existing semantic spec.
- Internal helper functions may receive well-formedness preconditions such as `0 <= lo <= hi <= length a`, as long as all callers prove those preconditions.
- Redundant or unused proof predicates may be removed when they are not part of Stage 1A semantics.

### Preserve implementation family and algorithmic intent

Do not change the implementation family.

- Recursive implementations must remain recursive.
- Imperative implementations must remain imperative.
- Do not replace loops with a new recursive algorithm.
- Do not replace recursive code with refs/loops.
- Do not switch arrays to lists or lists to arrays.
- Do not replace the core algorithm with a different algorithm merely because the new one is easier to prove.
- Do not remove meaningful branches, exceptions, traversal order, accumulator structure, or early-exit structure unless the change is a local proof-preserving cleanup.

### Minor implementation edits are allowed

Unlike a strictly minimal repair pass, this skill allows small local implementation edits when they improve proof robustness and preserve behavior.

Allowed examples:

- bind complex expressions to local variables;
- bind old accumulator values before updates;
- split a complex assignment into candidate computation plus update;
- introduce ghost variables or ghost local bindings;
- initialize an accumulator from a real witness instead of a sentinel, when the precondition guarantees such a witness and behavior is unchanged;
- add an internal helper function contract or variant;
- add a small helper predicate summarizing processed state;
- add a local proof branch around an existing executable branch;
- add assertions around array/list bounds, constructor shapes, `min`/`max` facts, equality facts, and accumulator updates;
- restructure a loop body locally to expose proof facts, without changing the loop traversal or algorithm;
- replace a proof-only intermediate assertion with a correct weaker or stronger proof sequence.

Disallowed examples:

- change the public contract to match the implementation;
- weaken the final ensures clause;
- remove a required `requires` clause;
- replace an algorithm with a different algorithm;
- change an imperative solution into a recursive one or vice versa;
- add axioms;
- mark a function as `diverges` merely to avoid proving termination, unless divergence is part of the original intended behavior;
- change a result for edge cases covered by the Stage 1A contract;
- silently repair a suspected Stage 1A specification bug.

## Remove tests from the final repaired file unless explicitly requested

The final repaired Stage 3 `.mlw` should usually omit:

- Stage 1A concrete lemma tests;
- Stage 2A executable tests;
- `run_tests ()`;
- test-only helper definitions;
- duplicate generated test scaffolding.

If a test-like lemma proves a reusable fact needed by the final proof, keep only the reusable fact and rename/restate it as a proof lemma.

## Required repair workflow

### 0. Read the verifier log first

Identify the earliest/root failure before editing the code. Later failures are often cascading.

Prioritize log messages about:

- syntax/type errors introduced by a previous repair;
- failed invariant initialization;
- failed invariant preservation;
- failed postcondition;
- unproved assertion;
- variant/termination failure;
- array bound or list pattern well-formedness failure;
- recursive-call precondition failure;
- lemma not proved;
- prover timeout/resource exhaustion.

When several goals fail, repair the weakest common proof structure, not just the first textual assertion.

### 1. Compare against Stage 1A and Stage 2A if available

If Stage 1A spec is provided:

- check that the failing Stage 3 file still contains the same semantic predicates/functions/contracts;
- restore accidental spec drift;
- do not simplify, weaken, or replace the Stage 1A semantic spec.

If Stage 2A implementation is provided:

- check that the failing Stage 3 file preserves recursive vs. imperative style;
- preserve the algorithmic skeleton;
- allow only local proof-oriented edits;
- if a proof-friendly local rewrite changes behavior, do not apply it.

### 2. Build a proof story before editing

Before making repairs, identify the proof story that should make the function verify.

Ask:

- What exact semantic postcondition must be established?
- Is the postcondition a pure equality, Boolean equivalence, upper/lower-bound property, existential witness, or max/min optimality property?
- Does the implementation use an accumulator?
- Does the accumulator need a witness invariant?
- Does the accumulator monotonically improve?
- Are processed-prefix, processed-suffix, processed-outer, or processed-inner predicates needed?
- Does the implementation check a simpler executable property and require a lemma connecting it to the Stage 1A predicate?
- Are recursive helper contracts strong enough?
- Is termination obvious to Why3?
- Are array bounds, list constructor facts, or quantifier instantiations missing?

If the failing file has no coherent proof story, add one.

### 3. Classify the root cause

Choose one primary classification:

- `missing_loop_invariant`
- `weak_loop_invariant`
- `missing_variant_or_termination_argument`
- `missing_assertion_or_instantiation`
- `missing_auxiliary_lemma`
- `missing_monotonicity_lemma`
- `missing_witness_invariant`
- `helper_contract_or_wellformedness_issue`
- `wrong_intermediate_assertion`
- `exception_or_loop_control_invariant_issue`
- `recursive_unfolding_issue`
- `prover_timeout_or_resource_issue`
- `spec_suspected_wrong_but_not_changed`
- `implementation_inconsistent_with_spec`
- `type_or_syntax_error`
- `mixed`
- `unknown`

Use `mixed` when the earliest failure combines multiple causes, for example a weak loop invariant plus a missing helper lemma.

### 4. Repair in a proof-strengthening order

Prefer local repairs when enough. Use deeper repairs when the failing file lacks the needed proof structure.

Recommended order:

1. Fix type/syntax errors introduced by earlier edits.
2. Remove or correct wrong intermediate assertions that are not part of the semantic spec.
3. Add missing variants for recursive functions or loops.
4. Add helper preconditions for well-formedness, especially array indexing and interval recursion.
5. Strengthen recursive helper contracts so each helper proves exactly the suffix/prefix/segment property it computes.
6. Strengthen loop invariants with index/list-shape bounds, accumulator meaning, witness facts, and processed-state facts.
7. Add real-witness initialization when the postcondition requires existence and the precondition guarantees a witness.
8. Add old/new accumulator bindings and monotonicity lemmas when the accumulator improves.
9. Add branch-local assertions to expose facts to the prover.
10. Add post-loop bridge assertions.
11. Add recursive unfolding assertions.
12. Add quantifier-instantiation facts or finite-domain enumeration facts.
13. Add small proved helper lemmas only when local assertions/invariants are insufficient.
14. If the proof appears too hard, report remaining obligations and risks rather than changing the spec or algorithm.

## Deep repair patterns

### Prefer real witnesses over sentinels

If the semantic postcondition requires an existential/witness fact, initialize from a real witness whenever the precondition guarantees one.

Prefer:

```why3
let best = ref a[0] in
invariant { exists k: int. 0 <= k < !i /\ !best = a[k] }
```

over:

```why3
let best = ref 0 in
invariant { !i = 0 \/ exists k: int. 0 <= k < !i /\ !best = a[k] }
```

For pairwise array problems with `requires { 2 <= length a }`, prefer initializing from the first valid pair:

```why3
let best = ref (pair_value a 0 1) in
invariant { has_pair_value a !best }
```

For non-empty list max/min, prefer initializing from the head:

```why3
match l with
| Nil -> absurd
| Cons x xs ->
    let best = ref x in
    ...
end
```

This often removes fragile conditional invariants such as `i = 0 \/ has_witness ...`.

### Preserve witness facts unconditionally when possible

If a valid witness is available at initialization, maintain:

```why3
invariant { has_witness input !best }
```

or:

```why3
invariant { exists k: int. 0 <= k < processed_bound /\ !best = value_at k }
```

Avoid conditional witness invariants unless the input may be empty or the algorithm genuinely has a no-witness initial state.

### Use old/new accumulator facts

When an accumulator is updated conditionally, bind the old value and assert the relationship.

```why3
let old_best = !best in
if candidate > !best then best := candidate;
assert { old_best <= !best };
```

For minima:

```why3
let old_best = !best in
if candidate < !best then best := candidate;
assert { !best <= old_best };
```

Use these facts to preserve previous processed-state invariants.

### Add monotonicity lemmas for processed bounds

When an invariant says all processed elements/pairs are bounded by an accumulator, and the accumulator monotonically improves, add a small lemma.

Example for maximum-like bounds:

```why3
let lemma processed_mono (a: array int) (old new_: int) (i: int)
  requires { old <= new_ }
  requires { processed_prefix a old i }
  ensures  { processed_prefix a new_ i }
=
  assert { forall k: int. 0 <= k < i -> value a k <= new_ }
```

Example for minimum-like bounds:

```why3
let lemma processed_mono_min (a: array int) (old new_: int) (i: int)
  requires { new_ <= old }
  requires { processed_prefix_min a old i }
  ensures  { processed_prefix_min a new_ i }
=
  assert { forall k: int. 0 <= k < i -> new_ <= value a k }
```

Call the lemma explicitly after updating the accumulator.

### Prefer proved `let lemma` helpers over unexplained bare lemmas

Bare lemmas are not axioms, but they create global proof obligations that may be hard for SMT solvers to prove without guidance.

Prefer:

```why3
let lemma processed_step (...)
  requires { ... }
  ensures  { ... }
=
  assert { ... };
  assert { ... }
```

Use a bare `lemma` only when it is very small and expected to be discharged automatically.

Never use `axiom` unless the user explicitly requests it and the output clearly marks the file as relying on an axiom.

### Add local proof breadcrumbs aggressively

Local assertions are not noise in a final verification repair. Add assertions when they expose:

- array bounds before every read/write;
- list constructor facts after each pattern match;
- `length` facts for cursor loops;
- `min`/`max` branch facts;
- arithmetic facts such as `i < j + 1`, `j <= n`, `i + 1 <= n`;
- equality between local variables and spec functions;
- nonnegativity facts;
- old/new accumulator relationships;
- exact predicate instances;
- final loop-bound equalities such as `!i = length a`;
- final cursor shape such as `!cur = Nil`.

Prefer assertions close to the code that needs them.

## Array repair patterns

### Imperative array loop

Common invariant categories:

- index bounds: `0 <= !i <= n`;
- relation between `n` and `length a`;
- bounds for every index used in the loop body;
- accumulator meaning over processed prefix/suffix;
- preservation of untouched arrays if mutation is present;
- witness invariants when returning an index or pair;
- upper/lower-bound invariants for max/min/count problems;
- monotonicity facts for best-so-far values;
- post-loop bridge: when `!i = n`, processed-prefix property implies full-array property.

For left-to-right prefix scans:

```why3
invariant { 0 <= !i <= length a }
invariant { !acc = spec_prefix a 0 !i }
variant   { length a - !i }
```

For right-to-left suffix scans:

```why3
invariant { 0 <= !i <= length a }
invariant { !acc = spec_suffix a !i (length a) }
variant   { !i }
```

### Pairwise array optimization

For pairwise maximum/minimum problems, maintain two kinds of facts:

1. current best has a valid witness pair;
2. all processed pairs are bounded by current best.

Typical helper predicates:

```why3
predicate processed_outer (a: array int) (best: int) (i: int) =
  forall p q: int.
    0 <= p < i -> p < q < length a -> pair_value a p q <= best

predicate processed_inner (a: array int) (best: int) (i: int) (j: int) =
  forall q: int.
    i < q < j -> pair_value a i q <= best
```

Use step lemmas:

- extend `processed_inner` after handling one pair;
- combine completed inner loop into `processed_outer`;
- show final `processed_outer` implies the Stage 1A upper-bound predicate;
- monotonicity when `best` increases.

For preconditions such as `2 <= length a`, initialize from pair `(0, 1)` instead of `0`.

### Recursive array helper over intervals

Common requirements:

- add preconditions such as `0 <= lo <= hi <= length a`;
- prove recursive-call preconditions with explicit assertions;
- use variant `{ hi - lo }` or `{ length a - i }`;
- assert bounds before every `a[i]` read;
- unfold one recursive step before hard assertions;
- add segment-splitting lemmas when the recursive spec uses intervals.

## List repair patterns

### Imperative list cursor loop

Common invariant categories:

- cursor shape and remaining-list measure: `0 <= length !cur`;
- accumulator meaning over processed elements plus `!cur`;
- post-loop fact: `!cur = Nil`;
- branch facts after matching `Cons x xs`;
- exception facts when using `raise`/`try` for early exits.

For count-like functions using `list.NumOcc`:

```why3
invariant { num_occ x !cur + !count = num_occ x l }
variant   { length !cur }
```

For sum-like recursive specs:

```why3
invariant { !acc + sum_list !cur = sum_list l }
variant   { length !cur }
```

For Boolean scans, preserve both directions when the final contract is an equivalence.

### Recursive list helper

Common requirements:

- use variant `{ l }` or a structurally smaller tail;
- assert unfolding facts for `Nil` and `Cons` cases;
- add helper lemmas over `Cons` only when repeated local unfolding is not enough;
- preserve structural recursion;
- strengthen helper postconditions to relate the result to the exact current suffix.

### Non-empty list max/min

For specs with `requires { l <> Nil }`, initialize from the head and scan the tail.

Maintain both membership/witness and bound facts:

```why3
invariant { mem !best l }
invariant { forall x: int. mem x processed_part -> x <= !best }
```

If no explicit processed-prefix representation exists, use a helper predicate summarizing the processed portion or a recursive helper with a strong postcondition.

### Sortedness and adjacent checks

When implementation checks adjacent pairs but Stage 1A uses pairwise sortedness, add lemmas connecting the executable/adjacent property to the semantic predicate.

For lists, common lemmas include:

- weakening `le_all` from a smaller head;
- sorted tail from sorted list;
- adjacent sorted implies semantic sorted;
- semantic sorted implies adjacent relation if needed.

## Exception and early-exit repairs

If the implementation uses exceptions for early exit, preserve that structure.

Add facts before each `raise`:

- the semantic predicate is false;
- a counterexample exists;
- the Boolean postcondition for the exceptional path will hold.

In the `with` branch, assert or maintain a ghost/ref fact that connects the exception to the returned result.

Do not remove exceptions merely to simplify verification.

## Recursive unfolding and matching repairs

For recursive functions, after matching on a value, assert one-step unfoldings when needed.

Example:

```why3
assert { count x (Cons y ys) = (if y = x then 1 else 0) + count x ys };
```

For list predicates:

```why3
assert { sorted_list (Cons x xs) <-> le_all x xs /\ sorted_list xs };
```

For negative branches, explicitly show contradiction:

```why3
assert { x > y };
assert { sorted_list (Cons x (Cons y ys)) -> x <= y };
assert { not sorted_list (Cons x (Cons y ys)) };
```

## Quantifier-instantiation repairs

When a quantified postcondition or invariant is not triggered, add exact instantiation facts.

Examples:

```why3
assert { 0 <= i < length a };
assert { valid_pair a i j };
assert { pair_value a i j <= !best };
assert {
  forall k: int. 0 <= k < i + 1 ->
    k < i \/ k = i
};
```

For finite domains in concrete helper lemmas, enumerate cases explicitly.

Avoid adding a large quantified lemma if a local instantiation assertion is enough.

## Wrong intermediate assertion

Intermediate assertions added during Stage 3 are allowed to be changed or removed if they are false, too strong, or badly shaped for SMT.

Do not confuse a wrong intermediate assertion with a wrong semantic spec. If an assertion was introduced only to help the prover, fix the assertion/proof scaffolding and leave the spec unchanged.

## Auxiliary lemma quality bar

Good lemmas are:

- small;
- local to the needed helper predicate/function;
- inductive over a simple integer interval or list tail;
- stated using existing semantic helpers rather than redefining the spec;
- explicitly called near the proof obligation they support;
- proved with `let lemma` and simple assertions or structural recursion when nontrivial.

Avoid:

- broad lemmas with many quantified variables;
- benchmark-specific lemmas that simply restate the final contract;
- lemmas that silently change the meaning of a Stage 1A helper;
- axioms.

## Prover-timeout repair

If the log shows timeouts rather than clear invalid VCs:

1. Split large assertions into smaller assertions.
2. Add local instantiation facts near the use site.
3. Replace one large lemma with smaller step lemmas.
4. Add `let lemma` proof bodies with explicit calls.
5. Avoid overly strong invariants with unrelated quantified facts.
6. Remove unused helper predicates and unused imports.
7. Prefer range-specific predicates over global quantified facts when possible.

Do not weaken the final contract to avoid timeouts.

## Validation policy

The user may run full verification offline. Do not assume you can finish full verification inside the repair stage unless the prompt explicitly allows it.

Always type-check the repaired file if `why3` is available:

```bash
why3 prove --type-only <repaired-file>.mlw
```

If full verification is allowed by the prompt, prefer the repository script if present:

```bash
scripts/why3-verify.sh <repaired-file>.mlw
```

When using the repository script:

1. Capture output into a fresh log file.
2. Use the process exit code as the primary success/failure signal.
3. If the log contains `VERIFY_*` summary markers, use the last occurrence from the current log.
4. Do not reuse `VERIFY_*` markers from previous runs or other files.
5. If exit code and `VERIFY_RESULT` disagree, report the inconsistency.

If full verification is not allowed or not available, write the exact offline command the user should run next.

## Required outputs

Create these outputs exactly when requested by the driver:

1. repaired `.mlw` file;
2. `repair_report.md`;
3. `repair_decision.json`;
4. unified diff from failing file to repaired file;
5. type-check log if Why3 is available.

If the driver only requests a repaired `.mlw`, still include a concise repair summary in the final response.

## `repair_report.md` format

Use this structure:

```markdown
# Final Verification Repair Report

## Suspected root cause

...

## Log evidence

...

## Spec preservation audit

...

## Implementation preservation audit

...

## Repair changes

...

## Validation

...

## Remaining risks

...

## Offline verification command

```bash
scripts/why3-verify.sh path/to/repaired.mlw
```
```

Keep the report practical and concise. Include line numbers, source locations, or goal names from the verifier log when available.

## `repair_decision.json` schema

Create a JSON object with at least these fields:

```json
{
  "classification": "missing_loop_invariant",
  "confidence": 0.82,
  "changed_spec": false,
  "changed_public_signature": false,
  "changed_implementation_strategy": false,
  "changed_core_algorithm": false,
  "minor_implementation_edits": true,
  "removed_tests_only": false,
  "added_invariants": [
    "invariant over processed prefix/suffix with explicit bounds"
  ],
  "added_variants": [
    "length a - !i"
  ],
  "added_assertions": [
    "array access bounds preserved at each step"
  ],
  "added_lemmas": [
    "monotonicity lemma for processed-prefix bound"
  ],
  "changed_helper_contracts": [
    "added recursive interval preconditions where needed"
  ],
  "implementation_edits_summary": [
    "bound candidate value before updating accumulator"
  ],
  "skill_example_pattern_used": "array_pairwise_optimization",
  "root_cause_summary": "...",
  "spec_preservation_summary": "...",
  "implementation_preservation_summary": "...",
  "repair_summary": ["..."],
  "key_log_locations": ["..."],
  "key_source_locations": ["..."],
  "typecheck_command": "why3 prove --type-only ...",
  "typecheck_exit_code": 0,
  "offline_verification_command": "scripts/why3-verify.sh ...",
  "remaining_risks": ["..."]
}
```

Set `changed_spec` to `false` unless the explicit prompt overrides this skill. In the Diversify2Verify final verification repair stage, the default is always `changed_spec: false`.

If the spec appears wrong but was not changed, use classification `spec_suspected_wrong_but_not_changed` and explain it in `remaining_risks`.

If the implementation appears inconsistent with the spec, use classification `implementation_inconsistent_with_spec` and avoid replacing it with a different algorithm unless the prompt explicitly requests implementation repair beyond Stage 3 proof repair.

## Final response

End with a short summary containing paths to:

- repaired `.mlw`;
- report;
- decision JSON;
- diff;
- type-check log/status;
- offline verification command.

Also state explicitly whether:

- the Stage 1A semantic specification was preserved;
- the public signature was preserved;
- the recursive/imperative implementation family was preserved;
- any minor local implementation edits were made.
