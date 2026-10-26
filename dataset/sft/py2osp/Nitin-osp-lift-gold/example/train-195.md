# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "py2osp",
  "fp": "osp__thomascarter613__monad-workspace__165__revsweep",
  "variant": "py2osp",
  "origin_file": "osp_merged_corpus.jsonl",
  "origin_id": "osp__thomascarter613__monad-workspace__165__revsweep",
  "tier": "v21_gold",
  "verification": "check+tests+elimination",
  "n_tokens": 1992,
  "n_answer_tokens": 1407
}
```

## SYSTEM

```
You are an expert jac language assistant.
```

## USER

Lift the Python code below into Jac OSP: graph data becomes node/edge archetypes and traversal becomes walker abilities. Preserve the API. Output only the Jac code.

```python
"""Dependency graph and impact analysis foundation.

Files belong to components, tasks depend on components, and tests cover
tasks; when a file changes, the blast radius is the owning components,
every task that depends on an impacted component, and the tests covering
those tasks (E25's changed-file impact analysis and impacted verification
recommendation). The chain below is hand-rolled: the model is three
dict-of-lists maps, and every hop of the ripple is a full reverse sweep
over one of them -- scanning every component's file list for each changed
file, then every task's component list, then every test's task list --
chained together with sets. No reverse index exists, so each lookup is a
linear scan of the whole map.
Ref: thomascarter613/monad-workspace#165
"""


def impacted(model, changed_files):
    """Changed-file impact analysis.

    ``model`` holds ``{"components": {comp: [files]}, "tasks": {task:
    [components]}, "tests": {test: [tasks]}}``. Returns
    ``{"components": sorted, "tasks": sorted, "tests": sorted}`` for the
    ripple file -> owning components -> depending tasks -> covering tests.
    A changed file belonging to no component has no impact.
    """
    comps = _owners(model["components"], changed_files)
    tasks = _dependents(model["tasks"], comps)
    tests = _dependents(model["tests"], tasks)
    return {"components": sorted(comps), "tasks": sorted(tasks), "tests": sorted(tests)}


def recommend_tests(model, changed_files):
    """Recommended verification for a change: tests covering impacted tasks."""
    return impacted(model, changed_files)["tests"]


def _owners(components, files):
    """Reverse sweep: components whose file list contains any changed file."""
    hit = set()
    for comp, owned in components.items():
        for f in files:
            if f in owned:
                hit.add(comp)
    return hit


def _dependents(mapping, targets):
    """Reverse sweep: keys whose value list intersects ``targets``."""
    hit = set()
    for key, vals in mapping.items():
        for v in vals:
            if v in targets:
                hit.add(key)
                break
    return hit
```

## ASSISTANT

"""Dependency graph and impact analysis foundation, lifted to OSP.

Files, components, tasks, and tests become node archetypes; ownership,
dependence, and coverage become typed PartOf / DependsOn / Covers edges.
The chained reverse sweeps over dict-of-lists become a single walker over
typed edges: from each changed file it follows PartOf forward to the
owning components, then reverse DependsOn to every task depending on them,
then reverse Covers to the covering tests. The per-archetype claim map is
the cycle policy for diamonds (a task depending on two impacted components
is reached twice and reported once). A changed file owned by no component
dead-ends immediately, exactly like the source sweep.
Ref: thomascarter613/monad-workspace#165
"""
node File {
    has name: str;
}
node Component {
    has name: str;
}
node Task {
    has name: str;
}
node TestNode {
    has name: str;
}
edge PartOf {}
edge DependsOn {}
edge Covers {}

"""Loader handle: entity names resolve through these lookup maps."""
obj Model {
    has files: dict[str, File];
    has comps: dict[str, Component];
    has tasks: dict[str, Task];
    has tests: dict[str, TestNode];

    def resolve_file(name: str) -> File | None {
        return self.files.get(name);
    }
}

"""Deterministic fresh-graph builder from the {kind: {name: [rels]}} model."""
def load_model(model: dict) -> Model {
    m = Model(files={}, comps={}, tasks={}, tests={});
    comps_map: dict[str, list[str]] = model.get("components", {});
    tasks_map: dict[str, list[str]] = model.get("tasks", {});
    tests_map: dict[str, list[str]] = model.get("tests", {});
    for comp in comps_map.keys() {
        c = Component(name=comp);
        root ++> c;
        m.comps[comp] = c;
    }
    for comp in comps_map.keys() {
        owner = m.comps[comp];
        for fname in comps_map[comp] {
            f = m.resolve_file(fname);
            if f is None {
                f = File(name=fname);
                root ++> f;
                m.files[fname] = f;
            }
            f +>:PartOf:+> owner;
        }
    }
    for task in tasks_map.keys() {
        t = Task(name=task);
        root ++> t;
        m.tasks[task] = t;
        for dep in tasks_map[task] {
            dc = m.comps.get(dep);
            if dc is not None {
                t +>:DependsOn:+> dc;
            }
        }
    }
    for tst in tests_map.keys() {
        e = TestNode(name=tst);
        root ++> e;
        m.tests[tst] = e;
        for covered in tests_map[tst] {
            tk = m.tasks.get(covered);
            if tk is not None {
                e +>:Covers:+> tk;
            }
        }
    }
    return m;
}

"""Ripple walker: file -> components -> depending tasks -> covering tests."""
walker ImpactWalk {
    has claimed: dict[str, bool] = {};
    has comps: list[str] = [];
    has tasks: list[str] = [];
    has tests: list[str] = [];

    can on_file with File entry {
        # Cycle policy: one visit per file regardless of path count.
        if "f:" + here.name in self.claimed {
            skip;
        }
        self.claimed["f:" + here.name] = True;
        visit [->:PartOf:->];
    }

    can on_component with Component entry {
        if "c:" + here.name in self.claimed {
            skip;
        }
        self.claimed["c:" + here.name] = True;
        if here.name not in self.comps {
            self.comps.append(here.name);
        }
        visit [<-:DependsOn:<-];
    }

    can on_task with Task entry {
        if "t:" + here.name in self.claimed {
            skip;
        }
        self.claimed["t:" + here.name] = True;
        if here.name not in self.tasks {
            self.tasks.append(here.name);
        }
        visit [<-:Covers:<-];
    }

    can on_test with TestNode entry {
        if "e:" + here.name in self.claimed {
            skip;
        }
        self.claimed["e:" + here.name] = True;
        if here.name not in self.tests {
            self.tests.append(here.name);
        }
    }
}

"""Changed-file impact analysis: impacted components, tasks, and tests."""
def impacted(model: dict, changed_files: list) -> dict {
    m = load_model(model);
    comps: list[str] = [];
    tasks: list[str] = [];
    tests: list[str] = [];
    for fname in changed_files {
        f = m.resolve_file(fname);
        if f is None {
            continue;  # owned by no component: no impact, like the source
        }
        w = f spawn ImpactWalk(claimed={}, comps=[], tasks=[], tests=[]);
        for c in w.comps {
            if c not in comps {
                comps.append(c);
            }
        }
        for t in w.tasks {
            if t not in tasks {
                tasks.append(t);
            }
        }
        for e in w.tests {
            if e not in tests {
                tests.append(e);
            }
        }
    }
    return {"components": sorted(comps), "tasks": sorted(tasks), "tests": sorted(tests)};
}

"""Recommended verification for a change: tests covering impacted tasks."""
def recommend_tests(model: dict, changed_files: list) -> list {
    return impacted(model, changed_files)["tests"];
}
