"""Check that the student plan exposes files and dependency direction."""

import json
import tempfile
import unittest
from pathlib import Path

from plan_md import render, validate_rendered
from claude_adapter import validate_call


class PlanMarkdownTest(unittest.TestCase):
    def test_a2pulse_plan_has_mermaid_graph_and_order(self) -> None:
        recipe = Path(__file__).with_name("recipes") / "a2pulse_week"
        plan = json.loads((recipe / "plan.json").read_text())
        request = json.loads((recipe / "task.json").read_text())["request"]
        markdown = render(plan, request)
        validate_rendered(markdown, plan)
        self.assertIn("M1 --> M2", markdown)
        self.assertIn("M2 --> M3", markdown)
        self.assertIn("## Frontend modules (.jac)", markdown)
        self.assertIn("## Backend modules (.jac)", markdown)
        self.assertNotIn('M1["jac.toml"]', markdown)
        self.assertNotIn('M3["styles.css"]', markdown)
        with self.assertRaisesRegex(ValueError, "Non-Jac support file"):
            validate_rendered(markdown.replace("flowchart LR\n", 'flowchart LR\n    X["styles.css"]\n'), plan)
        self.assertIn("brief_monday(now: date \\| datetime \\| None)", markdown)
        order = markdown.split("## Jac module build order", 1)[1]
        self.assertLess(order.index("`services/brief_dates.jac`"),
                        order.index("`components/WeekPlanner.jac`"))

    def test_newer_jac_recipe_uses_runtime_dependency_resolution(self) -> None:
        recipe = Path(__file__).with_name("recipes") / "a2pulse_week"
        plan = json.loads((recipe / "plan_md_v4.json").read_text())
        task = json.loads((recipe / "task_md_v4.json").read_text())
        markdown = render(plan, task["request"])
        validate_rendered(markdown, plan)
        self.assertIn("Jac resolves its React client runtime", markdown)
        self.assertNotIn("declare [dependencies.npm] react", markdown)

    def test_missing_edge_is_rejected(self) -> None:
        plan = {"files": [{"path": "a.jac", "write_order": 1, "purpose": "A", "exports": ["a"],
                            "imports_from_plan": [], "layer": "service"},
                           {"path": "b.jac", "write_order": 2, "purpose": "B", "exports": ["b"],
                            "imports_from_plan": ["a"], "layer": "page"}],
                "dependency_graph": {"a.jac": [], "b.jac": ["a.jac"]}, "verify": {}}
        markdown = render(plan).replace("M1 --> M2", "")
        with self.assertRaisesRegex(ValueError, "omits dependency"):
            validate_rendered(markdown, plan)
        legacy = render(plan, module_only=False)
        validate_rendered(legacy, plan, module_only=False)

    def test_machine_plan_is_hidden_from_markdown_student(self) -> None:
        schemas = {"read_file": {"parameters": {"type": "object"}},
                   "write_code": {"parameters": {"type": "object"}}}
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            decision = {"kind": "tool", "name": "read_file",
                        "args": {"file_path": str(workspace / ".jaccoder/build_plan.json")},
                        "summary": "Read plan"}
            with self.assertRaisesRegex(ValueError, "private"):
                validate_call(decision, schemas, workspace, hide_machine_plan=True)
            decision["name"] = "write_code"
            decision["args"]["file_path"] = str(workspace / "main.jac")
            with self.assertRaisesRegex(ValueError, "Write docs/plan.md"):
                validate_call(decision, schemas, workspace, hide_machine_plan=True)


if __name__ == "__main__":
    unittest.main()
