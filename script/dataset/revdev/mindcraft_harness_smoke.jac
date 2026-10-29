"""Isolated Mindcraft-shaped JacCoder tool dispatch probe, not an SFT trajectory.

Run from jacBuilder with its pinned 0.34.27 binary and PYTHONPATH=jacBuilder.
REVDEV_SMOKE_OUT must point to a gitignored or temporary JSON file.
"""

import json;
import os;
import tempfile;
import from sys { modules }

import from jac_coder.api { initialize }
import from jac_coder.infra.config { set_model }
import from jac_coder.core.nodes { MainAgent }
import from jac_coder.tool.read.filesystem { read_file }
import from jac_coder.tool.write.checked { write_code }
import from jac_coder.tool.run.guarded { run_command }
import from jac_coder.util.sandbox { set_sandbox_root }
import from jaclang.byllm.lib { MockLLM, MockToolCall, StreamEvent }
import from jaclang.byllm.llm { BaseLLM }

glob _requests: list = [];
glob _dispatches: list = [];

def finish_tool(final_output: str) -> str {
    return final_output;
}

obj CaptureMock(MockLLM) {
    def make_model_params(mt_run: any) -> dict {
        params = super.make_model_params(mt_run);
        _requests.append({"messages": params.get("messages"), "tools": params.get("tools")});
        return params;
    }
}

def record_dispatch(original: any) -> any {
    def wrapped(tool_calls: list) -> any {
        for (tc, result_msg, took_ms) in original(tool_calls) {
            _dispatches.append({
                "name": str(tc.tool.get_name()),
                "args": dict(tc.args),
                "result": result_msg.to_dict(),
                "took_ms": took_ms
            });
            yield (tc, result_msg, took_ms);
        }
    }
    return wrapped;
}

test "mindcraft harness tool smoke" {
    initialize(mode="web");
    set_model("jaccoder-test-invalid/no-such-model");
    ws = tempfile.mkdtemp(prefix="revdev-mindcraft-harness-");
    set_sandbox_root(ws);
    target = os.path.join(ws, "main.jac");
    source = (
        "node MindIsland { has created_at: str; }\n"
        + "walker:pub get_world {\n"
        + "    can fetch with Root entry { report {\"entities\": []}; }\n"
        + "}\n"
    );
    prompt = "Build a small emotional check-in app with a graph-backed island and a get_world walker. Start with typed Jac scaffolding.";
    llm_module = modules[MainAgent.__module__];
    original_llm = llm_module.llm;
    base_module = modules[BaseLLM.__module__];
    original_dispatch = base_module.dispatch_batch;
    base_module.dispatch_batch = record_dispatch(original_dispatch);
    llm_module.llm = CaptureMock(
        model_name="mockllm",
        config={"outputs": [
            MockToolCall(tool=write_code, args={"file_path": target, "content": source}),
            MockToolCall(tool=finish_tool, args={"final_output": "scaffold written"}),
            "scaffold written"
        ], "verbose": False}
    );
    try {
        for event in MainAgent().respond(prompt) {
            if isinstance(event, StreamEvent) { ; }
        }
    } finally {
        llm_module.llm = original_llm;
        base_module.dispatch_batch = original_dispatch;
    }
    file_text = read_file(target, 0, 20);
    cwd_text = run_command("pwd", ws, 10, False);
    assert os.path.isfile(target);
    assert "MindIsland" in file_text;
    assert cwd_text == ws;
    assert any(x["name"] == "write_code" and "OK: main.jac" in str(x["result"]) for x in _dispatches);
    out = os.environ.get("REVDEV_SMOKE_OUT", "/tmp/revdev_mindcraft_harness_smoke.json");
    os.makedirs(os.path.dirname(out), exist_ok=True);
    with open(out, "w", encoding="utf-8") as f {
        f.write(json.dumps({
            "reference_repo": "Mr-Shockwave/Mindcraft",
            "workspace": ws,
            "prompt": prompt,
            "requests": _requests,
            "dispatches": _dispatches,
            "direct_results": {"read_file": file_text, "run_command": cwd_text}
        }, default=str, indent=2));
    }
    print(json.dumps({"workspace": ws, "requests": len(_requests), "dispatches": [x["name"] for x in _dispatches], "out": out}));
}
