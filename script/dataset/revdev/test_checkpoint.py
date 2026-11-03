"""Checkpoint replay must preserve the student-visible workspace exactly."""

import json
import tempfile
import unittest
from pathlib import Path

from checkpoint import restore, save, resume_handoff


class CheckpointTest(unittest.TestCase):
    def test_restore_and_tamper_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "student"
            (workspace / ".jaccoder").mkdir(parents=True)
            (workspace / "main.jac").write_text("def title() -> str { raise NotImplementedError(); }\n")
            (workspace / ".jaccoder/build_plan.json").write_text(json.dumps({
                "files": [{"path": "main.jac", "status": "done"}]
            }))
            checkpoint = root / "checkpoint"
            meta = save(workspace, checkpoint, run_id="run-1", after_event_id="event-3",
                        segment_index=0, reference_id="ref-private", harness_schema_hash="schema-hash",
                        environment_fingerprint={"jac_version": "0.34.27"},
                        completed_work=["main scaffold"], remaining_work=["implement body"])
            self.assertEqual(meta["plan_consistency"]["state"], "scaffold_only")
            self.assertEqual(meta["plan_consistency"]["issues"][0]["path"], "main.jac")
            handoff = resume_handoff(meta, [
                {"decision": {"kind": "tool", "name": "run_command",
                              "args": {"command": "jac check main.jac"}},
                 "result": {"content": "TYPE ERRORS", "executed": True}},
                {"decision": {"kind": "tool", "name": "read_file",
                              "args": {"file_path": "main.jac"}},
                 "result": {"content": "source"}},
            ], {"files": [{"path": "main.jac"}, {"path": "missing.jac"}]})
            self.assertEqual(handoff["planned_files"][0]["sha256"],
                             next(row["sha256"] for row in meta["files"] if row["path"] == "main.jac"))
            self.assertTrue(handoff["planned_files"][0]["contains_stub"])
            self.assertFalse(handoff["planned_files"][1]["present"])
            self.assertEqual(handoff["observed_commands"][0]["result_excerpt"], "TYPE ERRORS")
            self.assertEqual(len(handoff["observed_commands"]), 1)
            restored = root / "resumed"
            self.assertEqual(restore(checkpoint, restored)["checkpoint_id"], meta["checkpoint_id"])
            self.assertEqual((restored / "main.jac").read_bytes(), (workspace / "main.jac").read_bytes())
            (checkpoint / "workspace/main.jac").write_text("tampered\n")
            with self.assertRaisesRegex(ValueError, "do not match"):
                restore(checkpoint, root / "should_not_exist")

    def test_done_file_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "student"
            (workspace / ".jaccoder").mkdir(parents=True)
            (workspace / ".jaccoder/build_plan.json").write_text(json.dumps({
                "files": [{"path": "main.jac", "status": "done"}]
            }))
            with self.assertRaisesRegex(ValueError, "done_file_missing"):
                save(workspace, root / "checkpoint", run_id="run-1", after_event_id="event-3",
                     segment_index=0, reference_id="ref-private", harness_schema_hash="schema-hash",
                     environment_fingerprint={}, completed_work=[], remaining_work=[])

    def test_pending_file_stub_is_reported_from_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "student"
            (workspace / ".jaccoder").mkdir(parents=True)
            (workspace / "main.jac").write_text("def title() -> str { raise NotImplementedError(); }\n")
            (workspace / ".jaccoder/build_plan.json").write_text(json.dumps({
                "files": [{"path": "main.jac", "status": "pending"}]
            }))
            meta = save(workspace, root / "checkpoint", run_id="run-1", after_event_id="event-3",
                        segment_index=0, reference_id="ref-private", harness_schema_hash="schema-hash",
                        environment_fingerprint={}, completed_work=[], remaining_work=[])
            self.assertEqual(meta["plan_consistency"]["state"], "scaffold_only")
            self.assertEqual(meta["plan_consistency"]["issues"],
                             [{"issue": "planned_file_has_stub", "path": "main.jac"}])


if __name__ == "__main__":
    unittest.main()
