# Rui/pm project-tree trajectories: pending after power interruption

The source repo is `dataset/raw/repo/Rui/pm`. Both attempts use one canonical
source repo and belong to the revdev **train** split; neither is active SFT.

## Fullstack attempt

`dataset/raw/revdev/PM/runs/claude_project_tree_0361_v1` contains 104 Claude
decisions and real JacCoder tool-call artifacts. Its final workspace passes
the two independent tests in `script/dataset/revdev/recipes/pm/acceptance.jac`,
derived from the reference project's project/task graph behavior. The
`validation.json` status is `checks_passed_pending_fullstack`, not accepted.

Clean replay is not established. Before the power interruption, one replay
reached 94 calls and had a `jac build main.jac` diagnostic-status mismatch at
step 100, even though the final tracked source hashes matched. The current
`replay.json` was overwritten by a post-reboot attempt that stopped at its
first call: the restricted sandbox cannot write Jac's Postgres lock under
`~/.cache/jac`. A fresh writable cache also cannot bind the Postgres Unix
socket in that sandbox. These are failed attempts, not success evidence.

The original UI uses `AuthGuard`, `HomePage`, and `Project.Panel`, with a
different interaction sequence and selectors from the generated
`ProjectBoard`. The current scripted browser spec matches only the generated
board. An original-versus-generated browser gate with the same spec has not
passed. Do not export this attempt until both clean replay and a grounded
UI comparison pass.

## Backend follow-up

The reusable backend-only task and plan are
`script/dataset/revdev/recipes/pm/task_project_tree_backend.json` and
`plan_project_tree_backend.json`. The new raw run
`dataset/raw/revdev/PM/runs/claude_project_tree_backend_0361_v1` stopped at
step 000 before a JacCoder tool result or workspace mutation. Its status is
`execution_interrupted`; it has no training examples. After the separate
Claude adapter request was rejected by automatic approval review, no new
teacher call was made for this follow-up.

## Harness recovery

The reboot cleared `/tmp/jac-0.34.27-linux-x86_64`, formerly used to run the
JacCoder dispatcher. A permanent copy exists under
`output/runtime/jac-v0.34.27/`; the target project checker remains Jac
0.36.1. `script/dataset/revdev/replay.py` now accepts optional
`--harness-jac`, matching the adapter's separate harness/target Jac choices
while preserving its original default. The local adapter/checkpoint/validator
unit tests passed 6/6 and `git diff --check` passed. This option has not yet
turned either PM attempt into an accepted replay.
