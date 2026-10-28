"""Count bad tool-use habits in JacHammer prod traces (main agent, each turn's own calls). Prints counts only, no content.
usage: python script/dataset/trajectory/habits.py [trace dir]   (default dataset/raw/prod)"""
import gzip, json, glob, re, sys
from collections import Counter

from clean import (READ_TOOLS, EDIT_TOOLS, RO_CMD, SHELL_WRITE, CACHE_RM, UI_FILE, APP_PATH, PAGE_CURL,
                   STATUS_ONLY, BROWSER_FAIL, LLM_DIRECT, args, text)

# Setting =================================================
IN_DIR         = "dataset/raw/prod"
LOOP_SAME_FILE = re.compile(r"LOOP DETECTED: \w+ called \d+ times on '([^']*)'")


# Functions ===============================================
def read_only(name: str, a: dict) -> bool:
    if name in READ_TOOLS:
        return True
    return name == "run_command" and bool(RO_CMD.match(a.get("command", ""))) and not SHELL_WRITE.search(a.get("command", ""))


def turn_habits(d: dict) -> tuple[Counter, int]:
    """One trace file (one turn) -> (occurrences per habit, number of main-agent tool calls)."""
    main = [c for c in d["calls"] if c["caller"] == "respond" and c["call_kind"] == "react_iteration"]
    seq, res = [], {}
    for k, c in enumerate(main):
        if k:
            for m in c["new_messages"]:
                if m.get("role") == "tool":
                    res[m.get("tool_call_id")] = text(m.get("content"))
        for tc in c["reply"].get("tool_calls") or []:
            seq.append((tc["id"], tc["function"]["name"], args(tc)))
    hit = Counter()
    seen, skills, last_status = {}, Counter(), None
    ui_edited, last_do = False, None
    for i, (cid, name, a) in enumerate(seq):
        key = (name, json.dumps(a, sort_keys=True))
        r = res.get(cid, "")
        if read_only(name, a):
            if key in seen:
                hit["redundant repeat: identical read-only call, no state change since the last one"] += 1
            seen[key] = i
        else:
            seen = {}           # any state-changing call makes earlier observations stale
        if name == "load_jac_skill":
            skills[a.get("name")] += 1
            if skills[a.get("name")] == 2:
                hit["same skill loaded twice in one turn"] += 1
        if name == "preview_status":
            last_status = r.lower()
        if name == "preview_restart" and last_status is not None and "running" in last_status and "fail" not in last_status and "error" not in last_status:
            hit["preview_restart while the last preview_status said running"] += 1
        if name == "read_file" and i and seq[i - 1][1] in ("write_code", "edit_code") and seq[i - 1][2].get("file_path") == a.get("file_path"):
            prev = res.get(seq[i - 1][0], "")
            clean = prev.startswith("OK") and not re.search(r"ERRORS:", prev)
            hit["read_file right after a CLEAN write/edit of the same file" if clean else "read_file right after a write/edit of the same file that reported errors (justified)"] += 1
        cmd = a.get("command", "")
        if name == "run_command" and SHELL_WRITE.search(cmd):
            if CACHE_RM.search(cmd) and not re.search(r"(>\s*[\w./-]+\.(jac|toml)|sed -i|\b(cp|mv)\s)", cmd):
                hit["build cache deleted through the shell (rm -rf .jac/..., node_modules, ...)"] += 1
            else:
                hit["project files changed through the shell (redirect, cp/mv, sed -i, rm -rf) instead of write/edit tools"] += 1
        if name == "run_command" and re.search(r"\bsleep\s+\d", cmd):
            hit["sleep in a shell command"] += 1
        # calls the system prompt forbids in so many words (clean.py M7)
        if "node_modules/@jac" in json.dumps(a):
            hit["@jac/* looked up under node_modules (a build alias, never there)"] += 1
        if any((u := PAGE_CURL.search(seg)) and not APP_PATH.match(u.group(1) or "/") and not STATUS_ONLY.search(seg)
               for seg in re.split(r"[;&|]{1,2}", cmd)):
            hit["curl of the app page or its CSS (prompt: never curl the page)"] += 1
        if name in ("write_code", "edit_code") and LLM_DIRECT.search(str(a.get("content", "")) + str(a.get("new_string", ""))):
            hit["LLM provider API called directly instead of byLLM"] += 1
        if name in ("browser_do", "browser_state") and ui_edited:
            hit["browser_do/state before browser_validate after a UI edit"] += 1
        if name in ("browser_validate", "browser_open", "browser_do", "browser_state"):
            ui_edited = False
        if name in EDIT_TOOLS and UI_FILE.search(str(a.get("file_path", ""))):
            ui_edited = True
        if name in EDIT_TOOLS or name in ("preview_restart", "run_command"):
            last_do = None
        if name == "browser_do":
            sig = json.dumps(a, sort_keys=True)
            if last_do and last_do[0] == sig and BROWSER_FAIL.search(last_do[1][:600]):
                hit["failing browser_do retried unchanged"] += 1
            last_do = (sig, r)
        if name == "edit_code" and r and not r.startswith("OK"):
            hit["edit_code rejected (old_string not found, LOOP DETECTED, BLOCKED, ...)"] += 1
        if name in ("write_code", "edit_code") and r.startswith("OK") and re.search(r"(?i)syntax error|type error|error\[", r):
            hit["write/edit accepted but the inline check reports Jac errors"] += 1
        if "LOOP DETECTED" in r:
            hit["harness LOOP DETECTED"] += 1
            m = LOOP_SAME_FILE.match(r)
            if m and not re.fullmatch(r"[\w.-]+\.\w{1,6}", m.group(1)):
                hit["harness LOOP DETECTED 'same file' naming a fragment, not a file"] += 1
    edits = [i for i, x in enumerate(seq) if x[1] in EDIT_TOOLS]
    if edits and not any(x[1] == "browser_validate" for x in seq[edits[-1] + 1:]):
        hit["turn changed code but never ran browser_validate after the last change"] += 1
    if len(main) >= 100:
        hit["turn hit the 100-call budget"] += 1
    last = [c for c in d["calls"] if c["caller"] == "respond"][-1]
    if last["call_kind"] != "final_answer_restream" and last["reply"].get("tool_calls") and not any(
            t["function"]["name"] == "finish_tool" for t in last["reply"]["tool_calls"]):
        hit["turn ends mid-work (last reply still calls tools)"] += 1
    return hit, len(seq)


# Run =====================================================
if __name__ == "__main__":
    files = sorted(glob.glob(f"{sys.argv[1] if len(sys.argv) > 1 else IN_DIR}/**/*.json.gz", recursive=True))
    T = Counter()     # turns showing the habit
    N = Counter()     # occurrences
    tot_calls = 0
    for f in files:
        hit, n = turn_habits(json.load(gzip.open(f)))
        tot_calls += n
        for k, v in hit.items():
            T[k] += 1
            N[k] += v
    print(f"turns {len(files)}, main-agent tool calls {tot_calls}")
    for k in sorted(T, key=lambda k: -T[k]):
        print(f"  turns {T[k]:4d} ({100 * T[k] / len(files):4.1f}%)  occurrences {N[k]:5d}  {k}")
