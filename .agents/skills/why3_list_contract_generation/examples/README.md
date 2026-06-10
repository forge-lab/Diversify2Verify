# List contract generation examples

These examples mirror the array contract examples but use Why3 lists:

- `count_occurrences_list.mlw`: recursive specification function over `Nil`/`Cons`.
- `max_list.mlw`: maximum specified with `mem` and universal upper bounds.
- `sorted_list.mlw`: sortedness specified with recursive `le_all` and `sorted_list` predicates.
