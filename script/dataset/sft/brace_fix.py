"""JacHammer-format SFT rows that restore one missing closing brace: the write or edit that dropped it, the guide
JacHammer asks for after a failed check, then the fix. Every tool result is JacHammer's own on jac 0.34.28."""

import hashlib, json, random, re, shutil, sys, tempfile, uuid
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from utils.classifier import classify_structural as classify
from dataset.pipeline import report
from dataset.parser.jachammer import call, fake_root, result, run_tools, session_parts, turn, user_text

# Setting =================================================
DS_NAME     = "brace_fix_v2"
SOURCE      = "synthetic-brace"
TASK_TYPE   = "jac_fix_brace"
JAC_VERSION = "0.34.28"
ROOT        = Path(__file__).resolve().parents[3]
SPIKE_OUT   = ROOT / "output/spike/1105-teacher-intervention"
TASKS       = ROOT / "script/spike/1105 Teacher Intervention/tasks"
OUT_DIR     = ROOT / f"output/sft/{TASK_TYPE}/{DS_NAME}"   # not under dataset/: moved there once reviewed
N_ROWS      = 40
MIN_LINES   = 12
MAX_LINES   = 400
SKIP_PARTS  = {".jac", "node_modules", "__pycache__", "ui", "docs", "scratch"}
SEED        = 3407


# Functions ===============================================
def workspaces() -> list[Path]:
    """Final workspaces of training episodes; the held-out eval runs (eval-*) are never used."""
    return sorted(p / "workspace" for p in (SPIKE_OUT / "episodes").iterdir()
                  if p.is_dir() and not p.name.startswith("eval-") and (p / "summary.json").is_file())


def jac_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.jac") if not SKIP_PARTS & set(p.relative_to(root).parts[:-1])
                  and MIN_LINES <= len(p.read_text(errors="replace").splitlines()) <= MAX_LINES)


def opener_of(lines: list[str], i: int, slot: bool) -> int | None:
    """Index of the line that opens the block closed at line i: same indent, ends with `{` (a slot starts with `{`)."""
    ind = len(lines[i]) - len(lines[i].lstrip())
    for j in range(i - 1, -1, -1):
        s, jind = lines[j].strip(), len(lines[j]) - len(lines[j].lstrip())
        if s and jind < ind:
            return None
        if s and jind == ind and s.endswith("{") and (s.startswith("{") == slot):
            return j
    return None


def mutations(text: str) -> list[dict]:
    """Each way to drop one closing brace: a `}}` slot end that keeps one `}`, or a `}` line removed."""
    lines, out = text.split("\n"), []
    for i, l in enumerate(lines):
        s = l.strip()
        if s not in ("}", "}}"):
            continue
        j = opener_of(lines, i, s == "}}")
        if j is None:
            continue
        if s == "}}":
            broken = lines[:i] + [l.replace("}}", "}")] + lines[i + 1:]
        else:
            broken = lines[:i] + lines[i + 1:]
        out.append({"kind": "slot" if s == "}}" else "block", "line": i, "opener": j,
                    "opener_text": lines[j].strip(), "broken": "\n".join(broken)})
    return out


def snippet(text: str, around: int, before: int = 2, after: int = 0) -> str:
    """Lines around index `around`, grown upward (then downward, at the top of the file) until they occur once."""
    lines = text.split("\n")
    while True:
        a, b = max(0, around - before), min(len(lines), around + after + 1)
        s = "\n".join(lines[a:b])
        if text.count(s) == 1 or (a == 0 and b == len(lines)):
            return s
        before, after = (before + 1, after) if a > 0 else (before, after + 1)


def first_error_line(check: str) -> int | None:
    m = re.search(r", line (\d+), col \d+:", check)
    return int(m.group(1)) if m else None


def fix_words(m: dict, rel: str, rng: random.Random) -> tuple[str, str]:
    """(visible content, short reasoning) for the restoring edit, from the facts of this break."""
    o, y = m["opener"] + 1, m["line"] + 1
    if m["kind"] == "slot":
        why = rng.choice([
            f"The `{m['opener_text']}` slot opened at line {o} is closed with a single `}}` at line {y}. A JSX statement "
            "slot needs `}}`: one brace ends the block, the other leaves the slot.",
            f"Line {y} ends the slot from line {o} (`{m['opener_text']}`) with `}}` only, so the JSX after it is parsed "
            "as part of the slot. It needs `}}`.",
            f"The slot opened at line {o} never closes: line {y} has `}}` where the slot needs `}}}}`, so the "
            "parser reads on past it."])
        say = rng.choice([f"The slot opened at line {o} is missing its second closing brace; restoring `}}}}` at line {y}.",
                          f"Line {y} closes the `{m['opener_text']}` slot with one brace instead of two. Fixing it."])
    else:
        why = rng.choice([
            f"`{m['opener_text']}` at line {o} has no matching `}}`, so everything after it is parsed inside that block "
            "and the parser runs out at the end of the file.",
            f"The block opened at line {o} (`{m['opener_text']}`) is never closed; the closing brace belongs after "
            f"line {y - 1}.",
            f"A missing `}}`: the `{m['opener_text']}` block from line {o} runs to the end of {rel}."])
        say = rng.choice([f"The block opened at line {o} is missing its closing brace; adding it after line {y - 1}.",
                          f"`{m['opener_text']}` (line {o}) was never closed. Adding the `}}`."])
    return say, why


def skill_for(original: str) -> tuple[str, str]:
    """The guide to load after the failed check, and what it shows that matters here."""
    if "JsxElement" in original:
        return "jac-cl-components", "how JSX blocks and `{...}` statement slots close"
    return "jac-core-cheatsheet", "that every block is `{ }`-braced"


def plan_calls(c: dict) -> list[tuple[str, dict, int]]:
    """(tool, args, weight) of the row, on the candidate's real project path: earlier lookups and the write or edit
    that dropped the brace (context), then the guide, the read and the fix (trained)."""
    path = str(c["path"])
    out = [(n, a, 0) for n, a in c["context"]]
    if c["origin"] == "write":
        out.append(("write_code", {"file_path": path, "content": c["mut"]["broken"]}, 0))
    else:
        out.append(("edit_code", {"file_path": path, "old_string": c["edit_old"], "new_string": c["edit_new"],
                                  "replace_all": False}, 0))
    out.append(("load_jac_skill", {"name": skill_for(c["original"])[0]}, 1))
    if c["read"]:
        out.append(("read_file", {"file_path": path, "offset": 0, "limit": 2000}, 1))
    out.append(("edit_code", {"file_path": path, "old_string": c["fix_old"], "new_string": c["fix_new"],
                              "replace_all": False}, 1))
    return out


def build_row(c: dict, sys_prompt: str, wrapper: str, project: str, tools: list[dict], rng: random.Random) -> dict:
    """One row: context turns (weight 0) that end in the write or edit that dropped the brace, then the trained
    guide load, read and fix. Tool results are the ones JacHammer's tools returned on the candidate's project."""
    fake = fake_root()
    rel, m = c["rel"], c["mut"]
    msgs = [{"role": "system", "content": sys_prompt},
            {"role": "user", "content": [{"type": "text", "text": user_text(wrapper, project, fake, c["request"])}]}]
    broken_check = c["results"][len(c["context"])]
    err = first_error_line(broken_check) or 0
    first = re.search(r", line \d+, col \d+: (.+)", broken_check).group(1)
    skill, what = skill_for(c["original"])
    at_end = err >= len(m["broken"].rstrip("\n").split("\n")) - 2
    for (name, args, w), res in zip(plan_calls(c), c["results"]):
        args = json.loads(json.dumps(args).replace(c["tmp_root"], fake))
        say, why = "", ""
        if name in ("write_code", "edit_code") and not w:
            say = rng.choice([f"Writing {rel}.", f"Now {rel}.", ""]) if name == "write_code" else \
                rng.choice([f"Updating {rel}.", ""])
        elif name == "load_jac_skill":
            where = (f"The errors pile up at line {err}, the end of {rel}" if at_end else
                     f"The errors start at line {err} with \"{first}\"")
            why = rng.choice([
                f"The check failed, and JacHammer asks for the relevant guide before a fix. {where}: a block opened "
                f"earlier never closes. {skill} shows {what}.",
                f"\"{first}\" at line {err}" + (", then more of the same to the end of the file" if at_end else "")
                + f": an unclosed block. Loading {skill} first, as the check asks; it shows {what}."])
        elif name == "read_file" and w:
            why = rng.choice([
                f"The errors only say where the parser gave up, line {err}. I need the numbered lines to find which "
                "block is open.",
                "Reading the file to find the block that never closes.",
                f"Line {err} is past the code itself. Reading {rel} to find where the brace went missing." if at_end else
                f"Line {err} is where the parser noticed, not where the brace went missing. Reading {rel}."])
        elif w:
            say, why = fix_words(m, rel, rng)
        k = call(name, args)
        msgs += [turn(say, why, k, w), result(k, res.replace(c["tmp_root"], fake))]
    fp = hashlib.sha1((c["episode"] + rel + m["broken"]).encode()).hexdigest()[:16]
    return {"messages": msgs, "tools": json.dumps(tools),
            "meta": {"source": SOURCE, "format": "trajectory", "class": classify(c["original"]), "task_type": TASK_TYPE,
                     "fp": fp, "jac_version": JAC_VERSION, "data_version": DS_NAME, "episode": c["episode"],
                     "file": rel, "file_lines": len(c["original"].splitlines()), "kind": m["kind"],
                     "origin": c["origin"], "read": c["read"], "skill": skill, "context_turns": len(c["context"])}}


def collect(tmp: Path, rng: random.Random) -> list[dict]:
    """Copy each training workspace under tmp, keep files JacHammer's check passes, and their brace mutations whose
    broken form fails that check. Returns candidates with every tool result filled in."""
    files = []
    for ws in workspaces():
        dst = tmp / f"prj_{uuid.uuid4().hex}"
        shutil.copytree(ws, dst, ignore=shutil.ignore_patterns(".jac", "node_modules", "__pycache__"))
        for p in jac_files(dst):
            files.append((ws.parent.name, dst, p))
    ok = run_tools([{"op": "check", "root": str(r), "path": str(p), "content": p.read_text(), "msg": "OK"}
                 for _, r, p in files])
    cands = []
    for (ep, r, p), res in zip(files, ok):
        if res != "OK":
            continue
        text = p.read_text()
        muts = mutations(text)
        by_kind = [[m for m in muts if m["kind"] == k] for k in ("slot", "block")]
        for m in [rng.choice(ms) for ms in by_kind if ms]:          # one of each kind a file has: slots are rarer
            cands.append({"episode": ep, "tmp_root": str(r), "root": r, "path": p, "rel": str(p.relative_to(r)),
                          "original": text, "mut": m})
    reqs = []
    for c in cands:
        name, m = c["path"].name, c["mut"]
        c["origin"] = "write" if rng.random() < 0.7 else "edit"
        n = len(m["broken"].splitlines())
        reqs.append({"op": "check", "root": c["tmp_root"], "path": str(c["path"]), "content": m["broken"],
                     "msg": f"OK: {name} ({n} lines)" if c["origin"] == "write" else f"OK: {name} (1 edit)"})
    for c, res in zip(cands, run_tools(reqs)):
        c["broken_check"] = res
    return [c for c in cands if "SYNTAX ERRORS" in c["broken_check"]]


def finish(cands: list[dict], rng: random.Random) -> list[dict]:
    """Pick N_ROWS spread over kind, file size and origin, run each row's calls with JacHammer's tools, and keep the
    ones whose results show the failed check and a clean fix (a write JacHammer blocks as an anti-pattern is dropped)."""
    size = lambda c: 0 if len(c["original"].splitlines()) < 60 else 1 if len(c["original"].splitlines()) < 150 else 2
    rng.shuffle(cands)
    picked, used, per = [], set(), Counter()
    want = N_ROWS + N_ROWS // 2                       # spares for rows the real tools reject
    for c in sorted(cands, key=lambda c: (per[(c["mut"]["kind"], size(c))], rng.random())):
        key = (c["mut"]["kind"], size(c))
        if (c["episode"], c["rel"]) in used or per[key] >= -(-want // 6):
            continue
        picked.append(c); used.add((c["episode"], c["rel"])); per[key] += 1
        if len(picked) == want:
            break
    for c in cands:                                   # groups with too few candidates leave room for the others
        if len(picked) == want:
            break
        if (c["episode"], c["rel"]) not in used:
            picked.append(c); used.add((c["episode"], c["rel"]))
    for i, c in enumerate(picked):                    # each row gets its own copy: a rejected session leaves files changed
        own = c["root"].parent / f"prj_{uuid.uuid4().hex}"
        shutil.copytree(c["root"], own)
        c["root"], c["tmp_root"], c["path"] = own, str(own), own / c["rel"]
    for c in picked:
        m = c["mut"]
        broken, orig = m["broken"], c["original"]
        bl = broken.split("\n")
        at = m["line"] if m["kind"] == "slot" else m["line"] - 1        # the line the fix touches in the broken file
        c["fix_old"] = snippet(broken, at, before=2)
        cut = c["fix_old"].rindex(bl[at])                              # the touched line ends the snippet
        c["fix_new"] = c["fix_old"][:cut] + bl[at].replace("}", "}}", 1) + c["fix_old"][cut + len(bl[at]):] \
            if m["kind"] == "slot" else c["fix_old"] + "\n" + orig.split("\n")[m["line"]]
        assert broken.replace(c["fix_old"], c["fix_new"], 1) == orig, (c["rel"], m["kind"])
        if c["origin"] == "edit":
            c["edit_new"] = snippet(broken, at, before=rng.randint(3, 6), after=rng.randint(1, 3))
            a = broken.index(c["edit_new"])
            c["edit_old"] = orig[a:a + len(c["edit_new"]) + (len(orig) - len(broken))]
            assert orig.replace(c["edit_old"], c["edit_new"], 1) == broken and orig.count(c["edit_old"]) == 1
        err = first_error_line(c["broken_check"]) or 0
        c["read"] = c["origin"] == "edit" or abs(err - (at + 1)) > 8 or len(bl) > 120 or rng.random() < 0.3
        others = [p for p in jac_files(c["root"]) if p != c["path"]]
        c["context"] = []
        if rng.random() < 0.6:
            c["context"].append(("list_files", {"directory": c["tmp_root"], "pattern": "**/*.jac"}))
            for p in rng.sample(others, min(len(others), rng.choice([0, 1, 2, 3]))):
                c["context"].append(("read_file", {"file_path": str(p), "offset": 0, "limit": 2000}))
    outs = run_tools([{"op": "session", "root": c["tmp_root"],
                       "calls": [{"name": n, "args": a} for n, a, _ in plan_calls(c)]} for c in picked])
    kept = []
    for c, res in zip(picked, outs):
        c["results"] = res
        broke, fixed = res[len(c["context"])], res[-1]
        if "SYNTAX ERRORS" not in broke or not fixed.startswith(f"OK: {c['path'].name} (1 edit)") or "ERRORS" in fixed:
            continue                                  # e.g. BLOCKED: anti-pattern, or a check that still fails
        if c["path"].read_text() != c["original"]:
            continue                                  # the write tool auto-fixed the content: the row would not match
        kept.append(c)
    print(f"{len(kept)} of {len(picked)} picked rows survive the real tools")
    return kept[:N_ROWS]


def brace_fix(out_dir: Path = OUT_DIR) -> None:
    rng = random.Random(SEED)
    sys_prompt, wrapper, project, tools = session_parts()
    with tempfile.TemporaryDirectory(prefix="brace-ws-") as d:
        cands = collect(Path(d), rng)
        print(f"{len(cands)} candidates that fail JacHammer's check")
        for c in cands:
            task = json.loads((SPIKE_OUT / "episodes" / c["episode"] / "summary.json").read_text())["task"]
            c["request"] = json.loads((TASKS / f"{task.removesuffix('_v1')}.json").read_text())["request"]
        rows = [build_row(c, sys_prompt, wrapper, project, tools, rng) for c in finish(cands, rng)]
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "train.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    report({"train": len(rows)}, out_dir)
    print(Counter((r["meta"]["kind"], r["meta"]["origin"], r["meta"]["read"], r["meta"]["skill"]) for r in rows))


# Run =====================================================
if __name__ == "__main__":
    brace_fix()
