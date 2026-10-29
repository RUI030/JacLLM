"""Check AST import and call evidence against a small Jac fixture."""

import os, shutil, tempfile, unittest
from pathlib import Path

from extract import build_manifest

# Setting =================================================
FIXTURE = Path(__file__).with_name("fixtures") / "import_graph"
JAC     = os.environ.get("REVDEV_JAC", "jac")


# Functions ===============================================
class ExtractFixtureTest(unittest.TestCase):
    def test_exact_compiler_pin_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory(prefix="revdev-version-") as tmp:
            copy = Path(tmp) / "fixture"
            shutil.copytree(FIXTURE, copy)
            (copy / "jac.toml").write_text('[project]\nname = "bad-pin"\njac-version = "==9.9.9"\n')
            with self.assertRaisesRegex(ValueError, "requires Jac 9.9.9"):
                build_manifest(copy, "fixture/bad-pin", JAC, check=False)

    def test_dependency_evidence_and_unresolved_import(self) -> None:
        manifest = build_manifest(FIXTURE, "fixture/import_graph", JAC, check=False)
        edges = manifest["dependencies"]
        pairs = {(edge["kind"], edge["from_file"], edge["to_file"]) for edge in edges}
        self.assertIn(("import", "a.jac", "b.jac"), pairs)
        self.assertIn(("import", "b.jac", "a.jac"), pairs)
        self.assertIn(("annex", "a.impl.jac", "a.jac"), pairs)
        self.assertIn(("call", "a.impl.jac", "b.jac"), pairs)
        self.assertIn(("symbol_use", "b.jac", "b.jac"), pairs)
        self.assertEqual(manifest["cycles"], [["a.jac", "b.jac"]])
        self.assertTrue(any(item["reason"] == "missing_local" and item.get("symbol") == "Ghost"
                            for item in manifest["unresolved_dependencies"]))
        self.assertTrue(any(sym["file"] == "a.jac" and sym["signature"] == "def a_value() -> str"
                            for sym in manifest["symbols"]))
        self.assertTrue(any(sym["name"] == "Item" and sym["fields"][0]["name"] == "title"
                            for sym in manifest["symbols"] if sym["kind"] == "node"))
        self.assertTrue(any(sym["kind"] == "enum" and sym["name"] == "Status"
                            for sym in manifest["symbols"]))
        for edge in edges:
            lines = (FIXTURE / edge["from_file"]).read_text().splitlines()
            position = edge["span"]
            self.assertGreater(position["line"], 0)
            self.assertLessEqual(position["line"], len(lines))
            self.assertGreater(position["column"], 0)
            self.assertLessEqual(position["column"], len(lines[position["line"] - 1]) + 1)
            fragment = lines[position["line"] - 1][position["column"] - 1:position["end_column"] - 1]
            if edge["kind"] == "import":
                self.assertIn(edge["imported_name"], fragment)
            elif edge["kind"] in {"call", "symbol_use"}:
                self.assertIn(edge["expression"], fragment)
            elif edge["kind"] == "annex":
                self.assertTrue(lines[position["line"] - 1].lstrip().startswith("impl "))


# Run =====================================================
if __name__ == "__main__":
    unittest.main()
