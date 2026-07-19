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
        source = (FIXTURES / "start-valid.md").read_text().replace(
            "<!-- gtp-record:v1 -->", "<!-- gtp-record:v2 -->"
        )
        result = classify_carrier(source)
        self.assertFalse(result.recognized)

    def test_exact_marker_with_malformed_json_is_invalid(self) -> None:
        source = (FIXTURES / "start-valid.md").read_text()
        start = source.index("```json\n") + len("```json\n")
        end = source.index("\n```", start)
        result = classify_carrier(source[:start] + "{" + source[end:])
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

    def test_marker_must_be_first_nonblank_line(self) -> None:
        source = "unexpected\n" + (FIXTURES / "start-valid.md").read_text()
        result = classify_carrier(source)
        self.assertTrue(result.recognized)
        self.assertFalse(result.schema_valid)
        self.assertEqual("invalid_marker_position", result.errors[0]["code"])

    def test_summary_is_one_clean_line(self) -> None:
        source = (FIXTURES / "start-valid.md").read_text()
        missing = source.replace("実装branchで作業を開始します\n", "")
        self.assertFalse(classify_carrier(missing).schema_valid)

        multiple = source.replace(
            "実装branchで作業を開始します\n",
            "実装branchで作業を開始します\n追加の要約\n",
        )
        self.assertFalse(classify_carrier(multiple).schema_valid)

        whitespace = source.replace(
            "実装branchで作業を開始します",
            " 実装branchで作業を開始します ",
        )
        result = classify_carrier(whitespace)
        self.assertFalse(result.schema_valid)
        self.assertEqual("invalid_summary", result.errors[0]["code"])

    def test_details_wrapper_is_exact(self) -> None:
        source = (FIXTURES / "start-valid.md").read_text().replace(
            "<details><summary>記録(JSON)</summary>",
            "<details><summary>JSON</summary>",
        )
        result = classify_carrier(source)
        self.assertFalse(result.schema_valid)
        self.assertEqual("invalid_details_wrapper", result.errors[0]["code"])

    def test_json_fence_is_exact_and_single(self) -> None:
        source = (FIXTURES / "start-valid.md").read_text()
        missing = source.replace("```json", "```JSON")
        self.assertEqual(
            "invalid_json_fence", classify_carrier(missing).errors[0]["code"]
        )

        multiple = source.replace("```json", "```json\n{}\n```\n\n```json", 1)
        self.assertEqual(
            "invalid_json_fence", classify_carrier(multiple).errors[0]["code"]
        )

        unclosed = source.replace("\n```\n\n</details>", "\n\n</details>")
        self.assertEqual(
            "invalid_json_fence", classify_carrier(unclosed).errors[0]["code"]
        )

    def test_spacing_is_canonical(self) -> None:
        source = (FIXTURES / "start-valid.md").read_text().replace(
            "実装branchで作業を開始します\n\n<details>",
            "実装branchで作業を開始します\n\n\n<details>",
        )
        result = classify_carrier(source)
        self.assertFalse(result.schema_valid)
        self.assertEqual("invalid_carrier_spacing", result.errors[0]["code"])

    def test_schema_invalid_carrier_never_returns_a_record(self) -> None:
        source = (FIXTURES / "start-valid.md").read_text().replace(
            '"branch": "codex/gtp-walking-skeleton"',
            '"branch": "codex/gtp-walking-skeleton",\n  "unknown": true',
        )
        result = classify_carrier(source)
        self.assertTrue(result.recognized)
        self.assertFalse(result.schema_valid)
        self.assertIsNone(result.record)
        self.assertIn(
            {"code": "unknown_field", "path": "$.unknown"}, result.errors
        )


if __name__ == "__main__":
    unittest.main()
