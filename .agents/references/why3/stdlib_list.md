# list.html Reference

## List
- `List.is_nil` (`predicate`): `list 'a -> bool` — True exactly when the list is empty.

## Length
- `Length.length` (`function`): `list 'a -> int` — Returns the number of elements in a list.

## Mem
- `Mem.mem` (`predicate`): `'a -> list 'a -> bool` — Tests whether an element occurs in a list.

## Quant
- `Quant.for_all` (`function`): `('a -> bool) -> list 'a -> bool` — Tests that a predicate holds for every list element.
- `Quant.for_some` (`function`): `('a -> bool) -> list 'a -> bool` — Tests that a predicate holds for some list element.
- `Quant.mem` (`function`): `('a -> 'a -> bool) -> 'a -> list 'a -> bool` — Membership test under a custom equality relation.

## Elements
- `Elements.elements` (`function`): `list 'a -> fset 'a` — Converts a list into a finite set of its elements.

## Nth
- `Nth.nth` (`function`): `int -> list 'a -> option 'a` — Returns the n-th element as `Some` or `None` when out of bounds.

## NthNoOpt
- `NthNoOpt.nth` (`function`): `int -> list 'a -> 'a` — Partial headless nth accessor at index `n`.

## NthLength
- No function/predicate declarations (lemma-only module).

## HdTl
- `HdTl.hd` (`function`): `list 'a -> option 'a` — Returns optional head element.
- `HdTl.tl` (`function`): `list 'a -> option (list 'a)` — Returns optional tail list.

## HdTlNoOpt
- `HdTlNoOpt.hd` (`function`): `list 'a -> 'a` — Total head selector (axiomatically specified).
- `HdTlNoOpt.tl` (`function`): `list 'a -> list 'a` — Total tail selector (axiomatically specified).

## NthHdTl
- No function/predicate declarations (lemma-only module).

## Append
- `Append.++` (`function`): `list 'a -> list 'a -> list 'a` — List concatenation.

## NthLengthAppend
- No function/predicate declarations (lemma-only module).

## Reverse
- `Reverse.reverse` (`function`): `list 'a -> list 'a` — Reverses a list.

## RevAppend
- `RevAppend.rev_append` (`function`): `list 'a -> list 'a -> list 'a` — Tail-recursive helper for list reversal with accumulator.

## Combine
- `Combine.combine` (`function`): `list 'a -> list 'b -> list ('a, 'b)` — Zips two lists into a list of pairs.

## Sorted
- `Sorted.le` (`predicate`): `t -> t -> bool` — User-supplied ordering relation for sortedness.
- `Sorted.sorted` (`predicate`): `list t -> bool` — Inductive predicate: list is sorted according to `le`.

## SortedInt
- No function/predicate declarations (clone-only module).

## RevSorted
- `RevSorted.compat` (`predicate`): `list t -> list t -> bool` — Checks head compatibility for adjacent elements across two lists.
- `RevSorted.ge` (`predicate`): `t -> t -> bool` — Reverse-order relation `le y x`.
- `RevSorted.le` (`predicate`): `t -> t -> bool` — Reused ordering relation (from module parameter `t`).

## NumOcc
- `NumOcc.num_occ` (`function`): `'a -> list 'a -> int` — Counts occurrences of a value in a list.

## Permut
- `Permut.permut` (`predicate`): `list 'a -> list 'a -> bool` — Lists are permutations iff they have equal occurrence counts.

## Distinct
- No function/predicate declarations (inductive-only module).

## Prefix
- `Prefix.prefix` (`function`): `int -> list 'a -> list 'a` — Takes the first `n` elements (or fewer).

## Sum
- `Sum.sum` (`function`): `list int -> int` — Sums all integers in a list.

## Map
- `Map.map` (`function`): `('a -> 'b) -> list 'a -> list 'b` — Maps a function over each element.

## FoldLeft
- `FoldLeft.fold_left` (`function`): `('b -> 'a -> 'b) -> 'b -> list 'a -> 'b` — Left fold over a list.

## FoldRight
- `FoldRight.fold_right` (`function`): `('a -> 'b -> 'b) -> list 'a -> 'b -> 'b` — Right fold over a list.

## ListRich
- No function/predicate declarations (module re-export/collection).
