---
name: why3_list_imperative_implementation
description: Generate imperative executable Why3 list implementations and runnable tests from a Stage 1A Why3 list specification file.
---

# Why3 List Imperative Implementation Skill

Use this skill when asked to generate an imperative Stage 2A implementation for a list-based Why3 task starting from a Stage 1A `.mlw` specification file.

This skill is for implementation and executable testing, not full verification.

The input is usually a Why3 module containing:

- predicates/functions describing the intended behavior,
- a `val` declaration for the target function,
- proof-style lemma tests with `assert`,
- concrete examples constructed with `Nil` and `Cons`.

The output should be an executable Why3 file with:

- an imperative-style implementation,
- executable tests as `let` functions returning `bool`,
- a `run_tests () : bool` function,
- no proof-oriented correctness contracts unless explicitly requested.

## Goal

Transform a Stage 1A list specification into a Stage 2A imperative implementation.

Stage 2A is implementation-oriented. The generated file should:

1. type-check with `why3 prove --type-only`,
2. execute tests with `why3 execute`,
3. return `true` from `run_tests ()`.

It does not need to prove the full formal specification.

## Use the examples

Use the examples in the local `examples/` directory as style references.

Expected examples include files such as:

```text
examples/sorted_list_imp.mlw
examples/max_list_imperative.mlw
examples/count_occurrences_list_imperative.mlw
```

These examples show the expected Stage 2A style:

- imperative traversal using `ref.Ref` cursor variables,
- `while` loops over the remaining list,
- local exceptions for early exit when useful,
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
3. Replace the abstract `val` declaration with an imperative-style `let` implementation.
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

## Imperative implementation rules

Why3 lists are immutable. For an imperative Stage 2A list implementation, use mutable references for traversal state and accumulators, not array indexing.

Use `ref.Ref` deliberately:

```why3
use ref.Ref
```

A standard cursor loop has this shape:

```why3
let cur = ref l in
while (match !cur with Nil -> false | Cons _ _ -> true end) do
  match !cur with
  | Nil -> ()
  | Cons x xs ->
      <process x>;
      cur := xs
  end
 done
```

For count-like functions:

```why3
let count_occurrences_list (l: list int) (x: int) : int =
  let count = ref 0 in
  let cur = ref l in
  while (match !cur with Nil -> false | Cons _ _ -> true end) do
    match !cur with
    | Nil -> ()
    | Cons y ys ->
        if y = x then count := !count + 1;
        cur := ys
    end
  done;
  !count
```

For maximum-like functions, handle the empty-list case according to the Stage 1A specification or examples. If the original specification requires a non-empty list, preserve that assumption in executable tests and avoid inventing behavior for `Nil` unless the user asks for it.

For sortedness, a cursor over adjacent pairs is usually appropriate:

```why3
exception NotSorted

let is_sorted_list (l: list int) : bool =
  try
    let cur = ref l in
    while (match !cur with Cons _ (Cons _ _) -> true | _ -> false end) do
      match !cur with
      | Cons x (Cons y ys) ->
          if x > y then raise NotSorted;
          cur := Cons y ys
      | _ -> ()
      end
    done;
    true
  with NotSorted ->
    false
  end
```

Use local exceptions for early exit from a traversal. Avoid recursive helpers when the user specifically requested an imperative implementation.

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
use ref.Ref
```

Add `list.Length` or `list.Mem` only when needed by retained specifications or tests.

Do not import array theories in list benchmarks.

## Executable tests

Convert Stage 1A lemma tests into executable boolean tests.

Use constructor-built lists:

```why3
let l = Cons 1 (Cons 2 (Cons 3 Nil)) in
```

Write tests as simple booleans and combine them with a nested `if` chain in `run_tests ()`.

## Common pitfalls

- Do not use `a[i]`, `length a`, `array.Init.init`, or `make` from arrays.
- Do not mutate list nodes; lists are immutable. Mutate the cursor reference instead.
- Do not call logical-only predicates from executable code.
- Do not add loop invariants unless the user requested full verification. Stage 2A only needs type-checking and execution.
