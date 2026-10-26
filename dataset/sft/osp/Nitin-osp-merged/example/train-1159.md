# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "osp",
  "fp": "iss_markmhendrickson__neotoma__2091",
  "origin_file": "osp_merged_corpus.jsonl",
  "origin_id": "iss_markmhendrickson__neotoma__2091",
  "tier": "legacy_test_verified",
  "verification": "check+tests",
  "n_tokens": 1918,
  "n_answer_tokens": 727
}
```

## USER

A maintainer on the project markmhendrickson/neotoma (unknown) filed this issue about hand-rolled graph machinery causing pain:

Issue #2091: Add user_id indexes for entities/sources COUNT scoping (#1889 AC b)

## What

PR #2041 (closes #1889) scopes the `list_resources` collection counts to the authenticated user via `.eq("user_id", userId)`. Measured `EXPLAIN QUERY PLAN` shows 2 of the 3 scoped counts still do a full table scan because there is no leading `user_id` index on `entities` or `sources`:

| Query | Plan (measured) |
|---|---|
| `COUNT(*) FROM entities WHERE user_id=? AND merged_to_entity_id IS NULL` | `SCAN entities` |
| `COUNT(*) FROM relationship_snapshots WHERE user_id=?` | `SCAN relationship_snapshots USING COVERING INDEX idx_rel_snapshots_target_user_live` |
| `COUNT(*) FROM sources WHERE user_id=?` | `SCAN sources` |

## Fix

In `src/repositories/sqlite/sqlite_client.ts`, alongside the existing `CREATE INDEX IF NOT EXISTS` calls (e.g. `idx_rel_snapshots_target_user`, `idx_observations_entity_id`):

```sql
CREATE INDEX IF NOT EXISTS idx_entities_user_id ON entities(user_id)
CREATE INDEX IF NOT EXISTS idx_sources_user_id ON sources(user_id)
```

Arch may prefer a composite `(user_id, merged_to_entity_id)` for the `entities` count specifically — defer that shape call to whoever picks this up; note the tradeoff in the PR.

## Test

Assert `EXPLAIN QUERY PLAN` output for the three scoped COUNT queries contains `SEARCH`/`USING INDEX` and not a bare `SCAN entities` / `SCAN sources`, using the sqlite EXPLAIN-plan test helper pattern already used elsewhere in the suite.

## Acceptance criteria

This closes #1889 acceptance criterion (b) — "counts use per-user indexes" — which PR #2041 explicitly deferred here per pm (Pavo) sign-off, to ship the confidentiality fix (AC a) without expanding that PR's blast radius to schema/index changes.

## Origin

Filed per Pavo's (pm) review guidance on PR #2041, round 1 of auto-fix review.

<!-- swarm-spec:start -->
## Swarm specification

_This section is maintained by the Ateles swarm. Each lens agent owns exactly one subsection below; the human-written description above these markers is never modified._

### Product / Scope (PM)

**Problem**
After PR #2041 scoped `list_resources` collection counts with `.eq("user_id", userId)`, measured `EXPLAIN QUERY PLAN` still shows full-table `SCAN` on `entities` and `sources` — so #1889 acceptance criterion (b) (“counts use per-user indexes”) remains open.

**In scope**
- Add `CREATE INDEX IF NOT EXISTS` for `entities(user_id)` and `sources(user_id)` in `src/repositories/sqlite/sqlite_client.ts` (alongside existing index DDL), or an arch-approved equivalent shape
- EXPLAIN QUERY PLAN tests for the three scoped COUNT queries (`entities`, `relationship_snapshots`, `sources`), following the existing sqlite EXPLAIN-plan helper pattern (`tests/unit/relationship_traversal_indexes.test.ts`)
- Document the entities index-shape tradeoff in the PR (`user_id` vs composite `(user_id, merged_to_entity_id)`) — arch decides shape

**Out of scope**
- Changing COUNT predicates / confidentiality scoping (done in #2041 / AC a)
- New or changed MCP / REST / CLI / SDK contracts or tools
- UX, UI, copy, or onboarding changes
- Reworking `relationship_snapshots` indexes (already covering-index eligible per measured plan)

**Acceptance criteria**
- [ ] `idx_entities_user_id` (or arch-approved equivalent) is created via the same `CREATE INDEX IF NOT EXISTS` path as peer indexes in `sqlite_client.ts`
- [ ] `idx_sources_user_id` (or arch-approved equivalent) is created likewise
- [ ] EXPLAIN QUERY PLAN for `COUNT(*) FROM entities WHERE user_id=? AND merged_to_entity_id IS NULL` shows `SEARCH` / `USING INDEX`, not a bare `SCAN entities`
- [ ] EXPLAIN QUERY PLAN for `COUNT(*) FROM sources WHERE user_id=?` shows `SEARCH` / `USING INDEX`, not a bare `SCAN sources`
- [ ] EXPLAIN QUERY PLAN for `COUNT(*) FROM relationship_snapshots WHERE user_id=?` continues to use an index (no regression)
- [ ] Effect-verified: tests assert the observed EXPLAIN plan detail (index use), not merely that `CREATE INDEX` DDL is accepted
- [ ] Cross-surface parity: N/A — SQLite index DDL only; no MCP/

Write a small self-contained Jac demo program that models the essential scenario from this issue natively: pick the 2-4 core entity types as node archetypes with typed has fields, connect instances with edges (typed edges where the relationship carries meaning), and implement walker(s) that perform the traversal the issue complains about (e.g. recursion over parents/children, cascade delete or invalidation, dependency ordering, cycle detection, reachability). Wire a small demonstration graph in a `with entry` block and spawn the walker(s). No I/O, no external libraries, no pytest blocks.

## ASSISTANT

"""Per-user scope demo: model entities/sources/relationship_snapshots as nodes
and walk them with a per-user scoping walker to mirror the indexed COUNT
traversal the issue is fixing."""

node Database {
    has name: str = "";
}

node Entity {
    has title: str = "";
    has user_id: str = "";
    has merged_to_entity_id: str | None = None;
}

node Source {
    has title: str = "";
    has user_id: str = "";
}

node RelationshipSnapshot {
    has target_user_id: str = "";
    has user_id: str = "";
}

edge Tables { }
edge OwnedBy { has user_id: str = ""; }
edge Targets { }

walker IndexedCount {
    has current_user: str = "";

    can start with Root entry {
        visit [-->];
    }

    can scope with Database entry {
        print(f"Counting scoped records for user_id={self.current_user}");
        visit [-->];
    }

    can scope_entities with Entity entry {
        if here.user_id == self.current_user and here.merged_to_entity_id is None {
            print(f"  [entities] {here.title} (uses idx_entities_user_id)");
        }
        visit [-->];
    }

    can scope_sources with Source entry {
        if here.user_id == self.current_user {
            print(f"  [sources] {here.title} (uses idx_sources_user_id)");
        }
        visit [-->];
    }

    can scope_snapshots with RelationshipSnapshot entry {
        if here.user_id == self.current_user {
            print(f"  [relationship_snapshots] target={here.target_user_id} (uses idx_rel_snapshots_target_user_live)");
        }
        visit [-->];
    }
}

with entry {
    db = Database(name="neotoma");
    root ++> db;

    db +>:Tables:+> Entity(title="Acme", user_id="u1", merged_to_entity_id=None);
    db +>:Tables:+> Entity(title="Beta", user_id="u1", merged_to_entity_id="ent-1");
    db +>:Tables:+> Entity(title="Gamma", user_id="u2", merged_to_entity_id=None);

    db +>:Tables:+> Source(title="Spec.md", user_id="u1");
    db +>:Tables:+> Source(title="Notes.md", user_id="u2");

    db +>:Tables:+> RelationshipSnapshot(target_user_id="u1", user_id="u1");
    db +>:Tables:+> RelationshipSnapshot(target_user_id="u1", user_id="u1");
    db +>:Tables:+> RelationshipSnapshot(target_user_id="u2", user_id="u2");

    db +>:OwnedBy(user_id="u1"):+> Entity(title="Acme", user_id="u1", merged_to_entity_id=None);
    db +>:OwnedBy(user_id="u1"):+> Source(title="Spec.md", user_id="u1");
    db +>:OwnedBy(user_id="u1"):+> RelationshipSnapshot(target_user_id="u1", user_id="u1");

    root spawn IndexedCount(current_user="u1");
}
