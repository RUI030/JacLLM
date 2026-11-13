import asyncio;
import from jaclang.byllm.lib { MockLLM }
import services.appService as svc;
import from main {
    Goal, Mission, MemoryEntry, InsightReport,
    get_goals, update_goal_progress, delete_goal,
    get_missions, toggle_mission, delete_mission,
    get_memories, get_agent_logs, get_agent_status, get_stats,
    agent_get_insights
}


test "toggling a mission records memory, logs and flips back" {
    m = root ++> Mission(title="Revdev toggle mission 41", xp=137, tag="RevdevTag41", difficulty="Hard");
    mid = jid(m);
    done = toggle_mission(mid);
    assert done is not None;
    assert done.done == True;
    mems = [e for e in get_memories() if e.summary == "Completed: Revdev toggle mission 41"];
    assert len(mems) == 1;
    assert mems[0].tags == "RevdevTag41";
    assert mems[0].focus_score == 85;
    assert mems[0].duration == "1h";
    logs = get_agent_logs();
    assert logs[-3].agent_name == "Execution";
    assert logs[-3].action == "Mission completed! +137 XP earned";
    assert logs[-3].detail == "Revdev toggle mission 41";
    assert logs[-2].agent_name == "Memory";
    assert logs[-2].action == "Session logged — completed: RevdevTag41 task";
    assert logs[-1].agent_name == "Analytics";
    assert logs[-1].detail == "+137 XP";
    undone = toggle_mission(mid);
    assert undone.done == False;
    last = get_agent_logs()[-1];
    assert last.action == "Mission marked incomplete";
    assert last.detail == "Revdev toggle mission 41";
    assert len([e for e in get_memories() if e.summary == "Completed: Revdev toggle mission 41"]) == 1;
    assert toggle_mission("no-such-mission-41") is None;
}


test "goal progress updates log coach milestones and deletion" {
    g = root ++> Goal(title="Revdev goal 52", timeline="5 months");
    gid = jid(g);
    upd = update_goal_progress(gid, 80);
    assert upd is not None and upd.progress == 80;
    logs = get_agent_logs();
    assert logs[-2].agent_name == "Analytics";
    assert logs[-2].action == "Progress updated to 80%";
    assert logs[-1].agent_name == "Coach";
    assert logs[-1].action == "75%+ reached — final push mode activated";
    update_goal_progress(gid, 100);
    assert get_agent_logs()[-1].action == "Goal completed! Celebrating achievement";
    update_goal_progress(gid, 40);
    last = get_agent_logs()[-1];
    assert last.agent_name == "Analytics" and last.action == "Progress updated to 40%";
    assert update_goal_progress("no-such-goal-52", 10) is None;
    assert delete_goal(gid) == True;
    assert get_agent_logs()[-1].action == "Goal removed from roadmap";
    assert not any(x.title == "Revdev goal 52" for x in get_goals());
    assert delete_goal(gid) == False;
}


test "stats and agent status aggregate missions and goals" {
    before = get_stats();
    m = root ++> Mission(title="Revdev stats mission 63", xp=263);
    root ++> Mission(title="Revdev stats mission 63b", xp=11);
    toggle_mission(jid(m));
    after = get_stats();
    assert after["total_missions"] == before["total_missions"] + 2;
    assert after["done_missions"] == before["done_missions"] + 1;
    assert after["total_xp"] == before["total_xp"] + 263;
    goals = get_goals();
    assert after["total_goals"] == len(goals);
    expected_avg = 0;
    if len(goals) > 0 {
        expected_avg = sum([x.progress for x in goals]) // len(goals);
    }
    assert after["avg_progress"] == expected_avg;
    status = get_agent_status();
    assert status["execution"]["tasks_done"] == after["done_missions"];
    assert status["execution"]["status"] == "active";
    assert status["research"] == {"status": "idle", "task": "Ready to scan opportunities", "tasks_done": 0};
    assert status["coach"]["status"] == "active";
    assert status["memory"]["task"] == "Indexed " + str(len(get_memories())) + " sessions";
    assert delete_mission(jid(m)) == True;
    assert get_agent_logs()[-1].action == "Mission removed from plan";
    assert delete_mission(jid(m)) == False;
}


test "insights come from the model when it answers" {
    g = root ++> Goal(title="Revdev insight goal 74", timeline="9 months", progress=30);
    canned = InsightReport(insights=["one", "two"], coach_message="keep going 74", predicted_completion="June", risk_level="Medium");
    svc.llm = MockLLM(model_name="mockllm", config={"outputs": [canned]});
    got = asyncio.run(agent_get_insights(jid(g)));
    assert got.coach_message == "keep going 74";
    assert got.insights == ["one", "two"];
    assert got.risk_level == "Medium";
    logs = get_agent_logs();
    assert logs[-2].agent_name == "Analytics" and logs[-2].action == "Generating insights for";
    assert logs[-2].detail == "Revdev insight goal 74";
    assert logs[-1].agent_name == "Coach" and logs[-1].action == "AI insights delivered";
}


test "insights fall back to rule-based report when the model fails" {
    g = root ++> Goal(title="Revdev fallback goal 85", timeline="11 months", progress=45);
    svc.llm = MockLLM(model_name="mockllm", config={"outputs": []});
    got = asyncio.run(agent_get_insights(jid(g)));
    stats = get_stats();
    done = stats["done_missions"];
    total = stats["total_missions"];
    pct = 0;
    if total > 0 {
        pct = (done * 100) // total;
    }
    expected_risk = "Low";
    if pct < 30 {
        expected_risk = "High";
    } elif pct < 60 {
        expected_risk = "Medium";
    }
    assert len(got.insights) == 4;
    assert got.insights[0] == "You have completed " + str(done) + " of " + str(total) + " missions (" + str(pct) + "% completion rate).";
    assert got.insights[1] == "Current goal progress is at 45% — keep pushing forward.";
    assert got.coach_message == "You're making progress on Revdev fallback goal 85. Stay consistent and trust the process!";
    assert got.predicted_completion == "On track for 11 months";
    assert got.risk_level == expected_risk;
    last = get_agent_logs()[-1];
    assert last.agent_name == "Coach" and last.action == "Rule-based insights generated";
    unknown = asyncio.run(agent_get_insights("no-such-goal-85"));
    assert unknown.predicted_completion == "On track for 3 months";
    assert unknown.coach_message == "You're making progress on your goal. Stay consistent and trust the process!";
}
