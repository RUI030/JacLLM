"""Scripted M3 prefix probe: real JacCoder plan/write/read results, not model SFT.

REVDEV_M3_TASK, REVDEV_M3_PLAN and REVDEV_M3_OUT point to private/local files.
The mock emits the grounded planning target and two scaffold writes so the
tool path, plan status and checkpoint can be exercised without an API key.
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
import from jac_coder.tool.write.checked { write_code }
import from jac_coder.tool.run.guarded { _set_chat_session, _clear_chat_session }
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
                "name": str(tc.tool.get_name()), "args": dict(tc.args),
                "result": result_msg.to_dict(), "took_ms": took_ms
            });
            yield (tc, result_msg, took_ms);
        }
    }
    return wrapped;
}

test "mindcraft M3 scripted prefix" {
    initialize(mode="web");
    set_model("jaccoder-test-invalid/no-such-model");
    with open(os.environ["REVDEV_M3_TASK"], "r", encoding="utf-8") as f {
        task = json.load(f);
    }
    with open(os.environ["REVDEV_M3_PLAN"], "r", encoding="utf-8") as f {
        plan = json.load(f);
    }
    ws = tempfile.mkdtemp(prefix="revdev-mindcraft-m3-");
    set_sandbox_root(ws);
    session = Session(directory=ws);
    root ++> session;
    _set_chat_session(session.id, "auto");
    plan_path = os.path.join(ws, ".jaccoder", "build_plan.json");
    config_path = os.path.join(ws, "jac.toml");
    service_path = os.path.join(ws, "services", "island.jac");
    config_source = (
        "[project]\nname = \"mindcraft-core\"\nversion = \"0.1.0\"\n"
        + "entry-point = \"main.jac\"\nkind = \"web-app\"\n"
        + "[serve]\nbase_route_app = \"app\"\n"
    );
    service_source = (
        "node MindIsland { has created_at: str; }\n"
        + "node EmotionalEntity { has description: str; has stage: str = \"pending\"; }\n"
        + "node InteractionEvent { has tool_id: str; }\n"
        + "node ValueAction { has text: str; }\n"
        + "edge Contains {}\n"
        + "walker:pub get_world { can fetch with Root entry { raise NotImplementedError(); } }\n"
        + "walker:pub manifest_emotion { has feeling_text: str; can manifest with Root entry { raise NotImplementedError(); } }\n"
        + "walker:pub place_entity { has entity_id: str; has x: float; has y: float; can place with Root entry { raise NotImplementedError(); } }\n"
        + "walker:pub apply_interaction { has entity_id: str; has tool_id: str; can apply with Root entry { raise NotImplementedError(); } }\n"
        + "walker:pub commit_value_action { has entity_id: str; has action_text: str; can commit with Root entry { raise NotImplementedError(); } }\n"
        + "walker:pub get_act_path { has entity_id: str; can trace with Root entry { raise NotImplementedError(); } }\n"
        + "walker:pub reset_demo { can reset with Root entry { raise NotImplementedError(); } }\n"
    );
    base_module = modules[BaseLLM.__module__];
    original_dispatch = base_module.dispatch_batch;
    base_module.dispatch_batch = record_dispatch(original_dispatch);
    planner_module = modules[PlannerAgent.__module__];
    original_planner_llm = planner_module.llm;
    main_module = modules[MainAgent.__module__];
    original_main_llm = main_module.llm;
    try {
        planner_module.llm = CaptureMock(
            model_name="mockllm",
            config={"outputs": [
                MockToolCall(tool=write_code, args={"file_path": plan_path, "content": json.dumps(plan)}),
                MockToolCall(tool=finish_tool, args={"final_output": "plan written"}),
                "plan written"
            ], "verbose": False}
        );
        planner_result = plan_build(task["request"]);
        main_module.llm = CaptureMock(
            model_name="mockllm",
            config={"outputs": [
                MockToolCall(tool=write_code, args={"file_path": config_path, "content": config_source}),
                MockToolCall(tool=write_code, args={"file_path": service_path, "content": service_source}),
                MockToolCall(tool=finish_tool, args={"final_output": "scaffold prefix written"}),
                "scaffold prefix written"
            ], "verbose": False}
        );
        for event in MainAgent().respond(task["request"]) {
            if isinstance(event, StreamEvent) { ; }
        }
    } finally {
        planner_module.llm = original_planner_llm;
        main_module.llm = original_main_llm;
        base_module.dispatch_batch = original_dispatch;
        _clear_chat_session();
    }
    plan_result = read_file(plan_path, 0, 30);
    service_result = read_file(service_path, 0, 30);
    with open(plan_path, "r", encoding="utf-8") as f {
        live_plan = json.load(f);
    }
    assert os.path.isfile(config_path) and os.path.isfile(service_path);
    assert "MindIsland" in service_result;
    assert live_plan["write_order"] == plan["write_order"];
    assert len([d for d in _dispatches if d["name"] == "write_code"]) == 3;
    assert "plan written" in str(planner_result);
    out = os.environ["REVDEV_M3_OUT"];
    os.makedirs(os.path.dirname(out), exist_ok=True);
    with open(out, "w", encoding="utf-8") as f {
        f.write(json.dumps({
            "mode": "scripted_mockllm_prefix_not_sft", "workspace": ws,
            "request": task["request"], "planner_result": planner_result,
            "requests": _requests, "dispatches": _dispatches,
            "observations": {"plan": plan_result, "service": service_result},
            "live_plan": live_plan
        }, default=str, indent=2));
    }
    print(json.dumps({"workspace": ws, "dispatches": [d["name"] for d in _dispatches], "out": out}));
}
