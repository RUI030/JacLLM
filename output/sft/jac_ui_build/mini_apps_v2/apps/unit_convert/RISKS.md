# RISKS for unit_convert

1. `components/KmPanel.jac` line 18: `km = float(raw.strip());` turns text into a number. The verified `calculator`
   never parses text (it builds its value digit by digit with `int(d)`), so `float(str)` and `str.strip()` on a
   client string are not shown there. `.strip()` is shown on a client string in `list_append` (`name.strip()`);
   `float(...)` is a plain Python-style builtin, assumed to compile to a JS number conversion.
2. `components/KmPanel.jac` lines 16-23: `try { ... return ... } except Exception { return ... }` inside a plain `def`
   used as the parse check. `try/except Exception` is shown only inside `async can with entry` in `list_append`;
   the whole app relies on `float("abc")` raising in the compiled JS. If the client compiles `float("abc")` to
   `NaN` instead of raising, "abc" would show "NaN km is NaN miles". Also `float("")` and `float("inf")` /
   `float("nan")` behave unverified.
3. `components/KmPanel.jac` lines 9-14: `show` copies the calculator's `show`: `str(round(n, 2))` does not pad
   zeros, so a result such as 62.0 would read "62" and 3.1 would read "3.1", not two fixed decimals. 10 km gives
   6.21371 -> "6.21" as the flow expects. Fixed-width formatting is not shown in a verified app (and `${x:.2f}` in JSX
   broke an app, pitfalls.md item 13), so it was not used.
4. `components/KmPanel.jac` line 19: the entered number is echoed with `show(km)`, so "10.0" reads "10 km" and
   "2.345" reads "2.35 km" (rounded), not as typed.
5. `components/KmPanel.jac` line 37: `<Input id="km" ...>` with a plain `<label htmlFor="km">` is copied from
   `list_append`; the flow fills it by label `^kilometres$`, the same way `list_append` fills `^name$`.
6. `components/KmPanel.jac` line 40: `<p role="status">` for the result line; `role="status"` is shown on a `div` in
   `calculator`, a `p` is assumed to behave the same.
7. `jac.toml`: only the `[client.app_meta_data]` text values were changed; `[project].description` still says
   "A counter saved on the server." because it was copied unchanged as instructed.
