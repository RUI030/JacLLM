# RISKS for counter_fn

1. `services/counter.jac` line 7: a private helper `def _tally() -> Tally` called from the `def:pub` endpoints.
   Based on `skills/jac-sv-endpoints.md` line 11 (underscore prefix keeps a function off the API); the exemplar has
   no server helper function, so calling a plain helper from a `def:pub` is not shown verbatim anywhere.
2. `services/counter.jac` lines 8-11: `found = [root-->][?:Tally]; if found { return found[0]; }` - list truthiness
   and indexing a filtered edge query. Based on the exemplar's `if not [-->][?:Habit]` (services/habits.jac line 17)
   and `skills/jac-cl-components.md` (`songs[0]`); `found[0]` on an edge query is not shown in a verified file.
3. `services/counter.jac` line 23: `tally.value = tally.value + 1` persisting an int field. Based on the exemplar's
   in-place `h.done_days = ...` (services/habits.jac line 42) and `i.done = not i.done` in `skills/jac-sv-endpoints.md`.
4. `services/counter.jac` lines 17-19 and 21-25: `def:pub` returning a plain `int`. Based on
   `skills/jac-sv-endpoints.md` line 15 (primitives auto-serialize); the exemplar only returns nodes.
5. `components/CounterScreen.jac` line 14: `value = await get_count();` with a primitive result inside a `try`
   in `async can with entry`. Based on the `await list_todos()` mount pattern in `skills/jac-cl-components.md` and
   pitfalls.md items 3 and 11; the exemplar's try block spawns a walker instead.
6. `jac.toml` is the exemplar's copy unchanged, so `[client.app_meta_data]` still carries the Streaks title and
   description (AUTHOR.md allows changing only `[jac-shadcn]`).
7. The flow assumes a fresh data store (`.jac/data/` empty), since it expects "Count: 0" on first open.
