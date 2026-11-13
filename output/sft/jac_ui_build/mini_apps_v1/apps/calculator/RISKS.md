# RISKS: calculator

Constructs not found verbatim in the exemplar or the skill files:

1. `components/Calculator.jac` lines 11, 22: nested `def` with a non-None return type (`def compute(...) -> float`, `def show(n: float) -> str`) inside the component. Based on the exemplar's nested handlers (`def set_adding`, `async def handle_add(...) -> None`) and ordinary top-level `def ... -> str` in `lib/days.jac`.
2. `components/Calculator.jac` lines 6, 40, 43: `has value: float = 0.0` assigned from `int(d)` and `value * 10 + int(d)` (an int stored in a float field). Based on `int(goal)` in `NewHabitDialog.jac`; int-to-float assignment is assumed to type-check.
3. `components/Calculator.jac` lines 23-26: `round(n)` compared with a float and `str(round(n, 2))` for the decimal case. `round(x, 2)` is from jac-cl-components ("Number formatting"); `round(...)` with one argument is from `HabitsDashboard.jac` line 60. That JS `str()` of a rounded float prints e.g. "3.33" (not "3.330") is assumed.
4. `components/Calculator.jac` line 107: `variant="default"` on Button (the exemplar only uses `variant="outline"` or no variant). Based on the standard shadcn Button variants.
5. `components/Calculator.jac` line 102: `role="status"` on the display div (the exemplar only uses `aria-label`). Plain HTML attribute, assumed to pass through like `aria-label`.
6. `components/Calculator.jac` lines 54, 74, 86-95: a handler calling other handlers (`press` -> `clear`, `press_op`, ...) and setting `display` after `clear()` set it in the same handler; the later setState is assumed to win, per React batching.
7. `jac.toml` is the exemplar's copy unchanged, so its `[client.app_meta_data]` still names "Streaks" (AUTHOR.md allows changing only `[jac-shadcn]`).
