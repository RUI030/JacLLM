# Orbitron fleet UI trajectory (2026-11-01)

## Source and scope

- Source repository: `dataset/raw/repo/JacHackSpring/orbitronsystems__ori-Jac-Demo/` (`98f7832`). The original full app passed Jac check/build but registered no usable page route; `GET /` returned 404 under Jac 0.34.27 and 0.36.1. It was rejected as whole-app ground truth.
- Usable slice: the unchanged `pages/dashboard/FleetModule.jac` (SHA-256 `2404e69c3a411331ecc7223c0aad41a92cea449e5f82db69516c76c456ec4c38`) in a thin Jac 0.36.1 wrapper at `/tmp/revdev-orbitron-fleet-reference/`. The reference UI passed the fleet-filter browser flow. Recipe, provenance, and browser spec are in `script/dataset/revdev/recipes/orbitron_fleet/`.
- Scope is a local six-vehicle fleet registry and status filter; it does not claim to rebuild the original repository's nonworking full app.

## Actual teacher run and gates

- Accepted run: `dataset/raw/revdev/OrbitronFleet/runs/claude_teacher_fleet_jac036_v2/`. Claude CLI produced 43 decisions; 38 JacCoder calls executed. The final workspace is `workspace-segment-3/`.
- The first generated page rendered six rows but used filter buttons and different labels. Browser evidence for this failed attempt is retained at `browser-attempt-1/browser.json`. The teacher continued from feedback and changed the UI to a dropdown. An adapter checkpoint initially dropped that feedback on the following step; the common adapter was subsequently fixed, and the continued run kept feedback through the repair.
- Independent Jac check/build passed. Clean replay passed all 38 calls. The shared scripted browser checker passed the same spec on the source wrapper (`dataset/raw/revdev/OrbitronFleet/preflight/reference-browser/browser.json`) and final generated page (`browser-final/browser.json`): six rows initially, then 4 Active, 1 Maintenance, 1 Idle, and six after resetting to All, without JavaScript errors. Both browser artifacts contain spec SHA-256 `13eb7ab1018cb9da1283f9d63c11510728b4008ab80353e16a69397b77312bab`.
- `validate.py --ui-only --accept-browser ... --reference-browser ...` marked the run **accepted** with zero issues. The teacher's own five source-oriented tests passed, but browser behavior is the independent acceptance evidence.

## SFT output

- Repository split: **train** (`orbitronsystems__ori-Jac-Demo`). This repository occurs in older SFT material, so the new run is not model-unseen validation.
- Formal outputs: `dataset/sft/revdev_{plan,scaffold,app,resume}/orbitron-fleet-jac036-v2/`; `revdev_function` has zero records. Six train records: plan 1 (1,059 tokens), scaffold 1 (5,554), app 1 (13,177), resume 3 (4,334, 17,897, 15,342). Five of six are at most 16,384 tokens; all fit the 65,536-token dataset cap.
- The dedicated SFT audit at `dataset/raw/revdev/OrbitronFleet/runs/claude_teacher_fleet_jac036_v2/export-audit.json` passed: **6 records, 57,363 total context tokens, zero issues**.
- A full revdev audit after this export (`full-revdev-audit.json` in the same run) passed with **55 records, 533,759 total context tokens, zero issues**. This is a point-in-time count while other repository runs may still be exporting.
- A separate estimate counts assistant payloads using the current tokenizer, excluding system/user/tool messages and deduplicating identical assistant payloads across records: 16,307 assistant-payload tokens across 46 turns, or 13,402 unique tokens across 36 unique turns. This is not the exact trainer loss-mask count; it omits chat-template tokens and may differ from the trainer's serialization.
