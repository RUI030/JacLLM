# RISKS: list_append

1. `components/GuestList.jac` line 46: the "Name" label is a plain HTML `<label htmlFor="name">`, not shadcn `FieldLabel`.
   The exemplar labels its Input only through `Field`/`FieldLabel` (`NewHabitDialog.jac` lines 34-36); the spec asks
   for only `input` and `table`, so the label part uses a plain element. Based on standard JSX plus the exemplar's
   `htmlFor` attribute on `FieldLabel`. If the flow's `fill` by label does not find the box, add `field` to shadcn.txt
   and switch to `Field` + `FieldLabel`.
2. `components/GuestList.jac` line 16: `guests = result.reports or [];`. The exemplar assigns `result.reports`
   directly (it always seeds, so reports are never empty). The `or []` guard for an empty list is based on the
   `name = user?.name or "Anonymous";` idiom in jac-core-cheatsheet and the empty-reports check in
   jac-fullstack-patterns. Not verified in a browser with zero reports.
3. `components/GuestList.jac` line 17: `except Exception {` without `as e` (the exemplar writes `except Exception as e`).
   Based on jac-core-cheatsheet ("drop the clause: `except ValueError { ... }`").
4. `components/GuestList.jac` line 66: `{for (i, g) in enumerate(guests) { ... }}` for the "#" column. Not in the
   exemplar; based on jac-cl-components ("`enumerate` destructuring needs parens").
5. `services/guests.jac` line 9: the rows rely on `visit [-->][?:Guest]` reporting guests in the order their edges were
   added to root. The exemplar uses the same walker shape but its flow never checks order. Not verified.
