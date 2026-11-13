"""JacHammer's own tool-result formatting, for building rows: run with jacBuilder on JACPATH and its pinned jac.

    JACPATH=<jacBuilder> jac run jachammer_tools.jac -- <requests.json> <results.json>

Each request carries the project `root`, and `content` to put in `path` for the call (the file is restored after):
{"op": "check", "msg"} returns what write_code / edit_code append to `msg` (checker sections, fix hints);
{"op": "read", "offset", "limit"} returns what read_file returns.
{"op": "session", "calls": [{"name", "args"}]} runs JacHammer's own tools in order on `root` (files stay changed,
loop-detector state starts empty) and returns the list of their results.
"""

import json;
import os;
import sys;
import from jac_coder.tool.read.filesystem { _quick_parse_check, read_file }
import from jac_coder.util.sandbox { set_sandbox_root }
import from jac_coder.runtime.events { start_turn }
import from jac_coder.runtime.permission { permission_engine }
import from jac_coder.tool.write.checked { write_code, edit_code, delete_code }
import from jac_coder.tool.read.filesystem { list_files }
import from jac_coder.tool.read.search { grep_search, find_files }
import from jac_coder.tool.read.load_jac_skill { load_jac_skill }
import from jac_coder.tool.run.guarded { run_command }

glob TOOLS: dict = {
    "write_code": write_code, "edit_code": edit_code, "delete_code": delete_code, "read_file": read_file,
    "list_files": list_files, "grep_search": grep_search, "find_files": find_files,
    "load_jac_skill": load_jac_skill, "run_command": run_command
};

def run_session(req: dict[str, any]) -> list[str] {
    set_sandbox_root(req["root"]);
    start_turn();    # empty loop-detector history, as at the start of a turn
    return [str(TOOLS[c["name"]](**c["args"])) for c in req["calls"]];
}

def run_one(req: dict[str, any]) -> any {
    if req["op"] == "session" {
        return run_session(req);
    }
    set_sandbox_root(req["root"]);    # tool results name files relative to the project, as in a session
    path = req["path"];
    before: str | None = None;
    if os.path.isfile(path) {
        with open(path, "r", encoding="utf-8") as f {
            before = f.read();
        }
    }
    with open(path, "w", encoding="utf-8") as f {
        f.write(req["content"]);
    }
    if req["op"] == "read" {
        out = read_file(path, req.get("offset", 0), req.get("limit", 2000));
    } else {
        out = _quick_parse_check(path, req["msg"]);
    }
    if before is None {
        os.remove(path);
    } else {
        with open(path, "w", encoding="utf-8") as f {
            f.write(before);
        }
    }
    return out;
}

with entry {
    permission_engine.enable_web_mode();    # what the web agent runs with: writes and commands need no approval
    with open(sys.argv[1], "r", encoding="utf-8") as f {
        reqs = json.load(f);
    }
    outs = [run_one(r) for r in reqs];
    with open(sys.argv[2], "w", encoding="utf-8") as f {
        json.dump(outs, f);
    }
}
