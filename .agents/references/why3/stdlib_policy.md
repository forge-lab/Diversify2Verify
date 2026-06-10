# Why3 Standard Library Policy

This policy applies to all Diversify2Verify Why3 contract-generation skills.

## Main rule

Prefer Why3 standard-library theories, functions, and predicates when they exist.

Do not define local helpers for generic concepts unless there is a concrete reason.

Examples of generic concepts include:

- absolute value
- minimum and maximum
- array length and indexing
- array initialization
- array equality
- sortedness
- occurrence counting
- list length
- list membership
- list nth access
- list append
- list reverse
- finite-set membership
- finite-set cardinality
- map lookup and update

## Required lookup step

Before defining a local helper, check the relevant reference file:

- arrays: `stdlib_array.md`
- integers: `stdlib_int.md`
- lists: `stdlib_list.md`
- booleans: `stdlib_bool.md`
- maps: `stdlib_map.md`
- sets and finite sets: `stdlib_set.md`

## Import discipline

Use only the imports that are needed.

Start from the target representation.

Array benchmarks usually need:

```why3
use int.Int
use array.Array
use array.Init
```

List benchmarks usually need:

```why3
use int.Int
use list.List
use list.Length
```

Then add specialized imports only when used.

Examples:

- Need absolute value:
  - use `int.Abs`

- Need min/max:
  - use `int.MinMax`

- Need concrete array construction:
  - use `array.Init`

- Need array sortedness:
  - use the relevant array sortedness theory from `stdlib_array.md`

- Need array equality:
  - use the relevant array equality theory from `stdlib_array.md`

- Need list nth access:
  - use the relevant nth theory from `stdlib_list.md`

- Need finite-set cardinality:
  - use the relevant finite-set theory from `stdlib_set.md`

## Local helper rule

A local helper is allowed when:

1. the helper is task-specific;
2. no suitable stdlib function or predicate is listed;
3. the stdlib concept exists but is awkward for the intended contract;
4. the helper improves solver behavior by making recursion or quantifier instantiation explicit.

If a local helper duplicates a standard-library concept, explain this in the PLAN.

Avoid this when `int.Abs.abs` is sufficient:

```why3
function abs_int (x:int) : int =
  if x < 0 then -x else x
```

Prefer:

```why3
use int.Abs
```

and write:

```why3
abs (x - y)
```

## Contract-generation guidance

The standard library should support the specification; it should not obscure it.

For simple semantic predicates, direct quantifiers are often clearer than forcing a library abstraction.

For example, this is acceptable:

```why3
predicate far_from_all (arr2: array int) (x:int) (d:int) =
  forall j:int. 0 <= j < length arr2 -> abs (x - arr2[j]) > d
```

Do not replace a clear direct definition with a library function if doing so makes the contract harder to read, type-check, or prove.

## PLAN requirements

Every generated PLAN should include a short section:

```markdown
## Why3 library usage

Used references:
- stdlib_array.md
- stdlib_int.md

Used theories:
- int.Int
- int.Abs
- array.Array
- array.Init

Local helpers:
- none
```

If local helpers are introduced, list them and explain why.

Example:

```markdown
Local helpers:
- `count_good_from`: task-specific recursive count over indices of `arr1`.
- No local helper for absolute value; the specification uses `int.Abs.abs`.
```

## Practical guidance for Codex

When generating a Why3 specification:

1. Read the normalized benchmark JSON.
2. Identify the target representation: array or list.
3. Read this policy file.
4. Read the relevant stdlib reference files.
5. Choose imports.
6. Generate task-specific semantic predicates/functions.
7. Avoid defining local generic helpers.
8. Record library usage and local-helper justification in the PLAN.
9. Run type-checking only unless the user explicitly requests full verification.

## Full verification

This policy does not require full verification.

For Diversify2Verify generation skills, the default is:

```bash
why3 prove --type-only <generated-file>.mlw
```

If full verification is requested, inspect and reuse the existing repository script:

```bash
scripts/why3-verify.sh
```

Do not replace that script and do not hardcode a separate full-verification pipeline.
