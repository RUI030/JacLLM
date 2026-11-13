# JacProjectFactory paper-library trajectory (2026-11-01)

## Source and scope

- Canonical source repository: `Rui/JacProjectFactory`; source subproject:
  `factory/output/repaircenter/Ornith_grad-student-paper-library`.
- Source files `model.jac`, `main.jac`, and `tests.jac` were unchanged. The
  isolated preflight removed the Jac 0.36.0 version pin and an unused watchdog
  dependency to run on Jac 0.36.1. The original five tests and `jac check
  main.jac` passed. See the source hashes and exact adaptation in
  `script/dataset/revdev/recipes/paper_library_backend/provenance.json`.
- The generated backend covers a Paper node in `model.jac` and save, list,
  search-by-tag, and ID lookup operations in `main.jac`. One trajectory stays
  within this source repo and has a cross-file import dependency.

## Independent acceptance and real-tool evidence

- The independent fixture's five behaviors passed against both the original
  source and the generated workspace. One tag in the fixture was made unique
  because two original test cases shared `recsys` while the validator used a
  shared test root; all five behavioral assertions remained the same. The
  original source's own tests also passed 5/5 in their normal isolated mode.
- The Claude teacher run contains 34 decision steps; 32 executed JacCoder
  calls passed clean-workspace replay with identical generated source hashes.
  Earlier compiler and test failures remain in the raw run. The final
  validation status is `accepted`, with zero issues. Evidence:
  `dataset/raw/revdev/JacProjectFactory/runs/claude_paper_library_036_v1/`.
- After a power outage removed the temporary Jac 0.34.27 harness binary, the
  official `v0.34.27` Linux binary was restored to the ignored
  `output/runtime/jac-v0.34.27/` directory and its release SHA-256 was
  verified. JacBuilder dependencies were restored from its existing
  `jac.toml`. Replay used Jac 0.34.27 for JacCoder dispatch and the recorded
  Jac 0.36.1 binary for target project commands.

The successful replay command from the JacLLM root was:

```bash
python script/dataset/revdev/replay.py \
  --run dataset/raw/revdev/JacProjectFactory/runs/claude_paper_library_036_v1 \
  --harness /home/imrui/Documents/Jaseci/JacLLM/jacBuilder \
  --jac /home/imrui/.local/bin/jac \
  --harness-jac /home/imrui/Documents/Jaseci/JacLLM/JacLLM/output/runtime/jac-v0.34.27/jac-0.34.27-linux-x86_64
```

The harness binary ran `install --global --no-save --no-npm` in the
`jacBuilder` directory beforehand, using its existing `jac.toml` to populate
`jacBuilder/.jac/venv`. No `PYTHONPATH` or `JAC_CACHE_HOME` override was needed.

## Export

- Canonical split group `rui__jacprojectfactory`, train only because this repo
  already appears in older SFT sources.
- Three distinct projections: plan 997 tokens, scaffold 4,160, app 18,709.
  Two 16k mirror records repeat the plan and scaffold, for five exported
  records and 29,023 context tokens total. No function or resume sample was
  emitted by the current generic exporter.
- The local export audit passed five records and zero issues. A point-in-time
  full revdev audit after this export passed 64 records, 633,192 context
  tokens, zero issues; other agents were exporting concurrently, so use a
  fresh full audit for final aggregate counts.
