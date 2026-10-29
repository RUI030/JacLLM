"""Capture the local JacCoder byLLM request and a small real tool sequence.

Run from jacBuilder with its pinned Jac binary and PYTHONPATH pointing at jacBuilder.
This is an M0 compatibility probe, not a dataset generator.
"""

import json;
import os;
import tempfile;
import from sys { modules }

import from jac_coder.api { initialize }
import from jac_coder.infra.config { set_model }
import from jac_coder.core.nodes { MainAgent, PlannerAgent, Session }
import from jac_coder.tool.meta.delegation { plan_build }
import from jac_coder.tool.read.filesystem { read_file }
import from jac_coder.tool.write.checked { write_code, edit_code }
import from jac_coder.tool.run.guarded { run_command, _set_chat_session, _clear_chat_session }
import from jac_coder.util.sandbox { set_sandbox_root }
import from jaclang.byllm.lib { MockLLM, MockToolCall, StreamEvent }
import from jaclang.byllm.llm { BaseLLM }

glob _requests: list = [];
glob _dispatches: list = [];

def finish_tool(final_output: str) -> str {
    return final_output;
}

def stringify(value: any) -> str {
    return str(value);
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

test "capture" {
    initialize(mode="web");
    set_model("jaccoder-test-invalid/no-such-model");
    ws = tempfile.mkdtemp(prefix="revdev-m0-");
    set_sandbox_root(ws);
    source = "def title() -> str {\n    return \"Tasks\";\n}\n";
    target = os.path.join(ws, "main.jac");
    llm_module = modules[MainAgent.__module__];
    original_llm = llm_module.llm;
    base_module = modules[BaseLLM.__module__];
    original_dispatch = base_module.dispatch_batch;
    base_module.dispatch_batch = record_dispatch(original_dispatch);
    llm_module.llm = CaptureMock(
        model_name="mockllm",
        config={"outputs": [
            MockToolCall(tool=write_code, args={"file_path": target, "content": source}),
            MockToolCall(tool=finish_tool, args={"final_output": "done"}),
            "done"
        ], "verbose": False}
    );
    try {
        for event in MainAgent().respond("Build a small task tracker") {
            if isinstance(event, StreamEvent) { ; }
        }
    } finally {
        llm_module.llm = original_llm;
        base_module.dispatch_batch = original_dispatch;
    }
    results = [
        {"tool": "write_code", "result": write_code(target, source)},
        {"tool": "read_file", "result": read_file(target, 0, 20)},
        {"tool": "edit_code", "result": edit_code(target, "Tasks", "My tasks")},
        {"tool": "run_command", "result": run_command("pwd", ws, 10, False)}
    ];
    plan_path = os.path.join(ws, ".jaccoder", "build_plan.json");
    os.makedirs(os.path.dirname(plan_path), exist_ok=True);
    plan = {"files": [
        {"path": "decl.jac", "status": "todo"},
        {"path": "ellipsis.jac", "status": "todo"},
        {"path": "raise.jac", "status": "todo"}
    ], "write_order": ["decl.jac", "ellipsis.jac", "raise.jac"]};
    results.append({"tool": "write_code", "result": write_code(plan_path, json.dumps(plan))});
    for (name, body) in [
        ("decl.jac", "def title() -> str;\n"),
        ("ellipsis.jac", "def title() -> str { ... }\n"),
        ("raise.jac", "def title() -> str { raise NotImplementedError(); }\n")
    ] {
        results.append({"tool": "write_code", "file": name, "result": write_code(os.path.join(ws, name), body)});
        with open(plan_path, "r", encoding="utf-8") as f {
            results.append({"tool": "plan_status", "file": name, "status": json.load(f)["files"]});
        }
    }
    plan_ws = tempfile.mkdtemp(prefix="revdev-m0-plan-");
    set_sandbox_root(plan_ws);
    session = Session(directory=plan_ws);
    root ++> session;
    _set_chat_session(session.id, "auto");
    planner_module = modules[PlannerAgent.__module__];
    original_planner_llm = planner_module.llm;
    planner_path = os.path.join(plan_ws, ".jaccoder", "build_plan.json");
    planner_module.llm = MockLLM(
        model_name="mockllm",
        config={"outputs": [
            MockToolCall(tool=write_code, args={"file_path": planner_path, "content": json.dumps(plan)}),
            MockToolCall(tool=finish_tool, args={"final_output": "plan written"}),
            "plan written"
        ], "verbose": False}
    );
    try {
        plan_result = plan_build("Build a small task tracker");
        results.append({"tool": "plan_build", "result": plan_result, "plan_exists": os.path.isfile(planner_path)});
    } finally {
        planner_module.llm = original_planner_llm;
        _clear_chat_session();
    }
    with open("/tmp/revdev_m0_capture.json", "w", encoding="utf-8") as f {
        f.write(json.dumps({"workspace": ws, "requests": _requests, "dispatches": _dispatches, "results": results}, default=stringify, indent=2));
    }
    print(json.dumps({"workspace": ws, "requests": len(_requests), "results": results}, default=stringify));
}
