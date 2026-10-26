# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "test_gen",
  "fp": "testfix__iss_jendrikseipp__vulture__431",
  "origin_file": "osp_repair/test_fix.jsonl",
  "origin_id": "testfix__iss_jendrikseipp__vulture__431",
  "verification": "jac_test_pass",
  "n_tokens": 2972,
  "n_answer_tokens": 1751
}
```

## SYSTEM

```
You are a helpful assistant.
```

## USER

Given the Jac program below, write a passing `jac test` suite for it. Output only the test file.

```jac
"""Blast-radius CI: model a corpus of repositories, run vulture twice over them
(baseline vs PR), and diff the findings via a walker that traverses the
typed corpus → repo → finding graph.

The hand-rolled machinery this replaces:
  * id-keyed dicts of repos and findings,
  * recursive walks over a corpus → repos tree to gather findings,
  * set arithmetic on finding hashes to compute appeared / disappeared /
    changed / unanalyzed sets (the "blast radius").
Idiomatic Jac lifts the corpus → repos → findings hierarchy into typed edges
and lets a walker perform the diff in a single typed traversal, preserving
the diff semantics as the report payload on the walker.
"""

# ---------- entity archetypes ----------

node Finding {
    has file_path: str = "";
    has line: int = 0;
    has kind: str = "";
    has message: str = "";
    has confidence: float = 0.0;

    def fingerprint() -> str {
        return f"{self.file_path}:{self.line}:{self.kind}";
    }
}

node Repo {
    has name: str = "";
    has commit_pin: str = "";
}

node Corpus {
    has label: str = "";
}

# ---------- relationship archetypes ----------

edge ContainsRepo { }     # Corpus → Repo
edge HasFinding { }      # Repo → Finding

# ---------- walker: performs the blast-radius diff ----------

walker BlastRadius {
    has findings: list = [];

    can start with Root entry {
        visit [-->];
    }

    can walk with Corpus entry {
        visit [->:ContainsRepo:->];
    }

    can gather with Repo entry {
        visit [->:HasFinding:->];
    }

    can record with Finding entry {
        self.findings.append(here.fingerprint());
    }
}

# ---------- demo graph + traversal ----------

with entry {
    corpus = Corpus(label="vulture-corpus");

    # Baseline repo set: skynet is clean, redundant_utils has a real finding.
    repo_a = Repo(name="skynet", commit_pin="v0.4");
    repo_b = Repo(name="redundant_utils", commit_pin="v0.4");

    # PR repo set: skynet unchanged; redundant_utils gains a new finding
    # and loses the old one (the exact regression-then-fix scenario).
    repo_c = Repo(name="redundant_utils", commit_pin="pr-431");

    corpus +>:ContainsRepo:+> repo_a;
    corpus +>:ContainsRepo:+> repo_b;
    corpus +>:ContainsRepo:+> repo_c;

    repo_a +>:HasFinding:+> Finding(
        file_path="skynet/agent.py", line=42, kind="unused",
        message="variable 'foo' is unused", confidence=0.9
    );

    repo_b +>:HasFinding:+> Finding(
        file_path="redundant_utils/helpers.py", line=17, kind="unused-attr",
        message="attribute 'bar' is unused", confidence=0.85
    );

    repo_c +>:HasFinding:+> Finding(
        file_path="redundant_utils/helpers.py", line=93, kind="unused-import",
        message="import 'baz' is unused", confidence=0.95
    );

    walker_baseline = BlastRadius();
    walker_pr = BlastRadius();
    corpus spawn walker_baseline;
    corpus spawn walker_pr;

    print(f"baseline findings gathered: {walker_baseline.findings}");
    print(f"pr findings gathered:       {walker_pr.findings}");

    # Compute the diff off the typed walker's accumulated state and report.
    base_set: list = [];
    for f in walker_baseline.findings {
        already = False;
        for g in base_set {
            if g == f {
                already = True;
                break;
            }
        }
        if not already {
            base_set.append(f);
        }
    }
    pr_set: list = [];
    for f in walker_pr.findings {
        already = False;
        for g in pr_set {
            if g == f {
                already = True;
                break;
            }
        }
        if not already {
            pr_set.append(f);
        }
    }

    appeared: list = [];
    for f in pr_set {
        in_base = False;
        for g in base_set {
            if g == f {
                in_base = True;
                break;
            }
        }
        if not in_base {
            appeared.append(f);
        }
    }
    disappeared: list = [];
    for f in base_set {
        in_pr = False;
        for g in pr_set {
            if g == f {
                in_pr = True;
                break;
            }
        }
        if not in_pr {
            disappeared.append(f);
        }
    }

    print(f"appeared:    {appeared}");
    print(f"disappeared: {disappeared}");
}
```

## ASSISTANT

"""Tests for the blast-radius CI demo: typed Corpus→Repo→Finding traversal,
duplicate-finding dedupe, and the appeared/disappeared diff semantics."""

import io;
import from contextlib { redirect_stdout }

# ---------- helpers ----------

def run_walker(corpus: Corpus) -> list {
    buf = io.StringIO();
    res = None;
    with redirect_stdout(buf) {
        res = corpus spawn BlastRadius();
    }
    return res.findings;
}

def dedupe(items: list) -> list {
    seen: list = [];
    for x in items {
        already = False;
        for s in seen {
            if s == x {
                already = True;
                break;
            }
        }
        if not already {
            seen.append(x);
        }
    }
    return seen;
}

def diff(base: list, pr: list) -> tuple {
    base_set = dedupe(base);
    pr_set = dedupe(pr);
    appeared: list = [];
    for f in pr_set {
        in_base = False;
        for g in base_set {
            if g == f {
                in_base = True;
                break;
            }
        }
        if not in_base {
            appeared.append(f);
        }
    }
    disappeared: list = [];
    for f in base_set {
        in_pr = False;
        for g in pr_set {
            if g == f {
                in_pr = True;
                break;
            }
        }
        if not in_pr {
            disappeared.append(f);
        }
    }
    return (appeared, disappeared);
}

# ---------- tests ----------

test "appeared and disappeared sets reproduce the regression-then-fix blast radius" {
    `root = Root();
    base_corpus = Corpus(label="baseline");
    pr_corpus   = Corpus(label="pr-431");
    `root ++> base_corpus;
    `root ++> pr_corpus;

    # baseline: skynet (clean), redundant_utils@v0.4 with one finding
    base_a = Repo(name="skynet", commit_pin="v0.4");
    base_b = Repo(name="redundant_utils", commit_pin="v0.4");
    base_corpus +>:ContainsRepo:+> base_a;
    base_corpus +>:ContainsRepo:+> base_b;

    base_b +>:HasFinding:+> Finding(
        file_path="redundant_utils/helpers.py", line=17, kind="unused-attr",
        message="attribute 'bar' is unused", confidence=0.85
    );

    # PR: skynet unchanged; redundant_utils@pr-431 with a new finding
    pr_a = Repo(name="skynet", commit_pin="v0.4");
    pr_b = Repo(name="redundant_utils", commit_pin="pr-431");
    pr_corpus +>:ContainsRepo:+> pr_a;
    pr_corpus +>:ContainsRepo:+> pr_b;

    pr_b +>:HasFinding:+> Finding(
        file_path="redundant_utils/helpers.py", line=93, kind="unused-import",
        message="import 'baz' is unused", confidence=0.95
    );

    base_findings = run_walker(base_corpus);
    pr_findings   = run_walker(pr_corpus);

    (appeared, disappeared) = diff(base_findings, pr_findings);

    expected_disappeared = "redundant_utils/helpers.py:17:unused-attr";
    expected_appeared    = "redundant_utils/helpers.py:93:unused-import";

    assert expected_disappeared in disappeared, f"expected disappeared to contain {expected_disappeared}, got {disappeared}";
    assert expected_appeared    in appeared,    f"expected appeared to contain {expected_appeared}, got {appeared}";
    assert len(appeared) == 1,    f"expected exactly 1 appeared, got {appeared}";
    assert len(disappeared) == 1, f"expected exactly 1 disappeared, got {disappeared}";
}

test "duplicate findings on the same repo are deduped by the diff" {
    `root = Root();
    corpus = Corpus(label="dedup");
    `root ++> corpus;

    repo = Repo(name="dup_repo", commit_pin="v0.4");
    corpus +>:ContainsRepo:+> repo;

    # Same fingerprint attached 3 times — must collapse to one.
    repo +>:HasFinding:+> Finding(
        file_path="dup_repo/a.py", line=1, kind="unused",
        message="x unused", confidence=0.9
    );
    repo +>:HasFinding:+> Finding(
        file_path="dup_repo/a.py", line=1, kind="unused",
        message="x unused", confidence=0.9
    );
    repo +>:HasFinding:+> Finding(
        file_path="dup_repo/a.py", line=1, kind="unused",
        message="x unused", confidence=0.9
    );

    findings = run_walker(corpus);
    deduped  = dedupe(findings);

    assert len(findings) == 3, f"walker should record every edge, got {findings}";
    assert len(deduped)  == 1, f"diff should collapse duplicates, got {deduped}";
    assert deduped[0] == "dup_repo/a.py:1:unused", f"got {deduped[0]}";
}

test "empty corpus yields no findings and an empty blast radius" {
    `root = Root();
    corpus = Corpus(label="empty");
    `root ++> corpus;

    findings = run_walker(corpus);
    (appeared, disappeared) = diff(findings, findings);

    assert findings == [], f"expected no findings, got {findings}";
    assert appeared == [],    f"expected empty appeared, got {appeared}";
    assert disappeared == [], f"expected empty disappeared, got {disappeared}";
}

test "walker only gathers findings reachable via ContainsRepo then HasFinding" {
    `root = Root();
    corpus = Corpus(label="reach");
    `root ++> corpus;

    # A repo NOT connected via ContainsRepo — its finding must not be reached.
    orphan_repo = Repo(name="orphan", commit_pin="v0.4");
    orphan_repo +>:HasFinding:+> Finding(
        file_path="orphan/x.py", line=1, kind="unused",
        message="must not appear", confidence=0.9
    );

    # A properly connected repo + finding.
    live_repo = Repo(name="live", commit_pin="v0.4");
    corpus +>:ContainsRepo:+> live_repo;
    live_repo +>:HasFinding:+> Finding(
        file_path="live/y.py", line=5, kind="unused-import",
        message="import 'z' is unused", confidence=0.9
    );

    findings = run_walker(corpus);

    assert "live/y.py:5:unused-import" in findings, f"live finding missing in {findings}";
    assert "orphan/x.py:1:unused" not in findings, f"orphan finding leaked into walk: {findings}";
    assert len(findings) == 1, f"expected exactly 1 finding, got {findings}";

    # ContainRepo / HasFinding edge counts as a sanity check on graph shape.
    repo_edges = [corpus ->:ContainsRepo:->];
    assert len(repo_edges) == 1, f"expected 1 ContainsRepo edge, got {repo_edges}";
}
