"""Execute one validated adapter request through the actual JacCoder tools."""
import json;
import os;
import re;
import hashlib;
import from jaclang.jac0core.program { JacProgram }
import jaclang.jac0core.unitree as uni;
import from jac_coder.api { initialize }
import from jac_coder.util.sandbox { set_sandbox_root }
import from jac_coder.tool.read.filesystem { read_file }
import from jac_coder.tool.read.load_jac_skill { load_jac_skill }
import from jac_coder.tool.write.checked { write_code, edit_code }
import from jac_coder.tool.run.guarded { run_command }

with entry {
    pinned = os.environ.get("REVDEV_JAC", "/tmp/jac-0.34.27-linux-x86_64");
    bin_dir = "/tmp/revdev-jac-bin-" + hashlib.sha256(pinned.encode()).hexdigest()[:12];
    os.makedirs(bin_dir, exist_ok=True);
    if not os.path.lexists(os.path.join(bin_dir, "jac")) {
        os.symlink(pinned, os.path.join(bin_dir, "jac"));
    }
    os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"];
    initialize(mode="web");
    with open(os.environ["REVDEV_CALL"], "r") as f { call = json.load(f); }
    set_sandbox_root(call["workspace"]);
    os.chdir(call["workspace"]);
    registry = {"read_file": read_file, "write_code": write_code,
                "edit_code": edit_code, "run_command": run_command,
                "load_jac_skill": load_jac_skill};
    rejection = "";
    if call.get("phase") == "scaffold" and call["name"] == "write_code" and call["args"]["file_path"].endswith(".jac") {
        mod = JacProgram().parse_str(call["args"]["content"], call["args"]["file_path"]);
        for ability in mod.get_all_sub_nodes(uni.Ability) {
            body = ability.body;
            if body is None or not isinstance(body, list) { continue; }  # `by llm` body is a call, not statements
            text = "".join([stmt.unparse() for stmt in body]);
            compact = re.sub(r"\s+", "", text);
            if compact != "raiseNotImplementedError();" and not (compact.startswith("return<") and compact.endswith(";")) {
                rejection = "Scaffold phase: every function/ability body must be only raise NotImplementedError(); (UI entry may return a minimal JSX placeholder). Complete all planned files before implementing bodies.";
            }
        }
    }
    result = registry[call["name"]](**call["args"]) if not rejection else rejection;
    with open(os.environ["REVDEV_RESULT"], "w") as f {
        json.dump({"name": call["name"], "content": result, "executed": not bool(rejection),
                   "origin": "adapter_phase_guard" if rejection else "jaccoder",
                   "runtime_binary": pinned,
                   "adapter_notice": "run_command resolves jac to the target binary recorded in runtime_binary."}, f);
    }
}
