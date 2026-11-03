# Revdev candidate apps (2026-11-02)

Goal: more distinct apps for request -> plan -> scaffold -> fill, weighted
toward cross-file imports. One app = one teacher run; a large repo may give
several slices, but every slice of one repo stays on the same split.

Data: `output/eval/revdev/slice-pool-20261102.json`, produced by
`script/dataset/revdev/slice_pool.py`. Columns:

- **closed**: modules that pass `jac check` 0.36.1 *and* whose local imports
  (transitively) also pass. Only these can form a slice. `components/ui/*`
  shadcn files and `.impl.jac` annexes (merged into their module) are excluded.
- **imp**: closed modules that import at least one other local module, i.e.
  cross-file fill targets. **edges**: local import edges among closed modules.
  **depth**: longest import chain.
- **orig imp**: the same as `imp`, but treating LLM-repaired files as unusable.
- **prior SFT**: repo name found in older non-revdev SFT data (train side only).

`jac check` is per file. It does not prove the app runs or behaves; every slice
still needs source-derived behavior tests, clean replay, and browser checks for
UI, exactly as the six accepted apps did.

## Ann Arbor (JacHack A2Tech, 20 repos)

None of the 20 is whitelisted and none passes `jac check` for every file. Five
pin Jac 0.37.x; only 0.36.1 and 0.34.27 binaries exist locally, so their
failures may be version mismatch rather than broken code. All usable ones
already appear in `scaffold2impl`/`tool_fim`, so they are train-only.

| Repo | Title | check | pin | closed | imp | edges | depth | Note |
|---|---|---|---|---:|---:|---:|---:|---|
| `pathakanshu__trace` | Trace | 44/76 | - | 22 | 16 | 42 | 4 | Best unpinned A2Tech candidate |
| `joohyeon__UMadeIt` | UMadeIt | 44/82 | 0.37.2 | 30 | 23 | 36 | 3 | Needs 0.37.2 binary |
| `Sahil0445__campussync` | CampusSync | 33/59 | 0.37.2 | 18 | 11 | 31 | 5 | Needs 0.37.2 binary |
| `A2Tech360__A2-Pulse` | A2 Pulse | 43/56 | - | 24 | 9 | 24 | 5 | Already used (week planner); other slices possible |
| `AgenticPortfolioX__POR-Jac-Enforced` | Proof of Reserve | 23/35 | 0.37.2 | 14 | 7 | 20 | 3 | Backend; .py is 0.85x .jac |
| `ASH-will-WIN__AccessibleBrowser` | Accessa | 8/11 | 0.37.2 | 6 | 4 | 7 | 2 | Small |
| `CosmonautJones__m-local` | M-Local | 35/62 | 0.37.23 | 14 | 3 | 3 | 1 | Already used (multifile) |
| `lizchambs__Adoptable-Pet-Match` | Adoptable Pet Match | 15/18 | - | 5 | 2 | 2 | 1 | Small |

The other 12 A2Tech repos have at most one closed importer.

## JacHacks Spring + 2026 (75 repos, all files pass 0.36.1)

71 of 75 repos reached green only after an LLM migration sweep (`repaired_by`
in `jac-data-gen/data/jachacks_nonsf_jac_files_checked.jsonl`; mostly pre-0.35
syntax such as `can` abilities and `root()`). Using repaired files as ground
truth is a policy decision; `orig imp` shows what is left without them.

| Repo | Title | Pool | repaired | closed | imp | orig imp | edges | depth | prior SFT |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| `ayushmk7__GhostWatch` | GhostWatch | 2026 | 36/82 | 63 | 33 | 14 | 120 | 7 | none |
| `Async-Avengers__repoGhost` | repoGhost | 2026 | 10/52 | 52 | 30 | 5 | 111 | 8 | none |
| `push-to-production__CareAnchor` | AnchorCare | 2026 | 27/40 | 40 | 27 | 2 | 80 | 7 | none |
| `lcsc0__AlphaWalker` | AlphaWalker | 2026 | 22/40 | 40 | 22 | 0 | 53 | 4 | none |
| `yousefalwahami__rent_jac` | Rentora | 2026 | 13/24 | 24 | 16 | 3 | 41 | 6 | none |
| `Dhravidk__TraceForge` | Trace Forge | 2026 | 12/19 | 19 | 14 | 1 | 82 | 10 | none |
| `Sebasparky__jac_hacks` | Jac-Browser | 2026 | 22/24 | 24 | 14 | 0 | 24 | 4 | none |
| `debssM__Jac_2026` | Claimora.AI | 2026 | 5/14 | 14 | 13 | 2 | 40 | 3 | none |
| `Wally-Ahmed__JacHacks2026` | Uni-bank | 2026 | 11/24 | 23 | 11 | 0 | 38 | 3 | none |
| `FluentFlier__corpus` | Corpus | 2026 | 11/12 | 12 | 11 | 0 | 11 | 1 | none |
| `thesanatt__orbit` | ORBIT | 2026 | 6/13 | 13 | 7 | 1 | 31 | 2 | none |
| `aadish98__Notes_For_JACathon` | BeanBot | 2026 | 5/11 | 11 | 7 | 4 | 22 | 4 | none |
| `YamaanNandolia__Outloop-AI` | Outloop AI | 2026 | 8/11 | 11 | 7 | 0 | 15 | 7 | none |
| `Anay162__agewise` | Agewise | 2026 | 123/264 | 264 | 118 | 8 | 573 | 3 | none; very large, cap slices |
| `krishs09-123__jachacks-engagement-auditor` | Flair | spring | 21/41 | 32 | 26 | 4 | 75 | 6 | scaffold2impl, tool_fim |
| `Anbu-00001__CivicMesh` | CivicMesh | spring | 24/36 | 29 | 24 | 4 | 69 | 6 | none |
| `Viktor-Nedev__Nourish` | Nourish | spring | 23/32 | 32 | 21 | 1 | 57 | 3 | tool_use (name match) |
| `shaileshdev4__depgraph` | DepGraph | spring | 10/22 | 22 | 15 | 5 | 35 | 6 | none |
| `nishantr14__jac` | PharmaGraph | spring | 12/15 | 15 | 12 | 0 | 24 | 2 | none |
| `gaganTakIITD__LegalForge-AI` | LegalForge AI | spring | 13/23 | 23 | 10 | 0 | 36 | 2 | none |
| `beatable-12__truthforge-ai` | TruthForge | spring | 11/12 | 12 | 9 | 0 | 26 | 2 | tool_use (name match) |
| `kshitijkumrawat20__JacHacks2026` | FutureOS | spring | 8/13 | 13 | 9 | 1 | 23 | 3 | scaffold2impl, tool_fim |
| `fozagtx__insuraAgent` | InsuraAgent | spring | 3/10 | 10 | 7 | 4 | 11 | 4 | none |

"Name match" means a plain-word grep hit (for example "Nourish"); confirm
before treating it as prior exposure.

## Suggested order

1. Hold out one unseen app for evaluation before any generation, for example
   `ayushmk7__GhostWatch` (most cross-file structure using only original files,
   no prior SFT). Its whole repo goes to valid.
2. Pilot two train apps end-to-end to measure yield and cost per app, for
   example `pathakanshu__trace` (Ann Arbor, unpinned) and `debssM__Jac_2026`
   (few repairs, dense imports).
3. Then batch the rest, capping each repo at roughly 10-15% of revdev tokens.
