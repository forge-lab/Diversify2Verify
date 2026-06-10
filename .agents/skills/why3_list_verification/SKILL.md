---
name: why3_list_verification
description: Combine a Stage 1A Why3 list specification and a Stage 2A list implementation into a final verified Why3 file with the original semantic contract, the same implementation style, and proof support such as contracts, variants, invariants, assertions, and small helper lemmas.
---

# Why3 List Verification Skill

Use this skill for Stage 3 of the Diversify2Verify pipeline when the inputs are:

```text
Stage 1A list specification .mlw
Stage 2A list implementation .mlw
  -> final verified Why3 .mlw with implementation + contract + proof support
```

The goal is to produce one final `.mlw` file that verifies against the Stage 1A semantic contract while preserving the Stage 2A implementation style. Add the proof scaffolding needed for verification: preconditions/postconditions, recursive variants, loop invariants, targeted assertions, and small helper lemmas when necessary.

The user may run full verification offline. If full verification is explicitly requested by the user, inspect and reuse `scripts/why3-verify.sh` rather than replacing it or hardcoding all Why3 prover commands.

## Required inputs

Use this skill when the user provides or points to:

- a Stage 1A list specification file,
- a Stage 2A recursive or imperative list implementation file,
- optionally, the original benchmark JSON,
- optionally, verifier output from a failed Stage 3 attempt.

The Stage 1A file usually contains:

- recursive predicates/functions describing the intended behavior,
- helper predicates/functions such as sortedness, membership, counting, max/min, prefix/suffix, or accumulator specifications,
- a `val` declaration for the target function,
- proof-style lemma tests.

The Stage 2A file usually contains:

- an executable `let` or `let rec` implementation,
- executable tests,
- no full correctness contract.

## Required output

Generate one final `.mlw` file. If the user, driver script, or orchestration layer provides a requested output path, use it exactly. Otherwise choose a clear name such as:

```text
<task_slug>_stage3_list_recursive.mlw
<task_slug>_stage3_list_imperative.mlw
```

For examples inside this skill, use this layout:

```text
.agents/skills/why3_list_verification/examples/<task_slug>/stage1a_spec.mlw
.agents/skills/why3_list_verification/examples/<task_slug>/stage2a_impl.mlw
.agents/skills/why3_list_verification/examples/<task_slug>/stage3_verified.mlw
```

Treat examples as proof-pattern references. If an older example keeps executable tests or rewrites a helper predicate, do not copy that output-shape choice into new Stage 3 files unless the current prompt explicitly asks for it.

## Core preservation rules

Stage 3 is verification repair, not specification repair and not implementation redesign.

Do not change the Stage 1A semantic specification. Preserve:

- the target function name,
- the original signature,
- all original `requires` clauses,
- all original `ensures` clauses,
- the meaning of Stage 1A helper predicates/functions,
- the intended non-empty-list behavior for tasks whose Stage 1A contract has `requires { l <> Nil }` or equivalent.

Do not replace a Stage 1A helper predicate/function with a different specification because it is easier to prove. For example, do not replace a recursive `sorted_list` predicate with a new `sorted_bool`-based definition unless you preserve the original predicate and prove the equivalence needed by the target contract.

Do not change the implementation style from Stage 2A:

- recursive implementations must remain recursive,
- imperative implementations must remain imperative,
- do not replace an imperative cursor loop with a fresh recursive algorithm,
- do not replace recursive code with refs/loops,
- do not switch lists to arrays.

Preserve the Stage 2A algorithm as much as possible. You may make proof-oriented local edits such as:

- adding contracts to helper functions,
- adding recursive `variant` clauses,
- adding loop invariants and loop variants,
- adding assertions before/after branches, pattern matches, or loops,
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
   - `stdlib_policy.md`,
   - `stdlib_int.md`,
   - `stdlib_bool.md`,
   - `stdlib_list.md`,
   - `stdlib_ref.md` for imperative cursor implementations.
5. Inspect local examples in `.agents/skills/why3_list_verification/examples/` when present. Prefer examples matching the implementation style and proof shape:
   - structural recursion over `Nil` / `Cons`,
   - imperative cursor traversal,
   - counting with `list.NumOcc`,
   - membership with `list.Mem`,
   - max/min with witness and upper/lower-bound facts,
   - sortedness with helper lemmas such as weakening over tails,
   - accumulator helpers.
6. Identify:
   - module name,
   - target function name,
   - argument types,
   - return type,
   - original preconditions and postconditions,
   - helper predicates/functions from Stage 1A,
   - executable implementation structure from Stage 2A,
   - whether the implementation is recursive or imperative,
   - whether the postcondition requires a witness/membership fact,
   - whether the implementation uses an accumulator, cursor, exception, or best-so-far value.
7. Before writing code, choose a proof-friendly first draft:
   - initialize best/witness accumulators from real list constructors when the precondition guarantees a non-empty list,
   - keep unconditional witness/membership invariants when possible,
   - choose helper contracts that mirror the Stage 1A recursive decomposition,
   - plan local assertions for constructor unfolding, accumulator updates, and loop exits.
8. Create a final module containing:
   - required imports,
   - preserved Stage 1A specification helpers,
   - derived proof helpers if needed,
   - helper lemmas if needed,
   - Stage 2A implementation with proof scaffolding,
   - the original Stage 1A semantic contract on the target function.
9. Validate the file:
   - always run `why3 prove --type-only <final-file>.mlw` when Why3 is available,
   - when full verification is explicitly requested by the user, run `scripts/why3-verify.sh <final-file>.mlw` if available.
10. If validation fails, use the current verifier output to add generally useful assertions, invariants, variants, or lemmas. Avoid overfitting to one proof obligation.

## Generated file shape

Prefer this structure:

```why3
module <ModuleName>_Stage3_<RecursiveOrImperative>

  use int.Int
  use list.List

  (* additional imports only when needed, e.g. list.Length, list.Mem, list.NumOcc, ref.Ref *)

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

Do not create the Stage 3 file by simply attaching the Stage 1A contract to the Stage 2A implementation and waiting for verifier failures. Before the first validation run, choose proof-friendly initial values, helper contracts, invariants, and assertions that make the final semantic postcondition easy to maintain.

### Prefer real witnesses for existential or membership-style postconditions

If the Stage 1A postcondition requires an existential or membership fact, initialize from a real constructor when the precondition guarantees one.

Prefer this for non-empty lists:

```why3
match l with
| Nil -> absurd
| Cons x xs ->
    let best = ref x in
    ...
end
```

with an invariant such as:

```why3
invariant { mem !best l }
invariant { forall y: int. <processed y> -> y <= !best }
```

over this weaker sentinel style:

```why3
let best = ref 0 in
invariant { !cur = l \/ mem !best l }
```

Sentinel values such as `0`, `min_int`, or `max_int` are acceptable only when the specification explicitly allows them or when the list may be empty and the postcondition accounts for that case.

### Preserve strong invariants unconditionally when possible

Avoid conditional invariants such as:

```why3
invariant { !cur = l \/ mem !best l }
```

when proof-friendly initialization can establish:

```why3
invariant { mem !best l }
```

Conditional invariants are acceptable only when no witness is available at initialization, for example in a search over a possibly empty list.

### Align helper contracts with the recursive specification

For recursive implementations, use helper contracts that directly mirror the Stage 1A recursive function or predicate.

For a suffix-processing helper:

```why3
let rec aux (xs: list int) : int
  ensures { result = spec_count xs }
  variant { xs }
= ...
```

For an accumulator helper:

```why3
let rec aux (xs: list int) (acc: int) : int
  ensures { result = acc + spec_count xs }
  variant { xs }
= ...
```

For boolean helpers, prove the exact equivalence needed by the target contract:

```why3
ensures { result <-> spec_predicate xs }
```

Do not use a weak helper contract if the top-level proof will require reconstructing the full semantic relation later.

### Use monotonicity or preservation lemmas when an accumulator improves

When a best-so-far value changes monotonically, previously processed facts usually need to be preserved under the new value. Add a small proved lemma rather than expecting SMT to infer this from quantifiers.

Example shape:

```why3
let lemma upper_bound_mono (l: list int) (old new_: int)
  requires { old <= new_ }
  requires { forall y: int. mem y l -> y <= old }
  ensures  { forall y: int. mem y l -> y <= new_ }
=
  assert { forall y: int. mem y l -> y <= new_ }
```

Then after an update, keep the old value and assert the relationship:

```why3
let old_best = !best in
if x > !best then best := x;
assert { old_best <= !best };
```

For minimum-like problems, use the dual relationship `!best <= old_best` or `new_ <= old`.

### Prefer proved `let lemma` helpers over unexplained bare lemmas

Bare lemmas are not axioms, but they create global proof obligations that may be hard for SMT solvers to prove without guidance. When the lemma is nontrivial, prefer a proved `let lemma` with local assertions or structural recursion:

```why3
let rec lemma le_all_tail (x: int) (y: int) (ys: list int)
  requires { le_all x (Cons y ys) }
  ensures  { le_all x ys }
  variant  { ys }
=
  match ys with
  | Nil -> ()
  | Cons _ zs -> le_all_tail x y zs
  end
```

Use a bare `lemma` only when it is very small and expected to be discharged automatically.

### Add local proof breadcrumbs in the first draft

For Stage 3, local assertions are not noise. Add them before the first full verification run when they expose:

- constructor shape after a `match`,
- one-step unfolding of recursive predicates/functions,
- length facts for variants,
- membership facts for `Cons`,
- accumulator old/new relationships,
- sortedness or bound facts needed in negative branches,
- the final cursor shape, usually `!cur = Nil`.

Prefer a slightly verbose first verified file over a short but fragile one.

## Recursive list verification strategy

For recursive list implementations, preserve structural recursion and make the proof follow the same list decomposition as the Stage 1A specification.

A verified recursive list function should usually look like:

```why3
let rec f (l: list int) : <ret>
  ensures { <original Stage 1A contract> }
  variant { l }
=
  match l with
  | Nil -> ...
  | Cons x xs ->
      assert { <one-step unfolding of the spec on Cons x xs> };
      ... f xs ...
  end
```

For helper recursion over an accumulator:

```why3
let rec f_aux (xs: list int) (acc: int) : int
  ensures { <relationship between result, acc, and the Stage 1A spec over xs> }
  variant { xs }
=
  match xs with
  | Nil -> ...
  | Cons x ys -> ... f_aux ys <updated_acc> ...
  end
```

Use accumulator lemmas only when a direct contract on the helper is not enough. Prefer a helper postcondition that exactly describes the suffix currently being processed plus the accumulator contribution.

## Imperative list verification strategy

For imperative cursor loops over lists, preserve the cursor-loop structure from Stage 2A. Use a mutable cursor plus invariants that relate the remaining suffix and accumulator to the original list.

A typical cursor loop should have:

```why3
while (match !cur with Nil -> false | Cons _ _ -> true end) do
  invariant { 0 <= length !cur }
  invariant { <relationship between !cur, accumulator, and original list> }
  variant   { length !cur }
  match !cur with
  | Nil -> absurd
  | Cons x xs ->
      ...;
      cur := xs
  end
 done
```

For count-like functions using `list.NumOcc`, a common invariant is:

```why3
invariant { num_occ x !cur + !count = num_occ x l }
variant   { length !cur }
```

For sum-like functions, use the same suffix-plus-accumulator shape:

```why3
invariant { !acc + sum_list !cur = sum_list l }
variant   { length !cur }
```

For all-elements Boolean scans, maintain that failure has not been seen and relate the remaining suffix to the original predicate:

```why3
invariant { !ok -> <all processed elements satisfy property> }
invariant { not !ok -> <a processed counterexample exists> }
variant   { length !cur }
```

For search/membership scans, use witness invariants:

```why3
invariant { not !found -> <no matching element has been seen in the processed prefix> }
invariant { !found -> <a matching witness has been seen> }
variant   { length !cur }
```

When direct processed-prefix reasoning is difficult, introduce a small helper predicate over the original list and current cursor only if needed. Keep the helper proof-oriented and do not replace the Stage 1A semantic predicate.

For max/min scans over a non-empty list, initialize from the head of the list and track both membership and bound facts:

```why3
match l with
| Nil -> absurd
| Cons x xs ->
    let best = ref x in
    let cur = ref xs in
    while ... do
      invariant { mem !best l }
      invariant { <all processed elements are <= !best> }
      variant   { length !cur }
      ...
    done;
    !best
end
```

If the implementation uses exceptions, preserve the exception structure and prove both paths:

- before `raise`, assert the semantic predicate is false or the postcondition for the exceptional result is established,
- in the `with` branch, assert the stored/global fact needed to return the correct Boolean result,
- do not remove exceptions merely to simplify verification.

## Sortedness patterns

For sortedness, the implementation may check adjacent pairs while the Stage 1A spec may be recursively defined using `le_all`, or may quantify over all pairs encoded recursively.

Useful specification helpers often have this shape:

```why3
predicate le_all (x: int) (l: list int) =
  match l with
  | Nil -> true
  | Cons y ys -> x <= y /\ le_all x ys
  end

predicate sorted_list (l: list int) =
  match l with
  | Nil -> true
  | Cons x xs -> le_all x xs /\ sorted_list xs
  end
```

For recursive implementations, prove the `Cons` case by exposing both parts:

```why3
assert { sorted_list (Cons x xs) <-> le_all x xs /\ sorted_list xs };
```

For imperative adjacent-pair implementations, maintain enough information to connect adjacent checks to the recursive predicate. This often requires helper lemmas such as:

```why3
let rec lemma le_all_weaken (x y: int) (l: list int)
  requires { x <= y }
  requires { le_all y l }
  ensures  { le_all x l }
  variant  { l }
=
  match l with
  | Nil -> ()
  | Cons _ ys -> le_all_weaken x y ys
  end
```

Negative branches should explicitly derive the contradiction:

```why3
assert { x > y };
assert { sorted_list (Cons x (Cons y ys)) -> x <= y };
assert { not sorted_list (Cons x (Cons y ys)) };
```

## Maximum/minimum/witness properties

For maximum-like and minimum-like functions over non-empty lists, maintain both bound and witness facts.

For a maximum value:

```why3
invariant { mem !best l }
invariant { forall y: int. <processed_member y> -> y <= !best }
```

For a recursive helper over a non-empty suffix, a strong contract is often simpler than cursor invariants:

```why3
let rec max_nonempty (l: list int) : int
  requires { l <> Nil }
  ensures  { mem result l }
  ensures  { forall y: int. mem y l -> y <= result }
  variant  { l }
= ...
```

For a minimum value, use the dual bound:

```why3
ensures { mem result l }
ensures { forall y: int. mem y l -> result <= y }
```

If the Stage 1A spec has its own `is_max_list`, `max_list`, `is_min_list`, or similar predicate/function, preserve it and prove the relationship using that original helper.

## Counting, occurrence, and length properties

For count-like functions, use `list.NumOcc.num_occ` when the Stage 1A spec uses it. Otherwise preserve the Stage 1A recursive counting function and align implementation contracts with it.

Recursive count pattern:

```why3
let rec count_occurrences_list (l: list int) (x: int) : int
  ensures { result = num_occ x l }
  variant { l }
=
  match l with
  | Nil -> 0
  | Cons y ys ->
      assert { num_occ x (Cons y ys) = (if y = x then 1 else 0) + num_occ x ys };
      (if y = x then 1 else 0) + count_occurrences_list ys x
  end
```

Imperative count pattern:

```why3
let count = ref 0 in
let cur = ref l in
while (match !cur with Nil -> false | Cons _ _ -> true end) do
  invariant { num_occ x !cur + !count = num_occ x l }
  variant   { length !cur }
  match !cur with
  | Nil -> absurd
  | Cons y ys ->
      if y = x then count := !count + 1;
      cur := ys
  end
 done;
assert { !cur = Nil };
assert { num_occ x Nil = 0 };
!count
```

Use `list.Length.length` for imperative loop variants over cursors.

## Logical/non-ghost separation

Do not use logical predicates such as `sorted_list`, `is_max_list`, or `mem` as executable branch conditions unless they are executable WhyML boolean functions. Keep executable code based on pattern matching, integer comparisons, booleans, and recursively computed executable helpers.

Incorrect:

```why3
if sorted_list l then true else false
```

Correct:

```why3
match l with
| Nil -> true
| Cons x xs -> ...
end
```

Then prove the relationship with `ensures` clauses, assertions, invariants, and lemmas.

Also avoid quantified formulas directly inside executable `if` guards:

```why3
if forall x: int. mem x l -> P x then ...
```

Put quantified properties in predicates, postconditions, assertions, or lemmas instead.

## Assertions and unfolding

Add assertions that reveal one constructor level at a time:

```why3
assert { sorted_list (Cons x xs) <-> le_all x xs /\ sorted_list xs };
assert { le_all x (Cons y ys) <-> x <= y /\ le_all x ys };
```

For membership and constructor facts, expose the relevant case:

```why3
assert { mem x (Cons x xs) };
assert { forall y: int. mem y xs -> mem y (Cons x xs) };
```

For negative branches, explicitly show the contradiction:

```why3
assert { x > y };
assert { sorted_list (Cons x (Cons y ys)) -> x <= y };
assert { not sorted_list (Cons x (Cons y ys)) };
```

For post-loop cursor reasoning, expose the final cursor shape:

```why3
assert { !cur = Nil };
```

Then instantiate the invariant at `Nil` or unfold the Stage 1A helper on `Nil`.

## Common helper lemmas

Use small, proved helper lemmas when assertions/invariants are not enough. Prefer lemmas that expose one recursive step, propagate a property over a tail, or prove a monotonicity/preservation fact.

Useful lemma families:

- sortedness weakening over tails,
- `le_all` / `ge_all` propagation,
- membership propagation through `Cons`,
- max/min bound preservation after a best update,
- counting decomposition over `Cons`,
- accumulator equivalence for tail-recursive helpers.

Keep helper lemmas local, reusable, and specification-driven. Avoid large benchmark-specific lemmas that merely encode the final answer.

## Common repair moves

Prefer these repair moves, in this order:

1. Add branch-local assertions exposing pattern-match shape, constructor facts, length facts, membership facts, and recursive unfolding facts.
2. Strengthen recursive helper contracts to describe exactly the suffix/list segment being processed.
3. For accumulator helpers, change the helper contract to a suffix-plus-accumulator relation instead of proving the accumulator relation only at the top level.
4. Strengthen loop invariants to connect the current cursor, processed contribution, accumulator, witness facts, and original list.
5. For max/min/existential results, initialize from a real witness when the precondition guarantees one.
6. Add post-loop assertions for the `Nil` cursor case.
7. Add small proved lemmas only when the VC needs induction, monotonicity, membership reasoning, counting decomposition, or sortedness propagation.
8. Prefer proved `let lemma` helpers with bodies over unexplained bare `lemma` declarations for nontrivial facts.

## What to avoid

- Do not switch the benchmark to arrays.
- Do not change the Stage 1A semantic specification.
- Do not remove or weaken preconditions just to make proofs easier.
- Do not weaken the postcondition to match the implementation.
- Do not invent behavior for `Nil` in non-empty-list tasks.
- Do not change recursive code to imperative code, or imperative code to recursive code.
- Do not substantially replace the Stage 2A algorithm with a different algorithm.
- Do not use predicates in non-ghost executable contexts.
- Do not introduce axioms unless explicitly requested and justified.
- Do not add large benchmark-specific lemmas when a small invariant or assertion is enough.
- Do not keep executable tests in the final Stage 3 file unless the user explicitly asks for a combined verified-and-executable artifact.
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
