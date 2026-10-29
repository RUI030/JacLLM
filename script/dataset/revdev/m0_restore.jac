"""Second-process checkpoint probe for the M0 disposable workspace."""

import json;
import os;
import from jac_coder.api { initialize }
import from jac_coder.tool.read.filesystem { read_file }
import from jac_coder.tool.run.guarded { run_command }
import from jac_coder.util.sandbox { set_sandbox_root }

test "restore" {
    initialize(mode="web");
    ws = "/tmp/revdev_m0_restored";
    set_sandbox_root(ws);
    result = {
        "read_file": read_file(os.path.join(ws, "main.jac"), 0, 20),
        "run_command": run_command("pwd", ws, 10, False)
    };
    with open(os.path.join(ws, ".jaccoder", "build_plan.json"), "r", encoding="utf-8") as f {
        result["plan"] = json.load(f);
    }
    assert "My tasks" in result["read_file"];
    assert result["run_command"] == ws;
    with open("/tmp/revdev_m0_restore.json", "w", encoding="utf-8") as f {
        f.write(json.dumps(result, indent=2));
    }
}
