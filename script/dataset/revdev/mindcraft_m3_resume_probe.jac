"""Resume a scripted Mindcraft prefix from a restored checkpoint via real tools."""

import json;
import os;
import from sys { modules }

import from jac_coder.api { initialize }
import from jac_coder.infra.config { set_model }
import from jac_coder.core.nodes { MainAgent }
import from jac_coder.tool.read.filesystem { read_file }
import from jac_coder.tool.write.checked { write_code, edit_code }
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

test "resume after checkpoint" {
    initialize(mode="web");
    set_model("jaccoder-test-invalid/no-such-model");
    ws = os.environ["REVDEV_M3_RESTORED"];
    set_sandbox_root(ws);
    plan_path = os.path.join(ws, ".jaccoder", "build_plan.json");
    service_path = os.path.join(ws, "services", "island.jac");
    styles_path = os.path.join(ws, "styles.css");
    component_path = os.path.join(ws, "components", "MindcraftApp.jac");
    main_path = os.path.join(ws, "main.jac");
    styles_source = "body { margin: 0; font-family: sans-serif; background: #f4f7f2; color: #243a30; }\nmain { max-width: 60rem; margin: 4rem auto; padding: 2rem; }\n";
    component_source = (
        "cl {\n"
        + "    import from ..services.island { get_world, manifest_emotion, place_entity, apply_interaction, commit_value_action, get_act_path, reset_demo }\n"
        + "    def:pub MindcraftApp() -> JsxElement {\n"
        + "        return <main><h1>Mindcraft</h1><p>Check in with yourself.</p></main>;\n"
        + "    }\n"
        + "}\n"
    );
    main_source = (
        "import from .services.island { get_world, manifest_emotion, place_entity, apply_interaction, commit_value_action, get_act_path, reset_demo }\n"
        + "cl {\n"
        + "    import \"./styles.css\";\n"
        + "    import from .components.MindcraftApp { MindcraftApp }\n"
        + "    def:pub app() -> JsxElement { return <MindcraftApp />; }\n"
        + "}\n"
    );
    old = "walker:pub get_world { can fetch with Root entry { raise NotImplementedError(); } }";
    new = (
        "walker:pub get_world {\n"
        + "    can fetch with Root entry {\n"
        + "        islands = [-->][?:MindIsland];\n"
        + "        if not islands {\n"
        + "            island = MindIsland(created_at=\"initial\");\n"
        + "            root +>:Contains():+> island;\n"
        + "        } else { island = islands[0]; }\n"
        + "        entities = [island -->[?:EmotionalEntity]];\n"
        + "        report {\"entities\": [{\"description\": e.description, \"stage\": e.stage} for e in entities]};\n"
        + "    }\n"
        + "}"
    );
    llm_module = modules[MainAgent.__module__];
    original_llm = llm_module.llm;
    base_module = modules[BaseLLM.__module__];
    original_dispatch = base_module.dispatch_batch;
    base_module.dispatch_batch = record_dispatch(original_dispatch);
    llm_module.llm = CaptureMock(
        model_name="mockllm",
        config={"outputs": [
            MockToolCall(tool=write_code, args={"file_path": styles_path, "content": styles_source}),
            MockToolCall(tool=write_code, args={"file_path": component_path, "content": component_source}),
            MockToolCall(tool=write_code, args={"file_path": main_path, "content": main_source}),
            MockToolCall(tool=read_file, args={"file_path": plan_path, "offset": 0, "limit": 150}),
            MockToolCall(tool=read_file, args={"file_path": service_path, "offset": 0, "limit": 80}),
            MockToolCall(tool=edit_code, args={"file_path": service_path, "old_string": old, "new_string": new}),
            MockToolCall(tool=finish_tool, args={"final_output": "get_world implementation written"}),
            "get_world implementation written"
        ], "verbose": False}
    );
    try {
        for event in MainAgent().respond("Continue the Mindcraft build. Inspect the saved plan and island service, then implement the first get_world walker.") {
            if isinstance(event, StreamEvent) { ; }
        }
    } finally {
        llm_module.llm = original_llm;
        base_module.dispatch_batch = original_dispatch;
    }
    assert [d["name"] for d in _dispatches] == ["write_code", "write_code", "write_code", "read_file", "read_file", "edit_code"];
    assert os.path.isfile(styles_path) and os.path.isfile(component_path) and os.path.isfile(main_path);
    assert "OK:" in str(_dispatches[-1]["result"]);
    with open(service_path, "r", encoding="utf-8") as f {
        updated = f.read();
        assert "islands = [-->][?:MindIsland]" in updated;
        assert "raise NotImplementedError();" in updated;  # remaining walkers are still scaffolds
    }
    out = os.environ["REVDEV_M3_RESUME_OUT"];
    os.makedirs(os.path.dirname(out), exist_ok=True);
    with open(out, "w", encoding="utf-8") as f {
        f.write(json.dumps({"mode": "scripted_mockllm_resume_not_sft", "workspace": ws,
                            "requests": _requests, "dispatches": _dispatches}, default=str, indent=2));
    }
    print(json.dumps({"workspace": ws, "dispatches": [d["name"] for d in _dispatches], "out": out}));
}
