from __future__ import annotations

from pathlib import Path
import unittest

from gtp.carrier import classify_carrier


FIXTURES = Path(__file__).parent / "fixtures" / "carriers"


class CarrierTests(unittest.TestCase):
    def test_all_four_valid_record_types(self) -> None:
        for name, record_type in (
            ("contract-valid.md", "contract"),
            ("start-valid.md", "start"),
            ("done-valid.md", "done"),
            ("stop-valid.md", "stop"),
        ):
            with self.subTest(name=name):
                result = classify_carrier((FIXTURES / name).read_text())
                self.assertTrue(result.recognized)
                self.assertTrue(result.schema_valid)
                self.assertEqual(record_type, result.record["type"])

    def test_normal_comment_is_not_recognized(self) -> None:
        result = classify_carrier("ordinary\n\n```json\n{}\n```\n")
        self.assertFalse(result.recognized)
        self.assertIsNone(result.schema_valid)

    def test_marker_typo_is_not_recognized(self) -> None:
        result = classify_carrier("summary\n\n<!-- gtp-record:v2 -->\n\n```json\n{}\n```\n")
        self.assertFalse(result.recognized)

    def test_exact_marker_with_malformed_json_is_invalid(self) -> None:
        result = classify_carrier("summary\n\n<!-- gtp-record:v1 -->\n\n```json\n{\n```\n")
        self.assertTrue(result.recognized)
        self.assertFalse(result.schema_valid)
        self.assertEqual("invalid_json", result.errors[0]["code"])

    def test_duplicate_key_is_rejected(self) -> None:
        source = (FIXTURES / "start-valid.md").read_text().replace(
            '"branch": "codex/gtp-walking-skeleton"',
            '"branch": "one",\n  "branch": "two"',
        )
        result = classify_carrier(source)
        self.assertFalse(result.schema_valid)
        self.assertEqual("duplicate_key", result.errors[0]["code"])

    def test_unknown_nested_field_is_rejected(self) -> None:
        source = (FIXTURES / "contract-valid.md").read_text().replace(
            '"evidence_kind": "artifact"',
            '"evidence_kind": "artifact",\n      "extra": true',
        )
        result = classify_carrier(source)
        self.assertFalse(result.schema_valid)
        self.assertIn(
            {"code": "unknown_field", "path": "$.done_conditions.acceptance_artifact.extra"},
            result.errors,
        )

    def test_additional_prose_is_rejected(self) -> None:
        source = (FIXTURES / "start-valid.md").read_text() + "extra\n"
        result = classify_carrier(source)
        self.assertFalse(result.schema_valid)
        self.assertEqual("invalid_carrier_layout", result.errors[0]["code"])


if __name__ == "__main__":
    unittest.main()
