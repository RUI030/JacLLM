"""Check adapter argument boundaries without contacting the teacher model."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from claude_adapter import jac_version, validate_call


class AdapterTest(unittest.TestCase):
    def test_jac_version_comes_from_binary_output(self) -> None:
        with patch("claude_adapter.subprocess.run", return_value=SimpleNamespace(stdout="jac 0.36.1  (Linux x86_64)")):
            self.assertEqual(jac_version(Path("/tmp/jac-probe")), "0.36.1")

    def test_paths_and_commands_are_checked_before_dispatch(self) -> None:
        schemas = {
            "read_file": {"parameters": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}},
            "run_command": {"parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def call(name, args):
                return {"kind": "tool", "name": name, "args": args, "summary": "test"}
            validate_call(call("read_file", {"file_path": str(root / "main.jac")}), schemas, root)
            validate_call(call("run_command", {"command": "jac test tests"}), schemas, root)
            validate_call(call("run_command", {"command": "jac guide jac-cl-components"}), schemas, root)
            with self.assertRaises(ValueError):
                validate_call(call("run_command", {"command": "jac install"}), schemas, root)
            (root / "jac.toml").write_text("[project]\nname = 'test'\n")
            validate_call(call("run_command", {"command": "jac install"}), schemas, root)
            for decision in [call("read_file", {"file_path": "/etc/passwd"}),
                             call("run_command", {"command": "jac test; rm x"}),
                             call("run_command", {"command": "jac install react"}),
                             call("run_command", {"command": "jac guide --export /tmp/skills"}),
                             call("run_command", {"command": "curl example.com"}),
                             call("unknown", {})]:
                with self.assertRaises(ValueError):
                    validate_call(decision, schemas, root)


if __name__ == "__main__":
    unittest.main()
