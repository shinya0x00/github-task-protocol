from __future__ import annotations

import json
from pathlib import Path
import unittest

from gtp.schema import RECORD_FIELDS, strict_json_loads, validate_record
from gtp.urls import parse_github_url


class SchemaTests(unittest.TestCase):
    def test_scope_rejects_parent_and_glob(self) -> None:
        base = {
            "gtp": "1.0",
            "type": "contract",
            "id": "01234567-89ab-4def-8123-456789abcdef",
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
            "contract_ref": "https://github.com/owner/repo/issues/1#issuecomment-2",
            "branch": "https:feature",
        }
        self.assertIn({"code": "invalid_value", "path": "$.branch"}, validate_record(start))

    def test_stop_combinations_are_closed(self) -> None:
        stop = {
            "gtp": "1.0",
            "type": "stop",
            "id": "31234567-89ab-4def-8123-456789abcdef",
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

    def test_record_field_sets_match_conformance_fixture(self) -> None:
        path = Path(__file__).parent / "fixtures" / "schema-conformance.json"
        expected = json.loads(path.read_text())
        self.assertEqual(
            {kind: set(fields) for kind, fields in expected.items()},
            {kind: set(fields) for kind, fields in RECORD_FIELDS.items()},
        )

    def test_removed_and_unknown_fields_are_rejected(self) -> None:
        start = {
            "gtp": "1.0",
            "type": "start",
            "id": "11234567-89ab-4def-8123-456789abcdef",
            "contract_ref": "https://github.com/owner/repo/issues/1#issuecomment-2",
            "branch": "feature/one",
            "supersedes": [],
            "author": "agent",
            "created_at": "2026-07-19T00:00:00Z",
        }
        errors = validate_record(start)
        self.assertEqual(
            {"$.author", "$.created_at", "$.supersedes"},
            {error["path"] for error in errors if error["code"] == "unknown_field"},
        )

    def test_envelope_version_type_and_uuid_are_closed(self) -> None:
        base = {
            "gtp": "1.0",
            "type": "start",
            "id": "11234567-89ab-4def-8123-456789abcdef",
            "contract_ref": "https://github.com/owner/repo/issues/1#issuecomment-2",
            "branch": "feature/one",
        }
        cases = (
            ("gtp", "2.0", "$.gtp"),
            ("type", "begin", "$.type"),
            ("id", "11234567-89AB-4def-8123-456789abcdef", "$.id"),
            ("id", "11234567-89ab-1def-8123-456789abcdef", "$.id"),
        )
        for field, value, path in cases:
            with self.subTest(field=field, value=value):
                record = dict(base)
                record[field] = value
                self.assertIn(path, {error["path"] for error in validate_record(record)})

    def test_start_requires_comment_ref_and_short_branch(self) -> None:
        base = {
            "gtp": "1.0",
            "type": "start",
            "id": "11234567-89ab-4def-8123-456789abcdef",
            "contract_ref": "https://github.com/owner/repo/issues/1#issuecomment-2",
            "branch": "feature/one",
        }
        self.assertFalse(validate_record(base))
        for field, value in (
            ("contract_ref", "https://github.com/owner/repo/issues/1"),
            ("branch", "refs/heads/feature/one"),
            ("branch", "https://github.com/owner/repo/tree/feature"),
            ("branch", " feature/one "),
        ):
            with self.subTest(field=field, value=value):
                record = dict(base)
                record[field] = value
                self.assertTrue(validate_record(record))

    def test_done_sha_condition_ids_and_urls_are_strict(self) -> None:
        base = {
            "gtp": "1.0",
            "type": "done",
            "id": "21234567-89ab-4def-8123-456789abcdef",
            "pr_ref": "https://github.com/owner/repo/pull/7",
            "head_sha": "0123456789abcdef0123456789abcdef01234567",
            "evidence": {
                "acceptance_artifact": "https://github.com/owner/repo/blob/0123456789abcdef0123456789abcdef01234567/acceptance/run.json"
            },
        }
        self.assertFalse(validate_record(base))
        bad_sha = dict(base, head_sha="ABC")
        self.assertIn("$.head_sha", {error["path"] for error in validate_record(bad_sha)})
        bad_pr = dict(base, pr_ref="https://github.com/owner/repo/issues/7")
        self.assertIn("$.pr_ref", {error["path"] for error in validate_record(bad_pr)})
        bad_evidence = dict(base, evidence={"Bad__ID": "https://example.com"})
        paths = {error["path"] for error in validate_record(bad_evidence)}
        self.assertIn("$.evidence.Bad__ID", paths)

    def test_contract_text_scope_and_nested_schema_are_strict(self) -> None:
        base = {
            "gtp": "1.0",
            "type": "contract",
            "id": "01234567-89ab-4def-8123-456789abcdef",
            "goal": "goal",
            "scope": ["src/", "README.md"],
            "done_conditions": {
                "tests_pass": {"text": "tests pass", "evidence_kind": "check"}
            },
        }
        self.assertFalse(validate_record(base))
        for record in (
            dict(base, goal=" goal "),
            dict(base, scope=["/absolute"]),
            dict(base, scope=["src//nested"]),
            dict(base, scope=["src/", "src/"]),
            dict(base, done_conditions={"Bad__ID": {"text": "x", "evidence_kind": "check"}}),
            dict(base, done_conditions={"tests": {"text": "x", "evidence_kind": "human"}}),
            dict(base, done_conditions={"tests": {"text": "x", "evidence_kind": "check", "extra": True}}),
        ):
            with self.subTest(record=record):
                self.assertTrue(validate_record(record))

    def test_strict_json_rejects_duplicate_and_nonstandard_constants(self) -> None:
        value, errors = strict_json_loads('{"id": 1, "id": 2}')
        self.assertIsNone(value)
        self.assertEqual("duplicate_key", errors[0]["code"])
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                value, errors = strict_json_loads('{"value": ' + token + "}")
                self.assertIsNone(value)
                self.assertEqual("invalid_json", errors[0]["code"])


if __name__ == "__main__":
    unittest.main()
