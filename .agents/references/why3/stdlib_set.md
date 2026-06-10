# set.html Reference

## Set
- `Set.mem` (`predicate`): `'a -> Set.set 'a -> bool` — Membership in a possibly-infinite set.
- `Set.subset` (`predicate`): `Set.set 'a -> Set.set 'a -> bool` — Set inclusion.
- `Set.is_empty` (`predicate`): `Set.set 'a -> bool` — Empty-set predicate.
- `Set.add` (`function`): `'a -> Set.set 'a -> Set.set 'a` — Insert an element.
- `Set.singleton` (`function`): `'a -> Set.set 'a` — Singleton set.
- `Set.remove` (`function`): `'a -> Set.set 'a -> Set.set 'a` — Remove an element.
- `Set.union` (`function`): `Set.set 'a -> Set.set 'a -> Set.set 'a` — Union.
- `Set.inter` (`function`): `Set.set 'a -> Set.set 'a -> Set.set 'a` — Intersection.
- `Set.diff` (`function`): `Set.set 'a -> Set.set 'a -> Set.set 'a` — Set difference.
- `Set.complement` (`function`): `Set.set 'a -> Set.set 'a` — Set complement.
- `Set.pick` (`function`): `Set.set 'a -> 'a` — Arbitrary element chooser.
- `Set.disjoint` (`predicate`): `Set.set 'a -> Set.set 'a -> bool` — Disjointness test.
- `Set.product` (`function`): `Set.set 'a -> Set.set 'b -> Set.set ('a, 'b)` — Cartesian product.
- `Set.filter` (`function`): `Set.set 'a -> ('a -> bool) -> Set.set 'a` — Filter by predicate.
- `Set.map` (`function`): `('a -> 'b) -> Set.set 'a -> Set.set 'b` — Map a function over set elements.

## Cardinal
- `Cardinal.is_finite` (`predicate`): `Set.set 'a -> bool` — Finiteness of possibly-infinite sets.
- `Cardinal.cardinal` (`function`): `Set.set 'a -> int` — Cardinality (with finiteness side conditions).

## Fset
- `Fset.mem` (`predicate`): `'a -> Fset.fset 'a -> bool` — Membership in a finite set.
- `Fset.==` (`predicate`): `Fset.fset 'a -> Fset.fset 'a -> bool` — Set extensional equality.
- `Fset.subset` (`predicate`): `Fset.fset 'a -> Fset.fset 'a -> bool` — Inclusion.
- `Fset.is_empty` (`predicate`): `Fset.fset 'a -> bool` — Empty finite set predicate.
- `Fset.add` (`function`): `'a -> Fset.fset 'a -> Fset.fset 'a` — Insert an element.
- `Fset.singleton` (`function`): `'a -> Fset.fset 'a` — Singleton finite set.
- `Fset.remove` (`function`): `'a -> Fset.fset 'a -> Fset.fset 'a` — Remove an element.
- `Fset.union` (`function`): `Fset.fset 'a -> Fset.fset 'a -> Fset.fset 'a` — Union.
- `Fset.inter` (`function`): `Fset.fset 'a -> Fset.fset 'a -> Fset.fset 'a` — Intersection.
- `Fset.diff` (`function`): `Fset.fset 'a -> Fset.fset 'a -> Fset.fset 'a` — Set difference.
- `Fset.pick` (`function`): `Fset.fset 'a -> 'a` — Arbitrary element chooser.
- `Fset.disjoint` (`predicate`): `Fset.fset 'a -> Fset.fset 'a -> bool` — Disjointness.
- `Fset.filter` (`function`): `Fset.fset 'a -> ('a -> bool) -> Fset.fset 'a` — Filter finite set.
- `Fset.map` (`function`): `('a -> 'b) -> Fset.fset 'a -> Fset.fset 'b` — Map over finite set.
- `Fset.cardinal` (`function`): `Fset.fset 'a -> int` — Finite-set cardinality.

## FsetInduction
- `FsetInduction.p` (`predicate`): `Fset.fset 't -> bool` — Induction predicate argument over finite sets.

## FsetInt
- `FsetInt.min_elt` (`function`): `Fset.fset int -> int` — Minimum element (non-empty required).
- `FsetInt.max_elt` (`function`): `Fset.fset int -> int` — Maximum element (non-empty required).
- `FsetInt.interval` (`function`): `int -> int -> Fset.fset int` — Integer interval set `[l, r)`.

## FsetSum
- `FsetSum.sum` (`function`): `Fset.fset 'a -> ('a -> int) -> int` — Sum of a function over a finite set.

## SetApp
- `SetApp.eq` (`predicate`): `SetApp.elt -> SetApp.elt -> bool` — Element equality used by concrete applicative set.
- `SetApp.mk` (`function`): `Fset.fset SetApp.elt -> SetApp.set` — Build applicative set from finite-set representation.
- `SetApp.mem` (`function`): `SetApp.elt -> SetApp.set -> bool` — Membership.
- `SetApp.==` (`predicate`): `SetApp.set -> SetApp.set -> bool` — Set equality.
- `SetApp.subset` (`function`): `SetApp.set -> SetApp.set -> bool` — Inclusion.
- `SetApp.empty` (`function`): `unit -> SetApp.set` — Empty set.
- `SetApp.is_empty` (`function`): `SetApp.set -> bool` — Empty check.
- `SetApp.add` (`function`): `SetApp.elt -> SetApp.set -> SetApp.set` — Insert element.
- `SetApp.singleton` (`function`): `SetApp.elt -> SetApp.set` — Singleton set.
- `SetApp.remove` (`function`): `SetApp.elt -> SetApp.set -> SetApp.set` — Remove element.
- `SetApp.union` (`function`): `SetApp.set -> SetApp.set -> SetApp.set` — Union.
- `SetApp.inter` (`function`): `SetApp.set -> SetApp.set -> SetApp.set` — Intersection.
- `SetApp.diff` (`function`): `SetApp.set -> SetApp.set -> SetApp.set` — Difference.
- `SetApp.choose` (`function`): `SetApp.set -> SetApp.elt` — Remove-free element chooser (requires non-empty).
- `SetApp.disjoint` (`function`): `SetApp.set -> SetApp.set -> bool` — Disjointness.
- `SetApp.cardinal` (`function`): `SetApp.set -> int` — Cardinality.

## SetAppInt
- `SetAppInt.min_elt` (`function`): `SetApp.set -> int` — Integer set minimum (non-empty required).
- `SetAppInt.max_elt` (`function`): `SetApp.set -> int` — Integer set maximum (non-empty required).
- `SetAppInt.interval` (`function`): `int -> int -> SetApp.set` — Integer interval set.

## SetImp
- `SetImp.eq` (`predicate`): `SetImp.elt -> SetImp.elt -> bool` — Element equality used by concrete imperative set.
- `SetImp.mem` (`function`): `SetImp.elt -> SetImp.set -> bool` — Membership.
- `SetImp.==` (`predicate`): `SetImp.set -> SetImp.set -> bool` — Set equality.
- `SetImp.subset` (`function`): `SetImp.set -> SetImp.set -> bool` — Inclusion.
- `SetImp.empty` (`function`): `unit -> SetImp.set` — Empty set.
- `SetImp.clear` (`function`): `SetImp.set -> unit` — Clear a set in place.
- `SetImp.is_empty` (`function`): `SetImp.set -> bool` — Empty check.
- `SetImp.add` (`function`): `SetImp.elt -> SetImp.set -> unit` — Insert element in place.
- `SetImp.singleton` (`function`): `SetImp.elt -> SetImp.set` — Build singleton set.
- `SetImp.remove` (`function`): `SetImp.elt -> SetImp.set -> unit` — Remove element in place.
- `SetImp.choose` (`function`): `SetImp.set -> SetImp.elt` — Arbitrary element chooser (requires non-empty).
- `SetImp.choose_and_remove` (`function`): `SetImp.set -> SetImp.elt` — Choose and remove one element.
- `SetImp.disjoint` (`function`): `SetImp.set -> SetImp.set -> bool` — Disjointness.
- `SetImp.cardinal` (`function`): `SetImp.set -> int` — Cardinality.

## SetImpInt
- No additional function/predicate declarations (clone-only module).
