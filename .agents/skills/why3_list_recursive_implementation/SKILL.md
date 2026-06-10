---
name: why3_list_recursive_implementation
description: Generate recursive executable Why3 list implementations and runnable tests from a Stage 1A Why3 list specification file.
---

# Why3 List Recursive Implementation Skill

Use this skill when asked to generate a recursive Stage 2A implementation for a list-based Why3 task starting from a Stage 1A `.mlw` specification file.

This skill is for implementation and executable testing, not full verification.

The input is usually a Why3 module containing:

- predicates/functions describing the intended behavior,
- a `val` declaration for the target function,
- proof-style lemma tests with `assert`,
- concrete examples constructed with `Nil` and `Cons`.

The output should be an executable Why3 file with:

- a recursive implementation,
- executable tests as `let` functions returning `bool`,
- a `run_tests () : bool` function,
- no proof-oriented correctness contracts unless explicitly requested.

## Goal

Transform a Stage 1A list specification into a Stage 2A recursive implementation.

Stage 2A is implementation-oriented. The generated file should:

1. type-check with `why3 prove --type-only`,
2. execute tests with `why3 execute`,
3. return `true` from `run_tests ()`.

It does not need to prove the full formal specification.

## Use the examples

Use the examples in the local `examples/` directory as style references.

Expected examples include files such as:

```text
examples/sorted_list_rec.mlw
examples/max_list_recursive.mlw
examples/count_occurrences_list_recursive.mlw
```

These examples show the expected Stage 2A style:

- recursive implementation using pattern matching over `Nil` and `Cons`,
- helper recursive functions when useful,
- explicit `variant` clauses on recursive functions,
- runnable executable tests,
- no `ensures` contracts unless explicitly requested,
- no lemma-based executable tests,
- `why3 prove --type-only` before `why3 execute`,
- bounded repair if syntax, type-checking, or execution fails.

## Required workflow

Follow this loop:

1. Inspect the Stage 1A `.mlw` file.
2. Extract:
   - module name,
   - target function name,
   - argument types,
   - return type,
   - intended behavior from predicates/functions,
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

## Repair budget

Use one initial generation plus 3 repair iterations, for 4 total attempts.

If no valid implementation is found after 4 total attempts, stop and report:

- the latest file content,
- the exact command that failed,
- the relevant error output,
- the likely reason for failure.

Do not keep trying indefinitely.

## Recursive implementation rules

Recursive implementations must include a `variant`.

For list scans, prefer direct structural recursion:

```why3
let rec f (l: list int) : bool
  variant { l }
=
  match l with
  | Nil -> true
  | Cons x xs -> <use x and recurse on xs>
  end
```

For adjacent list scans, inspect the tail:

```why3
let rec is_sorted_list (l: list int) : bool
  variant { l }
=
  match l with
  | Nil -> true
  | Cons _ Nil -> true
  | Cons x (Cons y ys) ->
      x <= y && is_sorted_list (Cons y ys)
  end
```

For integer-returning functions, use structural recursion or an accumulator helper when natural:

```why3
let rec count_occurrences_list (l: list int) (x: int) : int
  variant { l }
=
  match l with
  | Nil -> 0
  | Cons y ys ->
      (if y = x then 1 else 0) + count_occurrences_list ys x
  end
```

For maximum-like functions, preserve the Stage 1A precondition. If the specification requires a non-empty list, do not invent behavior for `Nil` unless the user asks for it.

A common recursive maximum pattern for non-empty lists is:

```why3
let rec max_from (xs: list int) (current: int) : int
  variant { xs }
=
  match xs with
  | Nil -> current
  | Cons y ys ->
      if y > current then max_from ys y else max_from ys current
  end

let max_list (l: list int) : int =
  match l with
  | Nil -> 0
  | Cons h t -> max_from t h
  end
```

Only use a default value such as `0` for `Nil` if that behavior is consistent with the Stage 1A specification or examples.

## Stage 2A contract policy

Do not add full correctness contracts unless explicitly requested.

Prefer:

```why3
let f (l: list int) : bool =
  ...
```

not:

```why3
let f (l: list int) : bool
  ensures { result <-> spec l }
=
  ...
```

It is acceptable to keep the original predicates and proof-style lemmas if the user asks to add the implementation to the existing file. However, runnable tests should be separate executable `let` functions, not lemmas.

## Imports

Prefer:

```why3
use int.Int
use list.List
use list.Length
use list.Mem
```

Import only what is needed. For purely structural programs, `list.List` plus `int.Int` is often enough.

Use `list.Length` for executable or proof code involving length. Use `list.Mem` only for specification predicates or tests involving membership.

## Executable tests

Convert Stage 1A lemma tests into executable boolean tests.

Use constructor-built lists:

```why3
let l = Cons 1 (Cons 2 (Cons 3 Nil)) in
```

Do not use arrays or `array.Init.init`.

Write tests as simple booleans:

```why3
let test_example_1 () : bool =
  let l = Cons 1 (Cons 2 (Cons 2 Nil)) in
  count_occurrences_list l 2 = 2
```

Use nested `if` chains for `run_tests ()` to keep Why3 execution simple:

```why3
let run_tests () : bool =
  if test_1 () then
  if test_2 () then
    true
  else false
  else false
```

## Common pitfalls

- Do not use array indexing on lists.
- Do not use non-structural recursion without a clear decreasing variant.
- Do not call logical-only predicates/functions from non-ghost executable code unless they are executable WhyML functions.
- Do not add proof obligations that are unnecessary for Stage 2A.
