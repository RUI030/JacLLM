# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "py2osp",
  "fp": "osp__duonghai258-beep__DT.BK_New__10__finalarc",
  "variant": "py2osp",
  "origin_file": "osp_merged_corpus.jsonl",
  "origin_id": "osp__duonghai258-beep__DT.BK_New__10__finalarc",
  "tier": "v21_gold",
  "verification": "check+tests+elimination",
  "n_tokens": 1436,
  "n_answer_tokens": 799
}
```

## SYSTEM

```
You are an expert jac language assistant.
```

## USER

Port this Python module to Jac. Replace the adjacency structures, queues and recursion with nodes, typed edges and walkers. Respond with the Jac code only.

```python
"""duonghai258-beep/DT.BK_New#10 — Architecture layer dependency audit."""

from __future__ import annotations


class ArchGraph:
    def __init__(self) -> None:
        self._layers: set[str] = set()
        self._depends: dict[str, list[str]] = {}
        self._layer_rank: dict[str, int] = {}


def load_arch_graph(
    layers: list[str],
    ranks: dict[str, int],
    deps: list[tuple[str, str]],
) -> ArchGraph:
    g = ArchGraph()
    for layer in layers:
        g._layers.add(layer)
        g._depends.setdefault(layer, [])
    g._layer_rank = dict(ranks)
    for src, dst in deps:
        if src in g._layers and dst in g._layers:
            g._depends.setdefault(src, []).append(dst)
    return g


def detect_cycles(graph: ArchGraph) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    visited: set[str] = set()
    stack: set[str] = set()

    def dfs(node: str) -> None:
        visited.add(node)
        stack.add(node)
        for nxt in graph._depends.get(node, []):
            if nxt in stack:
                errors.append((node, nxt))
            elif nxt not in visited:
                dfs(nxt)
        stack.remove(node)

    for layer in sorted(graph._layers):
        if layer not in visited:
            dfs(layer)
    return sorted(errors)


def reverse_layer_violations(graph: ArchGraph) -> list[tuple[str, str]]:
    bad: list[tuple[str, str]] = []
    for src in sorted(graph._layers):
        src_rank = graph._layer_rank.get(src, 0)
        for dst in graph._depends.get(src, []):
            dst_rank = graph._layer_rank.get(dst, 0)
            if src_rank < dst_rank:
                bad.append((src, dst))
    return sorted(bad)


def upstream_closure(graph: ArchGraph, layer: str) -> list[str]:
    if layer not in graph._layers:
        return []
    seen: set[str] = {layer}
    stack = [layer]
    while stack:
        cur = stack.pop()
        for nxt in graph._depends.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return sorted(seen)
```

## ASSISTANT

"""duonghai258-beep/DT.BK_New#10 — Architecture layer dependency audit."""

node LayerNode {
    has name: str;
    has rank: int = 0;
}

edge DependsOn {}

obj ArchGraph {
    has layers: dict[str, LayerNode] = {};
}

walker CycleProbe {
    has visited: dict[str, bool] = {};
    has stack: dict[str, bool] = {};
    has errors: list[tuple[str, str]] = [];

    can step with LayerNode entry {
        if here.name in self.visited { skip; }
        self.visited[here.name] = True;
        self.stack[here.name] = True;
        for nxt in [here ->:DependsOn:->][?:LayerNode] {
            if nxt.name in self.stack {
                self.errors.append((here.name, nxt.name));
            } else {
                if not (nxt.name in self.visited) { visit [nxt]; }
            }
        }
        self.stack[here.name] = False;
    }
}

walker UpstreamWalk {
    has claimed: dict[str, bool] = {};
    has reached: list[str] = [];

    can step with LayerNode entry {
        if here.name in self.claimed { skip; }
        self.claimed[here.name] = True;
        self.reached.append(here.name);
        visit [->:DependsOn:->][?:LayerNode];
    }
}

def load_arch_graph(
    layers: list[str],
    ranks: dict[str, int],
    deps: list[tuple[str, str]],
) -> ArchGraph {
    g = ArchGraph();
    for layer in layers {
        r = ranks.get(layer, 0);
        nd = LayerNode(name=layer, rank=r);
        root ++> nd;
        g.layers[layer] = nd;
    }
    for (src, dst) in deps {
        s = g.layers.get(src, None);
        d = g.layers.get(dst, None);
        if s is not None and d is not None { s +>:DependsOn:+> d; }
    }
    return g;
}

def detect_cycles(graph: ArchGraph) -> list[tuple[str, str]] {
    errors: list[tuple[str, str]] = [];
    visited: dict[str, bool] = {};
    for k in sorted(graph.layers.keys()) {
        if k in visited { continue; }
        nd = graph.layers[k];
        w = nd spawn CycleProbe(visited=visited, stack={}, errors=[]);
        errors = errors + w.errors;
        visited = w.visited;
    }
    return sorted(errors);
}

def reverse_layer_violations(graph: ArchGraph) -> list[tuple[str, str]] {
    bad: list[tuple[str, str]] = [];
    for k in sorted(graph.layers.keys()) {
        src = graph.layers[k];
        for dst in [src ->:DependsOn:->][?:LayerNode] {
            if src.rank < dst.rank { bad.append((src.name, dst.name)); }
        }
    }
    return sorted(bad);
}

def upstream_closure(graph: ArchGraph, layer: str) -> list[str] {
    nd = graph.layers.get(layer, None);
    if nd is None { return []; }
    w = nd spawn UpstreamWalk(claimed={}, reached=[]);
    return sorted(w.reached);
}
