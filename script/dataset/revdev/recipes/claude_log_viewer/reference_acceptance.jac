import os;
import tempfile;
import from logs.store { ProjectSummary, SessionSummary, TrajectoryNode, SubagentRef, list_projects, list_sessions }
import from logs.treeUtils { findNode, subagentRefFor }

test "project discovery and session summary" {
    with tempfile.TemporaryDirectory() as tmp {
        project_dir = os.path.join(tmp, "projects", "-home-user-demo");
        os.makedirs(project_dir);
        file_path = os.path.join(project_dir, "s1.jsonl");
        with open(file_path, "w") as f {
            f.write('{"type":"user","message":{"content":"hello"},"timestamp":"2026-01-01T00:00:00Z"}\n');
        }
        projects = list_projects(tmp);
        assert len(projects) == 1;
        assert projects[0].dir_name == "-home-user-demo";
        assert projects[0].decoded_path == "/home/user/demo";
        assert projects[0].session_count == 1;
        sessions = list_sessions(project_dir);
        assert len(sessions) == 1;
        assert sessions[0].session_id == "s1";
        assert sessions[0].message_count == 1;
    }
}

test "recursive tree and subagent lookup" {
    child = TrajectoryNode(id="child", record_uuid="c");
    tree_root = TrajectoryNode(id="root", record_uuid="r", children=[child]);
    assert findNode(tree_root, "child") is child;
    assert findNode(tree_root, "missing") is None;
    ref = SubagentRef(agent_id="a", file_path="/tmp/a.jsonl");
    assert subagentRefFor("child", {"child": ref}) is ref;
    assert subagentRefFor("missing", {"child": ref}) is None;
}

test "session parser retains title text and tool count across malformed rows" {
    with tempfile.TemporaryDirectory() as tmp {
        file_path = os.path.join(tmp, "s2.jsonl");
        with open(file_path, "w") as f {
            f.write('{"type":"ai-title","aiTitle":"Session two","timestamp":"2026-01-01T00:00:00Z","gitBranch":"main"}\n');
            f.write('not valid json\n');
            f.write('{"type":"user","message":{"content":[{"type":"text","text":"First question"}]}}\n');
            f.write('{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read"},{"type":"tool_use","name":"Write"}]},"timestamp":"2026-01-02T00:00:00Z"}\n');
        }
        sessions = list_sessions(tmp);
        assert len(sessions) == 1;
        assert sessions[0].ai_title == "Session two";
        assert sessions[0].first_user_message == "First question";
        assert sessions[0].message_count == 2;
        assert sessions[0].tool_call_count == 2;
        assert sessions[0].last_timestamp == "2026-01-02T00:00:00Z";
        assert sessions[0].git_branch == "main";
        assert sessions[0].size_bytes > 0;
    }
}
