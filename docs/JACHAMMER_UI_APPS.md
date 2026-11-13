# Reference web apps for UI training (jac 0.34.28, JacHammer template)

Date: 2026-11-11. Purpose: give the model complete examples of designed web apps built the way the JacHammer prompt asks.
Each app starts from JacHammer's empty template (`jacBuilder/assets/templates/empty.jacpack`). It is built with the
built-in commands, follows the `jaccoder-design` guide, and ends with a browser check of the whole user flow.

Earlier rows that show working behavior with plain UI stay in the training data. This set adds the UI side.

## First batch: 10 apps

The "Guide recipe" column refers to the `jaccoder-design` recipe sections; 3.3 is the inset-sidebar shell.

| # | App | Screen type and guide recipe | shadcn components installed | `jac retheme` | Server data |
|---|---|---|---|---|---|
| 1 | Ledgerly, household expenses | monitor (3.3 + 3.4) and browse (3.5), Add dialog | sidebar, table, badge, dialog, input, field, empty, select | nova, neutral, emerald, inter | expenses on the graph |
| 2 | Brewline, coffee subscription | persuade (3.9): split hero with product preview, bento, pricing, waitlist | badge, input, field, separator | vega, stone, amber, outfit | waitlist sign-ups, duplicate email rejected |
| 3 | Harbor, team chat | workspace (3.7): channel list, messages, composer | avatar, input, badge, separator, empty | nova, zinc, sky, dm-sans | channels and messages |
| 4 | Sprintboard, kanban | workspace board (3.7), New task dialog, move buttons | badge, avatar, dialog, input, field, select | lyra, zinc, indigo, geist | tasks and their status |
| 5 | Fieldnotes, private notebook | capture (3.2): split sign-in and sign-up, then browse | input, field, textarea, dialog, empty, badge | nova, stone, rose, figtree | per-user notes (`walker:priv`, `def:priv`) |
| 6 | Pantry, recipes | browse grid with search and ToggleGroup filter; focus page (3.8) with a servings scaler | input, badge, toggle-group, separator, empty | maia, stone, orange, nunito-sans | none (client data) |
| 7 | Streaks, habits | monitor (3.4): numbers row, 7-day checkbox table, Progress bars | checkbox, progress, dialog, input, field, select, badge, empty, table | nova, neutral, green, outfit | habits and the days they were done |
| 8 | Shelfmark, bookmarks | inset sidebar with tag filters, browse table, AlertDialog delete | sidebar, table, badge, dialog, alert-dialog, input, field, select, empty | mira, gray, blue, inter | bookmarks |
| 9 | Confwave, conference | browse with Tabs per day, focus page per session | tabs, badge, avatar, separator, empty | vega, neutral, violet, raleway | the visitor's saved sessions |
| 10 | Clientbook, CRM | inset sidebar, numbers row and browse table; focus page with an activity timeline | sidebar, table, badge, dialog, input, textarea, field, select, empty, avatar | nova, stone, teal, public-sans | clients and the activity on each |

What every app has:

- **Built with the template's commands:** `jac install --shadcn` and `jac retheme` with all six flags.
- **No template splash left:** `frontend.cl.jac` is deleted, and `main.jac` renders the app.
- **Design rules from the guide:**
  - one brand mark;
  - semantic colors only;
  - loading, empty and error states;
  - real copy;
  - one solid primary action per screen;
  - a phone layout.

## How they were checked

`jac check` passes on every file. Each app was then run with `jac start --dev` on 0.34.28 and driven in Chrome by
`script/eval/agent/e2e_check.py`. Each flow comes from the request, for example: add two expenses, search, reload, and
check the dashboard totals. All 10 flows pass, and every screenshot was looked at.

Steps added to the checker for these flows:

| Step | What it does |
|---|---|
| `fill` by label | types into the field with that label |
| `choose` | picks an option from a shadcn Select, found by its label |
| `click` on checkboxes | `click` now also matches checkboxes |
| `viewport` | resizes the page, used for the phone layout |
| `full_page` | takes a full-page screenshot |

Option `--node-modules`: the harness projects only install the Inter font, so a copy of node_modules with the other
fonts was used.

## Runtime findings on 0.34.28

- **A `def:pub` read is never refreshed after a write.**
  - What happens: the client caches reader endpoints for 60 s.
  - Cause: the boundary analysis gives a `def:pub` reader the touch set `["*"]`. A writer that creates a node gets the
    node's type, for example `["Expense"]`. The runtime's overlap test only clears a reader when the writer's set
    contains `"*"` or the two sets share a name, so this reader is never cleared.
  - Effect: in a write-then-refetch handler, the refetch returns the old list.
  - What the apps do instead: read through a walker that enters the node type (`visit [-->][?:Expense]` plus
    `can collect with Expense entry { report here; }`). Walker reads are not in the cache map, so they always reach
    the server. The client also updates its state from the writer's return value.
- **Typed lambdas use parentheses on 0.34.28:** `lambda (e: T) -> R { ... }`.
- **No inline `key=lambda` in client `sorted()`:** use a named key function.
- **Globs:**
  - A glob in a module whose only client code is JSX gets no client copy (E5082). Keep shared client data in the
    module of the page that renders it.
  - Lists or dicts nested inside a glob need an `as` cast before a loop.

## Second batch: 10 multi-page apps with file-based routing

Every app uses a `pages/` directory instead of a manual `<Router>`. `main.jac` exports `def:pub app(children)`, which
renders `<>{children}</>`. Each app covers a new kind of screen, has at least 5 routes, and has a designed 404 page and
an in-app state for an unknown id.

| App | Kind | Routes and routing features | `jac retheme` (style, base, accent, font) | Server data |
|---|---|---|---|---|
| Cartwell | online store | `/`, `/shop?category=&sort=`, `/products/[slug]`, `/cart`, `/checkout` (full-screen through the root layout), `/orders/[id]`; cart in a `createContext` provider mounted by `app(children)` | maia, neutral, red, dm-sans | cart lines, orders |
| Hireboard | job board | `/`, `/jobs?q=&type=&remote=`, `/jobs/[id]`, `/jobs/<id>/apply` through `jobs/[...rest].jac`, `/applications`, `/companies/[slug]`; filters in a Sheet on phones | mira, zinc, lime, geist | applications |
| Inkwell | magazine | `/`, `/posts/[slug]`, `/tags/[tag]`, `/authors/[handle]`, `/archive?year=&page=`, `/about`, `/posts` → `Navigate` | luma, neutral, neutral, public-sans | comments, claps |
| Coursely | online courses | `/?level=`, `/courses/[id]`, `/courses/<id>/lessons/<lesson>` through `courses/[...rest].jac`, `/my-learning`; the lesson reader is full-screen through the root layout | rhea, gray, yellow, figtree | enrollments, lesson completion |
| Northdocs | docs site | `/`, `/manual/[slug]` (side nav marks the current page, prev/next, "On this page"), `/manual` → `Navigate`, `/search?q=`, `/changelog` | mira, zinc, cyan, geist | "was this helpful" votes |
| Tablefor | restaurant | `/`, `/menu?course=`, `/reserve?step=1\|2\|3` (party, date and time kept in the URL), `/reservations`, `/reservations/[code]` | vega, stone, orange, dm-sans | reservations, fully booked slots |
| Deskline | helpdesk with accounts | `/login`, `/signup` (full-screen); under `pages/(auth)/`: `/` → `Navigate`, `/tickets?status=&q=`, `/tickets/new`, `/tickets/[id]`, `/reports` | vega, neutral, purple, geist | per-user tickets and replies (`walker:priv`, `def:priv`) |
| Teamroom | settings console | `/`, `/settings` → `Navigate` to `/settings/profile`, `/settings/{profile,notifications,team,billing}`, each wrapped in a `SettingsShell` component | mira, zinc, zinc, dm-sans | profile, notification switches, members, plan |
| Staylight | vacation rentals | `/` search form → `/stays?city=&guests=&price=&sort=`, `/stays/[id]?checkin=&checkout=&guests=`, `/book/[id]` (slim header through the root layout), `/trips`, `/trips/[id]` | maia, stone, pink, figtree | trips |
| Pulse | analytics dashboard | `/?range=7d\|30d\|90d` with a Chart, `/reports`, `/reports/[id]`, `/events?type=&page=` with Pagination; inset sidebar shell in the root layout | mira, zinc, indigo, geist | days, events, saved reports, seeded with a fixed random seed |

Browser flows, all passing, 59 to 89 steps each:
- every route is visited by clicking links;
- filters are checked in the URL and after a reload;
- deep links to `[id]` pages are reloaded;
- forms are submitted and their results checked after a reload;
- the flow hits an unknown id, the 404 page and the auth redirect;
- it ends with full-page phone screenshots at 390x844.

The apps were built by 5 parallel agents from one written brief. I reviewed every app's screenshots and sent back
three fixes:
- form errors that stayed after the field was corrected (Tablefor, Hireboard);
- the Pulse events table cut off at phone width;
- raw palette colors on the Pulse trend numbers.

## Routing findings on 0.34.28

The routing guide (`jac-cl-routing`) describes several features that 0.34.28 does not have. The model reads that guide in
JacHammer, so it will hit these too.

| Guide says | What 0.34.28 does | What the apps do |
|---|---|---|
| A `layout.jac` in a subfolder wraps that folder's routes | The generated entry uses only `layouts["/"]`; other layouts are compiled and never rendered | A section shell component (`SettingsShell`, `DocsShell`) that each page of the section wraps itself in; full-screen pages branch on `useLocation().pathname` in the root layout |
| `[id]` works as a folder name (`pages/jobs/[id]/apply.jac`) | Only file names are converted; the route becomes the literal `/jobs/[id]/apply` and falls through to the 404 page | `pages/jobs/[...rest].jac` (matches `/jobs/*`, while `[id].jac` still wins for `/jobs/:id`) and split `useParams()["*"]`, or a flat route such as `pages/book/[id].jac` |
| Any path name can be a route | In dev, Vite sends `/walker`, `/function`, `/user`, `/introspect`, `/static`, `/docs`, `/openapi.json`, `/admin`, `/graph`, `/redoc`, `/assets` to the API server; a reload on `/docs/x` ends in an endless recompile loop | Northdocs serves its pages at `/manual/[slug]` |
| `new(URLSearchParams, location.search).get("q")` | Works at runtime, but `jac check` reports E1053 and E1031 on it | `search: any = new(URLSearchParams, ...)  # jac:ignore[E1053]` in one helper |

What works as the guide says:
- root `pages/layout.jac` with `<Outlet />`;
- `index.jac`, nested folders, `[id].jac` and `[...notFound].jac`;
- the `(auth)/` group, which redirects to `/login`;
- `useParams`, `useNavigate`, `<Navigate replace>`, `<Link>` and active links through `useLocation`.

`useParams()` values passed to a `str` prop need `(params["x"] or "") as str` (E1100).

## More 0.34.28 findings from the second batch

- **Helpers shared by several client modules.**
  - Problem: a plain `lib/format.jac` imported by more than one client module is only exported for the first importer.
    Other pages fail to load with "does not provide an export named 'initials'".
  - Cause: a later importer clears the client JS of the earlier one (`codespace_pull_pass.pull_import_items_client`).
  - `[placement.pins]` has no effect on 0.34.28.
  - What works: `lib/x.cl.jac` with `def:pub` helpers; a plain `def` there is not exported. Alternatively, keep a helper
    in the component module that uses it. An `obj` is never exported to client JS; use `import type` for annotations.
- **`Empty` and its parts, and `Sidebar*`, drop their base classes when given `className`.**
  - Cause: the installed primitive spreads the props after `className`.
  - Fix: put the border or padding on a wrapper `div`. The first batch's 9 empty states were changed this way and their
    flows rerun.
- **State assigned in a handler is not readable until the next render.** Validate with local variables, then assign
  them to state.
- **Client code generation:**
  - `{key: v}` with a variable key keeps the literal name `key`, also inside `{**d, key: v}`; assign with `d[key] = v`.
  - `del d[k]` fails client codegen; use a dict comprehension.
  - A list comprehension over a string compiles to `.filter` and fails at runtime; use a `for` loop.
- **Components:**
  - The installed `Button` does not forward refs, so `<PopoverTrigger asChild><Button>` opens off-screen. Style the
    trigger with `buttonVariants()` instead.
  - `PaginationLink` is a plain `<a>`: use router `Link`s, or add an `onClick` that calls `nav()`.
- **Client navigation keeps the old scroll position.** Two apps reset it in the root layout:
  `can with [path] entry { window.scrollTo(0, 0); }`.

## Files

- `output/sft/jac_ui_build/text/<app>.text.json`: the hand-written parts of each training row.
- `output/sft/jac_ui_build/ui_apps_harness_v1/`: the rows, screenshots and harness runs (see below).
- `output/sft/jac_ui_build/ui_apps_v1/` (first batch) and `ui_apps_v2/` (second batch), each with:
  - `apps/<app>/`: the final project sources;
  - `flows/<app>.json`: the browser flow;
  - `e2e/<app>/`: the report and one screenshot per step;
  - `overview.png`: one screenshot per app.

## Training rows through the real harness

`script/dataset/sft/ui_apps.py` turns every app into JacHammer-format SFT rows. Each app is built through jacBuilder's
`verification_runner` running jac_coder. Only the model is replaced: `script/dataset/parser/harness_replay.py` is an
OpenAI-compatible server that sends the tool calls of a known-good build in order. Everything else comes from the
harness:
- `plan_build` and the planner's `build_plan.json`;
- `jac install --shadcn`, `jac retheme`, `jac install`;
- each write's check result;
- `preview_status`;
- `browser_validate` with its Plan coverage block;
- `browser_open` and `browser_do` with their annotated screenshots.

The script follows the build steps in the harness system prompt:
1. Inspect the template, then call `plan_build`.
2. Load `jac-cl-organization` and `jac-fullstack-patterns` (build step 5).
3. Run `jac install --shadcn` and `jac retheme` with all six flags, edit `jac.toml` metadata, then run `jac install`.
4. Write the files in leaf-first order and delete `frontend.cl.jac`.
5. Check `preview_status` and `browser_validate`.
6. Open the core-flow route the coverage block names and run that flow once with `browser_do`.
7. Write `.jaccoder/agent_journal.md` and reply with **Next steps**.

The hand-written parts of each row are in `output/sft/jac_ui_build/text/<app>.text.json`:
- the user request;
- each file's purpose and the reasoning before each write;
- the plan text;
- the journal;
- the final reply;
- the browser steps.

Output (`output/sft/jac_ui_build/ui_apps_harness_v1/`):
- `train.jsonl`: 40 rows, one main-agent row and one planner row per app, in the prod-64k format of
  `script/dataset/trajectory/clean.py`. Screenshots sit inside their tool message; `finish_tool` becomes the plain-text
  reply; the project path and preview URL are made prod-shaped.
- `img/`: 108 harness screenshots.
- `runs/<app>/`: `calls.jsonl`, `replay.log`, `run.log` and `spec.json`.

Every replay finishes with no script error, no blocked write and no check error.

Token counts, using the Ornith tokenizer plus 1 token per 32x32 px of image:
- planner rows: 16k to 21k;
- main rows: 42k to 70k. Cartwell (65.8k), Tablefor (66.6k) and Staylight (69.7k) are over prod-64k's 65,536 cap.

`sft_img.py` skips rows over `max_seq_length`. A one-step test on the longest row trained it whole. Setup:
- Staylight, 69.7k tokens;
- `--max-seq-length 81920`, `--max-steps 1`, `--grad-acc 1`;
- run in its own systemd unit with `MemoryMax=17G` and `MemorySwapMax=0`.

Result:
- peak VRAM 46.2 GB of 47.35 GB usable;
- peak RAM 10 GB;
- 77 s for the step.

So all 40 rows train whole with `--max-seq-length 73728`, with no RAM offload and no splitting.

In six first-batch rows (dialog apps), opening a Dialog makes the harness report React's ref warning from the
installed `DialogOverlay`. The reply after it says the warning comes from `components/ui`, not the app, and moves on.

To rerun, raise `[byllm.compaction] ctx_window` in jacBuilder's `jac.toml` first. At 65,536 the harness compacts a
long build halfway, and the row loses its early writes. It was set back to 65,536 afterwards.

## What the real harness caught

The browser checks in sections above passed all of these; the harness did not.

| What happened | Fix in the apps or the replay |
|---|---|
| A write under `pages/` is BLOCKED while `main.jac` still has the template's parameterless `app()` | For file-based apps, main.jac is written right after services and lib |
| After `jac retheme --font`, the preview shows "Can't resolve '@fontsource-variable/<font>'" | Run `jac install` after jac.toml is final (build step 9) |
| The harness rewrites every backtick pair into an f-string, also inside strings and docstrings | No backticks in .jac files; Northdocs marks inline code with `{{ }}` |
| `import from react { createContext, useContext }` is BLOCKED (only `useEffect` is allowed), although the 0.34.28 `jac-cl-organization` guide teaches it | Cartwell reads the cart from the server on each screen; the header refetches on path change and on a `cart-changed` window event |
| `browser_do` reports page errors (console.error) to the model | All 20 apps pass `e2e_check.py --console-errors` |
| `<Button asChild><Link>`, `<XTrigger asChild><Button>`, `<BreadcrumbLink asChild>` warn: Button has no ref forwarding, and `asChild` leaks onto `<a>` | A `Link` or trigger styled with `cn(buttonVariants().call(None, {...}))`; without `cn()` conflicting classes stay and outline buttons render filled |
| `SidebarMenuButton` and `PaginationLink` leak `isActive`; Sheet and Calendar primitives warn (`SheetOverlay` ref, `rootRef`, `showCloseButton`) | Plain `Link`s with sidebar classes and `data-active`; inline fold-out panels instead of Sheet; native date inputs or a date strip instead of Calendar |
| A plain `lib/format.jac` imported by several client modules fails once the harness writes files one at a time ("does not provide an export named 'newest_first'") | `lib/format.cl.jac` with `def:pub` helpers |
| An agent-browser click on an element below the fold reports "Done" and does nothing | `focus @ref` before every `click @ref` (focus scrolls the element into view; both are allowed in one `browser_do`) |
| `app_type`/`nav_pattern` outside the planner schema | Values from `jac_coder/core/nodes.jac`, asserted when the spec is built |
| A type error (E1055) in Teamroom's 404 page that only the check caught; `jac start --dev` still serves the page | Typed the value; every own file now passes `jac check` |

`e2e_check.py --console-errors` ignores two known sources no app file can fix:
- "Failed to load resource": the checker's favicon 404 and symlinked fonts;
- the `DialogOverlay`/`AlertDialogOverlay` ref warning from the installed primitives.
