# Revdev wave-2 recipe brief

You prepare ONE reverse-development recipe from ONE hackathon repository. You do
not run the teacher (`claude -p`, `claude_adapter.py`) and you do not edit any
file outside your recipe directory and your own `/tmp` preflight directory.

Project root: `/home/imrui/Documents/Jaseci/JacLLM/JacLLM` (call it ROOT).
Python: `~/miniforge3/envs/tornith/bin/python`. Target Jac: `~/.local/bin/jac`
(0.36.1). Read these first:

- `ROOT/script/dataset/revdev/recipes/paper_library_backend/` — the model to
  copy: `task.json`, `plan.json`, `provenance.json`, `reference_acceptance.jac`.
- `ROOT/script/dataset/revdev/plan_md.py` — your plan must pass
  `validate_rendered(render(plan, task["request"]), plan)`.
- `ROOT/script/dataset/revdev/validate.py` — how acceptance is run later: the
  generated workspace is copied, your `reference_acceptance.jac` is placed at the
  workspace root as `revdev_acceptance.jac`, then `jac check main.jac` and
  `jac test revdev_acceptance.jac` run with `JAC_TEST_NATIVE=1 JAC_TEST_JOBS=0`.
  `accept_backend` rejects any plan row whose layer is page/client/frontend, any
  `ui.pages`, and any JSX in the workspace.

## Goal of the dataset

Train a small model to go request -> Markdown plan -> scaffold (real signatures,
`raise NotImplementedError()` bodies) -> fill bodies in dependency order, with
emphasis on CROSS-FILE IMPORTS so it stops hallucinating names from other
modules. The slice you choose must make the importer depend on real names
defined in other planned modules.

## Source of truth (wave-2 rules)

- The upstream clone named in your assignment (a git checkout; record its
  commit SHA) is the source. Use its files verbatim whenever they pass
  `jac check` on 0.36.1.
- Only when an upstream file fails 0.36.1 check, use the copy repaired by the
  jac-data-gen sweep (path given in your assignment) and record `repaired_by`.
  Those repairs sometimes turned `import from x.y` into `import from ..x.y`,
  which passes check but fails at runtime ("attempted relative import beyond
  top-level package"); restore the upstream import line in that case and record it.
- Never rewrite, simplify or substitute logic in a source file. Allowed edits:
  deleting whole out-of-slice declarations or imports that the slice does not
  use. Record each edit. A new thin `main.jac` holding only imports is allowed.

## Choose the slice

1. Backend only: no JSX, no client components, no `cl`/`sv` markers, no
   network, no external API, no randomness or wall-clock dependence in the
   tested behavior.
2. `by llm` is ALLOWED and wanted when the slice's real logic uses it. Keep the
   `by llm` declarations and their `sem` strings verbatim and put them in the
   plan signatures. Tests replace the model WITHOUT editing source:
   `import from jaclang.byllm.lib { MockLLM }`, `import pkg.mod as m;`, then in
   the test `m.llm = MockLLM(model_name="mockllm", config={"outputs": [...]})`
   before calling (if the module declares its own `glob <name> = Model(...)`,
   assign that name instead). Outputs are consumed one per `by` call, in order;
   typed returns take pre-built values (enum members, obj instances). A
   `glob llm = MockLLM(...)` in the test file does NOT work: the source keeps
   its own model. Test the deterministic logic around the LLM call (parsing,
   graph updates, routing on the returned value), not the prompt.
3. Repo-local Python: the slice may include `.py` helpers the slice imports
   only if their total is at most 100 lines; copy them verbatim, list them as
   plan rows (layer util) so the model writes them, and test through them.
   Otherwise choose another slice.
4. 2 to 5 `.jac` modules (plus any allowed `.py` helpers) with their relative
   paths kept. Prefer an import chain of depth >= 2 and at least 2 local import
   edges. Pull in every local module the slice imports (transitively).
5. Avoid slices whose behavior is mostly keyword/regex heuristics or long
   template text: a plan cannot state them without becoming the source code.
6. The workspace root must contain `main.jac` and `jac.toml`. `jac.toml` is a
   minimal `[project]` service config without a version pin (see the paper
   library plan's jac.toml row).

## Preflight (must pass before you finish)

In `/tmp/revdev-<slug>-preflight/`: copy the slice files and your `jac.toml`,
run `~/.local/bin/jac check main.jac`, then write `reference_acceptance.jac`
there and run
`JAC_TEST_NATIVE=1 JAC_TEST_JOBS=0 ~/.local/bin/jac test reference_acceptance.jac`
(name it `revdev_acceptance.jac` in the preflight dir if discovery needs it).
All tests must pass against the ORIGINAL slice.

Acceptance tests: 3 to 6 `test "..." { }` blocks, deterministic, importing only
names listed in the plan's exports/signatures. At least two tests must call an
importer module's public function/walker whose result depends on a provider
module (the cross-file path). Graph root persists across tests: use unique
values (ids, names, tags) per test and lower-bound counts.

SPEC RULE (wave 1 lost two apps to this): every value a test asserts — dict
keys, exact strings or HTML, ordering, rounding, classification rules,
numeric weights — must be stated in task.json or plan.json. The teacher sees
only those two files. Before finishing, reread each assertion and point to
the plan text that determines it; add the missing contract to the plan.

## Write the recipe

Directory: `ROOT/script/dataset/revdev/recipes/<slug>/` with exactly:

- `task.json`: same keys as the paper library. `request` is a natural user
  request (what the service does, module names and public operations; no code).
  `acceptance` 3-5 observable behaviors. `constraints` must include
  "Use Jac 0.36.1 and a backend-only service; no JSX or browser UI; never call a real model (test any by llm function with MockLLM)."
  plus the exact public names to keep. Never mention any Jac version other than
  0.36.1 anywhere in task or plan (the adapter rejects it).
- `plan.json`: same schema as the paper library. `jac.toml` first, then modules
  in dependency order (providers before importers). Every module row has
  `purpose` (fields, behavior, which provider names it uses), `exports`,
  `imports_from_plan`, and `signatures` with the exact source signatures of every
  public def/walker/obj method the tests or importers use. `dependency_graph`
  must match the real imports. `ui.pages` empty, `backend_required` true,
  `ai_required` true only when the slice has `by llm` functions, else false. Layers: config, model, service, util or similar; never
  page/client/frontend.
- `provenance.json`: same keys as the paper library, plus `source_dataset`
  (the jsonl or directory the files came from), `repaired_files` (list),
  `slice_import_edges` (list of [importer, provider]). `split` "train",
  `split_group` = lowercase `owner__repo`. `independent_acceptance_sha256` is the
  sha256 of the final `reference_acceptance.jac`; `reference_preflight` records
  the check/test outcome and the preflight path.
- `reference_acceptance.jac`.

Check the plan with:

```bash
cd ROOT && ~/miniforge3/envs/tornith/bin/python -c "import json,sys; sys.path.insert(0,'script'); from dataset.revdev.plan_md import render, validate_rendered; p=json.load(open('script/dataset/revdev/recipes/<slug>/plan.json')); t=json.load(open('script/dataset/revdev/recipes/<slug>/task.json')); validate_rendered(render(p, t['request']), p); print('plan ok')"
```

## Report back (short)

slug; source; slice files with line counts; import edges; repaired files used;
any source edits; test names; exact preflight check/test output summary; anything
doubtful. If no slice in this repo satisfies the rules, say so and why instead of
forcing one.
