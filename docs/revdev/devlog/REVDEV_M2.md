# Reverse Development M2: grounded tasks and plan

Status: M2 task/plan artifact generation complete on 2026-10-27. No student
trajectory or SFT export exists yet. The pilot reference still needs browser
acceptance before it is called a fully working ground truth app.

## Reference and runtime evidence

The raw `Rui/pm` commit is `e93a47fb2a3d5f4fcc708ee0031467a472abb34b`.
M1 used Jac 0.34.27: `jac check main.jac` exited 0, but `jac start main.jac`
failed while parsing JSX in `components/ui/button.jac` and `badge.jac`. A
disposable copy started with Jac 0.36.1 and served `GET /` with HTTP 200. A
real `POST /function/create_root_project` returned HTTP 200 and a Project
node; `POST /function/get_projects` returned HTTP 200 with the same node ID.
The probe used an anonymous backend session and did not exercise signup,
browser rendering, nested projects or tasks. These are open acceptance checks,
not inferred successes.

The M2 extractor reran with `jac` 0.36.1 against the same raw repo. Its fresh
`jac check main.jac` exited 0. The private manifest has 27 selected files,
135 AST symbols and 295 accepted dependency edges, matching M1 counts.
`dataset/raw/revdev/Rui_pm/m2/private/reference_manifest_0361.json` and
`reference_probe/{summary.json,*.txt,*.log}` retain exact local evidence.
They are gitignored along with other raw dataset artifacts. The raw probe
files retain response bodies; the summary records HTTP statuses, response
results, file hashes and whether the returned project ID appears in the list
response. It does not represent a browser test.

## M2 output

[tasks.py](../../../script/dataset/revdev/tasks.py) combines the compiler manifest
with an explicit [pilot recipe](../../../script/dataset/revdev/recipes/pm_mvp.json).
Each feature and planned file names source symbol IDs, signatures, source
spans and file hashes in the **private** oracle. Missing or ambiguous symbols
stop generation. The student task contains only a natural request and
acceptance flows; its planning target follows the captured JacCoder
`build_plan.json` schema and contains no private evidence or function bodies.
Its `reference_id` is opaque; the raw repo identity stays private.

The first build covers account access, root projects, nested projects and
tasks. It excludes the raw app's LLM drafting and draft-approval features:
those need a configured model and are outside the first shippable scope. The
reference has 23 Jac source files, while the captured JacCoder planner targets
4–7 files and rejects more than 8 for a create-mode build. The plan therefore
maps the domain model and endpoint evidence into one service, and maps the
existing page/panel evidence into three pages plus `main.jac`. This is an
explicit implementation adaptation, not an assertion that target files exist
in the raw repo.

Two wording variants currently share the same scope:

| Task | Request excerpt | Files | Pages |
| --- | --- | ---: | ---: |
| `rui_pm_core_a` | “Build a project and task manager for individual accounts…” | 5 | 3 |
| `rui_pm_core_b` | “I need a personal workspace for organizing projects…” | 5 | 3 |

The full `rui_pm_core_a` request is:

> Build a project and task manager for individual accounts. Let people sign
> up and log in, create projects with a name and goal, open a project to add
> subprojects and tasks, and browse their projects and tasks.

Its plan writes `services/pm.jac`, `components/LoginPage.jac`,
`components/HomePage.jac`, `components/ProjectPage.jac`, then `main.jac`.
The service exports the two domain types and the create/read endpoints.
HomePage and ProjectPage import only earlier service exports; `main.jac`
imports the three page exports. Routes are `/login`, `/` and `/project/:id`.
The planned verification flow is `create_root_project` from `/`. Every file
starts `pending`, and template removals are empty until an actual template
listing supports them.

Each task directory contains:

```text
visible/task.json                natural user request and acceptance
private/oracle_plan.json         source evidence and signatures for validation
private/planning_target.json     JacCoder-compatible planning-only target
```

`planning_target.json` is an offline supervised target. It is **not** a
`plan_build` tool result. M3 will capture the real planner and builder calls
and compare the resulting plan structurally against the oracle. Both task
variants belong to the same source repo and must stay in the same split.

## Reproduce and checks

```bash
python script/dataset/revdev/tasks.py \
  --manifest dataset/raw/revdev/Rui_pm/m2/private/reference_manifest_0361.json \
  --out dataset/raw/revdev/Rui_pm/m2
python script/dataset/revdev/test_tasks.py
```

Both artifact-generation tests passed. They check evidence rejection, plan
ordering, the five-file JacCoder contract, and removal of source signatures
and IDs from the student surfaces. This validates planning data only; it does
not claim a reconstructed app can run.

## JacBuilder runtime decision for M3

The isolated 0.36.1 compatibility run is recorded in
[REVDEV_JACBUILDER_0361.md](REVDEV_JACBUILDER_0361.md). It found a real
JacBuilder runtime import break and a source placement migration. The preview
template served HTTP 200 after that migration, but the unmodified JacCoder
planner could not load, and the migrated root app did not finish its client
build within the 180-second probe. Therefore the 0.36.1 uplift did **not**
pass its gate and no JacBuilder production/template/sandbox/CI pins were
changed. M3 cannot treat the temporary diagnostic shim as a supported harness.
