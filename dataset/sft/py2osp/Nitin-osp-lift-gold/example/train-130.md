# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "py2osp",
  "fp": "osp__grandchallenge__QUANTUM-TECHNOLOGIES__114__qtrc90ex",
  "variant": "py2osp",
  "origin_file": "osp_merged_corpus.jsonl",
  "origin_id": "osp__grandchallenge__QUANTUM-TECHNOLOGIES__114__qtrc90ex",
  "tier": "v21_gold",
  "verification": "check+tests+elimination",
  "n_tokens": 1706,
  "n_answer_tokens": 923
}
```

## SYSTEM

```
You are a helpful assistant.
```

## USER

Port this Python module to Jac. Replace the adjacency structures, queues and recursion with nodes, typed edges and walkers. Respond with the Jac code only.

```python
"""grandchallenge/QUANTUM-TECHNOLOGIES#114 — decoder pipeline stage ordering."""

from __future__ import annotations

from collections import deque


class CycleError(Exception):
    pass


class DecoderPipeline:
    def __init__(self) -> None:
        self._stages: set[str] = set()
        self._requires: dict[str, list[str]] = {}


def load_decoder_dag(
    stage_names: list[str],
    require_edges: list[tuple[str, str]],
) -> DecoderPipeline:
    pipe = DecoderPipeline()
    for stage in stage_names:
        pipe._stages.add(stage)
        pipe._requires.setdefault(stage, [])
    for upstream, downstream in require_edges:
        if upstream in pipe._stages and downstream in pipe._stages:
            pipe._requires.setdefault(downstream, []).append(upstream)
    return pipe


def execution_order(pipe: DecoderPipeline) -> list[str]:
    indegree: dict[str, int] = {s: 0 for s in pipe._stages}
    rev: dict[str, list[str]] = {s: [] for s in pipe._stages}
    for stage, reqs in pipe._requires.items():
        for _ in reqs:
            indegree[stage] += 1
        for up in reqs:
            rev[up].append(stage)
    order: list[str] = []
    ready = sorted(s for s, d in indegree.items() if d == 0)
    visited: set[str] = set()
    while ready:
        node = ready.pop(0)
        if node in visited:
            continue
        visited.add(node)
        order.append(node)
        for other in rev.get(node, []):
            indegree[other] -= 1
            if indegree[other] == 0 and other not in visited:
                ready.append(other)
        ready = sorted(ready)
    if len(visited) != len(pipe._stages):
        raise CycleError("stage dependency cycle")
    return order


def stage_reachable(pipe: DecoderPipeline, root: str) -> list[str]:
    if root not in pipe._stages:
        return []
    rev: dict[str, list[str]] = {s: [] for s in pipe._stages}
    for stage, reqs in pipe._requires.items():
        for up in reqs:
            rev[up].append(stage)
    seen: set[str] = set()
    queue: deque[str] = deque([root])
    while queue:
        cur = queue.popleft()
        for nxt in rev.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return sorted(seen)


def compile_validate_decode_order(pipe: DecoderPipeline) -> list[str]:
    order = execution_order(pipe)
    phases = ["compile", "validate", "decode"]
    out: list[str] = []
    for phase in phases:
        if phase in order:
            out.append(phase)
    for stage in order:
        if stage not in out:
            out.append(stage)
    return out
```

## ASSISTANT

"""grandchallenge/QUANTUM-TECHNOLOGIES#114 — decoder pipeline stage ordering."""

class CycleError(Exception) {}

node Stage {
    has name: str;
}

edge Requires {}

obj DecoderPipeline {
    has stages: dict[str, Stage] = {};
}

walker DownstreamReach {
    has claimed: dict[str, bool] = {};
    has reached: list[str] = [];

    can step with Stage entry {
        if here.name in self.claimed { skip; }
        self.claimed[here.name] = True;
        self.reached.append(here.name);
        visit [<-:Requires:<-][?:Stage];
    }
}

def load_decoder_dag(
    stage_names: list[str],
    require_edges: list[tuple[str, str]],
) -> DecoderPipeline {
    pipe = DecoderPipeline();
    for stage in stage_names {
        nd = Stage(name=stage);
        root ++> nd;
        pipe.stages[stage] = nd;
    }
    for (upstream, downstream) in require_edges {
        u = pipe.stages.get(upstream, None);
        d = pipe.stages.get(downstream, None);
        if u is not None and d is not None { d +>:Requires:+> u; }
    }
    return pipe;
}

def execution_order(pipe: DecoderPipeline) -> list[str] {
    indegree: dict[str, int] = {};
    rev: dict[str, list[str]] = {};
    for sid in pipe.stages {
        indegree[sid] = 0;
        rev[sid] = [];
    }
    for sid in pipe.stages {
        nd = pipe.stages[sid];
        for up in [nd ->:Requires:->][?:Stage] {
            indegree[sid] += 1;
            rev[up.name].append(sid);
        }
    }
    order: list[str] = [];
    visited: dict[str, bool] = {};
    ready: dict[str, bool] = {};
    for sid in pipe.stages {
        if indegree[sid] == 0 { ready[sid] = True; }
    }
    while len(ready) > 0 {
        keys = sorted([s for s in ready.keys()]);
        stage_id = keys[0];
        next_ready: dict[str, bool] = {};
        for k in keys[1:] { next_ready[k] = True; }
        ready = next_ready;
        if stage_id in visited { continue; }
        visited[stage_id] = True;
        order.append(stage_id);
        for other in rev.get(stage_id, []) {
            indegree[other] -= 1;
            if indegree[other] == 0 and not (other in visited) {
                ready[other] = True;
            }
        }
    }
    if len(visited) != len(pipe.stages) {
        raise CycleError("stage dependency cycle");
    }
    return order;
}

def stage_reachable(pipe: DecoderPipeline, `root: str) -> list[str] {
    nd = pipe.stages.get(`root, None);
    if nd is None { return []; }
    w = nd spawn DownstreamReach(claimed={}, reached=[]);
    out: list[str] = [];
    for s in w.reached {
        if s != `root { out.append(s); }
    }
    return sorted(out);
}

def compile_validate_decode_order(pipe: DecoderPipeline) -> list[str] {
    order = execution_order(pipe);
    phases = ["compile", "validate", "decode"];
    out: list[str] = [];
    for phase in phases {
        if phase in order { out.append(phase); }
    }
    for stage in order {
        dup = False;
        for x in out {
            if x == stage { dup = True; }
        }
        if not dup { out.append(stage); }
    }
    return out;
}
