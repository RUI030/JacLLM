# JacBuilder 0.36.1 isolated compatibility probe

Status: 2026-10-27; **uplift gate failed**. The real JacBuilder checkout was
not modified. All source changes and dependency installation took place in
`/tmp/revdev-jb-0361`, copied from the local JacBuilder checkout without
`.git`, `.jac` or `node_modules`. Existing untracked JacBuilder documents were
left alone. Local raw evidence is gitignored under
`dataset/raw/revdev/harness_0361_probe/private/`; the complete diagnostic
JacCoder capture is also gitignored at
`script/dataset/trajectory/harness/jaccoder.m2-0361-diagnostic.json`.

## Results

| Probe | Actual result |
| --- | --- |
| JacCoder entry `jac check jac_coder_sv.jac` | Exit 0 under Jac 0.36.1, with warnings. |
| Unmodified JacCoder M0 capture test | Failed during module import: `No module named 'jaclang.runtimelib.query_plan'`, from `jac_coder/core/lookup.jac`. No planner tool result was produced. |
| Isolated `write_code(main.jac, ...)` in web mode | Returned `OK: main.jac (1 lines)` and its real auto-check reported `ok`. |
| Diagnostic JacCoder capture with temporary `QueryPlan = None` shim | One MockLLM-driven `plan_build` wrote `.jaccoder/build_plan.json`; read, edit, write and check calls returned real results. This does not validate lookup behavior or production use. |
| Tool schemas | 27 tools; exact JSON equality with the M0 0.34.27 capture. SHA-256 of sorted JSON: `9155fa1d7371901f3a9c30af7343e353c38aba935bc4e7f8ee488236d88cabb5`. |
| Unmigrated preview template `jac start` | Failed: removed `cl` placement marker in `main.jac`. |
| Template after `jac fix placement` | `jac start main.jac --port 38138 --no-dev` served `GET /` with HTTP 200 and 1,198 body bytes. The probe stopped the server afterward. No browser render test was performed. |
| Root app after diagnostic shim and `jac fix placement` | `jac check main.jac` exit 0; `jac start` remained at `Building client from main.jac...` and served no HTTP response before the 180-second probe timeout. No explicit compilation error was emitted in that interval. |

The temporary shim replaced only the top-level `QueryPlan` imports in the
isolated `jac_coder/core/lookup.jac` and
`deployment/deploy.impl/reconcile.impl.jac` with `None`. Calls that depend on
the old query planner therefore do **not** have working replacement semantics.
The unmodified import failure is the compatibility result; the shimmed success
only shows that planner/tool wiring can still execute past that first failure.

## Scope of the required migration

- The JacBuilder root, preview template, sandbox base version manifest, CI and
  deploy workflows currently pin 0.34.27. Updating one pin would leave the
  harness components on different runtimes.
- Jac 0.36.1 removes the `QueryPlan` module used by JacCoder lookup. The
  module also appears in deployment reconciliation; an owner-project store
  query in `services/ideServer.jac` imports it dynamically. Replacements must
  preserve lookup, ownership and permission semantics rather than merely make
  imports succeed.
- `jac fix placement` in the disposable root migrated 16 files containing
  removed placement markers, renamed 423 old-suffix files and wrote seven
  microservice routes. The preview template had seven additional old-suffix
  files renamed first. JacBuilder still contains source logic and tests that
  recognize `.cl.jac` paths, including JacCoder's client-file detection and
  checked-write path; these need a behavior review after renaming.
- A successful `jac check` did not predict import or preview success in this
  probe. The final gate needs root boot, JacCoder planner/write/check, preview,
  lookup/permission behavior and relevant tests under one 0.36.1 runtime.

The [Jac 0.36.1 release](https://github.com/jaseci-labs/jac/releases/tag/v0.36.1)
is available. Its availability is separate from JacBuilder compatibility.
Until the migration passes, keep the existing 0.34.27 pins and do not use the
temporary diagnostic capture as an M3 trajectory. A 0.34.27-compatible pilot
repo is the alternative if dataset generation must proceed before this
larger JacBuilder migration is completed.
