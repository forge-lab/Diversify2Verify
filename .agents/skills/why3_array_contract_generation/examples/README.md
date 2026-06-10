# Why3 Array Contract Generation Examples

These examples illustrate the preferred style for generated Stage 1A array specification files.

## count_occurrences_array.mlw

Use this example for recursive counting specifications.

Important patterns:
- define a recursive logical function with a `variant`;
- test the recursive function directly;
- use `let lemma test_name () = ...`;
- include intermediate assertions for suffix values.

## max_array.mlw

Use this example for specifications involving existential witnesses and universal bounds.

Important patterns:
- define helper predicates for witnesses and bounds;
- assert concrete witness facts;
- assert per-index upper/lower-bound facts;
- assert finite-domain enumeration to help quantifier instantiation;
- assert the final semantic predicate.

## sorted_array.mlw

Use this example for universally quantified pairwise properties.

Important patterns:
- define a pairwise helper predicate;
- enumerate relevant index pairs in concrete tests;
- assert finite-domain index enumeration;
- assert the final sortedness predicate;
- for negative tests, assert the violating pair before asserting the negated predicate.

## General rule

Concrete test lemmas should validate the generated specification predicates/functions, not merely call the abstract `val` function.

Use intermediate `assert` statements to expose concrete facts and help Why3 instantiate quantifiers.
