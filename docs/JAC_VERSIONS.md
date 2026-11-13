# Jac versions: 0.34.28 vs 0.36.1 vs 0.37.25

Measured on 2026-11-09. Question: is the gap between 0.34 and 0.36 larger than the gap between 0.36 and 0.37, and
would moving JacHammer to 0.37 bring it closer to our 0.36.1 training data?

## Release lines

0.34.x is a maintenance line released alongside the newer minors, so version numbers do not follow release dates.
All of these are non-prerelease on GitHub (`jaseci-labs/jac`).

| Line | Releases | Dates |
|---|---|---|
| 0.34.x | 0.34.0 to 0.34.28 | 2026-07-20 to 2026-10-22 |
| 0.35.x | 0.35.0, 0.35.1 | 2026-07-30, 07-31 |
| 0.36.x | 0.36.0, 0.36.1 | 2026-08-09, 08-10 |
| 0.37.x | 0.37.1 to 0.37.25 | 2026-08-31 to 2026-10-06 |
| 0.38.x, 0.39.x | 0.38.0 to 0.39.1 | 2026-10-19 to 2026-11-04 |

jacBuilder bakes 0.34.28 into its sandbox image (`sandbox/templates/sandbox-base.versions.json`) and only lists 0.34.x
as supported; `jac_version.jac` notes that JacCoder guide compatibility is deliberately narrower than runtime support.
It already has `jac_preview_uses_run_serve()` for projects pinned to 0.37 or later.

## Evidence 1: bundled guides

The skills bundled in each binary (`site/jaclang/cli/skills/*.md`), compared with `diff`.

| Pair | Changed lines | Guides added |
|---|---|---|
| 0.34.28 → 0.36.1 | 716 | none (same 40 guides) |
| 0.36.1 → 0.37.25 | 2294 | 6 (`jac-apps`, `jac-arch-wiring`, `jac-comptime`, `jac-essentials`, `jac-packages`) |

In 0.37 the frontend guides were cut down and the details moved to `jac guide reference/agent-patterns/<name>`
(`jac-cl-components` 282 → 40 lines, `jac-shadcn-components` 485 → 32 lines).

## Evidence 2: release notes

Entries headed "Breaking" in the 0.37.25 release notes (`docs/community/release_notes/jaclang.md`). The 0.34.7 to
0.34.28 releases have no notes there.

| Range | Breaking entries | Ones that change code or commands an agent writes |
|---|---|---|
| 0.35.0 to 0.36.1 | 9 | `sv`/`cl`/`na` markers removed; `.na.jac` retired; `AccessLevel` enum; closed `[?...]` filter language |
| 0.37.0 to 0.37.25 | 31 | `jac start`/`jac dev` replaced by `jac run --serve/--dev` (0.37.0); keywords need backticks (0.37.0); `JAC_CLIENT_00x` codes replaced by `E7xxx` (0.37.0); `entry-point` is a module name (0.37.12); bare `dict`/`list`/`tuple` is an error (0.37.18); edges must name endpoints (0.37.22); plain `def`/`walker` no longer served, `:protect`/`:pub` decide exposure (0.37.22) |

## Evidence 3: the same code under `jac check`

Each item is copied to a temp directory and checked with each binary. Columns: the corpus; how many items pass on
0.36.1 (the base set); how many of those still pass on 0.34.28 and on 0.37.25; the main error codes behind the failures.

| Corpus | Pass on 0.36.1 | Still pass on 0.34.28 | Still pass on 0.37.25 | Main causes |
|---|---|---|---|---|
| 150 random RL `solution.jac` (backend functions) | 150 | 150 | 134 | 0.37: `E1123` (`typing.List`/`Tuple` imports) |
| 74 spike episode workspaces (fullstack) | 54 | 24 | 21 (34 after fixing `entry-point` in `jac.toml`) | 0.34: JSX as a tail expression without `return` (22), client helper imported across modules `E5082` (5), other (3). 0.37: `entry-point = "main.jac"` rejected (25), bare `dict`/`list` `E1036` (16 of the 20 code failures), state assigned during render `E0082`, `await` outside `async` `E2085`, edge without endpoints `E2086`, keyword as a name `E0013` |

Single-construct probes (`jac check` exit code 0 = pass):

| Construct | 0.34.28 | 0.36.1 | 0.37.25 |
|---|---|---|---|
| `cl { ... }` marker block | pass | E0005 | E0005 |
| `d: dict` / `has items: list` | pass (W1036) | pass (W1036) | E1036 |
| field named `skip` | pass | pass | E0013 |
| `edge Knows {}` | pass | pass | E2086 |
| JSX tail expression, no `return` | E0002, E1004 | pass | pass |
| untyped parameter | E0052 | E0052 | E0052 |

## Findings

- "0.34 to 0.36 added many strict type checks" is not what the measurements show. 0.34.28 passes all 150 backend
  solutions that pass on 0.36.1. Its fullstack failures come from syntax 0.36 added (JSX tail expressions) and from
  placement inference that does not cross modules (`E5082`), not from stricter type checking.
- The markers make the versions incompatible in one direction only: 0.34.28 accepts both marker and markerless code;
  0.36 and later reject markers.
- 0.36 → 0.37 is the larger change by every measure here: about 3x the guide changes, 31 vs 9 breaking entries, and
  0.37 adds checks 0.36 did not have (`E1036`, `E0082`, `E2085`, `E2036`, `E1123`, `E2086`, `E0013`). On fullstack code it
  passes more of our workspaces than 0.34.28 only after a `jac.toml` change.
- 0.37 also changes what the agent types: `jac start --dev main.jac`, which the JacHammer prompt prescribes, is gone,
  and endpoint exposure changed in 0.37.22. Moving JacHammer to 0.37 means editing its prompt and tools, not just
  the version pin.

Limits: `jac check` only (no `jac test`, no running app); the workspace corpus was written for 0.36.1, so it
favours 0.36.1; 0.37.25 is one point in a line that changed a lot between patch releases.
