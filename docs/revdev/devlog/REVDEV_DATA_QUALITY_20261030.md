# Revdev data quality audit (2026-10-30)

## Scope and result

The active `dataset/sft/revdev_*` directories contain 35 JSONL records:
33 primary examples plus two 16k mirrors. They total 375,614 tokens under
the current training tokenizer. The new Mindcraft auto-compaction run is a
separate raw preview: four distinct projections plus one 16k plan mirror,
112,475 tokens including that mirror. It has not been added to active SFT.

`script/dataset/revdev/audit_sft.py` passed both sets. It checks the actual
tool schemas and argument values, tool-call/result pairing, visible local
paths, nonempty assistant supervision, exact training-template token counts,
the 65,536-token cap, and repo-group isolation between train and valid. The
active audit found zero issues. Active groups are Mindcraft, Alongside,
Aegis, m-local, A2-Pulse, and GhostBoard. Only the Mindcraft pilot has a
full-app example; the remaining examples do not constitute six independent
full-app reconstructions.

To reproduce the audit from the repo root:

```bash
/home/imrui/miniforge3/envs/tornith/bin/python script/dataset/revdev/audit_sft.py \
  --out output/eval/revdev/data-quality-20261030.json
REVDEV_JAC=/tmp/jac-0.34.27-linux-x86_64 \
  /home/imrui/miniforge3/envs/tornith/bin/python -m unittest discover \
  -s script/dataset/revdev -p 'test_*.py' -q
```

The 12 unit tests passed with the task's pinned Jac 0.34.27. Using the host
default Jac 0.36.1 makes the AST fixture correctly refuse its 0.34.27 pin.
That is an environment mismatch, not a dataset failure.

## Corrections made

1. Exported SFT messages used machine-specific `/home/imrui/...` workspace
   and runtime paths. The exporter now projects those to `/workspace`,
   `/runtime/jac-cache`, `/project`, and `/home/student`. Raw event logs and
   tool results remain intact for replay and provenance. Active Mindcraft
   and multifile records were regenerated; the audit finds no visible host
   paths.
2. A schema-rejected `final` decision in the auto-compaction run was being
   represented as an assistant answer. It is now excluded from SFT and
   counted in trajectory metadata. The raw rejection remains available.
3. Mindcraft used an opaque split group while other tasks used the source
   repo name; multifile tasks used absolute repo paths. Groups are now
   canonical repo names, so train/valid isolation is testable across task
   types. This does not create an independent validation example for the
   Mindcraft preview.

## Remaining quality work before bulk generation

The current generic resume prompt caused repeated whole-file reads. Its
preview has 26,711 total tokens but only 1,247 tokens with training loss
under the current assistant mask (about 4.7%). That makes it a poor bulk
training pattern despite passing structural checks. Produce a deterministic
handoff from the checkpoint's real file hashes, completed work, and observed
verification outcomes; then test that continuation avoids needless rereads.
The handoff must not reveal hidden reference code or invent prior results.

Next run one *different* full-app repo with that handoff. Require actual
JacCoder tool execution, independent replay, behavior tests (and browser
flows when the app has a UI), valid train/valid repo grouping, and a quality
audit. Once that passes, run a controlled 3–5-repo batch and inspect loss
density, failure causes, and tokens per unique repo. Bulk production can
begin after that batch passes. There is no reliable calendar date yet:
teacher runtime, version compatibility, and cross-repo success rate have
not been measured at batch scale.

The existing full-app Mindcraft run has passed independent replay and
browser acceptance; it establishes technical feasibility, not bulk yield.

The local Transformers loader warns about a Mistral regex in the Ornith
tokenizer. The exporter, audit, and current trainer all load the same
unmodified tokenizer, so the reported token counts match this training
configuration. In this environment, trying `fix_mistral_regex=True` raised
`AttributeError` inside Transformers' Qwen2 tokenizer loader. Do not silently
switch tokenizer settings during a dataset batch; resolving that library
warning is a separate compatibility check before changing training behavior.
