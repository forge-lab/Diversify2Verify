# bool.html Reference

## Bool
- `Bool.andb` (`function`): `bool -> bool -> bool` — Boolean conjunction.
- `Bool.orb` (`function`): `bool -> bool -> bool` — Boolean disjunction.
- `Bool.notb` (`function`): `bool -> bool` — Boolean negation.
- `Bool.xorb` (`function`): `bool -> bool -> bool` — Boolean exclusive OR.
- `Bool.implb` (`function`): `bool -> bool -> bool` — Boolean implication.
- `Bool.=` (`predicate`): `bool -> bool -> bool` — Boolean equality.

## Ite
- `Ite.ite` (`function`): `bool -> 'a -> 'a -> 'a` — If-then-else value selector (`True -> x`, `False -> y`).
