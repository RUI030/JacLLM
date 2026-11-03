"""Check SFT projection of rejected finals and local execution paths."""

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from export import assemble_existing, event_rows, normalize_paths, planning_system


class ExportTest(unittest.TestCase):
    def test_rejected_final_is_not_a_successful_answer(self) -> None:
        rejected = {"decision": {"kind": "final", "summary": "Done"},
                    "result": {"executed": False, "origin": "adapter_validation",
                               "content": "Unexpected output field"}}
        accepted = {"decision": {"kind": "final", "summary": "Verified"}}
        self.assertEqual(event_rows([rejected]), [])
        self.assertEqual(event_rows([accepted])[0]["content"], "Verified")
        self.assertEqual(event_rows([rejected, accepted]), event_rows([accepted]))
        invalid_tool = {"decision": {"kind": "tool", "name": "edit_code", "args": {},
                                     "summary": "Invalid proposal"},
                        "result": {"executed": False, "origin": "adapter_validation",
                                   "content": "Missing replace_all"}}
        self.assertEqual(event_rows([invalid_tool, accepted]), event_rows([accepted]))

    def test_workspace_paths_are_stable_inside_nested_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "workspace"
            resumed = Path(temp) / "workspace-segment-1"
            value = {"workspace": str(resumed),
                     "args": {"file_path": str(first / "services/island.jac")},
                     "result": f"See {resumed}/main.jac"}
            projected = normalize_paths(value, [first, resumed])
            self.assertEqual(projected["workspace"], "/workspace")
            self.assertEqual(projected["args"]["file_path"],
                             "/workspace/services/island.jac")
            self.assertEqual(projected["result"], "See /workspace/main.jac")

    def test_planning_prompt_names_target_jac_version(self) -> None:
        prompt = planning_system("markdown_mermaid_v2", "0.36.1")
        self.assertIn("Target Jac version: 0.36.1", prompt)
        self.assertIn("frontend and backend", prompt)

    def test_one_dataset_keeps_apps_together_and_excludes_mirrors(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sft"
            original = {"messages": [{"role": "user", "content": "Build it"},
                                     {"role": "assistant", "content": "Done"}],
                        "tools": "[]",
                        "meta": {"validation": "accepted", "task_type": "revdev_plan",
                                 "fp": "example/run#plan",
                                 "split_group": "example__app", "tokens": 20}}
            for name, split in (("example", "valid"), ("example-16k", "valid")):
                target = root / "revdev_plan" / name
                target.mkdir(parents=True)
                (target / f"{split}.jsonl").write_text(json.dumps(original) + "\n")
            with redirect_stdout(StringIO()):
                stats = assemble_existing(root, root, "accepted")
                repeated = assemble_existing(root, root, "accepted")
            self.assertEqual(stats["records"], 1)
            self.assertEqual(repeated["records"], 1)
            output = root / "revdev" / "accepted"
            self.assertFalse((output / "valid.jsonl").exists())
            record = json.loads((output / "train.jsonl").read_text())
            self.assertEqual(record["meta"]["task_type"], "revdev")
            self.assertEqual(record["meta"]["stage"], "revdev_plan")
            self.assertEqual(record["meta"]["source_split"], "train")


if __name__ == "__main__":
    unittest.main()
