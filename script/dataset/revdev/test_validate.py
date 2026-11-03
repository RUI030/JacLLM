"""Check that backend acceptance cannot certify an untested UI."""

import json
import tempfile
import unittest
from pathlib import Path

from checkpoint import workspace_files
from validate import accept_backend


class BackendAcceptanceTest(unittest.TestCase):
    def test_requires_backend_plan_and_unchanged_replayed_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            workspace = run / "workspace"
            (workspace / ".jaccoder").mkdir(parents=True)
            source = workspace / "main.jac"
            source.write_text("def:pub get_status -> str { return \"ok\"; }\n")
            plan = {"ui": {"pages": []}, "files": [{"path": "main.jac", "layer": "service"}]}
            (workspace / ".jaccoder/build_plan.json").write_text(json.dumps(plan))
            (run / "run.json").write_text(json.dumps({"workspace": str(workspace)}))
            (run / "replay.json").write_text(json.dumps({"status": "passed"}))
            (run / "validation.json").write_text(json.dumps({
                "status": "checks_passed_pending_fullstack", "issues": [],
                "workspace_files": workspace_files(workspace)}))
            self.assertEqual(accept_backend(run)["status"], "accepted")

            plan["ui"]["pages"] = [{"route": "/"}]
            (workspace / ".jaccoder/build_plan.json").write_text(json.dumps(plan))
            (run / "validation.json").write_text(json.dumps({
                "status": "checks_passed_pending_fullstack", "issues": [],
                "workspace_files": []}))
            with self.assertRaisesRegex(ValueError, "Workspace changed"):
                accept_backend(run)
            (run / "validation.json").write_text(json.dumps({
                "status": "checks_passed_pending_fullstack", "issues": [],
                "workspace_files": workspace_files(workspace)}))
            with self.assertRaisesRegex(ValueError, "planned UI"):
                accept_backend(run)


if __name__ == "__main__":
    unittest.main()
