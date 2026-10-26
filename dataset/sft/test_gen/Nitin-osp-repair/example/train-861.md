# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "test_gen",
  "fp": "testfix__osp_A_02__composer_v16",
  "origin_file": "osp_repair/test_fix.jsonl",
  "origin_id": "testfix__osp_A_02__composer_v16",
  "verification": "jac_test_pass",
  "n_tokens": 1200,
  "n_answer_tokens": 865
}
```

## SYSTEM

```
You are a helpful assistant.
```

## USER

Given the Jac program below, write a passing `jac test` suite for it. Output only the test file.

```jac
"""Hiking trail: chain waypoints from trailhead to summit; a hiker walker counts each stop."""

node TrailStop {
    has label: str = "";
}

node TrailHead(TrailStop) {
    has label: str = "Trailhead";
}

node Waypoint(TrailStop) {
}

node Summit(TrailStop) {
    has label: str = "Summit";
}

walker Hiker {
    has stop_count: int = 0;

    can start with Root entry {
        visit [-->];
    }

    can hike with TrailHead | Waypoint | Summit entry {
        self.stop_count += 1;
        marker = here.label if here.label else "waypoint";
        print(f"Stop {self.stop_count}: {marker}");
        visit [-->] else {
            print(f"Trail complete — passed {self.stop_count} stops.");
            disengage;
        }
    }
}

with entry {
    root ++> TrailHead()
        ++> Waypoint()
        ++> Waypoint()
        ++> Waypoint()
        ++> Summit();
    root spawn Hiker();
}
```

## ASSISTANT

"""Test annex for hiking trail program."""

import io;
import from contextlib { redirect_stdout }

test "hiker prints each stop with incrementing count" {
    root ++> TrailHead()
        ++> Waypoint()
        ++> Waypoint()
        ++> Summit();

    buf = io.StringIO();
    with redirect_stdout(buf) {
        res = root spawn Hiker();
    }
    out = buf.getvalue();

    assert "Stop 1: Trailhead" in out, f"expected stop 1 trailhead, got: {out}";
    assert "Stop 2: waypoint" in out, f"expected stop 2 unlabeled waypoint, got: {out}";
    assert "Stop 3: waypoint" in out, f"expected stop 3 unlabeled waypoint, got: {out}";
    assert "Stop 4: Summit" in out, f"expected stop 4 summit, got: {out}";
}

test "hiker counts exactly the number of trail stops" {
    root ++> TrailHead()
        ++> Waypoint()
        ++> Waypoint()
        ++> Waypoint()
        ++> Summit();

    buf = io.StringIO();
    with redirect_stdout(buf) {
        res = root spawn Hiker();
    }
    out = buf.getvalue();

    assert res.stop_count == 5, f"expected 5 stops counted, got {res.stop_count}";
    assert "Trail complete — passed 5 stops." in out, f"missing completion line: {out}";
}

test "hiker uses default label when waypoint label is empty" {
    root ++> TrailHead()
        ++> Waypoint()
        ++> Summit();

    buf = io.StringIO();
    with redirect_stdout(buf) {
        res = root spawn Hiker();
    }
    out = buf.getvalue();

    assert "Stop 2: waypoint" in out, f"expected default 'waypoint' label for unlabeled waypoint, got: {out}";
    assert "Trail complete — passed 3 stops." in out, f"missing completion line: {out}";
}

test "hiker disengages when there are no outgoing edges" {
    root ++> TrailHead()
        ++> Summit();

    buf = io.StringIO();
    with redirect_stdout(buf) {
        res = root spawn Hiker();
    }
    out = buf.getvalue();

    assert "Stop 1: Trailhead" in out, f"expected trailhead stop, got: {out}";
    assert "Stop 2: Summit" in out, f"expected summit stop, got: {out}";
    assert "Trail complete — passed 2 stops." in out, f"expected completion at summit, got: {out}";
}

test "hiker traverses chain in order and visits every linked node" {
    root ++> TrailHead()
        ++> Waypoint()
        ++> Waypoint()
        ++> Summit();

    buf = io.StringIO();
    with redirect_stdout(buf) {
        res = root spawn Hiker();
    }
    out = buf.getvalue();

    lines = [l for l in out.split("\n") if l];
    stop_lines = [l for l in lines if l.startswith("Stop ")];

    assert len(stop_lines) == 4, f"expected 4 stop lines, got {len(stop_lines)}: {stop_lines}";
    assert stop_lines[0] == "Stop 1: Trailhead", f"first stop wrong: {stop_lines[0]}";
    assert stop_lines[-1] == "Stop 4: Summit", f"last stop wrong: {stop_lines[-1]}";
    assert "Trail complete — passed 4 stops." in out, f"missing completion line: {out}";
}
