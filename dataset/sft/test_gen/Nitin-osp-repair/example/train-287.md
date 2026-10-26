# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "test_gen",
  "fp": "testfix__osp_C_59__mm3_v7",
  "origin_file": "osp_repair/test_fix.jsonl",
  "origin_id": "testfix__osp_C_59__mm3_v7",
  "verification": "jac_test_pass",
  "n_tokens": 1652,
  "n_answer_tokens": 1157
}
```

## SYSTEM

```
You are a Jac programming assistant in a chat interface. Put all Jac code in your reply inside a ```jac fenced code block.
```

## USER

Write a Jac test annex (`main.test.jac`) for the program below. Use `test "..." { }` blocks that exercise its public behavior. Return the complete file.

```jac
"""Build dependency graph: audit total build minutes, counting each task once even when diamonds cause multiple visits."""

node Task {
    has title: str = "";
    has minutes: int = 0;
}

walker BuildAuditor {
    has audited: dict[str, bool] = {};
    has total: int = 0;
    has order: list[str] = [];

    can start with Root entry {
        visit [-->];
    }

    can audit with Task entry {
        key = here.title;
        if self.audited.get(key, False) {
            visit [-->];
            disengage;
        }
        self.audited[key] = True;
        self.order.append(key);
        self.total += here.minutes;
        print(f"+{here.minutes}min -> {here.title} (running total {self.total}min)");
        visit [-->];
    }
}

with entry {
    # Diamond: utils is needed by both compile and pack, which both feed into ship.
    utils = Task(title="compile_utils", minutes=5);
    compile = Task(title="compile_src", minutes=20);
    pack = Task(title="pack_artifacts", minutes=10);
    ship = Task(title="ship_release", minutes=3);

    # The graph topology is the diamond itself:
    # root -> utils, utils -> compile, utils -> pack, compile -> ship, pack -> ship.
    root ++> utils;
    utils ++> compile;
    utils ++> pack;
    compile ++> ship;
    pack ++> ship;

    auditor = BuildAuditor();
    root spawn auditor;

    print(f"\nAudit order: {auditor.order}");
    print(f"Total build minutes (each task counted once): {auditor.total}min");
}
```

## ASSISTANT

```jac
"""Regression tests for BuildAuditor: total minutes and de-dup behavior across diamond traversals."""

import io;
import from contextlib { redirect_stdout }

# Diamond topology identical to the program under test.
# root -> utils, utils -> compile, utils -> pack, compile -> ship, pack -> ship.
def make_diamond() {
    utils = Task(title="compile_utils", minutes=5);
    compile = Task(title="compile_src", minutes=20);
    pack = Task(title="pack_artifacts", minutes=10);
    ship = Task(title="ship_release", minutes=3);
    root ++> utils;
    utils ++> compile;
    utils ++> pack;
    compile ++> ship;
    pack ++> ship;
    return [utils, compile, pack, ship];
}

test "diamond: total minutes sums each task exactly once" {
    make_diamond();
    auditor = BuildAuditor();
    root spawn auditor;
    # 5 + 20 + 10 + 3 = 38. If diamonds were double-counted, utils (and possibly
    # ship) would inflate this.
    assert auditor.total == 38, f"expected 38 audited minutes, got {auditor.total}";
}

test "diamond: each task appears exactly once in audit order" {
    make_diamond();
    auditor = BuildAuditor();
    root spawn auditor;
    assert len(auditor.order) == 4, f"expected 4 audit entries, got {len(auditor.order)}: {auditor.order}";
    expected = ["compile_utils", "compile_src", "pack_artifacts", "ship_release"];
    assert auditor.order == expected, f"audit order {auditor.order} != {expected}";
}

test "diamond: audited dict marks every visited task true and only those" {
    make_diamond();
    auditor = BuildAuditor();
    root spawn auditor;
    # Every node the walker reached must be flagged; no extras.
    assert set(auditor.audited.keys()) == set(auditor.order), (
        f"audited keys {sorted(auditor.audited.keys())} != order {sorted(auditor.order)}"
    );
    for (k, v) in auditor.audited.items() {
        assert v is True, f"task {k} not marked audited: {v}";
    }
    assert len(auditor.audited) == 4, f"expected 4 audited tasks, got {len(auditor.audited)}";
}

test "diamond: print output contains per-task minute lines and running total" {
    make_diamond();
    buf = io.StringIO();
    auditor = BuildAuditor();
    with redirect_stdout(buf) {
        root spawn auditor;
    }
    out = buf.getvalue();
    # Each unique task must appear with its minute count.
    assert "+5min -> compile_utils" in out, f"missing utils line: {out!r}";
    assert "+20min -> compile_src" in out, f"missing compile line: {out!r}";
    assert "+10min -> pack_artifacts" in out, f"missing pack line: {out!r}";
    assert "+3min -> ship_release" in out, f"missing ship line: {out!r}";
    # No task should be printed twice — that would mean the de-dup guard failed.
    assert out.count("compile_utils") == 1, f"compile_utils logged {out.count('compile_utils')} times";
    assert out.count("compile_src") == 1, f"compile_src logged {out.count('compile_src')} times";
    assert out.count("pack_artifacts") == 1, f"pack_artifacts logged {out.count('pack_artifacts')} times";
    assert out.count("ship_release") == 1, f"ship_release logged {out.count('ship_release')} times";
}

test "diamond: deeper diamond (root -> a -> b,c -> d; b,c both -> d) still de-dups d" {
    # Three parents funnel into one child via a deeper diamond.
    a = Task(title="a", minutes=1);
    b = Task(title="b", minutes=2);
    c = Task(title="c", minutes=4);
    d = Task(title="d", minutes=8);
    root ++> a;
    a ++> b;
    a ++> c;
    b ++> d;
    c ++> d;
    auditor = BuildAuditor();
    root spawn auditor;
    # 1+2+4+8 = 15; naive double-count of d would give 23.
    assert auditor.total == 15, f"expected 15 audited minutes, got {auditor.total}";
    assert auditor.order.count("d") == 1, f"task d audited {auditor.order.count('d')} times";
    assert len(auditor.order) == 4, f"expected 4 entries, got {auditor.order}";
}
```
