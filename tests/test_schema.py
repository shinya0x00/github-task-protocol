from __future__ import annotations

import unittest

from gtp.schema import validate_record
from gtp.urls import parse_github_url


class SchemaTests(unittest.TestCase):
    def test_scope_rejects_parent_and_glob(self) -> None:
        base = {
            "gtp": "1.0",
            "type": "contract",
            "id": "01234567-89ab-4def-8123-456789abcdef",
            "supersedes": [],
            "goal": "goal",
            "scope": ["../outside", "src/*.py", "src/[ab].py"],
            "done_conditions": {"tests": {"text": "tests pass", "evidence_kind": "check"}},
        }
        errors = validate_record(base)
        self.assertEqual(3, sum(error["code"] == "invalid_value" and error["path"].startswith("$.scope") for error in errors))

    def test_start_rejects_url_shaped_branch(self) -> None:
        start = {
            "gtp": "1.0",
            "type": "start",
            "id": "11234567-89ab-4def-8123-456789abcdef",
            "supersedes": [],
            "branch": "https:feature",
        }
        self.assertIn({"code": "invalid_value", "path": "$.branch"}, validate_record(start))

    def test_stop_combinations_are_closed(self) -> None:
        stop = {
            "gtp": "1.0",
            "type": "stop",
            "id": "31234567-89ab-4def-8123-456789abcdef",
            "supersedes": [],
            "reason": "abandoned",
            "successor_ref": "https://github.com/owner/repo/issues/2",
        }
        self.assertTrue(validate_record(stop))
        stop["reason"] = "superseded"
        self.assertFalse(validate_record(stop))

    def test_github_resource_profiles(self) -> None:
        self.assertIsNotNone(parse_github_url("https://github.com/o/r/issues/1", "issue"))
        self.assertIsNotNone(parse_github_url("https://github.com/o/r/issues/1#issuecomment-2", "comment"))
        self.assertIsNotNone(parse_github_url("https://github.com/o/r/pull/3", "pr"))
        self.assertIsNotNone(parse_github_url("https://github.com/o/r/runs/4", "check"))
        self.assertIsNotNone(parse_github_url("https://github.com/o/r/blob/0123456789abcdef0123456789abcdef01234567/a%20b.txt", "artifact"))
        self.assertIsNone(parse_github_url("https://github.com/o/r/issues/01", "issue"))
        self.assertIsNone(parse_github_url("https://github.com/o/r/blob/main/a.txt", "artifact"))
        self.assertIsNone(parse_github_url("https://github.com/o/r/blob/0123456789abcdef0123456789abcdef01234567/a%2Fb", "artifact"))


if __name__ == "__main__":
    unittest.main()
