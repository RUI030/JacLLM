# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "test_gen",
  "fp": "testfix__osp_A_08__mm3_v37",
  "origin_file": "osp_repair/test_fix.jsonl",
  "origin_id": "testfix__osp_A_08__mm3_v37",
  "verification": "jac_test_pass",
  "n_tokens": 1358,
  "n_answer_tokens": 1027
}
```

## SYSTEM

```
You are an expert AI assistant specializing in the jac programming language.
```

## USER

Write Jac tests for this program. Build any graph state inside each test and assert on the observable behavior. Respond with the test code only.

```jac
"""Quiz grader walker: collects integer scores from quiz nodes and reports the class average."""

node Quiz {
    has student: str = "";
    has score: int = 0;
}

walker Grader {
    has scores: list[int] = [];
    has report: int = 0;

    can start with Root entry {
        visit [-->];
    }

    can grade with Quiz entry {
        self.scores.append(here.score);
        print(f"{here.student}: {here.score}");
        visit [-->];
    }
}

with entry {
    root ++> Quiz(student="Alice", score=88)
        ++> Quiz(student="Bob", score=72)
        ++> Quiz(student="Carla", score=95)
        ++> Quiz(student="Diego", score=60);

    grader = Grader() spawn root;
    total = sum(grader.scores);
    count = len(grader.scores);
    grader.report = total // count if count > 0 else 0;
    print(f"Collected scores: {grader.scores}");
    print(f"Class average: {grader.report}");
}
```

## ASSISTANT

"""Tests for the quiz grader walker."""

import io;
import from contextlib { redirect_stdout }

test "grader collects integer scores and computes average" {
    root ++> Quiz(student="Alice", score=88)
        ++> Quiz(student="Bob", score=72)
        ++> Quiz(student="Carla", score=95)
        ++> Quiz(student="Diego", score=60);

    buf = io.StringIO();
    with redirect_stdout(buf) {
        grader = Grader() spawn root;
        total = sum(grader.scores);
        count = len(grader.scores);
        grader.report = total // count if count > 0 else 0;
        print(f"Collected scores: {grader.scores}");
        print(f"Class average: {grader.report}");
    }
    out = buf.getvalue();

    assert len(grader.scores) == 4, f"expected 4 scores, got {len(grader.scores)}";
    assert all(isinstance(s, int) for s in grader.scores), f"non-int in scores: {grader.scores}";
    assert isinstance(grader.report, int), f"report must be int, got {type(grader.report)}";
    assert grader.report == (88 + 72 + 95 + 60) // 4, f"expected average 78, got {grader.report}";

    assert "Alice: 88" in out, f"missing Alice line: {out}";
    assert "Bob: 72" in out, f"missing Bob line: {out}";
    assert "Carla: 95" in out, f"missing Carla line: {out}";
    assert "Diego: 60" in out, f"missing Diego line: {out}";
    assert "Collected scores:" in out, f"missing collected scores line: {out}";
    assert "Class average: 78" in out, f"missing/invalid average line: {out}";
}

test "grader works with single quiz" {
    root ++> Quiz(student="Solo", score=100);

    grader = Grader() spawn root;

    assert len(grader.scores) == 1, f"expected 1 score, got {len(grader.scores)}";
    assert grader.scores[0] == 100, f"expected 100, got {grader.scores[0]}";
    assert isinstance(grader.report, int), f"report must be int, got {type(grader.report)}";
}

test "grader walks and visits connected quizzes" {
    root ++> Quiz(student="A", score=50)
        ++> Quiz(student="B", score=70)
        ++> Quiz(student="C", score=90);

    buf = io.StringIO();
    with redirect_stdout(buf) {
        grader = Grader() spawn root;
    }
    out = buf.getvalue();

    assert len(grader.scores) == 3, f"expected 3 scores after walk, got {len(grader.scores)}";
    assert "A: 50" in out, f"missing A: {out}";
    assert "B: 70" in out, f"missing B: {out}";
    assert "C: 90" in out, f"missing C: {out}";
}

test "grader reports integer average with no decimals" {
    root ++> Quiz(student="X", score=10)
        ++> Quiz(student="Y", score=20)
        ++> Quiz(student="Z", score=31);

    buf = io.StringIO();
    with redirect_stdout(buf) {
        grader = Grader() spawn root;
        total = sum(grader.scores);
        count = len(grader.scores);
        grader.report = total // count if count > 0 else 0;
        print(f"Class average: {grader.report}");
    }
    out = buf.getvalue();

    assert isinstance(grader.report, int), f"report must be int, got {type(grader.report)}";
    assert grader.report == (10 + 20 + 31) // 3, f"expected 20, got {grader.report}";
    assert "Class average: 20" in out, f"missing integer average: {out}";
}
