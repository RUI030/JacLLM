# Revdev distribution and scale gate (2026-10-30)

This review is a stop/go check before multi-repo generation. The existing
active SFT dataset and the isolated Jac 0.36.1 pilot were audited separately.
The pilot is not yet part of active training.

## Active SFT distribution

The active audit passed: 35 records, 375,614 full-context tokens, no schema,
path, cap, or train/valid group issues. The exact training mask measured
55,617 loss-bearing tokens (14.8%). Of the 35 records, 27 fit the current
16,384-token training limit; eight are longer but below the 65,536-token
dataset cap. The recent rank-16 training recipe selected 15 records (14 new
module tasks plus an older plan), and did not train on full-app, scaffold, or
multifile trajectories.

| Task type | Records | Context tokens | Loss tokens |
| --- | ---: | ---: | ---: |
| App | 1 | 44,877 | 12,815 |
| Function/repair | 16 | 75,362 | 7,939 |
| Multifile | 4 | 70,410 | 11,734 |
| Plan | 2 | 2,830 | 2,584 |
| Resume | 11 | 148,783 | 16,024 |
| Scaffold | 1 | 33,352 | 4,521 |

Mindcraft contributes 15 records, 254,388 context tokens, and 34,772 loss
tokens: 67.7% of context and 62.5% of loss. These include 16k mirrors, which
are duplicate views of the same source, not independent tasks. The other
active source groups are Alongside (9), Aegis (7), A2-Pulse (2), m-local (1),
and GhostBoard (1). Active A2-Pulse and GhostBoard are valid-side groups.

The accepted Jac 0.36.1 A2-Pulse week-planner pilot is isolated: four distinct
projections plus two 16k mirrors, 75,101 context tokens, zero audit issues.
Its app and resume records are about 23.7k and 17.2k tokens, so the current
16k trainer cannot consume them. The valid-side re-export is the current
`export-preview`; the earlier train-side preview and audit are retained as
`export-preview-train-attempt-1` and `export-audit-train-attempt-1.json`.
Auditing active SFT together with the valid-side preview passed: 41 records,
450,715 tokens, no repo split overlap.
The same training mask measures 20,366 loss tokens across all six records;
15,555 are in the four distinct projections after excluding mirror copies.
Only plan and scaffold fit 16k in this pilot. This valid-side material is
held out only within a revdev training mix. It is not globally unseen source
material: A2-Pulse also appears in older `scaffold2impl` and `tool_fim` train
data. The current Orbitron, Rui/pm, and pomodoro candidate repos also appear
there, so the new runs are assigned to train. A globally unseen-source model
evaluation needs a fresh repo outside those prior training inputs.

## Source pool and diversity

`dataset/raw/repo/stats.json` lists 35 repos. Current metadata whitelists 11
and excludes 24 under its Jac-dominance and quality rules. The metadata was
generated on 2026-10-15 and its `jac_check` is a per-file check, not proof
that an app starts or has behavior tests. Some whitelisted repos still list
failing files: ClaudeLogViewer 1, JacProjectFactory 1 generated test file,
pomodoro 2 UI files, this_is_jac 9, and jms 37. A full-app candidate must
pass an independent entry/build/behavior preflight before generation.

Proposed *maximum six new repos* for the first controlled generation batch,
selected for different code shapes rather than popularity. This is a
candidate list, not an acceptance claim or a generation order:

| Repo | Distinct shape | Proposed split | Preflight concern |
| --- | --- | --- | --- |
| `JacHackSpring/orbitronsystems__ori-Jac-Demo` | Frontend-only, 17 Jac files, no OSP | train | `jac check main.jac` passes 0.36.1; browser behavior and build pending |
| `Rui/JacProjectFactory` (`factory/` root) | Backend CLI, OSP, 14 inline tests | train | Exact 0.36.0 pin; scope nested generated projects out |
| `Rui/pm` | Medium fullstack, graph + AI, 23 Jac files | train | `jac check main.jac` passes; independent behavior test pending |
| `JacHackSpring/kshitijkumrawat20__JacHacks2026` | Fullstack AI app, 13 Jac files | valid | `jac check main.jac` passes; original has local changes and no tests |
| `Rui/ClaudeLogViewer` | Fullstack without OSP or AI, 27 Jac files | valid | Exact 0.36.0 pin and one failing source file |
| `Rui/pomodoro` | Small deterministic fullstack UI, 12 Jac files | train | Exact 0.36.0 pin and two failing UI files |

Entry checks on Jac 0.36.1 pass for Orbitron, pm, FutureOS and GhostBoard
(the last is already an active valid-side repo, so it is only a control).
The backend and pinned/failing-file candidates are conditional; replace them
rather than lowering acceptance requirements. Entry checks alone do not
establish a working app.
`jaseci/this_is_jac` (69 Jac files) and `jaseci/flowline` (124 files, 0.37.7
pin) are useful later stress cases, not first-batch full-app targets. Do not
expand beyond ten distinct repos before reviewing acceptance yield, token
lengths, loss density, and error taxonomy. Assign split at source-repo level
before any teacher run, and check shared templates/near-duplicates in
addition to exact repo names.

## Settings fixed and open gates

Fixed in the shared full-app exporter: source `--split-group` and `--split`
are now required, so a pilot cannot silently default to train; planning-only
SFT now states the target Jac version in its system context. A valid-side
A2-Pulse export was produced and audited alongside active data. Teacher and
replay dispatch now set `JAC_TEST_JOBS=0` to avoid spawning 32 test workers per
repo. The adapter now permits the read-only `jac guide <topic>` command through
real JacCoder `run_command`, and directs 0.36.1 teachers to this target-binary
guide instead of the captured 0.34.27 skill. An actual JacCoder guide call
returned the 0.36.1 client-placement guide. Existing revdev unit tests pass,
and `git diff --check` is clean.

Open before bulk production:

1. The generic full-app `revdev_function` projection is still specific to a
   Mindcraft island repair and embeds Jac 0.34.27 in its prompt. The newer
   full-app pilots exported zero function examples. Generalize and audit this
   stage, or explicitly exclude it from the batch contract.
2. The new 0.36.1 `jac guide` routing passed a direct harness call but has not
   yet been observed in a fresh teacher trajectory; check its usage and
   quality in the first candidate before a multi-repo batch.
3. The 0.36.0 and 0.37.7 pins need matching binaries or a documented isolated
   migration baseline. Per-file whitelist status cannot substitute for app
   build and original behavior tests.
4. The general full-app adapter still takes one hand-authored task and plan;
   no audited one-command selector/generator has produced diverse full apps
   from the entire raw pool. Scale in a controlled batch first, not all 35.

Evidence: `output/eval/revdev/current-distribution-20261030.json`,
`output/eval/revdev/data-quality-20261030.json`, the new A2-Pulse pilot's
`combined-audit.json` and `export-token-mask.json`, and the raw repo
`meta.json`/`stats.json`.
