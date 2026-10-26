# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "py2osp",
  "fp": "osp__ZanattaMichael__Dsc.PipelineRunner__6__bugcircu",
  "variant": "py2osp",
  "origin_file": "osp_merged_corpus.jsonl",
  "origin_id": "osp__ZanattaMichael__Dsc.PipelineRunner__6__bugcircu",
  "tier": "v21_gold",
  "verification": "check+tests+elimination",
  "n_tokens": 1205,
  "n_answer_tokens": 694
}
```

## SYSTEM

```
You are an expert jac language assistant.
```

## USER

Port this Python module to Jac. Replace the adjacency structures, queues and recursion with nodes, typed edges and walkers. Respond with the Jac code only.

```python
"""ZanattaMichael/Dsc.PipelineRunner#6 — circular-reference detection with backtracking path set."""

from __future__ import annotations


class ConfigStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}


def load_config(entries: list[tuple[str, str]]) -> ConfigStore:
    cfg = ConfigStore()
    for key, raw in entries:
        cfg._values[key] = raw
    return cfg


class CircularReferenceError(ValueError):
    pass


def _resolve_key(cfg: ConfigStore, key: str, path: set[str]) -> str:
    if key not in cfg._values:
        raise KeyError(key)
    if key in path:
        raise CircularReferenceError(f"circular reference involving {key}")
    raw = cfg._values[key]
    if not (raw.startswith("[ref:") and raw.endswith("]")):
        return raw
    target = raw[5:-1]
    path.add(key)
    try:
        out = _resolve_key(cfg, target, path)
    finally:
        path.remove(key)
    return out


def expand_references(cfg: ConfigStore) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in sorted(cfg._values):
        out[key] = _resolve_key(cfg, key, set())
    return out


def reference_chain(cfg: ConfigStore, key: str) -> list[str]:
    if key not in cfg._values:
        return []
    chain = [key]
    path: set[str] = {key}
    raw = cfg._values[key]
    while raw.startswith("[ref:") and raw.endswith("]"):
        nxt = raw[5:-1]
        if nxt in path or nxt not in cfg._values:
            break
        path.add(nxt)
        chain.append(nxt)
        raw = cfg._values[nxt]
    return chain
```

## ASSISTANT

"""ZanattaMichael/Dsc.PipelineRunner#6 — reference resolver (OSP lift)."""

obj ConfigStore { has entries: dict[str, ConfigEntry] = {}; }

node ConfigEntry {
    has key: str;
    has raw: str;
}

edge RefTo {}

class CircularReferenceError(ValueError) {}

def load_config(entries: list[tuple[str, str]]) -> ConfigStore {
    cfg = ConfigStore();
    for (key, raw) in entries {
        e = ConfigEntry(key=key, raw=raw);
        root ++> e;
        cfg.entries[key] = e;
    }
    for e in cfg.entries.values() {
        raw = e.raw;
        if raw.startswith("[ref:") and raw.endswith("]") {
            tgt = raw[5:-1];
            dst = cfg.entries.get(tgt, None);
            if dst is not None { e +>:RefTo:+> dst; }
        }
    }
    return cfg;
}

walker ResolveWalk {
    has path: dict[str, bool] = {};
    has result: str = "";
    has cyclic: bool = False;
    has cycle_key: str = "";

    can step with ConfigEntry entry {
        if here.key in self.path {
            self.cyclic = True;
            self.cycle_key = here.key;
            skip;
        }
        self.path[here.key] = True;
        if not (here.raw.startswith("[ref:") and here.raw.endswith("]")) {
            self.result = here.raw;
            disengage;
        }
        targets = [here ->:RefTo:->][?:ConfigEntry];
        if targets { visit [targets[0]]; }
    }
}

def expand_references(cfg: ConfigStore) -> dict[str, str] {
    out: dict[str, str] = {};
    for key in sorted(cfg.entries.keys()) {
        e = cfg.entries[key];
        w = e spawn ResolveWalk(path={}, result="", cyclic=False, cycle_key="");
        if w.cyclic {
            raise CircularReferenceError(f"circular reference involving {w.cycle_key}");
        }
        out[key] = w.result if w.result else e.raw;
    }
    return out;
}

walker ChainWalk {
    has path: dict[str, bool] = {};
    has chain: list[str] = [];

    can step with ConfigEntry entry {
        if here.key in self.path { skip; }
        self.path[here.key] = True;
        self.chain.append(here.key);
        if not (here.raw.startswith("[ref:") and here.raw.endswith("]")) { disengage; }
        targets = [here ->:RefTo:->][?:ConfigEntry];
        if targets { visit [targets[0]]; }
    }
}

def reference_chain(cfg: ConfigStore, key: str) -> list[str] {
    e = cfg.entries.get(key, None);
    if e is None { return []; }
    w = e spawn ChainWalk(path={}, chain=[]);
    return w.chain;
}
