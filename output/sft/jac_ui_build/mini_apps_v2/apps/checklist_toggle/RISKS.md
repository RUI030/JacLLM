# RISKS: checklist_toggle

1. `services/packing.jac` lines 5, 29 and 32: a `bool` node field (`has packed: bool = False`) and a `def:pub` that takes
   a `bool` argument (`packed: bool`) and assigns it. The exemplar's `toggle_day` takes only `str` arguments and the
   verified apps only use `str`/`int` fields. Based on the exemplar's `toggle_day` shape and standard Jac types.
2. `components/PackingList.jac` line 21: `await set_packed(jid(item), not item.packed)` sends the flipped value instead
   of the value `onCheckedChange` passes (the exemplar's lambda also ignores it, line 129). If a click arrives before the
   previous update lands, the two can disagree; the flow ticks two different items so it is not affected.
3. `components/PackingList.jac` lines 39-48: the rows are a plain `<ul>`/`<li>`, not a shadcn `Table` (exemplar uses a
   `TableCell` around its Checkbox). The Checkbox itself is used exactly as in `HabitsDashboard.jac` lines 126-130.
4. `services/packing.jac` line 21 and flow steps `{"check": 0}` / `{"check": 2}`: the nth checkbox relies on
   `visit [-->][?:PackItem]` reporting the items in the order they were seeded (Passport, Charger, Toothbrush). The
   exemplar seeds the same way but its flow never checks order. Not verified.
5. `components/PackingList.jac` line 47: `className={"..." + ("..." if item.packed else "")}` on a per-item element
   inside a `for`; the exemplar uses the same concatenation on `TableHead` (line 114), not inside a loop row.
6. `components/PackingList.jac` lines 36-37 and 52-54: the items and the "N of 3 packed" line render only after the
   first walker read returns, so the first `expect_text` relies on the flow waiting for the text to appear.
