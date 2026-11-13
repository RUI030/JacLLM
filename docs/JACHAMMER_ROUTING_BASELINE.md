# JacHammer routing baseline: JacLLM-1107 (2026-11-09)

The model as it is today, in the real JacHammer agent, on multi-page web apps. No teacher, no extra hints. Purpose:
find what to put in the routing data before writing it.

## Setup

- **Harness:** jac_coder through `script/eval/agent/run_jaccoder.sh` (jacBuilder `evaluation/verification_runner`).
  - jacBuilder `feature/llm-agent-loop` @ 4e346d5, plus the 4 uncommitted skill-loading prompt edits (load a skill
    when a check fails, not before writing).
  - Projects run on jac **0.34.28**, the version jacBuilder bakes into its sandbox (see `docs/JAC_VERSIONS.md`).
  - Template `empty` (a jac-shadcn web app). One stage per scenario. JacHammer's own limits: 100 iterations,
    32,000 output tokens per call.
- **Model:** `JacLLM-1107-teacher-iv-v6-on-1105` Q8_0 GGUF, served with `script/eval/agent/serve.sh`.
  - One 64k slot; temp 0.6, top_p 0.95, top_k 20.
  - jacBuilder compacts at 0.6 × 65,536 tokens.
- **Scenarios:** `script/eval/agent/scenarios/routing_*`. Each is a user-style request; none names the routing
  feature it needs.

| Scenario | What the user asks for | What the app needs |
|---|---|---|
| `routing_blog` | article list; each article on its own address with a back link | a route with a parameter, read in the page |
| `routing_site` | Home / About / Contact with one navigation bar on every page; a contact form | shared layout around the routes |
| `routing_members` | sign up, log in, a profile page; logged-out visitors sent to login | a guarded route |
| `routing_search` | search box; the keyword is in the address, so a reload keeps the results | a query parameter read from the URL |
| `routing_notes` | a list page and a separate add page; after saving, back to the list | programmatic navigation |
| `routing_notfound` | recipe list and recipe pages; an unknown address shows "page not found" | a catch-all route |

- **Runs:** 2 per scenario, 12 in all, one at a time. The batch (`output/eval/agent/routing_baseline_1109.sh`) logs
  to `routing_baseline_1109.status`. Per-run output is in `output/eval/agent/<scenario>/jaccoder-<model>_<stamp>/`.
- **Analysis:** a scratch script reads each run's `run.log` timeline, `calls.jsonl` (every model request and
  response), `run.json`, and the final project snapshot. It also re-runs `jac check .` with 0.34.28 on that snapshot.

## Results

Columns:
- **Run:** the scenario and the run's start time.
- **Harness verdict:** `run.json`'s gate code.
- **Real outcome:** my reading of the final project against the request.
- **Calls:** model calls.
- **Repeated steps:** timeline steps identical to one of the 4 before them.
- **Ended by:** what stopped the run.
- **Final `jac check`:** the snapshot re-checked with 0.34.28.

| Run | Harness verdict | Real outcome | Calls | Repeated steps | Ended by | Final `jac check` |
|---|---|---|---|---|---|---|
| blog 18:53 | FAILED_ERROR | fail | 23 | 3 | runaway thinking (32k tokens) | 23 errors (unclosed `{if}` slot) |
| blog 21:58 | FAILED_VALIDATION | fail | 106 | 48 | iteration budget | ok |
| members 20:54 | FAILED_ERROR | fail | 25 | 4 | runaway thinking | ok |
| members 21:33 | FAILED_VALIDATION | fail | 107 | 77 | iteration budget | ok |
| notes 21:09 | FAILED_ERROR | fail | 15 | 1 | runaway thinking | ok |
| notes 21:45 | FAILED_VALIDATION | fail | 107 | 42 | iteration budget | ok |
| notfound 21:16 | FAILED_ERROR | fail | 60 | 5 | runaway thinking | 1 error |
| notfound 21:53 | PASS_SYSTEM_VALIDATED | **fail** | 108 | 61 | iteration budget | 79 errors (JSX tail expressions) |
| search 21:03 | PASS_SYSTEM_VALIDATED | **fail** | 107 | 37 | iteration budget | 3 errors (JSX tail expression) |
| search 21:40 | PASS_SYSTEM_VALIDATED | **fail** | 108 | 59 | iteration budget | 28 errors |
| site 20:43 | FAILED_ERROR | fail | 57 | 1 | runaway thinking | ok (runtime error) |
| site 21:28 | PASS | **pass** | 106 | 44 | iteration budget, after it had validated | ok |

**1 of 12 runs built what was asked.** The harness reports 4 passes, but 3 of them are `PASS_SYSTEM_VALIDATED`:
the agent never confirmed its own app, the runner's browser check found a page that loads, and the final code does
not compile on 0.34.28. Don't use the harness verdict alone as a score.

Cost per run:

| Measure | Range over the 12 runs |
|---|---|
| Wall time | 4.5–11 min (whole batch: 80 min) |
| Prompt tokens sent | 0.27M–3.2M, about 97% served from the prompt cache |
| Output tokens | 20k–48k; one runaway call alone is 32k |
| Largest prompt | 39.7k tokens (compaction keeps it under ~40k) |

## Why the runs fail

Numbers in brackets count runs out of 12.

### 1. Loops: every run that did not pass ends in one (11/11)

There are two kinds, and the same scenario showed either one.

- **Runaway thinking [5].** One call spends all 32,000 output tokens restating the same few sentences and returns
  nothing. JacHammer treats an empty reply as fatal and ends the run (`FAILED_ERROR`). Each time, the trigger was an
  observation the model did not expect:

  | Run | What it saw just before |
  |---|---|
  | blog 18:53 | 160 lines of check errors for one missing `}` |
  | site 20:43 | `Router is not defined` in the browser, after 3 refused reads of compiled JS |
  | members 20:54 | a login click that did not change the page |
  | notes 21:09 | a blank page |
  | notfound 21:16 | a Vite import-resolution log |

  In blog 18:53 the loop is the same paragraph about `</div>;` repeated about 100 times. The training data has no
  reasoning with any sentence repeated three or more times, so the loop is not copied from the data. It matches
  what the literature reports for small models distilled from stronger ones (Pipis et al., ICML 2026).

- **Tool-call loops [7].** The same call, often with the same result, until the 100-iteration budget runs out:

  | Run | Most repeated call |
  |---|---|
  | search 21:40 | `edit_code` on ProductSearch.jac ×59 |
  | members 21:33 | `read_file` on Login.jac ×54 |
  | search 21:03 | the same `grep` on `.vite` chunk maps ×38 |
  | site 21:28 | `ls .jac/client/compiled/components/ui/` ×26, after it had already validated |
  | notfound 21:53 | `read_file` on a missing journal ×23 |
  | blog 21:58 | `preview_status` ×19 |
  | notes 21:45 | `edit_code` on main.jac ×14 |

  JacHammer's own doom-loop detector fired 6–29 times in these runs without stopping them.

### 2. Route parameters are never read (4/4 runs that need one)

Every detail page gets its parameter wrong, so it shows the wrong item or nothing:

| Run | How the detail route passes the parameter |
|---|---|
| blog 18:53 | `element={<ArticleView title={":title"} />}` (the literal string) |
| notfound 21:53 | `element={<RecipePage title={":title"} />}` (the literal string) |
| notfound 21:16 | `element={<RecipePage title={params.id} />}` (`params` is undefined in `app`) |
| blog 21:58 | `element={<ArticleDetail article={find_article(articles, articles[0].title)} />}` (always the first) |

None of the 12 runs uses `useParams()`. Two other routing gaps:
- Links are plain `<a href>` in 6 runs (a full page reload) and `<Link>` in 1.
- site 20:43 used `<Router>` / `<Routes>` / `<Route>` without importing them. `jac check` only warns, and the page
  fails at runtime.

**The routing system is right.** JacHammer's prompt says "ROUTING — default to manual Router", and 11/12 runs use a
manual `<Router>` (search 21:40 has none). The routing data planned earlier assumed `pages/`. For JacHammer it should
teach the manual Router the prompt prescribes: `useParams()` inside the routed component, `<Link>`/`useNavigate`,
imports from `@jac/runtime`, and a layout around `<Routes>`.

### 3. Syntax that 0.34.28 rejects

- **JSX as a tail expression without `return` [2: search 21:03, notfound 21:53].** This is 0.36 syntax, the habit
  `docs/JAC_VERSIONS.md` predicted. JacHammer's write check reports it (as "may implicitly return None" and
  "Missing ';'"), and the model kept the form across edits.
- **Unclosed JSX blocks ("Unexpected end of JSX content") [3: blog 18:53, site 21:28, notfound 21:53].** The
  error points at the end of the file, far from the missing brace. This is what `brace_fix_v2` (below) targets.
- **HTML written as a string inside JSX [1: members 20:54].** It rendered as literal text
  (`Don't have an account? <a href='/signup' ...>`).

### 4. Working against the harness instead of the source

- **Started its own server [7].** The model ran `jac start --dev main.jac` in 7 runs, although the prompt says the
  preview is owned by the platform and must not be started by hand.
- **Inspected compiled JS and Vite caches instead of reading the `.jac` source [3: site 20:43, site 21:28,
  search 21:03].** JacHammer refuses reads of compiled output, and the model retried them.
- **Wrong `browser_do` syntax [1: members 20:54].** It wrote `open("...")`, which is not a browser_do command.
- **Few skill loads.** The model loaded a skill in 5 of the 12 runs, mostly near the start. It almost never did so
  in response to a failure, which is what the edited prompt now asks for.

## What this says for the data

In order of how many runs each item would have saved:

1. **Breaking out of loops (11/12).** Rows where an unexpected observation (blank page, runtime error, no-op
   click, refused read) is followed by a short diagnosis and a *different* next action. Reasoning stays short.
   - The trained tool-call turns in `prod-64k` include 103 exact repeats with identical results, in 66 of 207
     rows. Most are `preview_restart` / `preview_status` / `browser_*` polling. They teach "do the same thing again"
     and should be weight 0, not deleted (deleting would break the trajectory).
2. **Manual-Router routing with `useParams` (4/4 detail pages wrong).** Per JacHammer's prompt.
3. **0.34.28 syntax: `return` before JSX (2/12), closing braces (3/12).** `brace_fix_v2` covers the braces,
   `loop_break_v1`'s `jsx_return` rows the `return`.
4. **Respect the platform-owned preview (7/12 ran `jac start`).**

Inference-side mitigations exist but are not tried here: a presence penalty (Qwen suggests 0–2), and a harness that
stops repeated calls. The literature treats temperature and penalties as stopgaps and points to training-time fixes.

## Data built from this baseline (2026-11-10)

Three sets, all in `output/sft/<task_type>/<name>/{train.jsonl, statistic.json}`, not under `dataset/` (moved there
once reviewed). All three share one format and one way of getting tool results:

- **Format.** The system prompt, the 27 tool schemas and the user-message wrapper come from a real JacHammer session
  (the blog 18:53 run: jac 0.34.28, the skill-loading prompt edits). Paths use prod's
  `/app/.jachome/.jac-ide/projects/<id>/prj_<hex>` form. One tool call per assistant turn; short reasoning, mostly
  no visible text, as the prompt asks.
- **Tool results are JacHammer's own.** `script/dataset/sft/jachammer_tools.jac` runs jacBuilder's real
  `write_code`, `edit_code`, `read_file`, `list_files`, `grep_search`, `load_jac_skill` and `run_command`, in order,
  on a real project, with web-mode permissions and the loop detector's state reset per row. So every result carries
  what the agent would see: the check sections, `[ACTION REQUIRED ...]`, `[HINTS: ...]`, refusals, and LOOP DETECTED.
  Shared row helpers are in `script/dataset/parser/jachammer.py`.
- **Two JacHammer rules the rows follow** (both from its own code and prompt):
  - After a failed check, JacHammer appends "[ACTION REQUIRED: Load the relevant skill ... BEFORE attempting to fix]"
    to every write/edit result with `SYNTAX ERRORS` (`_enforce_check`). Trained turns after it load a skill first.
  - The write/edit check "is authoritative — do NOT re-validate ... via a `jac check` run_command". No row re-checks.

### The apps (`script/dataset/parser/jachammer_apps.py`)

Six small multi-page apps on JacHammer's `empty` template (created with `jac create --use
assets/templates/empty.jacpack` plus `jac install --shadcn input`, as the platform does). Domains avoid the six eval
scenarios: a gear shop, a team directory, a pottery course, harbor events, a help center, an issue tracker.

- **Routing as JacHammer prescribes:** `main.jac` exports a no-argument `app()` returning `<Router><Routes>...`; route
  components live in `components/`. Two layouts (a layout route with `<Outlet/>`, or a nav bar above `<Routes>`),
  two lookups (a find helper, or a comprehension), three apps with an add form that navigates back with
  `useNavigate`.
- **Native Jac, no placement markers.** The URL parameter is read the way the routing guide writes it,
  `params["id"]`, with an `as str` cast where a typed helper takes it (the `jac-types` escape hatch). The data and
  its helpers sit in the list page's module, which its JSX makes client. On 0.34.28 a separate pure data module
  would fail E5082 unless pinned `.cl.jac` (placement does not cross modules there); 0.36 retired the marker and
  propagates across modules. The chosen layout passes `jac check` on both 0.34.28 and 0.36.1, and builds on 0.34.28.
- **Verified in a browser** on 0.34.28 (`jac start`): list, each detail page by URL, an unknown id, an unknown
  address, and the add form (it saves, returns to the list, and the new item has its own page). The symptoms the
  requests describe were also seen: a literal `":id"` prop gives "no match", ignoring the URL always shows the first
  item, and a missing `@jac/runtime` import shows "Something went wrong / Router is not defined" (not a blank page;
  JacHammer's write check does not flag it, `jac check` only warns W2001).
- Found on the way: `jac check` passes a client module whose `glob`/`def` lack `:pub`, but the build then fails
  ("not exported"). And `params.id` is not an error on 0.34.28, although the guide says E1030.

### `router_params_v1` (39 rows, `jac_route_fix`)

Producer `script/dataset/sft/router_params.py`. Each row starts from a complete app with one routing problem, phrased
as a user would report it, and ends when the code is fixed (the last turn is a tool result; preview and
`browser_validate` are not in the rows). All turns are trained.

| Task | Start state | Rows |
|---|---|---|
| `add_detail` | list without links, no detail route | 6 |
| `literal_param` | route passes `{":id"}` as a prop | 6 |
| `first_item` | detail page shows `ITEMS[0]` | 6 |
| `links_reload` | nav and list use `<a href>` | 6 |
| `missing_import` | `main.jac` has no `@jac/runtime` import | 6 |
| `catch_all` | no `path="*"` route | 6 |
| `stay_on_form` | add form clears itself instead of navigating | 3 |

Tokens per row 17.4k–20.2k (median 18.0k; ~16k is the system prompt), 718k in all. 174 trained turns.

### `loop_break_v1` (36 rows, `jac_loop_break`)

Producer `script/dataset/sft/loop_break.py`. The same fixes with one of the loops seen in the baseline put in. The
loop and everything before it are weight 0; the turn that breaks out (a short diagnosis that names the repetition and
a different call) and the rest of the fix are trained.

| Loop (`loop`) | The repeated call, and JacHammer's real answer | Break-out |
|---|---|---|
| `edit_miss_2` | `edit_code` with an `old_string` not in the file, twice | `read_file`, then the edit with the exact text |
| `edit_miss_3` | the same, three times; the 3rd gets LOOP DETECTED | same |
| `compiled_read` | `read_file` of `.jac/client/compiled/*.js`, twice; refused both times | read the `.jac` source |
| `missing_journal` | `read_file` of `.jaccoder/agent_journal.md`, twice; not found | go on with the task |
| `ls_repeat` | `run_command ls components`, three times; the 3rd gets LOOP DETECTED | read the file the listing shows |
| `jsx_return` | a component written with bare JSX (no `return`, the 0.36 habit), 2 or 3 times; `SYNTAX ERRORS` plus ACTION REQUIRED | `load_jac_skill jac-cl-components`, then one fix |

6 rows of each, one per app. Tokens per row 18.0k–28.3k (median 19.5k), 742k in all. 138 trained turns, 145 weight 0.

What the detector does, learned from its code (`jac_coder/runtime/events.jac:check_tool_loop`) and the rows:
- It counts a tool plus its key argument in the last 5 calls. `read_file` is not tracked at all, which is why the
  baseline's 54 identical reads of Login.jac were never flagged. A blocked call is not executed.
- `write_code`'s key is the file path alone: after two writes of a file, a third write is refused whatever its
  content. So the 2-write `jsx_return` rows fix the file with `edit_code`.
- 4 `edit_code` calls on one file within 5 calls are refused too. So the JSX fix is one edit over all blocks, and
  `edit_miss_2` is only used where one edit follows.
- The model in the baseline evaded it by alternating `ls` and `ls -la`: arguments differ, so the count never reached 3.

### `brace_fix_v2` (replaces `brace_fix_v1`)

Producer `script/dataset/sft/brace_fix.py`. Sources: files that pass JacHammer's check on 0.34.28, from 25
training-episode workspaces of the teacher spike (no held-out `eval-*` workspace; no `.cl`/`.sv` file or marker in
any of them). One closing brace is dropped from a file; the write or edit that dropped it is context (weight 0).

Why v1 was replaced: v1 got its check output from `_quick_parse_check` alone, so its failed writes lacked the
"[ACTION REQUIRED: Load the relevant skill ...]" line JacHammer appends, and its fix went straight to an edit; 18 of
its rows also re-ran `jac check` after the fix, which the prompt forbids. v2 runs the real tools, so:
- trained turns: `load_jac_skill` (`jac-cl-components` for a file with JSX, else `jac-core-cheatsheet`), a
  `read_file` when needed, then the `edit_code` that restores the brace; no re-check;
- a row is dropped if the real `write_code` changes it (auto-fix) or refuses it (anti-pattern): 55 of 60 picked
  candidates survived;
- the reasoning only says "the end of the file" when the first error really is there (32 rows; 8 break mid-file).

| Field | Values |
|---|---|
| rows | 40, each from a different file (15–206 lines), 25 workspaces |
| `kind` | `block` (a `}` line removed) 27, `slot` (a JSX `}}` left as `}`) 13 |
| `origin` | `write_code` 29, `edit_code` 11 |
| `read` before the fix | 32 yes, 8 no |
| `skill` | `jac-core-cheatsheet` 24, `jac-cl-components` 16 |
| context turns before the break | 0–4 (17 rows have none) |
| tokens per row | 21.0k–31.5k, median 24.8k (the guide adds ~4–6k over v1); 992k in all |

Candidates fell from 356 (v1) to 197: the tools now run with `jac` on PATH, as in the sandbox, and fewer original
files pass that fuller check. `output/sft/jac_fix_brace/brace_fix_v1/` is left in place for comparison.

### Checks run on all three sets

- Every row renders through the 1107 chat template; no host or temp path remains; every trained turn has reasoning.
- Every result after the break-out is clean (no `ERRORS`, `Error`, LOOP DETECTED); every row ends with the files
  equal to the intended final files.
- Every trained turn that follows an ACTION REQUIRED result is a `load_jac_skill`.
- No call writes a `.cl.jac` file; no `str(params[...])` wrapper.

## Limits

- Two runs per scenario. Whether a run hits runaway thinking or a tool loop varied between the two runs of the same
  scenario.
- Only 1107 was measured; no comparison with 1105 or the base model in JacHammer.
- "Real outcome" is read from the final code, not from clicking through each app.
