# RISKS: scoreboard_walker

Constructs not shown in any verified app, with what each is based on.

1. Walker with an argument as a `has` field.
   - `services/scores.jac` line 23: `has team: str;` in `walker:pub add_point`.
   - Based on `skills/jac-sv-endpoints.md` line 52: `has title: str;                       # request body field`
     (inside `walker:pub add_task`), and line 73: "`POST /walker/<name>` - spawn a walker; body maps onto `has` fields."

2. Spawning a walker with a keyword argument.
   - `components/ScoreboardPanel.jac` line 22: `result = root spawn add_point(team=team_name);`
   - Based on `skills/jac-fullstack-patterns.md` line 39: `result = root spawn add_task(title=title);      # kwargs -> \`has title: str;\``
     and line 28: "**KWARGS only** - they map to the walker's `has` fields".

3. Reading the walker's own field as `self.team` and filtering the edge list by a field.
   - `services/scores.jac` line 26: `visit [-->][?:Team][?name == self.team];`
   - Filter form based on `skills/jac-sv-persistence.md` line 54: `[root -->][?:Post][?author == "alice"]     # filter by any has-field (brackets, not parens - W0061)`.
     `self.<field>` in a walker ability based on `skills/jac-sv-endpoints.md` line 55: `Item(title=self.title)`.
     Using `self.team` inside the `[?...]` filter (rather than a literal) is not shown anywhere: a guess.

4. Replacing a node in client state from a walker report (not a `def:pub` return).
   - `components/ScoreboardPanel.jac` lines 24-25: `updated = result.reports[0];` then
     `teams = [updated if jid(t) == jid(updated) else t for t in teams];`
   - The replace comprehension is from `exemplar/app/components/HabitsDashboard.jac` line 42 (there with a `def:pub`
     return); that a reported node keeps the same `jid` as the one from `open_scoreboard` is based on
     `skills/jac-fullstack-patterns.md` line 48: "graph identity survives the wire".

5. Two `here ++>` creations in one seed block (`services/scores.jac` lines 11-12): the exemplar seeds several nodes in
   a `for` loop (`exemplar/app/services/habits.jac` lines 18-20); the display order Home then Away relies on edges
   being visited in creation order, which no verified flow checks for two node values. The flow matches by text, so
   order does not affect it.

6. The flow ends with `New game` after the reload step (as the requested flow says), not with the reload check itself;
   the reload check (`Home: 2`, `Away: 1`) is still present before it.
