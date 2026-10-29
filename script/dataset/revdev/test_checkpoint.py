"""Checkpoint replay must preserve the student-visible workspace exactly."""

import json
import tempfile
import unittest
from pathlib import Path

from checkpoint import restore, save


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


if __name__ == "__main__":
    unittest.main()
