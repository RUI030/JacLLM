# RISKS: shopping_delete

1. `services/shopping.jac` line 26: `del it;` deletes the node found by `jid`. No verified app deletes a node, and the
   provided skills do not show the delete form: `jac-sv-persistence.md` line 60 points to a `jac-node-edge-patterns`
   skill that is not in `skills/`, `jac-sv-endpoints.md` line 42 only says the find-by-`jid` loop is "the same pattern
   for update/delete", and `jac-core-cheatsheet.md` line 134 lists `del` as a Jac keyword. `pitfalls.md` item 5 names
   `del task` as the delete statement (it fails only on a node passed from the client; here the node comes from the
   `[root-->]` loop). If the node survives a reload, the fallback is disconnecting the edge from root
   (`root del--> it;`), which is not shown in any source either.
2. `components/ShoppingScreen.jac` line 77: `aria-label` on `Button`. The exemplar puts `aria-label` only on `Checkbox`
   (`HabitsDashboard.jac` line 127); the template `components/ui/button.jac` forwards every prop except className,
   variant, size, asChild and children to `<button>` (`{**restProps}`), so the label should reach the DOM. The flow's
   `click "^remove milk$"` depends on it.
3. `components/ShoppingScreen.jac` line 53: `className="flex-1"` on `Field`. The exemplar uses `<Field>` without a
   className (`NewHabitDialog.jac` line 34). Based on shadcn components taking className; layout only.
4. `components/ShoppingScreen.jac` lines 64-68: `Empty` with only `EmptyHeader` and `EmptyTitle` (no `EmptyMedia`,
   `EmptyDescription`, `EmptyContent`). The exemplar uses all five (`HabitsDashboard.jac` lines 98-105); leaving parts
   out is based on them being independent children.
5. `components/ShoppingScreen.jac` line 71: plain `<ul>`/`<li>` rows instead of a shadcn Table. Standard JSX elements,
   like the plain `<label>`/`<p>` in the verified list_append; not in a verified app as list rows.
6. `components/ShoppingScreen.jac` line 34: the filtering comprehension `[i for i in items if jid(i) != jid(item)]`
   inside an `async def` handler. The exemplar uses filtering comprehensions in the client render body
   (`HabitsDashboard.jac` line 49) and `jid(h) == jid(habit)` in a handler (line 42), but not this exact combination.
