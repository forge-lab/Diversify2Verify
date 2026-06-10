# Why3 References for Diversify2Verify

These files summarize the Why3 standard-library theories that are useful for generating contracts and concrete tests.

Use these references before defining local helper functions.

## Core references

- `stdlib_int.md`: integer arithmetic, absolute value, min/max, integer ranges, sums, and counts.
- `stdlib_array.md`: arrays, indexing, initialization, equality, sortedness, sums, occurrence counts, and permutations.
- `stdlib_list.md`: lists, length, membership, nth access, append, reverse, sortedness, occurrence counts, and permutations.
- `stdlib_bool.md`: Boolean functions and if-then-else helpers.
- `stdlib_map.md`: maps, lookup/update, extensional equality, range equality, occurrence counts, and permutation-style predicates.
- `stdlib_set.md`: sets, finite sets, membership, cardinality, intervals, and set operations.

## Usage rule

Before writing a generic helper such as `abs_int`, `array_eq`, `list_mem`, `num_occ`, `sum`, `min`, or `max`, check the relevant stdlib reference file.

Prefer standard-library theories when they directly express the intended concept.

Only define local helpers when:
- the helper is task-specific;
- no suitable standard-library concept is listed;
- the standard-library version is inconvenient for the generated specification;
- or the helper improves solver behavior by making recursion or quantifier instantiation explicit.

## Recommended directory layout

Place these files under:

```text
.agents/references/why3/
```

Suggested layout:

```text
.agents/
  references/
    why3/
      README.md
      stdlib_policy.md
      stdlib_array.md
      stdlib_bool.md
      stdlib_int.md
      stdlib_list.md
      stdlib_map.md
      stdlib_set.md
      contract_patterns_array.md
      contract_patterns_list.md
```

## Import selection guide

| Need | Check file | Likely theory |
|---|---|---|
| integer arithmetic | `stdlib_int.md` | `int.Int` |
| absolute value | `stdlib_int.md` | `int.Abs` |
| min/max | `stdlib_int.md` | `int.MinMax` |
| build concrete arrays | `stdlib_array.md` | `array.Init` |
| array indexing/length | `stdlib_array.md` | `array.Array` |
| array sortedness | `stdlib_array.md` | array sortedness theory |
| array equality | `stdlib_array.md` | array equality theory |
| count array elements | `stdlib_array.md` | array occurrence/counting theory |
| list length | `stdlib_list.md` | list length theory |
| list membership | `stdlib_list.md` | list membership theory |
| list nth access | `stdlib_list.md` | list nth theory |
| list permutation | `stdlib_list.md` | list permutation theory |
| finite-set membership | `stdlib_set.md` | finite-set theory |
| finite-set cardinality | `stdlib_set.md` | finite-set cardinality theory |
| map lookup/update | `stdlib_map.md` | map theory |
| map range equality | `stdlib_map.md` | map equality theory |

## Skill integration

Contract-generation skills should reference this folder before generating imports or helper functions.

For example, `why3_array_contract_generation/SKILL.md` should say:

```markdown
Before generating imports or helper functions, read:

- `.agents/references/why3/stdlib_policy.md`
- `.agents/references/why3/stdlib_int.md`
- `.agents/references/why3/stdlib_array.md`
- `.agents/references/why3/stdlib_bool.md`

Read additional references only when needed:

- `.agents/references/why3/stdlib_list.md` if converting arrays to lists or comparing against list-like results.
- `.agents/references/why3/stdlib_map.md` if the specification naturally uses maps or index-to-value functions.
- `.agents/references/why3/stdlib_set.md` if the specification naturally uses sets, finite sets, membership, or cardinality.
```

## Design principle

The skill should describe behavior:

```text
Given normalized array JSON, generate a Why3 contract and 5-10 test lemmas.
```

The references should provide facts:

```text
What Why3 theories, functions, and predicates exist?
```

The policy should provide decision rules:

```text
When should Codex use a library function versus define a local helper?
```
