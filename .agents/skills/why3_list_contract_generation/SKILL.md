---
name: why3_list_contract_generation
description: Generate a Why3 list specification file and a small set of concrete specification test lemmas from a normalized Diversify2Verify list benchmark JSON.
---

# Why3 List Contract Generation

Use this skill for Stage 1A of the Diversify2Verify pipeline:

```text
normalized list JSON
  -> PLAN
  -> Why3 list specification file
  -> 5-10 concrete specification test lemmas
  -> Why3 type-check only
```

This skill generates one Why3 `.mlw` specification file for one normalized benchmark whose `target.name` is `"list"`.

The generated file should specify the intended behavior of the target function and include a small number of concrete test lemmas that validate the generated specification. The test lemmas should use intermediate `assert` statements to help Why3 instantiate quantifiers, unfold recursive list predicates/functions, and expose concrete list facts.

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
  "name": "list",
  "language": "why3"
}
```

If `target.name` is not `"list"`, stop and report that this skill only handles list benchmarks.

Use only the normalized `tests` array. Do not parse the original raw Python `test` string.

## Required outputs

Generate:

```text
generated/plans/list/<task_id>.list.plan.md
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
.agents/references/why3/stdlib_list.md
```

Read additional references only when needed:

```text
.agents/references/why3/stdlib_map.md
.agents/references/why3/stdlib_set.md
.agents/references/why3/stdlib_array.md
```

Prefer Why3 standard-library functions and predicates when available. Do not define local helpers for generic concepts such as length, membership, append, reverse, nth, sortedness, occurrence counting, or sums unless justified in the PLAN.

Useful examples for this skill should be stored in:

```text
.agents/skills/why3_list_contract_generation/examples/
```

Expected examples:

```text
.agents/skills/why3_list_contract_generation/examples/count_occurrences_list.mlw
.agents/skills/why3_list_contract_generation/examples/max_list.mlw
.agents/skills/why3_list_contract_generation/examples/sorted_list.mlw
```

Use these examples as style guides:

- `count_occurrences_list.mlw`: recursive list specification functions and suffix/tail assertions.
- `max_list.mlw`: membership witnesses, universal bounds over `mem`, and finite-domain membership enumeration assertions.
- `sorted_list.mlw`: structurally recursive predicates, pair/tail assertions, and negative counterexample lemmas.

Do not copy benchmark-specific names from the examples unless they match the current benchmark.

## Workflow

1. Read the normalized JSON.
2. Confirm `target.name = "list"` and `target.language = "why3"`.
3. Read the relevant Why3 reference files.
4. Inspect the list examples if available.
5. Extract:
   - task id from `task.task_id`;
   - module name from `target.module_name`;
   - output path from `target.output_file`;
   - function name from `target.signature.function_name`;
   - raw signature from `target.signature.raw`;
   - parameters from `target.signature.parameters`;
   - return type from `target.signature.return`;
   - problem description from `problem.description`;
   - normalized tests from `tests`.
6. Select 5-10 tests deterministically, defaulting to 7.
7. Write a compact PLAN.
8. Generate the Why3 `.mlw` file.
9. Run type-checking only:

```bash
why3 prove --type-only <generated-file>.mlw
```

10. Fix syntax, import, and type errors if needed.
11. Re-run the same type-check command after each fix.
12. Do not run full verification unless explicitly requested.

## PLAN format

Before writing the Why3 file, create a concise plan:

```markdown
# PLAN: <task_id> / list

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
- stdlib_list.md
- stdlib_bool.md, if used
- any additional reference files used

Used theories:
- int.Int
- list.List
- list.Length, if length is used
- list.Mem, if membership is used
- list.Nth, only if index-based list access is central
- list.Append, list.Reverse, or other list theories when needed

Local helpers:
- list each local helper and explain why it is needed
- explicitly justify any helper that duplicates a standard-library concept

## Contract design

List the helper predicates/functions and the final postcondition.

## Selected test lemmas

List the selected test ids and explain the coverage briefly.

## Test lemma proof strategy

For the selected tests, identify the main proof style:
- structural recursive computation;
- membership witness plus universal bound;
- finite-domain membership enumeration;
- direct constructor/tail decomposition;
- negative counterexample;
- direct semantic predicate assertion;
- expected-list equality assertion.

## Type-check command

```bash
why3 prove --type-only <resolved output path>
```
```

Do not include long hidden reasoning traces in the PLAN.

## Generated file shape

Prefer this module structure:

```why3
module <ModuleName>

  use int.Int
  use list.List
  use list.Length
  use list.Mem

  <helper specification functions/predicates>

  val <function_name> <args> : <return_type>
    requires { <preconditions, if any> }
    ensures  { <postcondition> }

  <concrete test lemmas>

end
```

Only import the list theories actually needed. For many purely structural specifications, `list.List` is enough.

## List representation rules

Use Why3 lists directly:

```why3
Nil
Cons 1 (Cons 2 (Cons 3 Nil))
```

Do not use arrays, `array.Init.init`, `a[i]`, or array lengths in list specifications.

Prefer structural recursion and pattern matching over index-based access:

```why3
let rec function count_from (l: list int) (x: int) : int
  variant { l }
=
  match l with
  | Nil -> 0
  | Cons y ys -> (if y = x then 1 else 0) + count_from ys x
  end
```

Use `list.Nth` only when the original task is inherently index-based, such as returning positions, preserving index relationships, or matching LeetCode-style output indices. If using `nth`, explicitly handle bounds and justify it in the PLAN.

## Specification design rules

Prefer total logical helpers with structural recursion. Examples:

```why3
let rec function num_occ_list (l: list int) (x: int) : int
  variant { l }
=
  match l with
  | Nil -> 0
  | Cons y ys -> (if y = x then 1 else 0) + num_occ_list ys x
  end
```

For membership properties, prefer `mem` from `list.Mem`:

```why3
predicate is_max_list (l: list int) (m: int) =
  mem m l /\
  forall x: int. mem x l -> x <= m
```

For sortedness and other all-tail properties, prefer recursive predicates:

```why3
let rec predicate le_all (x: int) (l: list int)
  variant { l }
=
  match l with
  | Nil -> true
  | Cons y ys -> x <= y /\ le_all x ys
  end

let rec predicate sorted_list (l: list int)
  variant { l }
=
  match l with
  | Nil -> true
  | Cons x xs -> le_all x xs /\ sorted_list xs
  end
```

Use `requires { l <> Nil }` for maximum/minimum-style functions when the intended problem assumes a non-empty list. Do not invent a default value for `Nil` unless the problem statement or normalized tests require it.

## Concrete test lemma rules

Use concrete constructor-built lists and unfold specifications step by step.

For recursive helper functions, assert the values of relevant tails:

```why3
assert { num_occ_list Nil 2 = 0 };
assert { num_occ_list (Cons 2 Nil) 2 = 1 };
assert { num_occ_list (Cons 1 (Cons 2 Nil)) 2 = 1 };
```

For `mem`-based predicates, expose all possible members of a concrete list:

```why3
assert { forall x: int. mem x l -> x = 3 \/ x = 1 \/ x = 4 \/ x = 2 };
```

For sortedness, assert helper predicates on tails before asserting the top-level predicate:

```why3
assert { le_all 1 (Cons 2 (Cons 2 Nil)) };
assert { sorted_list (Cons 2 (Cons 2 Nil)) };
assert { sorted_list (Cons 1 (Cons 2 (Cons 2 Nil))) };
```

Negative tests should show a concrete counterexample and end with `assert { not (<predicate> ...) }`. Do not rely on a negative test alone as evidence that the specification is correct.

## What to avoid

- Do not use arrays in list benchmarks.
- Do not use `length` or `nth` when structural recursion is simpler.
- Do not write partial functions that pattern-match `Nil` unsafely.
- Do not add executable implementations in Stage 1A.
- Do not run full verification unless explicitly requested.
