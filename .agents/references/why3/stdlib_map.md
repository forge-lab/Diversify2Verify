# map.html Reference

## Map
- `Map.get` (`function`): `map 'a 'b -> 'a -> 'b` — Function application/lookup on maps.
- `Map.set` (`function`): `map 'a 'b -> 'a -> 'b -> map 'a 'b` — Functional update that replaces the value at a key.
- `Map.[]` (`function`): `map 'a 'b -> 'a -> 'b` — Indexing notation for map lookup.
- `Map.[<-]` (`function`): `map 'a 'b -> 'a -> 'b -> map 'a 'b` — Indexing update notation for map assignment.

## Const
- `Const.const` (`function`): `'b -> map 'a 'b` — Constant map returning a fixed value for all keys.

## MapExt
- `MapExt.==` (`predicate`): `('a -> 'b) -> ('a -> 'b) -> bool` — Extensional equality of functions (maps).

## MapSorted
- `MapSorted.le` (`predicate`): `elt -> elt -> bool` — Ordering predicate for values.
- `MapSorted.sorted_sub` (`predicate`): `map int elt -> int -> int -> bool` — Segment `[l, u)` of a map is sorted under `le`.

## MapEq
- `MapEq.map_eq_sub` (`predicate`): `map int 'a -> map int 'a -> int -> int -> bool` — Equality of two maps on index range `[l, u)`.

## MapExchange
- `MapExchange.exchange` (`predicate`): `map int 'a -> map int 'a -> int -> int -> int -> bool` — Two maps differ by exchanging values at two indices.

## MapSum
- `MapSum.sum` (`function`): `map int int -> int -> int -> int` — Sum of map values `m[i]` over `l <= i < h`.

## Occ
- `Occ.occ` (`function`): `'a -> map int 'a -> int -> int -> int` — Number of occurrences of a value in a map range `[l, u)`.

## MapPermut
- `MapPermut.permut` (`predicate`): `map int 'a -> map int 'a -> int -> int -> bool` — Two maps are permutations on range `[l, u)` (same occurrence count for all values).

## MapInjection
- `MapInjection.injective` (`predicate`): `map int int -> int -> bool` — Map is injective on `[0, n-1]`.
- `MapInjection.surjective` (`predicate`): `map int int -> int -> bool` — Map is surjective from `[0, n-1]` onto `[0, n-1]`.
- `MapInjection.range` (`predicate`): `map int int -> int -> bool` — Map values stay within `[0, n-1]` on domain `[0, n-1]`.
