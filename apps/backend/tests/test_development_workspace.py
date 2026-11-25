"""Workspace revisions are distinct from the independently reviewed candidate."""
import json
import unittest

from pathlib import Path
from ago.company_engineering import entry_command, reviewed_candidate, verify_persisted_candidate
from ago.company_engineering import RevisionConflict, edited_candidate, workspace_snapshot


class DevelopmentWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.files = [
            {"path": "src/math_ops.py", "content": "def add(a,b): return a+b\n"},
            {"path": "tests/test_add.py", "content": "import unittest\n"},
        ]
        self.original = reviewed_candidate(json.dumps({
            "files": self.files, "acceptance_checks": ["adds two integers"],
        }))
        self.row = {"run_id": "run", "run_status": "completed",
                    "run_result": {"engineering_candidate": self.original}}
        self.initial = workspace_snapshot(self.row, None)
        self.change = {"run_id": "run", "expected_revision": 0,
                       "files": [{**self.files[0], "content": "def add(a,b): return b+a\n"},
                                 self.files[1]]}

    def test_edit_preserves_original_and_checks(self):
        edited = edited_candidate(self.initial, self.change)
        next_version = workspace_snapshot(self.row, {"revision": 1, "candidate": edited})
        self.assertEqual(next_version["original_sha256"], self.initial["candidate_sha256"])
        self.assertNotEqual(next_version["candidate_sha256"], next_version["original_sha256"])
        self.assertEqual(next_version["acceptance_checks"], self.initial["acceptance_checks"])
        self.assertFalse(edited["tests_executed"])
        self.assertFalse(edited["qa_approved"])

    def test_missing_or_unfinished_task(self):
        for row in (None, {**self.row, "run_status": "running"}):
            with self.assertRaises(LookupError):
                workspace_snapshot(row, None)

    def test_rejects_stale_run_and_revision(self):
        for change in ({"expected_revision": 1}, {"run_id": "old"}):
            with self.assertRaises(RevisionConflict):
                edited_candidate(self.initial, {**self.change, **change})

    def test_rejects_unsafe_paths_and_invalid_syntax(self):
        for item in ({"path": "../src/x.py"}, {"content": "def broken(:"}):
            with self.assertRaises(ValueError):
                edited_candidate(self.initial, {**self.change,
                    "files": [{**self.files[0], **item}, self.files[1]]})

    def test_node_uses_fixed_offline_runtime_and_workspace_scope(self):
        files = [{"path": "src/main.mjs", "content": "export const value = 3;"},
                 {"path": "tests/main.test.mjs", "content": "import 'node:test';"}]
        edited = edited_candidate(self.initial, {**self.change, "files": files})
        self.assertEqual(verify_persisted_candidate(edited, workspace=True), edited)
        with self.assertRaises(ValueError):
            verify_persisted_candidate(edited)
        command = entry_command(Path("."), "ago-test-" + "1"*32, edited, "src/main.mjs")
        self.assertEqual(command[-3:], ["node:22-alpine", "node", "/work/src/main.mjs"])
        self.assertIn("--pull=never", command)
        self.assertEqual(command[command.index("--network")+1], "none")
        with self.assertRaises(ValueError):
            entry_command(Path("."), "ago-test-" + "1"*32, edited, "/bin/sh")

    def test_rejects_modified_stored_evidence(self):
        with self.assertRaises(PermissionError):
            workspace_snapshot(self.row, {"revision": 1, "candidate": {
                **self.original, "candidate_sha256": "0"*64}})


if __name__ == "__main__":
    unittest.main()
