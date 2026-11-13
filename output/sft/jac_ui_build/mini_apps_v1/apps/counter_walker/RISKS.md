# RISKS: counter_walker

1. `services/likes.jac` line 29: `here.total = here.total + 1;` mutates a node field inside a walker ability.
   The exemplar only mutates node fields inside a `def:pub` (`toggle_day`, `h.done_days = ...`), and walks/reports
   unmutated nodes in `open_habits`. Based on `jac-sv-persistence` ("Writes persist automatically") and the exemplar's
   `here` / `report here` usage in `open_habits`.
2. `services/likes.jac` lines 20-32: a walker that writes (`add_like`). The exemplar has only a reading walker; the
   writing-walker shape (`walker:pub add_task` reporting after a write) comes from `jac-sv-endpoints` "Walker endpoints",
   and spawning it from the client with no kwargs from `jac-fullstack-patterns` "Walker spawn".
3. `components/LikesCard.jac` lines 16 and 28: `result.reports[0].total as int` reads one field of the first report.
   The exemplar assigns the whole `result.reports` list; `result.reports[0]` and the `len(result.reports) > 0` guard
   come from `jac-fullstack-patterns` "Walker spawn"; the `as int` cast mirrors the exemplar's `h["goal"] as int`.
4. `components/LikesCard.jac` lines 25-33: `try/except` inside an `async def` handler. The exemplar uses `try/except`
   only inside `async can with entry`; same construct, different place.
5. `jac.toml` is the exemplar's copy unchanged, so `[client.app_meta_data]` (page title, description) still says
   "Streaks". AUTHOR.md allows changing only `[jac-shadcn]`; the flow checks visible text only.
