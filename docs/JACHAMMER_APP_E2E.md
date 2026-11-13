# JacHammer app builds: browser end-to-end check (1107, 1110, spike_v6)

Date: 2026-11-11. Checker: `script/eval/agent/e2e_check.py` (Playwright on system Chrome). It starts each final
project with `jac start --dev`, runs the scenario's `e2e.json` user flow, and saves a screenshot per step. A step fails on a
missing text or control, a blank page, Vite's error overlay, or an uncaught page error.

## Why a separate check

The harness's own `browser_validate` is not a reliable verdict:

- It passed pages that show Vite's error overlay.
- It passed 5 of the 8 app scenarios below, although each of those pages still shows the template's build splash
  ("When you start to build, changes will appear here.").

## 1. JacHammer runs (jac 0.34.28 harness)

The routing scenarios are the 6 `routing_*` ones, 2 runs each per model. The app scenarios are 8 new `app_*` ones, modeled on
TodoMVC, Trello, linkding, Actual Budget, Mealie, Rallly, Memos and Beaver Habits, with 1 run each on 1110 only.

| Model | Runs | Harness pass | Browser flow pass |
|---|---|---|---|
| 1107, routing | 12 | 4 | 1 (routing_members) |
| 1110, routing | 12 | 6 | 0 |
| 1110, app | 8 | 5 | 0 |

The first failure in each failed run falls into one of these groups:

| What the user sees | Runs | Cause found in the code |
|---|---|---|
| Template build splash, no app | 6 (app) | The model wrote components and services but never replaced the template's client entry `frontend.cl.jac` (`main.jac` imports `app` from it), so nothing it wrote is mounted. This holds for all 8 app runs; the other 2 failed earlier, as counted in the rows below. |
| Vite overlay "Failed to fetch dynamically imported module" | 8 | A client module fails to compile, e.g. `components/Home.jac` imports `.components.ui.button` (wrong relative path) and `input`, `label`, `textarea`, which were never installed. |
| Vite overlay, other compile errors | 3 | A duplicate identifier (`props`, `tag`) from a hand-written ui component; `@jac/router` import unresolved. |
| Server does not start | 7 | Syntax errors in the final code, e.g. `Missing ';'`. |
| Page error at runtime | 5 | `useParams is not defined`, `Button is not defined`, a Promise rendered as a React child, a blank render (2). |
| Page opens, but a requested control or text is missing | 2 | No search box; no About link. |

Model habits these runs show:

1. The model does not know the template's file layout: the client entry is `frontend.cl.jac`, not `main.jac`. In the
   mix_1110 training rows, 1 of 355 writes or edits `frontend.cl.jac`. `main.jac` is written 236 times.
2. It imports shadcn components that are not installed, instead of running `jac install --shadcn <name>`. It also
   hand-writes them.
3. It ends the run on the harness's pass while the page is broken. The harness pass is not a reliable signal for this.

## 2. spike_v6 "successful" web apps (jac 0.36.1)

The 10 web episodes the spike counted as successful were checked in the browser with a user flow written from the task's
request. The spike's own check was static only: tests, `jac check`, and compiling the client.

| App | Opens | User flow | Result |
|---|---|---|---|
| chat_rooms | yes | join room, send, reload, rejoin, message still there | works |
| tournament_bracket | yes | enter 6 seeds, build bracket | wrong: round 2 shows "A vs Bye", the final "Bye vs Bye" |
| class_attendance | yes | add a class | `Class is not defined` on click |
| dev_forum | yes | write a post | no post form; the page has only a link |
| memo_visibility | placeholder text only | – | not built |
| envelope_budget, item_recommender, records_crud-r2, sales_dashboard, team_invites | no (crash on load) | – | broken |

**1 of 10 works.** The others were trained as successful trajectories:

- the 22 rows from the broken and placeholder apps contain 150 student turns;
- the remaining rows of tournament_bracket, class_attendance and dev_forum also teach a broken result.

## 3. Why the UIs are plain HTML

| Data | Rows | Rows with JSX | Import shadcn ui | Use Tailwind classes |
|---|---|---|---|---|
| spike_v6 train | 776 | 267 | 0 | 18 |
| prod-64k train | 208 | 77 | 34 | 71 |
| mix_1110 (synthetic router/loop) | 75 | 54 | 0 | 60 |

- **Spike tasks.** Each one starts from an empty workspace (`workspace_kind: clean`), with no Tailwind and no shadcn.
  The requests and acceptance criteria describe only logic, and the student has no browser. Every spike app therefore
  renders as unstyled HTML. Where it does write `className` values, no stylesheet defines them.
- **JacHammer.** The harness template does ship Tailwind and shadcn (`components/ui/{button,card,skeleton}`,
  `styles/global.css`). The model's components use Tailwind classes there, but they are never mounted (see section 1).

## What would make the training data trustworthy

1. **Keep a web trajectory only if its final app passes a browser flow written from the request.** "Opens without an
   error" is not enough: tournament_bracket opens and is wrong.
2. **Build web tasks from the JacHammer template, not from an empty workspace**, so the trajectories show:
   - replacing `frontend.cl.jac`;
   - `jac install --shadcn <name>` before importing a component;
   - Tailwind or shadcn styling.
3. **Put UI requirements in the requests**: layout and the components to use. Have the e2e flow check them.

## Files

- e2e outputs per run: `output/eval/agent/<scenario>/<run>/e2e/{report.json, step_NN.png, server.log}`.
- Scenario flows: `script/eval/agent/scenarios/{routing,app}_*/e2e.json`.
