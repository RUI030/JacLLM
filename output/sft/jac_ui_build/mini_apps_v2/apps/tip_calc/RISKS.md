# RISKS (constructs not found in a verified app)

Formatting: the verified `calculator` only shows `str(round(n))` / `str(round(n, 2))`, which drops trailing zeros ("10", not "10.00"). Two-decimal money needed more, so `money()` builds it from cents.

1. `components/TipScreen.jac` lines 11-18 (`money`): `round(n * 100)` with one argument is verified (calculator `show`); `int(cents / 100)` and `int(...)` of a float are based on `int(d)` in calculator, but int() of a float expression is unverified. String padding with `"$" + str(x) + ".0" + str(rest)` and `if rest < 10` are plain concatenation and comparison, not shown in a verified app. Float noise (e.g. 0.1+0.2) could make round() land one cent off in other inputs; the flow values are exact.
2. `TipScreen.jac` line 29 `float(text)`: float() is not shown in any verified app (calculator uses int()). Based on the Jac builtin; assumed to compile to JS parseFloat/Number.
3. `TipScreen.jac` line 30 `amount != amount` as NaN test: assumes float("abc") yields NaN and does not raise. If it raises instead, "Enter a bill amount" will not show for non-numeric text. Also parseFloat-style parsing would accept "12abc" as 12.
4. `TipScreen.jac` lines 23-37 (`apply_percent(p: int)`): a plain `def` with early `return;` and a `str` `.strip()` are verified (calculator `return;`, list_append `.strip()`); `amount * p / 100` arithmetic with an int param is not shown.
5. `TipScreen.jac` lines 48-54: `{for p in [10, 15, 20] { <Button key={p} ...> }}` with int items and `str(p) + "%"`; calculator loops over strings, not ints. Button `variant={"outline"}` is verified.
6. `TipScreen.jac`: `<Input ... />` and `<label htmlFor>` follow list_append; `shadcn.txt` lists `input` as list_append does. Hand-written `<div role="status">` with two `<p>` children is unverified markup but plain JSX.
7. Files: no `lib/utils.jac`, `components/ui/*` or `styles/global.css` were written; they are assumed to come from the template.
