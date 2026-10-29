"""Checks for the M2 private evidence and JacCoder-facing planning contract."""

import copy
import json
import unittest
from pathlib import Path

from tasks import RECIPE, build, validate_plan


HERE = Path(__file__).resolve().parent
MANIFEST = HERE.parents[2] / "dataset/raw/revdev/Rui_pm/m2/private/reference_manifest_0361.json"
MINDCRAFT_MANIFEST = HERE.parents[2] / "dataset/raw/revdev/Mindcraft/m1/private/reference_manifest.json"
MINDCRAFT_RECIPE = HERE / "recipes/mindcraft_core.json"


class TaskGenerationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MANIFEST.is_file():
            raise unittest.SkipTest("M2 pilot manifest is gitignored; run the extractor first")
        cls.manifest = json.loads(MANIFEST.read_text())
        cls.recipe = json.loads(RECIPE.read_text())

    def test_grounded_artifacts_and_clean_student_surface(self) -> None:
        for task in self.recipe["tasks"]:
            visible, oracle, plan = build(self.manifest, self.recipe, task)
            self.assertEqual(visible["task_id"], oracle["task_id"])
            self.assertEqual(plan["write_order"], oracle["write_order"])
            self.assertEqual(len(plan["files"]), 5)
            self.assertEqual(len(plan["ui"]["pages"]), 3)
            self.assertNotIn("source_file", json.dumps(visible))
            self.assertNotIn("symbol_id", json.dumps(visible))
            self.assertNotIn("Rui/pm", json.dumps(visible))
            self.assertNotIn("signature", json.dumps(plan))
            self.assertNotIn("source_sha256", json.dumps(plan))
            self.assertTrue(all(f["signatures"] and f["source_files"] for f in oracle["files"]))
            validate_plan(plan, self.recipe)

    def test_missing_evidence_and_wrong_order_are_rejected(self) -> None:
        recipe = copy.deepcopy(self.recipe)
        recipe["features"][0]["evidence"] = ["models/Project.jac::invented"]
        with self.assertRaisesRegex(ValueError, "Evidence must identify one symbol"):
            build(self.manifest, recipe, recipe["tasks"][0])
        _, _, plan = build(self.manifest, self.recipe, self.recipe["tasks"][0])
        plan["write_order"] = list(reversed(plan["write_order"]))
        with self.assertRaisesRegex(ValueError, "Write order"):
            validate_plan(plan, self.recipe)

    def test_mindcraft_clean_workspace_plan(self) -> None:
        if not MINDCRAFT_MANIFEST.is_file():
            self.skipTest("Mindcraft manifest is gitignored; run the extractor first")
        manifest = json.loads(MINDCRAFT_MANIFEST.read_text())
        recipe = json.loads(MINDCRAFT_RECIPE.read_text())
        visible, oracle, plan = build(manifest, recipe, recipe["tasks"][0])
        self.assertEqual(visible["workspace_kind"], "empty")
        self.assertFalse(plan["ui"]["auth_required"])
        self.assertEqual(plan["write_order"], ["jac.toml", "services/island.jac", "styles.css",
                                               "components/MindcraftApp.jac", "main.jac"])
        self.assertEqual(plan["dependency_graph"]["components/MindcraftApp.jac"], ["services/island.jac"])
        self.assertEqual(plan["dependency_graph"]["main.jac"], ["services/island.jac", "components/MindcraftApp.jac"])
        self.assertNotIn("Mr-Shockwave", json.dumps(visible))
        self.assertNotIn("source_sha256", json.dumps(plan))
        self.assertTrue(all(f["source_files"] for f in oracle["files"]))
        validate_plan(plan, recipe)


if __name__ == "__main__":
    unittest.main()
