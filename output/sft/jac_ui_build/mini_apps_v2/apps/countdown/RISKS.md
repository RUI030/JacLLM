# Risks

- `components/TeaTimer.jac`, `handle_tick`: a local `left` is read after `seconds = left;` in the same handler, and the handler sets `running`/`finished` inside an `if`. The verified timer's handlers only assign once; this follows pitfall 11 (use a local) but the multi-assignment-in-`if` form is not in a verified app.
- `components/TeaTimer.jac`, `drop_second`: assigns a module glob inside an `if` block; the verified timer assigns the glob unconditionally.
- `components/TeaTimer.jac`: the "Done" state is a separate `finished` has field set by the tick that reaches 0 (Ticker unmounts when `running` becomes False, which is the verified cleanup path).
- `components/TeaTimer.jac`, `handle_start`: Start after "Done" refills to 3:00 and restarts; not in the brief, chosen so Start is not dead after Done.
