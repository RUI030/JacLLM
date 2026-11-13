# ClaudeLogViewer core dataset (2026-11-02)

Source: `dataset/raw/repo/Rui/ClaudeLogViewer`, canonical split group
`rui__claudelogviewer`. This source already occurs in old `scaffold2impl` and
`tool_fim` train rows, so this run is train-side only. The checkout was clean.

The scoped backend target uses original, unchanged `logs/store.jac` and
`logs/treeUtils.jac`: project/session JSONL listing plus cross-file trajectory
tree lookup. In an isolated Jac 0.36.1 project, both source files passed
`jac check`; three independent source-derived behavior tests passed with
`JAC_TEST_NATIVE=1`. The source pins Jac 0.36.0, so this is a documented
isolated migration baseline. Recipe and SHA provenance are in
`script/dataset/revdev/recipes/claude_log_viewer/`.

Generation attempts were retained rather than rewritten:

- `claude_core_0361_v1_recipe_rejected`: adapter rejected a recipe that
  mentioned both Jac versions in model-visible plan text.
- `claude_core_0361_v2`: Claude CLI stopped at step zero with sandbox
  `EAI_AGAIN`; no tool call executed.
- Initial unsandboxed retry was rejected by automatic approval review because
  the private teacher prompt, task and plan would be sent to Claude API.
  After the user explicitly authorized sending those three files, the same
  adapter call was approved.
- `claude_core_0361_v3`: Claude produced a plan write, but dispatch used Jac
  0.36.1 for the old JacBuilder harness and failed before the write.
- `claude_core_0361_v4`: the Jac 0.34.27 harness binary was passed as a
  relative path; dispatch failed to launch it. No write completed.
- `claude_core_0361_v5`: target Jac 0.36.1 and absolute-path JacBuilder Jac
  0.34.27 were specified separately. The teacher finished in 20 decisions,
  including 18 executed JacCoder calls. It wrote `docs/plan.md` with a Mermaid
  module graph, all scaffolds, implementation and seven tests. A real Jac
  diagnostic E1053 and a schema-rejected edit were preserved; the teacher
  corrected the code. Its seven tests and final all-file Jac check passed.

Independent `validate.py` ran the three source-derived tests in a copied
workspace and passed. The first sandbox replay failed at step zero because
JacBuilder's runtime dependency was inaccessible there; after local replay
was approved, clean replay reproduced all 18 calls and final file hashes.
`validate.py --accept-backend` marked the run `accepted` only after replay.

Exported to `dataset/sft/revdev_{plan,scaffold,app}/claudelogviewer-core-0361-v5`
with train split: three distinct samples at 1,423 / 5,146 / 17,050 context
tokens, plus two <=16k mirrors of plan and scaffold. There is no function or
resume sample from this short run. Total five records / 30,188 context tokens,
with three distinct task projections. The full revdev audit immediately after
export passed at 69 records / 663,380 context tokens / zero issues. This
aggregate includes concurrent exports from other runs and is a point-in-time
count, not a ClaudeLogViewer-only count.
