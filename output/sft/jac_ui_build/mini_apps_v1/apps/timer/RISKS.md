# RISKS: timer

Nothing here was run. Each entry says what a construct is based on.

## The interval (the risky part)

Lines I relied on, quoted from the skill files:

- `skills/jac-cl-components.md` line 115: "⚠ **`entry` and `exit` compile to SEPARATE `useEffect` closures.** A handle
  created in `can with entry` (interval id, WebSocket, listener) is **invisible** in `can with exit` - the cleanup
  silently no-ops. For acquire-then-release pairs, use a single manual `useEffect` whose body returns the cleanup - and
  the outer lambda must NOT be annotated `-> None` (it returns a function)"
- `skills/jac-cl-components.md` lines 118 and 123-126:
  `import from react { useEffect }` /
  `useEffect(lambda {` / `interval = setInterval(lambda { fetch_data(); }, 5000);` /
  `return lambda { clearInterval(interval); };` / `}, []);`
- `skills/jac-cl-js-interop.md` line 90: "**Polling:** single `useEffect` returning cleanup - `interval =
  setInterval(lambda { fetch_data(); }, 5000); return lambda { clearInterval(interval); };`. Outer lambda must NOT be
  `-> None`."
- `skills/jac-cl-js-interop.md` line 86: "`setTimeout`/`setInterval`/`clearInterval` ... all available directly, no import."

How I used them: `components/Ticker.jac` lines 1 and 4-8 copy that shape exactly (empty dep list, unannotated outer
lambda, cleanup returned). The Ticker is rendered only while `running` is true (`components/Stopwatch.jac` lines
47-51), so Stop and Reset unmount it and React runs the returned `clearInterval`. A second Start leaves `running`
true and the one mounted Ticker alone; `handle_start` also only sets it when it is false.

What I am unsure of:

1. **Mount/unmount as the on/off switch.** The skill shows the pattern only with `[]` on a component that stays
   mounted. Using a conditional child to start and stop it is my own design; it relies on ordinary React unmount
   cleanup, which the skill does not state for Jac. (Under React StrictMode in dev the effect runs, cleans up and runs
   again on mount; the cleanup should keep that to one interval.)
2. **Stale closure in the interval callback.** `skills/jac-cl-components.md` line 3: "all `useState` semantics apply:
   writes are async, the closure stays stale until the next render", and line 171: "**Long-running async code reads a
   STALE snapshot of `has` state.** ... Accumulate into a LOCAL and assign the whole value each step". The interval
   callback is created once, so `seconds = seconds + 1` there would read 0 every tick and stick at 0:01. To avoid
   reading any `has` field in the callback, the count lives in a module `glob _elapsed` (`components/Stopwatch.jac`
   lines 5-15) and `handle_tick` only *assigns* `seconds = next_second();` (line 27). Basis: `skills/jac-cl-js-interop.md`
   line 40 ("`glob` in a client module is a JS module variable: shared across all components importing the module,
   survives re-renders, NOT reactive") and `skills/jac-core-cheatsheet.md` lines 76-79 / 86 (a bare assignment in a
   function "assigns the glob directly - no `global` statement"). Unsure: the skills show a glob assigned from a
   module-level `def`, but not one in the same file as a component, called from a component handler that a stale
   closure holds. I also assume the `seconds` setter React gives the stale `handle_tick` still works (React setters are
   stable), which the skills do not say. The skill's own timing patterns use `Ref` value fields instead
   (`skills/jac-cl-js-interop.md` line 88, "all use `Ref` value fields - see `jac-npm-packages`"); I did not use `Ref`
   because how it is imported is in `jac-npm-packages`, which is not among the files I was given.
3. **Calling the prop from the interval.** `components/Ticker.jac` lines 5-6 copy `onTick` to a local and call it with
   `tick_cb.call(None)`, based on `skills/jac-cl-js-interop.md` lines 27-33 ("A callback held in a variable/dict and
   invoked later must be called with `.call(None, args...)`"). The skill's example is for a WebSocket handler, not a
   React prop; the exemplar calls props directly (`onSave(...)`), so a direct `onTick()` may also work.
4. **Hand-written hook.** `useEffect` is the one React hook in the app, allowed by AUTHOR.md rule 1 for this case. It is
   called at the top of `Ticker` before the return, which has no `has` fields or conditional return
   (`skills/jac-cl-components.md` line 169).

## Other constructs not found in the exemplar or skills

- `components/Stopwatch.jac` lines 18-19: `%` and `/` on ints in client code (`total % 60`, `(total - secs) / 60`).
  Not shown in the exemplar or skills. Based on these compiling to the JS operators; `(total - secs) / 60` is always a
  whole number, so `str()` should print "1" not "1.0" in the browser. `jac check` may type it as float (a type-only
  issue per pitfalls.md 13). `zfill` is from the exemplar (`lib/days.jac` line 4).
- `components/Stopwatch.jac` line 27: a no-argument `def handle_tick() { ... }` handler passed as a `Callable[[], None]`
  prop. Exemplar handlers all take an argument; `Callable[[], None]` for a no-arg callback is from
  `skills/jac-cl-components.md` line 47.
- `components/Stopwatch.jac` line 42: an `<h1>` inside `CardTitle` so the heading is a real heading; `CardTitle` and
  `CardDescription` are imported as in the exemplar (`components/HabitsDashboard.jac` line 7).
- `components/Stopwatch.jac` lines 54-55: `variant="outline"` on `Button`, taken from the exemplar
  (`components/NewHabitDialog.jac` line 53).
- `main.jac` has no services import: the app is client-only, so there is no `services/` folder (AUTHOR.md rule 2).
- `jac.toml` is the exemplar's copied unchanged, so its `[client.app_meta_data]` still describes "Streaks"; AUTHOR.md
  allows changing only `[jac-shadcn]`.
