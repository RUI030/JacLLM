import from app.models.core { DecisionItem, BlockerItem }
import from app.models.workflow { WorkflowRequest }
import from app.models.outputs { WorkflowResultBundle, ActionPlan, GeneratedTicket }
import from app.services.memory_store {
    remember_session,
    recent_session_runs,
    update_project_memory,
    get_project_memory
}


test "remember_session records request fields and the action plan headline" {
    req = WorkflowRequest(
        repo_path="/repos/revdev-ghost-alpha",
        prompt="Plan the search refactor",
        mode="refactor"
    );
    bundle = WorkflowResultBundle(action_plan=ActionPlan(headline="Refactor search ranking first"));
    record = remember_session(req, bundle);

    assert record["repo_path"] == "/repos/revdev-ghost-alpha";
    assert record["mode"] == "refactor";
    assert record["prompt"] == "Plan the search refactor";
    assert record["headline"] == "Refactor search ranking first";
    assert record["saved_at"] != "";
}


test "recent_session_runs accumulates remembered sessions" {
    before = len(recent_session_runs());
    req = WorkflowRequest(repo_path="/repos/revdev-ghost-beta", prompt="Write tickets");
    remember_session(req, WorkflowResultBundle(action_plan=ActionPlan(headline="Beta headline")));
    runs = recent_session_runs();

    assert len(runs) >= before + 1;
    beta = [r for r in runs if r["repo_path"] == "/repos/revdev-ghost-beta"];
    assert len(beta) >= 1;
    assert beta[-1]["headline"] == "Beta headline";
    assert beta[-1]["mode"] == "feature_plan";
}


test "update_project_memory stores decision, blocker and ticket titles" {
    bundle = WorkflowResultBundle(
        decisions=[DecisionItem(title="Use graph store"), DecisionItem(title="Drop polling")],
        blockers=[BlockerItem(title="Waiting on API keys", severity="high")],
        tickets=[GeneratedTicket(title="Add ranking tests")]
    );
    mem = update_project_memory("/repos/revdev-ghost-gamma", bundle);

    assert mem["decisions"] == ["Use graph store", "Drop polling"];
    assert mem["blockers"] == ["Waiting on API keys"];
    assert mem["tickets"] == ["Add ranking tests"];
    assert mem["updated_at"] != "";

    fetched = get_project_memory("/repos/revdev-ghost-gamma");
    assert fetched["decisions"] == ["Use graph store", "Drop polling"];
    assert fetched["tickets"] == ["Add ranking tests"];
}


test "get_project_memory returns an empty default for unknown repos" {
    mem = get_project_memory("/repos/revdev-ghost-never-saved");
    assert mem["decisions"] == [];
    assert mem["blockers"] == [];
    assert mem["tickets"] == [];
    assert mem["updated_at"] == "";
}


test "empty repo path is stored under the default key" {
    bundle = WorkflowResultBundle(decisions=[DecisionItem(title="revdev-ghost-default-decision")]);
    update_project_memory("", bundle);
    mem = get_project_memory("");
    assert mem["decisions"] == ["revdev-ghost-default-decision"];
    assert get_project_memory("default")["decisions"] == ["revdev-ghost-default-decision"];
}
