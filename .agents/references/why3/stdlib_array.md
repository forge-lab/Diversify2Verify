# array.html Reference

## Array
- `Array.[]` (`function`): `Array.array 'a -> int -> 'a` — Read element at index.
- `Array.[<-]` (`function`): `Array.array 'a -> int -> 'a -> Array.array 'a` — Pure functional update at index.
- `Array.defensive_get` (`function`): `Array.array 'a -> int -> 'a` — Safe get with bounds check, may raise `OutOfBounds`.
- `Array.defensive_set` (`function`): `Array.array 'a -> int -> 'a -> unit` — Safe set with bounds check, may raise `OutOfBounds`.
- `Array.make` (`function`): `int -> 'a -> Array.array 'a` — Create array of fixed length filled with a value.
- `Array.empty` (`function`): `unit -> Array.array 'a` — Empty array constructor.
- `Array.copy` (`function`): `Array.array 'a -> Array.array 'a` — Copy entire array.
- `Array.sub` (`function`): `Array.array 'a -> int -> int -> Array.array 'a` — Extract subarray slice `[ofs, ofs+len)`.
- `Array.fill` (`function`): `Array.array 'a -> int -> int -> 'a -> unit` — Fill a range with one value.
- `Array.blit` (`function`): `Array.array 'a -> int -> Array.array 'a -> int -> int -> unit` — Copy a range from source to destination.
- `Array.append` (`function`): `Array.array 'a -> Array.array 'a -> Array.array 'a` — Concatenate two arrays.
- `Array.self_blit` (`function`): `Array.array 'a -> int -> int -> int -> unit` — Copy within the same array with overlapping-safe direction.
- `Init.init` (`function`): `int -> (int -> 'a) -> Array.array 'a` — Build array from initializer function.

## IntArraySorted
- `IntArraySorted.sorted_sub` (`predicate`): `Array.array int -> int -> int -> bool` — Segment `[l, u)` is sorted by `<=`.
- `IntArraySorted.sorted` (`predicate`): `Array.array int -> bool` — Whole array is sorted by `<=`.

## Sorted
- `Sorted.le` (`predicate`): `elt -> elt -> bool` — User-provided element order relation.
- `Sorted.sorted_sub` (`predicate`): `Array.array elt -> int -> int -> bool` — Segment sorted under `le`.
- `Sorted.sorted` (`predicate`): `Array.array elt -> bool` — Whole array sorted under `le`.

## ArrayEq
- `ArrayEq.array_eq_sub` (`predicate`): `Array.array 'a -> Array.array 'a -> int -> int -> bool` — Segment equality on `[l, u)` with equal lengths.
- `ArrayEq.array_eq` (`predicate`): `Array.array 'a -> Array.array 'a -> bool` — Full-array equality.

## ArrayExchange
- `ArrayExchange.exchange` (`predicate`): `Array.array 'a -> Array.array 'a -> int -> int -> bool` — Arrays differ only by a swap at two indices.

## ArrayPermut
- `ArrayPermut.permut` (`predicate`): `Array.array 'a -> Array.array 'a -> int -> int -> bool` — Segment `[l, u)` are permutations.
- `ArrayPermut.permut_sub` (`predicate`): `Array.array 'a -> Array.array 'a -> int -> int -> bool` — Segment permutation with outside-segment equality.
- `ArrayPermut.permut_all` (`predicate`): `Array.array 'a -> Array.array 'a -> bool` — Full-array permutation.

## ArraySwap
- `ArraySwap.swap` (`function`): `Array.array 'a -> int -> int -> unit` — In-place swap; postcondition states the two arrays are `exchange`.

## ArraySum
- `ArraySum.sum` (`function`): `Array.array int -> int -> int -> int` — Sum of values `a[i]` for `l <= i < h`.

## NumOf
- `NumOf.numof` (`function`): `(int -> 'a -> bool) -> Array.array 'a -> int -> int -> int` — Count elements satisfying an index/value predicate.

## NumOfEq
- `NumOfEq.numof` (`function`): `Array.array 'a -> 'a -> int -> int -> int` — Count occurrences of a value in range.

## ToList
- `ToList.to_list` (`function`): `Array.array 'a -> int -> int -> List.list 'a` — Convert array slice to list.

## ToSeq
- `ToSeq.to_seq_sub` (`function`): `Array.array 'a -> int -> int -> Seq.seq 'a` — Convert slice to sequence.
- `ToSeq.to_seq` (`function`): `Array.array 'a -> Seq.seq 'a` — Convert full array to sequence.

## Inversions
- `Inversions.inversion` (`predicate`): `Array.array int -> int -> int -> bool` — Tests `a[i] > a[j]`.
- `Inversions.inversions_for` (`function`): `Array.array int -> int -> int` — Inversions contributed by fixed `i`.
- `Inversions.inversions` (`function`): `Array.array int -> int` — Total number of inversions in array.
