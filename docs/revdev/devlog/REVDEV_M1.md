# Reverse Development M1: reference manifest

Status: M1 extractor and first raw-repo baseline complete on 2026-10-27.
This milestone creates private reference evidence only; it exports no SFT row.

## Implementation

- [extract.jac](../../../script/dataset/revdev/extract.jac) uses the pinned Jac
  compiler's `JacProgram.parse_str` AST and `CodeIntelligence`. It records
  declaration signatures and locations, archetype fields, enums, import items,
  call sites and compiler symbol references. The bridge runs against a
  disposable copy of the repo.
- [extract.py](../../../script/dataset/revdev/extract.py) reuses
  `dataset.parser.repo.iter_repo_files` for selection and `utils.jac_cli.execute`
  for Jac execution. It resolves local import paths, imported symbols,
  conservative bare-name calls, unique compiler `def/use` links and
  declaration/implementation annexes. It records uncertain imports and
  dynamic calls without inventing targets.
  Import cycles use strongly connected components. Accepted edges are rejected
  if the target or source span is missing.
- `utils.jac_cli.execute` gained an optional `jac` executable argument so the
  extractor and baseline can use the same pinned runtime. Existing callers
  keep the original default. An exact `jac-version` declaration is checked
  before extraction; the fixture test also verifies a mismatch is rejected.

The retained JacCoder prompt/schema capture remains in the gitignored
`script/dataset/trajectory/harness/jaccoder.m0.json`, following the older
dataset convention. Manifest outputs go under gitignored `dataset/raw/revdev/`;
eventual SFT producers still use `dataset/sft/<task_type>/<DS_NAME>/` and
`dataset.pipeline`.

## Fixture evidence

The [import_graph fixture](../../../script/dataset/revdev/fixtures/import_graph)
has two modules importing one another, one `.impl.jac` annex, a node field,
an enum, local and cross-module calls, and one missing relative import. The
extractor found:

- Eight accepted edges: three imports, one annex edge, three calls and one
  compiler `symbol_use` edge. Every edge points to an existing selected file
  and a valid source line/column.
- Cycle: `a.jac` ↔ `b.jac`.
- Unresolved: `.missing` / `Ghost`, with its import location.

[test_extract.py](../../../script/dataset/revdev/test_extract.py) checks these
relationships, source text at each position and compiler-version rejection.
Both tests passed with Jac 0.34.27. The compiler
bridge also passed `jac check` under that version.

## First raw repo: `Rui/pm`

The private local artifact is
`dataset/raw/revdev/Rui_pm/m1/private/reference_manifest.json`; it is ignored
by Git. The source commit is `e93a47fb2a3d5f4fcc708ee0031467a472abb34b`,
with no local modifications observed when extracted. Results:

| Measure | Count |
| --- | ---: |
| Selected files | 27 |
| Excluded roots/files recorded | 4 |
| AST symbols | 135 |
| Accepted local import edges | 108 |
| Accepted syntactic call edges | 102 |
| Accepted compiler symbol-use edges | 84 |
| Accepted asset edges | 1 |
| Unresolved dynamic or non-bare calls | 99 |
| External or unavailable import paths | 34 |
| Accepted edges without valid source span | 0 |

`Rui/pm` does not declare an exact Jac version. The fresh baseline ran
`jac check main.jac` with Jac 0.34.27 in a disposable
copy, returned exit code 0 and took 982 ms. The full extraction command took
about three seconds.
Compiler output included W1051 and W1100 warnings, including missing frontend
package references. A passing check is not runtime or browser verification;
M2 should keep this repo as a candidate, not treat it as an approved working
app sample yet.

M2 subsequently tested a disposable copy: Jac 0.34.27 failed to start on
`components/ui` JSX syntax even though `jac check main.jac` passed. The same
source started with Jac 0.36.1 and passed a root-project HTTP create/readback
probe. See [REVDEV_M2.md](REVDEV_M2.md). The M1 check result remains an exact
record of that command, not a claim of runtime compatibility.

## Interpretation and M2 handoff

Resolved imports are grounded in compiler AST locations and selected local
files. Same-module `symbol_use` edges require a unique matching compiler
definition and carry `confidence: "compiler_symbol"`. Bare-name call edges are syntactic
bindings to an unambiguous local or imported declaration and carry
`confidence: "syntactic"`; they are not claimed to be fully compiler-resolved
semantic call edges. `CodeIntelligence` references are retained separately
and can be sparse when compilation cannot resolve the whole project. Member
calls remain unresolved rather than being guessed.

M2 can use confirmed import/annex edges to build a file order. It should
review syntactic call edges and external imports when grounding a task scope,
and run the selected app's actual acceptance flow before labeling the source
as working ground truth.
