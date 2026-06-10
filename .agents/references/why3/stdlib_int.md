# int.html Reference

## Int
- `Int.=` (`predicate`): `int -> int -> bool` — Integer equality.
- `Int.-_` (`function`): `int -> int` — Unary minus.
- `Int.+` (`function`): `int -> int -> int` — Integer addition.
- `Int.*` (`function`): `int -> int -> int` — Integer multiplication.
- `Int.<` (`predicate`): `int -> int -> bool` — Integer less-than relation.
- `Int.-` (`function`): `int -> int -> int` — Subtraction, defined as `x + (-y)`.
- `Int.>` (`predicate`): `int -> int -> bool` — Greater-than relation.
- `Int.<=` (`predicate`): `int -> int -> bool` — Less-or-equal relation.
- `Int.>=` (`predicate`): `int -> int -> bool` — Greater-or-equal relation.

## Abs
- `Abs.abs` (`function`): `int -> int` — Absolute value.

## MinMax
- `MinMax.min` (`function`): `int -> int -> int` — Minimum of two ints.
- `MinMax.max` (`function`): `int -> int -> int` — Maximum of two ints.

## Lex2
- `Lex2.lt_nat` (`predicate`): `int -> int -> bool` — Well-founded nat-like order used for lexicographic proofs.

## EuclideanDivision
- `EuclideanDivision.div` (`function`): `int -> int -> int` — Euclidean quotient (non-negative remainder).
- `EuclideanDivision.mod` (`function`): `int -> int -> int` — Euclidean remainder.

## Div2
- No function/predicate declarations (lemma-only module).

## ComputerDivision
- `ComputerDivision.div` (`function`): `int -> int -> int` — C/Java-style integer division.
- `ComputerDivision.mod` (`function`): `int -> int -> int` — C/Java-style remainder.

## Exponentiation
- `Exponentiation.*` (`function`): `t -> t -> t` — Multiplicative operator on generic type `t`.
- `Exponentiation.power` (`function`): `t -> int -> t` — Generic integer exponentiation for monoids.

## Power
- `Power.power` (`function`): `int -> int -> int` — Integer power.

## NumOf
- `NumOf.numof` (`function`): `(int -> bool) -> int -> int -> int` — Count values `n` in `[a, b)` satisfying predicate.

## Sum
- `Sum.sum` (`function`): `(int -> int) -> int -> int -> int` — Sum `f n` over `n` in `[a, b)`.

## SumParam
- `SumParam.sum` (`function`): `('a -> int -> int) -> 'a -> int -> int -> int` — Sum `f x n` over `n` in `[a, b)` with parameter `x`.

## Fact
- `Fact.fact` (`function`): `int -> int` — Factorial.

## Iter
- `Iter.iter` (`function`): `('a -> 'a) -> int -> 'a -> 'a` — Iterate function `k` times.

## IntInf
- `IntInf.add` (`function`): `IntInf.t -> IntInf.t -> IntInf.t` — Addition with an infinity constructor.
- `IntInf.eq` (`predicate`): `IntInf.t -> IntInf.t -> bool` — Equality on extended integers.
- `IntInf.lt` (`predicate`): `IntInf.t -> IntInf.t -> bool` — Strict order on extended integers.
- `IntInf.le` (`predicate`): `IntInf.t -> IntInf.t -> bool` — Non-strict order on extended integers.

## SimpleInduction
- `SimpleInduction.p` (`predicate`): `int -> bool` — Generic predicate for nonnegative induction.

## Induction
- `Induction.p` (`predicate`): `int -> bool` — Predicate used for bounded/unbounded nonnegative induction forms.

## Fibonacci
- `Fibonacci.fib` (`function`): `int -> int` — Fibonacci number by recursion.

## WFltof
- `WFltof.f` (`function`): `WFltof.t -> int` — Mapping into integers used for well-founded order.
- `WFltof.ltof` (`predicate`): `WFltof.t -> WFltof.t -> bool` — Lexicographic-to-function order (`f x < f y`).
