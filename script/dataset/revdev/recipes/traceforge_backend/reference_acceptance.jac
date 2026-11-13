import from traceforge.parser { ParsedRun, RawTurn, extract_turns, segment_steps }
import from traceforge.features {
    bounded_ratio,
    summarize_counts,
    compute_run_fingerprint,
    dominant_failure_label,
    build_run_digest
}
import from traceforge.critical { localize_critical_step }


# A failing agent trajectory: inspect -> broken patch -> failing test -> premature submit.
def failing_raw() -> dict[str, any] {
    return {
        "messages": [
            {"role": "user", "content": "Task: Fix the date parser\nSee the issue."},
            {"role": "assistant", "content": "Let me look at src/dates.py first."},
            {"role": "tool", "name": "bash", "content": "cat src/dates.py\ndef parse(): pass"},
            {"role": "assistant", "content": "Applying a patch to src/dates.py"},
            {"role": "tool", "content": "diff --git a/src/dates.py b/src/dates.py\n+ x = 1\n+ y = 2\n- z = 3"},
            {"role": "assistant", "content": "Running the tests now."},
            {"role": "tool", "content": "pytest tests/test_dates.py\nTraceback (most recent call last):\nSyntaxError: invalid syntax"},
            {"role": "assistant", "content": "I will submit the final answer now."}
        ],
        "info": {"exit_status": "failed"}
    };
}


def make_run(run_id: str, status: str) -> ParsedRun {
    turns = extract_turns(failing_raw());
    return ParsedRun(
        run_id=run_id,
        source_path="memory://" + run_id,
        turns=turns,
        steps=segment_steps(turns),
        metadata={"status": status},
        task_title="Fix the date parser",
    );
}


test "segments raw turns into kind and phase tagged steps" {
    turns = extract_turns(failing_raw());
    assert len(turns) == 8;
    assert isinstance(turns[0], RawTurn);
    assert turns[2].role == "tool";
    assert "Tool: bash" in turns[2].content;

    steps = segment_steps(turns);
    assert len(steps) == 5;
    assert [s.kind for s in steps] == ["OTHER", "COMMAND", "EDIT", "TEST", "SUBMIT"];
    assert [s.phase for s in steps] == ["reason", "inspect", "edit", "test", "submit"];
    assert "src/dates.py" in steps[1].touched_files;
    assert steps[3].touched_files == ["tests/test_dates.py"];
}


test "count helpers rank tokens and clamp ratios" {
    assert summarize_counts(["b", "a", "b", "c", "a", "b"], 2) == [("b", 3), ("a", 2)];
    assert bounded_ratio(5, 2) == 1.0;
    assert bounded_ratio(1, 0) == 0.0;
    assert bounded_ratio(1, 3) == 0.3333;
}


test "fingerprint of a parsed run flags an invalid patch" {
    run = make_run("tf-fp-run", "failed");
    fp = compute_run_fingerprint(run);
    assert fp["num_steps"] == 5;
    assert fp["num_turns"] == 8;
    assert fp["num_patches"] == 1;
    assert fp["num_tests"] == 1;
    assert fp["first_patch_step"] == 2;
    assert fp["first_error_step"] == 3;
    assert fp["first_submit_step"] == 4;
    assert fp["submit_before_recovery"] == True;
    assert fp["did_any_syntax_error"] == True;
    assert fp["step_kind_sequence"] == ["OTHER", "COMMAND", "EDIT", "TEST", "SUBMIT"];
    assert fp["failure_class_scores"]["INVALID_PATCH"] == 0.95;
    assert dominant_failure_label(fp) == "INVALID_PATCH";
    assert dominant_failure_label({"failure_class_scores": {}}) == "UNKNOWN";
}


test "run digest summarizes status and primary failure" {
    run = make_run("tf-digest-run", "failed");
    digest = build_run_digest(run, compute_run_fingerprint(run));
    assert digest.startswith("Run tf-digest-run on task 'Fix the date parser' ended with status failed.");
    assert "5 decision steps, 1 test actions, 1 patch actions." in digest;
    assert "Primary failure family: INVALID_PATCH." in digest;
    assert "Submission happened before visible recovery." in digest;
}


test "localizes the critical step at the breaking patch" {
    run = make_run("tf-critical-run", "failed");
    result = localize_critical_step(run, compute_run_fingerprint(run));
    assert result["status"] == "localized";
    assert result["critical_step_idx"] == 2;
    assert result["confidence"] >= 0.45;
    assert [c["step_idx"] for c in result["candidate_scores"]] == [2, 3, 4];
    assert result["candidate_scores"][0]["signals"]["patch_to_error_signal"] == 0.25;
    assert [w["idx"] for w in result["evidence_window"]] == [1, 2, 3];
    assert result["evidence_window"][1]["kind"] == "EDIT";
}


test "resolved runs are not localized" {
    run = make_run("tf-resolved-run", "resolved");
    result = localize_critical_step(run, compute_run_fingerprint(run));
    assert result["status"] == "resolved_run";
    assert result["critical_step_idx"] == -1;
    assert result["candidate_scores"] == [];
    assert result["evidence_window"] == [];
}
