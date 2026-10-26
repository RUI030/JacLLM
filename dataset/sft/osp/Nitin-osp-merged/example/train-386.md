# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "osp",
  "fp": "iss_evomimic__map-holons__661",
  "origin_file": "osp_merged_corpus.jsonl",
  "origin_id": "iss_evomimic__map-holons__661",
  "tier": "legacy_test_verified",
  "verification": "check+tests",
  "n_tokens": 3069,
  "n_answer_tokens": 1420
}
```

## USER

A maintainer on the project evomimic/map-holons (unknown) filed this issue about hand-rolled graph machinery causing pain:

Issue #661: [sub issue] Storage SL5b-V1 — Holon space membership

### 1. Summary (Required)

**What is the enhancement?**

Make `Holon --OwnedBy--> HolonSpace` and its `HolonSpace --Owns--> Holon` inverse real, persisted
relationships, correct across the whole holon lifecycle: a new lineage acquires membership when it
is published, a new version inherits its lineage root's rather than acquiring its own, and a deleted
holon has its membership retracted.

Membership becomes queryable through ordinary relationship traversal — ask a holon which space owns
it, ask a space what it owns — with no new read API and no change to `GetAllHolons`.

---

### 2. Problem Statement (Required)

**Why is this needed?**

The MAP Core Schema declares `OwnedBy` / `Owns` in `schema-src/core/relationship-types.tdl`, and
`root.tdl` puts `OwnedBy` in `HolonType`'s `InstanceRelationships`, so every holon's effective
contract already includes it. Nothing writes or reads it. `CoreRelationshipTypeName::OwnedBy` and
`::Owns` exist in `relationship_names.rs` purely so the names are spellable.

The consequence is that a holon cannot answer which space it belongs to, and a space cannot
enumerate its members, even though the schema says both should be possible. Whole-space discovery is
served instead by `AllHolonNodes`, a storage-owned global index that duplicates this topology
(#642 §2).

This slice closes the gap between the declared schema and the persisted graph. It does **not** touch
discovery — that is [SL5b-V2](storage_sl5b_v2_issue.md).

---

### 3. Dependencies (Required)

**Does this depend on other issues or features?**

- Depends on PR #637 (Storage SL5a): the `HolonNodeUpdates` revision index is retired.
- Depends on the bootstrap `LocalHolonSpace` anchor existing, which
  `dance_adapter::init_guest_context` guarantees before any dance body runs.
- Does **not** depend on `QueryExpression` / `QueryDance` (#642 §3).
- Does **not** depend on, and is not blocked by, V2 or the `AllHolonNodes` teardown.

Nothing depends on this slice landing except V2.

---

### 4. Proposed Solution (Required)

**How would you solve it?**

**4.1 Author membership when a lineage is published.** `commit_holon`'s `ForCreate` arm calls
`stage_space_membership` (`commit_functions.rs`), which stages `OwnedBy → current HolonSpace` on the
staged holon. The ordinary relationship pass then persists it and materializes the `Owns` inverse
through the existing `save_smartlinks_for_collection`. This mirrors the adjacent
`stage_predecessor_relationship`, which already mutates a staged holon mid-commit for the same
reason.

It is called *after* `persist_holon` returns, so the new lineage's own id is available to the
self-ownership guard below.

**4.2 A space does not own itself.** `stage_space_membership` returns early when the holon being
published is the space itself. The `LocalHolonSpace` anchor is exempt in practice because
`create_local_space_holon` publishes it through `persist_holon` directly and it never reaches
`commit` — the guard makes the rule hold on its own terms rather than as a consequence of that
routing.

**4.3 Do not re-anchor membership on a new version.** A version-producing commit replays the full
relationship scope against the *new* version's id, which would make the space own the lineage root
and every version after it separately (#642 §8 rejects this). `RelationshipCommitScope` gains a
`FullExceptMembership` variant, set by `prepare_new_version_relationship_commit_scope()` and used by
the `ForUpdateNewVersion` arm. It is a commit *scope* rather than a check on staged state because by
the time the relationship pass reads it the holon is already `Committed` and its version-producing
origin is no longer visible.

**4.4 Write membership before anything that can fail.** The relationship pass stops at a source
holon's first failing relationship, and undescribed holons with freeform relationships fail there by
design (`simple_add_remove_related_holons_fixture` is the canonical case). `OwnedBy` is therefore
ordered first under `Full` scope, so a failing user relationship cannot preempt membership.

**4.5 Resolve the inverse structurally.** `resolve_inverse_relationship_name`
(`inverse_resolution.rs`) short-circuits `OwnedBy → Owns` without descriptor resolution. The general
path goes through the source holon's `DescribedBy`, which membership cannot rely on twice over:
undescribed holons commit successfully today, and on the first core-schema load the `OwnedBy`
descriptor is itself among the holons being staged. The TDL header already describes this
relationship as infrastructure-supplied.

**4.6 Retract membership on delete.** `delete_holon_node` deletes only the `LocalHolonSpace` path
link and the entry; every SmartLink survives it. `delete_holon_internal` gains
`retract_space_membership`, which deletes the `Owns` link on the space and the `OwnedBy` link on the
holon. The space's inverse view is retracted first, since that is the side a future discovery
implementation reads. It lives in `guest_holon_service.rs` rather than `persistence_layer`, which is
deliberately descriptor-unaware.

**4.7 Do not skip quietly.** `stage_space_membership` warns when no space is bound to the
transaction. That branch should be unreachable, which is exactly why silence there would hide a
regression.

**No new read code is required.** `related_holons("OwnedBy")` and `related_holons("Owns")` are
already served by `fetch_related_holons_internal` via `expand_from_source`. That is what makes this
a vertical slice rather than a write-only layer: the capability is observable the moment the writes
land.

---

### 5. Scope and Impact (Required)

**What does this impact?**

| Area | Change |
| --- | --- |
| `happ/crates/holons_guest/src/guest_shared_objects/commit_functions.rs` | `stage_space_membership` + its `ForCreate` call site |
| `shared_crates/holons_core/src/core_shared_objects/holon/staged.rs` | `FullExceptMembership` scope, its setter, `OwnedBy`-first ordering |
| `shared_crates/holons_core/src/descriptors/inverse

Write a small self-contained Jac demo program that models the essential scenario from this issue natively: pick the 2-4 core entity types as node archetypes with typed has fields, connect instances with edges (typed edges where the relationship carries meaning), and implement walker(s) that perform the traversal the issue complains about (e.g. recursion over parents/children, cascade delete or invalidation, dependency ordering, cycle detection, reachability). Wire a small demonstration graph in a `with entry` block and spawn the walker(s). No I/O, no external libraries, no pytest blocks.

## ASSISTANT

"""Holon space membership: model Holons and HolonSpaces with typed OwnedBy/Owns
edges and demonstrate membership creation, version inheritance (no re-anchor),
self-ownership guard, and retraction on delete.
"""

node HolonSpace {
    has name: str = "";
}

node Holon {
    has title: str = "";
    has version: int = 1;
    has deleted: bool = False;
}

edge OwnedBy {
    has since: str = "";
}

edge Owns {
    has since: str = "";
}

# Stages membership: owned_by the bound space, unless the holon IS the space.
walker MembershipStager {
    has space_name: str = "";

    can stage with Root entry {
        bound_space: HolonSpace | None = None;
        for n in [-->] {
            if isinstance(n, HolonSpace) {
                bound_space = n;
            }
        }
        if bound_space is None {
            print("WARN: no HolonSpace bound to this transaction");
            disengage;
        }
        visit [-->];
        print(f"Staged membership for space: {bound_space.name}");
    }

    can stage_with_holon with Holon entry {
        if here.deleted {
            visit [-->];
        }
        for n in [-->] {
            if isinstance(n, HolonSpace) {
                # Self-ownership guard: a space does not own itself.
                if here.title == n.name {
                    visit [-->];
                }
            }
        }
        print(f"  -> Holon '{here.title}' v{here.version} staged for membership");
        visit [-->];
    }
}

# Resolves the inverse structurally: OwnedBy on a Holon -> Owns on the Space.
walker InverseResolver {
    can start with Root entry {
        visit [-->];
    }

    can resolve_inverse with Holon entry {
        space_node: HolonSpace | None = None;
        for n in [-->] {
            if isinstance(n, HolonSpace) {
                space_node = n;
            }
        }
        if space_node is not None {
            label = "Owns";
        } else {
            label = "UNRESOLVED";
        }
        print(f"Inverse of {here.title}'s OwnedBy -> {label}");
        visit [-->];
    }
}

# Versioning walker: a new version inherits its lineage root's space membership
# rather than acquiring its own.
walker VersionProducer {
    has new_version: int = 0;

    can start with Root entry {
        visit [-->];
    }

    can produce_version with Holon entry {
        if here.version >= self.new_version {
            visit [-->];
        }
        here.version = self.new_version;
        print(f"Produced v{self.new_version} of '{here.title}' (inherits lineage root's space)");
        visit [-->];
    }
}

# Retraction walker: deletes the Owns link on the space and the OwnedBy link on the holon.
walker MembershipRetractor {
    can start with Root entry {
        visit [-->];
    }

    can retract with Holon entry {
        if not here.deleted {
            visit [-->];
        }
        # Retract Owns from the space side first (the side future discovery reads).
        for n in [-->] {
            if isinstance(n, HolonSpace) {
                print(f"Retracting Owns from space '{n.name}' for deleted holon '{here.title}'");
                n del --> here;
            }
        }
        # Then retract OwnedBy on the holon itself.
        here del --> [-->];
        print(f"Retracted OwnedBy on deleted holon '{here.title}'");
        visit [-->];
    }
}

# Membership auditor: walks every holon and reports its bound space (or none).
walker MembershipAuditor {
    has total: int = 0;
    has bound: int = 0;

    can start with Root entry {
        visit [-->];
    }

    can audit with Holon entry {
        self.total += 1;
        found_space: HolonSpace | None = None;
        for n in [-->] {
            if isinstance(n, HolonSpace) {
                found_space = n;
            }
        }
        if found_space is not None {
            self.bound += 1;
            print(f"  AUDIT: '{here.title}' v{here.version} -> space '{found_space.name}'");
        } else {
            print(f"  AUDIT: '{here.title}' v{here.version} -> NO SPACE");
        }
        visit [-->];
    }

    can audit_space with HolonSpace entry {
        members: list = [];
        for n in [-->] {
            if isinstance(n, Holon) and not n.deleted {
                members.append(n.title);
            }
        }
        print(f"  AUDIT: space '{here.name}' owns {len(members)} holon(s): {members}");
    }
}

with entry {
    local_space = HolonSpace(name="LocalHolonSpace");
    root ++> local_space;

    h1 = Holon(title="Alpha");
    h2 = Holon(title="Beta");
    h3 = Holon(title="Gamma");
    local_space ++> h1;
    local_space ++> h2;
    local_space ++> h3;

    print("=== Stage membership on create ===");
    root spawn MembershipStager();

    print("\n=== Resolve inverses structurally ===");
    root spawn InverseResolver();

    print("\n=== Audit membership ===");
    root spawn MembershipAuditor();

    print("\n=== Produce a new version of Alpha (must NOT re-anchor) ===");
    root spawn VersionProducer(new_version=2);

    print("\n=== Mark Beta as deleted and retract its membership ===");
    h2.deleted = True;
    root spawn MembershipRetractor();

    print("\n=== Final audit ===");
    root spawn MembershipAuditor();
}
