"""JacHammer-format SFT rows that break out of a tool-call loop: the same failing call repeated (weight 0), then a short
diagnosis and a different call (trained), then the rest of the fix. The loops are the ones JacLLM-1107 fell into on
JacHammer (docs/JACHAMMER_ROUTING_BASELINE.md); every tool result, LOOP DETECTED included, is JacHammer's own."""

import hashlib, json, random, re, sys, tempfile
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from utils.classifier import classify_structural as classify
from dataset.pipeline import report
from dataset.parser.jachammer import session_parts
from dataset.parser.jachammer_apps import DOMAINS, TASKS, app, expand, fix_steps, names
from dataset.sft.router_params import build_row, run_jobs, template

# Setting =================================================
DS_NAME     = "loop_break_v1"
SOURCE      = "synthetic-loop"
TASK_TYPE   = "jac_loop_break"
JAC_VERSION = "0.34.28"
ROOT        = Path(__file__).resolve().parents[3]
OUT_DIR     = ROOT / f"output/sft/{TASK_TYPE}/{DS_NAME}"     # not under dataset/: moved there once reviewed
# loop kind -> the tasks whose fix steps have the call the loop needs
KINDS = {
    # two misses leave both in the detector's window, so a 2nd later edit of that file would make 4 and be blocked
    "edit_miss_2":     ["literal_param", "missing_import"],
    "edit_miss_3":     ["add_detail", "literal_param", "links_reload", "missing_import", "catch_all", "stay_on_form"],
    "compiled_read":   ["add_detail", "literal_param", "first_item", "links_reload", "stay_on_form"],
    "missing_journal": list(TASKS),
    "ls_repeat":       ["add_detail", "literal_param", "first_item", "links_reload", "stay_on_form"],
    "jsx_return":      ["add_detail", "literal_param", "first_item", "catch_all"],
}
SEED        = 3407


# Functions ===============================================
def rel_of(c: dict) -> str:
    return c["args"]["file_path"].removeprefix("@ROOT@/")


def miss(old: str) -> str:
    """An old_string the model might type that the file does not contain: single quotes, or no spaces inside braces.
    (Less indentation would not do: it is still a substring of the indented line.)"""
    if '"' in old:
        return old.replace('"', "'")
    return old.replace("{ ", "{").replace(" }", "}")


def no_return(text: str) -> str:
    """The 0.36 habit: JSX as a bare tail expression, no `return`, no `;` after the closing tag."""
    return re.sub(r"(\n *)return <", r"\1<", text).replace("</div>;\n", "</div>\n")


def edit_miss(calls: list[dict], k: int, rng) -> tuple[list[dict], int]:
    i = next(j for j, c in enumerate(calls) if c["name"] == "edit_code")
    good = calls[i]
    bad = {**good, "args": {**good["args"], "old_string": miss(good["args"]["old_string"])}}
    tries = [{**bad, "why": good["why"], "weight": 0}] + [{**bad, "why": "Trying the edit again.", "weight": 0}] * (k - 1)
    flagged = " and JacHammer has flagged the loop" if k == 3 else ""
    quoted = '"' in good["args"]["old_string"]
    read = {"name": "read_file", "args": {"file_path": good["args"]["file_path"], "offset": 0, "limit": 2000},
            "why": rng.choice([f"edit_code failed {k} times with the same old_string{flagged}. Sending it again "
                               "cannot work: what I typed is not in the file. Reading the file to copy the exact text.",
                               f"Same \"old_string not found\" {k} times{flagged}. I have been guessing the text instead "
                               f"of reading it; reading {rel_of(good)}."])}
    fixed = {**good, "why": ("The file uses double quotes; my old_string had single quotes. " if quoted else
                             "The file writes `{ Name }` with spaces inside the braces; mine had none. ")
                            + "Using its exact text. " + good["why"]}
    return calls[:i] + tries + [read, fixed] + calls[i + 1:], i + k


def compiled_read(calls: list[dict], d: dict, rng) -> tuple[list[dict], int]:
    i = next(j for j, c in enumerate(calls) if c["name"] == "read_file" and rel_of(c).startswith("components/"))
    good, comp = calls[i], Path(rel_of(calls[i])).stem
    js = {"name": "read_file", "args": {"file_path": f"@ROOT@/.jac/client/compiled/components/{comp}.js", "offset": 0,
                                        "limit": 2000}}
    tries = [{**js, "why": f"Looking at what {comp} compiles to.", "weight": 0},
             {**js, "why": "Reading the compiled file again.", "weight": 0}]
    src = {**good, "why": rng.choice([f"Both reads were refused, and the same call gets the same refusal. The compiled "
                                      f"JS says nothing the source doesn't; the source is {rel_of(good)}. ",
                                      f"Refused twice: compiled output is not readable here. Reading {rel_of(good)} "
                                      "instead. "]) + good["why"]}
    return calls[:i] + tries + [src] + calls[i + 1:], i + 2


def missing_journal(calls: list[dict], rng) -> tuple[list[dict], int]:
    j = {"name": "read_file", "args": {"file_path": "@ROOT@/.jaccoder/agent_journal.md", "offset": 0, "limit": 2000}}
    tries = [{**j, "why": "Checking the agent journal for earlier notes.", "weight": 0},
             {**j, "why": "Reading the journal.", "weight": 0}]
    first = {**calls[0], "why": rng.choice(["There is no journal for this project, and asking again returns the same "
                                            "error. Going on without it. ",
                                            "File not found twice: no journal exists yet. Nothing to read there; moving "
                                            "on. "]) + calls[0]["why"]}
    return tries + [first] + calls[1:], 2


def ls_repeat(calls: list[dict], rng) -> tuple[list[dict], int]:
    i = next(j for j, c in enumerate(calls) if c["name"] == "read_file" and rel_of(c).startswith("components/"))
    ls = {"name": "run_command", "args": {"command": "ls components", "workdir": "@ROOT@", "timeout": 60,
                                          "background": False}}
    tries = [{**ls, "why": "Listing the components.", "weight": 0}] + [{**ls, "why": "Listing them again.", "weight": 0}] * 2
    good = calls[i]
    nxt = {**good, "why": rng.choice([f"I ran the same ls three times and got the same listing; JacHammer flagged it. "
                                      f"The listing already has {Path(rel_of(good)).name}. ",
                                      f"Three identical listings, then LOOP DETECTED. Listing again tells me nothing "
                                      f"new; the file I need, {Path(rel_of(good)).name}, is right there. "]) + good["why"]}
    return calls[:i] + tries + [nxt] + calls[i + 1:], i + 3


def jsx_return(calls: list[dict], k: int) -> tuple[list[dict], int]:
    """The same broken write k times (the 3rd is refused with LOOP DETECTED), then the guide JacHammer asks for, then
    the fix: k=2 by edit_code, since a 3rd write_code of the file would be refused; k=3 by one rewrite. The trained
    reasonings are filled in by jsx_whys from the real check output."""
    i = next(j for j, c in enumerate(calls) if c["name"] == "write_code" and rel_of(c).startswith("components/"))
    good = calls[i]
    broken = no_return(good["args"]["content"])
    assert broken != good["args"]["content"]
    tries = [{**good, "args": {**good["args"], "content": broken}, "weight": 0},
             {**good, "args": {**good["args"], "content": broken}, "why": "Writing the file again.", "weight": 0}]
    if k == 3:
        tries.append({**good, "args": {**good["args"], "content": broken.replace("text-2xl", "text-3xl", 1)},
                      "why": "Changing the heading and writing it once more.", "weight": 0})
    skill = {"name": "load_jac_skill", "args": {"name": "jac-cl-components"}, "why": "", "jsx": "skill"}
    if k == 3:
        return calls[:i] + tries + [skill, {**good, "why": "", "jsx": "fix"}] + calls[i + 1:], i + 3
    # one edit from the first JSX block to the last: fixing them one at a time leaves the file failing in between
    text = good["args"]["content"]
    blocks = list(re.finditer(r"(?m)^( *)return <div[\s\S]*?\n\1</div>;", text))
    span = text[blocks[0].start():blocks[-1].end()]
    old = no_return("\n" + span + "\n")[1:-1]
    assert broken.count(old) == 1
    fix = {"name": "edit_code", "args": {"file_path": good["args"]["file_path"], "old_string": old, "new_string": span,
                                        "replace_all": False}, "why": "", "jsx": "fix"}
    return calls[:i] + tries + [skill, fix] + calls[i + 1:], i + 2


def jsx_whys(s: dict, rng) -> None:
    """Reasonings for the skill load and the fix, from what the check actually reported."""
    at = next(j for j, c in enumerate(s["calls"]) if c["weight"])
    check = s["results"][at - s["loop_n"]]
    seen = ("the parser stops at '<' where a JSX block starts" if "Unexpected token in expression: '<'" in check else
            "the check says the function may implicitly return None")
    asked = " JacHammer asks for the relevant guide before another attempt." if "ACTION REQUIRED" in check else ""
    if s["flagged"]:
        head = "Three writes, the same errors each time, and now LOOP DETECTED."
    else:
        head = rng.choice(["Writing the file again gave exactly the same errors, so the rewrite changed nothing that "
                           "matters.", "Same errors, same lines, twice."])
    skill_why = (f"{head}{asked} The fix hint about a `component` keyword does not apply; there is none in the file. "
                 "Checking how the components guide writes a component.")
    how = ("one rewrite with all of them" if s["flagged"] else
           "a third write_code of this file would be refused, so one edit_code over all the JSX blocks")
    fix_why = (f"Every component in the guide ends with `return <...>;`. That is what is missing here: {seen}, because "
               f"in jac 0.34 a JSX expression standing alone is not returned. Each JSX block needs `return` and the "
               f"closing `;`: {how}.")
    for c in s["calls"]:
        if c.get("jsx") == "skill":
            c["why"] = skill_why
        elif c.get("jsx") == "fix":
            c["why"] = fix_why


def inject(kind: str, calls: list[dict], d: dict, rng) -> tuple[list[dict], int, bool]:
    """(the fix calls with the loop put in, how many calls the loop has, whether the detector fires on its last).
    Calls before the trained break-out are weight 0, the rest weight 1."""
    if kind.startswith("edit_miss"):
        k = int(kind[-1])
        out, at = edit_miss(calls, k, rng)
    elif kind == "compiled_read":
        (out, at), k = compiled_read(calls, d, rng), 2
    elif kind == "missing_journal":
        (out, at), k = missing_journal(calls, rng), 2
    elif kind == "ls_repeat":
        (out, at), k = ls_repeat(calls, rng), 3
    else:
        k = rng.choice([2, 3])
        out, at = jsx_return(calls, k)
    return [{**c, "weight": 0 if j < at else 1} for j, c in enumerate(out)], k, k == 3


def check_loops(s: dict) -> None:
    """The results show the loop the row claims: the same failure each time, LOOP DETECTED where the detector fires,
    and no failure after the break-out."""
    at = next(j for j, c in enumerate(s["calls"]) if c["weight"])
    loop, kind = s["results"][at - s["loop_n"]:at], s["kind"]
    first = {"edit_miss_2": "Error: old_string not found", "edit_miss_3": "Error: old_string not found",
             "missing_journal": "Error: File not found", "ls_repeat": "", "compiled_read": "Error: ",
             "jsx_return": "OK: "}[kind]
    assert all(r.startswith(first) for r in loop[:2]), (kind, loop)
    if kind == "jsx_return":
        assert all("SYNTAX ERRORS" in r for r in loop[:2]), loop
    assert loop[-1].startswith("LOOP DETECTED") == s["flagged"], (kind, loop[-1][:200])
    assert not any("ERRORS" in r or r.startswith(("Error", "LOOP")) for r in s["results"][at:]), (kind, s["results"][at:])


def loop_break(out_dir: Path = OUT_DIR) -> None:
    rng = random.Random(SEED)
    sys_prompt, wrapper, project, tools = session_parts()
    specs = []
    for kind, tasks in KINDS.items():
        for n, d in enumerate(DOMAINS):
            ok = [t for t in tasks if t != "stay_on_form" or d["form"]]
            task = ok[n % len(ok)]                                # rotate tasks over domains
            start, request = TASKS[task](d)
            final = app(d)
            calls, k, flagged = inject(kind, expand(fix_steps(d, task, rng), start, final), d, rng)
            specs.append({"domain": d, "task": task, "kind": kind, "start": start, "final": final,
                          "request": request, "calls": calls, "loop_n": k, "flagged": flagged})
    with tempfile.TemporaryDirectory(prefix="loop-ws-") as t:
        base = template(Path(t))
        specs = run_jobs(base, Path(t), specs)
        for s in specs:
            check_loops(s)
            if s["kind"] == "jsx_return":
                jsx_whys(s, rng)
        rows = []
        for s in specs:
            r = build_row(s, sys_prompt, wrapper, project, tools)
            r["meta"].update({"source": SOURCE, "task_type": TASK_TYPE, "data_version": DS_NAME, "loop": s["kind"],
                              "fp": hashlib.sha1(f"{DS_NAME}/{s['domain']['key']}/{s['task']}/{s['kind']}".encode()).hexdigest()[:16]})
            rows.append(r)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "train.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    report({"train": len(rows)}, out_dir)
    print(Counter((r["meta"]["loop"], r["meta"]["task"]) for r in rows))


# Run =====================================================
if __name__ == "__main__":
    loop_break()
