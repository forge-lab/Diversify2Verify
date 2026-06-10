---
name: why3_array_recursive_implementation
description: Generate recursive executable Why3 array implementations and runnable tests from a Stage 1A Why3 array specification file.
---

# Why3 Array Recursive Implementation Skill

Use this skill when asked to generate a recursive Stage 2A implementation for an array-based Why3 task starting from a Stage 1A `.mlw` specification file.

This skill is for implementation and executable testing, not full verification.

The input is usually a Why3 module containing:

- predicates describing the intended behavior,
- a `val` declaration for the target function,
- proof-style lemma tests with `assert`,
- concrete examples constructed with `array.Init.init`.

The output should be an executable Why3 file with:

- a recursive implementation,
- executable tests as `let` functions returning `bool`,
- a `run_tests () : bool` function,
- no proof-oriented correctness contracts unless explicitly requested.

## Goal

Transform a Stage 1A array specification into a Stage 2A recursive implementation.

Stage 2A is implementation-oriented. The generated file should:

1. type-check with `why3 prove --type-only`,
2. execute tests with `why3 execute`,
3. return `true` from `run_tests ()`.

It does not need to prove the full formal specification.

## Use the Examples

Use the examples in the local `examples/` directory as style references.

Expected examples include files such as:

```text
examples/sorted_array_rec.mlw
examples/max_array_recursive.mlw
examples/count_occurrences_array_recursive.mlw
```

These examples show the expected Stage 2A style:

- recursive implementation,
- helper recursive functions when useful,
- explicit `variant` clauses on recursive functions,
- runnable executable tests,
- no `ensures` contracts unless explicitly requested,
- no lemma-based executable tests,
- `why3 prove --type-only` before `why3 execute`,
- bounded repair if syntax, type-checking, or execution fails.

## Required Workflow

Follow this loop:

1. Inspect the Stage 1A `.mlw` file.
2. Extract:
   - module name,
   - target function name,
   - argument types,
   - return type,
   - intended behavior from predicates,
   - concrete examples from lemma tests.
3. Replace the abstract `val` declaration with a recursive `let` implementation.
4. Add executable test functions returning `bool`.
5. Add a `run_tests () : bool` function.
6. Run syntax/type checking first:

```bash
why3 prove --type-only <file>.mlw
```

7. Only if type checking succeeds, run executable tests:

```bash
why3 execute <file>.mlw --use=<ModuleName> 'run_tests ()'
```

8. If either command fails, repair the implementation or tests and repeat.
9. Stop when both commands succeed, or after the repair budget is exhausted.

## Repair Budget

Use one initial generation plus 3 repair iterations, for 4 total attempts.

If no valid implementation is found after 4 total attempts, stop and report:

- the latest file content,
- the exact command that failed,
- the relevant error output,
- the likely reason for failure.

Do not keep trying indefinitely.

## Recursive Implementation Rules

Recursive implementations must include a `variant`.

For array scans, prefer a helper function indexed by position:

```why3
let rec f_from (a: array int) (i: int) : bool
  variant { length a - i }
=
  if i >= length a then
    true
  else
    ...

let f (a: array int) : bool =
  f_from a 0
```

For adjacent array scans, this pattern is often appropriate:

```why3
let rec f_from (a: array int) (i: int) : bool
  variant { length a - i }
=
  if i + 1 >= length a then
    true
  else if condition_at_index a i then
    f_from a (i + 1)
  else
    false
```

For integer-returning functions, use recursive accumulators when natural:

```why3
let rec count_from (a: array int) (x: int) (i: int) (acc: int) : int
  variant { length a - i }
=
  if i >= length a then
    acc
  else if a[i] = x then
    count_from a x (i + 1) (acc + 1)
  else
    count_from a x (i + 1) acc

let count_occurrences (a: array int) (x: int) : int =
  count_from a x 0 0
```

For maximum-like functions, handle the empty-array case according to the Stage 1A specification or examples. If the original specification requires a non-empty array, preserve that assumption in executable tests and avoid inventing behavior for empty arrays unless the user asks for it.

A common recursive maximum pattern for non-empty arrays is:

```why3
let rec max_from (a: array int) (i: int) (best: int) : int
  variant { length a - i }
=
  if i >= length a then
    best
  else if a[i] > best then
    max_from a (i + 1) a[i]
  else
    max_from a (i + 1) best

let max_array (a: array int) : int =
  if length a = 0 then
    0
  else
    max_from a 1 a[0]
```

Only use a default value such as `0` for empty arrays if that behavior is consistent with the Stage 1A spec or examples.

## Common Recursive Pattern: Sortedness

For sortedness, use adjacent comparisons:

```why3
let rec is_sorted_array_from (a: array int) (i: int) : bool
  variant { length a - i }
=
  if i + 1 >= length a then
    true
  else if a[i] <= a[i + 1] then
    is_sorted_array_from a (i + 1)
  else
    false

let is_sorted_array (a: array int) : bool =
  is_sorted_array_from a 0
```

## Stage 2A Contract Policy

Do not add full correctness contracts unless explicitly requested.

Prefer:

```why3
let f (a: array int) : bool =
  ...
```

not:

```why3
let f (a: array int) : bool
  ensures { result <-> spec a }
=
  ...
```

It is acceptable to keep the original predicates and proof-style lemmas if the user asks to add the implementation to the existing file. However, runnable tests should be separate executable `let` functions, not lemmas.

## Imports

Prefer:

```why3
use int.Int
use array.Array
use array.Init
```

instead of:

```why3
use import array.Array
use import array.Init
```

The `import` keyword is often redundant and can produce warnings.

Use `array.Init` for concrete arrays:

```why3
init n [| ... |]
```

Use `array.Array` for:

- `array`,
- `length`,
- indexing,
- `make`.

Recursive implementations usually do not need `ref.Ref`.

## Empty Arrays

Do not generate:

```why3
init 0 [||]
```

This can cause a syntax error.

Use:

```why3
make 0 0
```

The fill value is arbitrary because the array has length `0`.

Only include an empty-array test if the Stage 1A behavior is defined or can be safely inferred.

## Executable Test Pattern

Generate tests as `let` functions returning `bool`.

For Boolean-returning functions, positive tests should return the function result directly:

```why3
let test_positive () : bool =
  let a = init 4 [|1; 2; 2; 5|] in
  f a
```

Negative tests should use `not`:

```why3
let test_negative () : bool =
  let a = init 4 [|1; 3; 2; 5|] in
  not (f a)
```

Avoid:

```why3
f a = true
f a = false
```

These can trigger unnecessary typing or parsing issues in executable tests.

For non-Boolean return values, bind the result first, then compare:

```why3
let test_count_occurrences_1 () : bool =
  let a = init 5 [|1; 2; 1; 3; 1|] in
  let r = count_occurrences a 1 in
  r = 3
```

Prefer this over complex inline expressions.

## `run_tests` Pattern

Use nested `if` expressions for robustness:

```why3
let run_tests () : bool =
  if test_1 () then
  if test_2 () then
  if test_3 () then
    true
  else false
  else false
  else false
```

Avoid relying on complex boolean chains if they cause parsing or typing issues.

## Test Coverage Guidelines

Generate runnable tests from the Stage 1A lemma tests.

For array predicates/functions, include when relevant:

- one normal positive example,
- one singleton example,
- one empty-array example if the behavior is defined,
- one duplicate-value example,
- one negative example with a counterexample in the middle,
- one negative example with a counterexample near the end,
- one example involving the boundary index or last element.

Do not invent tests that contradict the Stage 1A specification.

If the Stage 1A file includes proof-style lemma tests, convert their concrete examples into executable tests.

## Command-Line Execution

Use this command form:

```bash
why3 execute <file>.mlw --use=<ModuleName> 'run_tests ()'
```

Do not use:

```bash
why3 execute <file>.mlw <ModuleName>.run_tests
```

That may fail with:

```text
unbound function or predicate symbol '<ModuleName>.run_tests'
```

Always run type checking before execution:

```bash
why3 prove --type-only <file>.mlw
```

Then run:

```bash
why3 execute <file>.mlw --use=<ModuleName> 'run_tests ()'
```

## Success Criteria

The generated file is valid when:

1. `why3 prove --type-only <file>.mlw` succeeds.
2. `why3 execute <file>.mlw --use=<ModuleName> 'run_tests ()'` prints or evaluates to `true`.

If `run_tests ()` evaluates to `false`, repair the implementation or tests.

If type checking fails, repair syntax, imports, names, variants, or typing before trying to execute.

## Final Response Requirements

Report:

1. The generated recursive implementation file.
2. The exact type-check command.
3. The exact test execution command.
4. Whether both commands succeeded.
5. If repair was needed, summarize the repair briefly.
6. If the repair budget was exhausted, report the final failure clearly.

## Do Not

- Do not generate an imperative implementation in this skill.
- Do not add full `ensures` contracts unless explicitly requested.
- Do not attempt full proof verification unless explicitly requested.
- Do not use `init 0 [||]`.
- Do not write executable tests as lemmas.
- Do not use `f a = true` or `f a = false` in executable tests.
- Do not skip type checking before executing tests.
- Do not continue repair beyond the iteration budget.
- Do not ignore the examples in the local `examples/` directory.
