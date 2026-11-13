# RISKS for toggle_fn

1. `services/lamp.jac` lines 7-14: private helper `def _lamp() -> Lamp` with `[root-->][?:Lamp]`, `if found`, `found[0]`, `root ++> lamp`. Same shape as the verified counter_fn `_tally`; no new construct.
2. `services/lamp.jac` lines 17-24: `def:pub` returning a plain `bool`, and `lamp.lit = not lamp.lit` persisting a bool field. Based on counter_fn returning an int and on `i.done = not i.done` in `skills/jac-sv-endpoints.md` line 34.
3. `components/PorchPanel.jac` lines 31 and 36: conditional expressions as JSX children (`{"The light is on" if lit else "The light is off"}`, `{"Turn off" if lit else "Turn on"}`). Verified apps use the same `a if cond else b` form only in a JSX attribute (calculator `variant=`), not as a child; likely fine since `{expr}` children are used throughout.
4. `components/PorchPanel.jac` line 11: `lit = value;` where `value` is an awaited bool; same shape as counter_fn's int.
5. The flow assumes a fresh data store (light starts off).
