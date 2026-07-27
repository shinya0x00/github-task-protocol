from __future__ import annotations

import unittest

from gtp.human_post import SECTIONS, validate_human_post


def body(target: str, *, technical: bool = False) -> str:
    parts = []
    for title in SECTIONS[target]:
        content = f"{title}について人が判断できる説明です。"
        if title == "決定事項":
            content = (
                "- 採用した方針: 既存の公開契約どおりに修正する。新しい設計判断は行わない。\n"
                "- 今回は採用しない案: none\n"
                "- 見直す条件: 既存契約と実際のbehaviorが衝突していることを再現した場合。\n"
                "- 根拠・履歴: none"
            )
        parts.append(f"## {title}\n\n{content}")
    if technical:
        parts.append("## 技術詳細\n\ncommitやtestの詳細です。")
    return "\n\n".join(parts) + "\n"


class HumanPostTests(unittest.TestCase):
    def assert_error(self, source: str, target: str, code: str) -> None:
        result = validate_human_post(source, target)
        self.assertFalse(result.valid)
        self.assertIn(code, [error["code"] for error in result.errors])

    def test_issue_and_pr_contracts_are_distinct_and_valid(self) -> None:
        for target in ("issue", "pr"):
            with self.subTest(target=target):
                result = validate_human_post(body(target, technical=True), target)
                self.assertTrue(result.valid, result.errors)
        self.assertIn("現在わかっていること", SECTIONS["issue"])
        self.assertIn("変更内容", SECTIONS["pr"])
        self.assertIn("利用者への影響", SECTIONS["pr"])
        self.assertNotIn("何が問題か", SECTIONS["pr"])

    def test_required_relationship_rejects_missing_duplicate_order_and_empty(self) -> None:
        valid = body("pr")
        self.assert_error(valid.replace("## ゴール\n\nゴールについて人が判断できる説明です。\n\n", ""), "pr", "missing_section")
        self.assert_error(valid + "\n## 目的\n\n重複です。\n", "pr", "duplicate_section")
        swapped = valid.replace("## 目的", "## TEMP", 1).replace("## ゴール", "## 目的", 1).replace("## TEMP", "## ゴール", 1)
        self.assert_error(swapped, "pr", "invalid_first_section")
        self.assert_error(valid.replace("## 現在地\n\n現在地について人が判断できる説明です。", "## 現在地"), "pr", "empty_section")

    def test_technical_details_are_optional_but_last(self) -> None:
        valid = body("issue")
        self.assertTrue(validate_human_post(valid, "issue").valid)
        misplaced = valid.replace("## ゴール", "## 技術詳細\n\n先行した技術情報です。\n\n## ゴール", 1)
        self.assert_error(misplaced, "issue", "invalid_technical_position")
        self.assert_error(valid + "\n## 技術詳細\n", "issue", "empty_section")

    def test_decision_record_requires_four_nonempty_unique_fields(self) -> None:
        valid = body("issue")
        for field in ("採用した方針", "今回は採用しない案", "見直す条件", "根拠・履歴"):
            with self.subTest(field=field):
                line = next(line for line in valid.splitlines() if line.startswith(f"- {field}:"))
                self.assert_error(valid.replace(line + "\n", ""), "issue", "missing_decision_field")
                self.assert_error(valid.replace(line, f"- {field}:"), "issue", "empty_decision_field")
                self.assert_error(valid.replace(line, f"{line}\n{line}"), "issue", "duplicate_decision_field")

    def test_decision_reference_is_none_or_fixed_github_permalink(self) -> None:
        valid = body("issue")
        none = "- 根拠・履歴: none"
        comment = "https://github.com/example/project/issues/7#issuecomment-123"
        blob = "https://github.com/example/project/blob/0123456789abcdef0123456789abcdef01234567/DESIGN.md"
        for references in (comment, blob, f"{comment}、{blob}"):
            with self.subTest(references=references):
                result = validate_human_post(valid.replace(none, f"- 根拠・履歴: {references}"), "issue")
                self.assertTrue(result.valid, result.errors)
        self.assert_error(valid.replace(none, "- 根拠・履歴: https://github.com/example/project/issues/7"), "issue", "invalid_decision_reference")
        self.assert_error(valid.replace(none, f"- 根拠・履歴: {blob}?raw=1"), "issue", "invalid_decision_reference")

    def test_decision_record_allows_explanation_without_judging_quality(self) -> None:
        source = body("issue").replace("- 採用した方針:", "判断の背景です。\n\n- 採用した方針:")
        result = validate_human_post(source, "issue")
        self.assertTrue(result.valid, result.errors)

    def test_fenced_and_commented_headings_cannot_satisfy_contract(self) -> None:
        source = (
            "```markdown\n" + body("issue") + "```\n"
            "<!--\n" + body("issue") + "-->\n"
        )
        result = validate_human_post(source, "issue")
        self.assertFalse(result.valid)
        self.assertEqual("invalid_first_section", result.errors[0]["code"])
        self.assertIn("missing_section", [error["code"] for error in result.errors])

    def test_contract_does_not_require_language_issue_or_gtp_record(self) -> None:
        source = body("pr").replace("について人が判断できる説明です。", " section is complete.")
        result = validate_human_post(source, "pr")
        self.assertTrue(result.valid, result.errors)
        self.assertNotIn("Issue", source)
        self.assertNotIn("gtp-record", source)


if __name__ == "__main__":
    unittest.main()
