from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import unittest

from gtp.human_post import validate_human_post


FIXTURES = Path(__file__).parent / "fixtures" / "human-posts"
REQUIRED_HEADINGS = (
    "何が起きたか",
    "何が変わるか",
    "何は変わらないか",
    "人間が次に判断すること",
)
INTERNAL_TERMS = (
    "GTP Record",
    "Carrier",
    "Exact Marker",
    "strict JSON",
    "closed schema",
    "Done Condition",
    "Done Claim",
    "Contract",
    "Start",
    "Done",
    "Stop",
    "Evidence",
    "Record",
    "Records",
    "scope",
    "binding",
    "head_sha",
    "schema_valid",
    "halt",
    "halt_reason",
    "terminal_violation",
    "invalid_record",
    "invalid_binding",
    "stale_evidence",
    "Acquisition Error",
)
KNOWN_COMMANDS = (
    "git",
    "gh",
    "gtp",
    "python",
    "python3",
    "pytest",
    "unittest",
    "uv",
    "uvx",
    "pip",
    "npm",
    "pnpm",
    "yarn",
    "node",
    "cargo",
    "go",
    "make",
    "curl",
    "wget",
    "docker",
    "kubectl",
)


def render_post(
    *,
    first: str = "投稿前の確認が、人の読む本文には適用されていませんでした。",
    second: str = "人の読む本文にも、投稿前の確認を適用します。",
    third: str = "内容が正しいかどうかは、引き続き人が判断します。",
    fourth: str = "この確認方法を採用するか判断してください。",
    technical: str | None = None,
) -> str:
    bodies = (first, second, third, fourth)
    chunks = [
        f"## {heading}\n\n{body}" for heading, body in zip(REQUIRED_HEADINGS, bodies)
    ]
    if technical is not None:
        chunks.append(f"## 技術的な検証情報\n\n{technical}")
    return "\n\n".join(chunks) + "\n"


class HumanPostTests(unittest.TestCase):
    def assert_rejected_with(self, body: str, code: str) -> None:
        result = validate_human_post(body, "pr")
        self.assertFalse(result.valid)
        self.assertIn(code, [error["code"] for error in result.errors])

    def test_valid_fixture_accepts_all_human_targets(self) -> None:
        body = (FIXTURES / "valid.md").read_text(encoding="utf-8")
        for target in ("issue", "pr", "comment"):
            with self.subTest(target=target):
                result = validate_human_post(body, target)
                self.assertEqual(target, result.target)
                self.assertTrue(result.valid, result.errors)
                self.assertEqual([], result.errors)

    def test_exact_pr117_body_is_rejected(self) -> None:
        source = (FIXTURES / "pr117.md").read_bytes()
        self.assertEqual(
            "b471e60d4d77f10fe33582217b0414d47268163e3a83714266c1a4abdd4d92e5",
            sha256(source).hexdigest(),
        )
        body = source.decode("utf-8")
        result = validate_human_post(body, "pr")
        self.assertFalse(result.valid)
        self.assertIn("invalid_first_heading", [error["code"] for error in result.errors])

    def test_first_nonblank_line_must_be_the_exact_first_heading(self) -> None:
        valid = render_post()
        for name, body in (
            ("preamble", "説明です。\n\n" + valid),
            ("h1", valid.replace("## 何が起きたか", "# 何が起きたか", 1)),
            ("trailing space", valid.replace("## 何が起きたか", "## 何が起きたか ", 1)),
        ):
            with self.subTest(name=name):
                self.assert_rejected_with(body, "invalid_first_heading")

        result = validate_human_post("\n \n\t\n" + valid, "issue")
        self.assertTrue(result.valid, result.errors)

    def test_html_comments_do_not_supply_or_obscure_visible_structure(self) -> None:
        comment_before_heading = (
            "<!--\n内部の投稿メタデータです。\n## 何が変わるか\n-->\n\n"
            + render_post()
        )
        result = validate_human_post(comment_before_heading, "issue")
        self.assertTrue(result.valid, result.errors)

        comment_only_body = render_post(second="<!-- 内部メモだけです。 -->")
        self.assert_rejected_with(comment_only_body, "empty_section")

        visible_third = (
            "## 何は変わらないか\n\n"
            "内容が正しいかどうかは、引き続き人が判断します。"
        )
        hidden_heading = render_post().replace(
            visible_third,
            f"<!--\n{visible_third}\n-->",
            1,
        )
        self.assert_rejected_with(hidden_heading, "missing_section")

        synthesized_heading = render_post().replace(
            "## 何が変わるか",
            "#<!-- 内部メモ --># 何が変わるか",
            1,
        )
        self.assert_rejected_with(synthesized_heading, "missing_section")

    def test_html_comment_literals_inside_inline_code_do_not_hide_later_sections(self) -> None:
        for literal in ("`<!--`", "`<!-- 内部メモ -->`"):
            with self.subTest(literal=literal):
                result = validate_human_post(
                    render_post(
                        first=f"記号{literal}について日本語で状況を説明します。"
                    ),
                    "comment",
                )
                self.assertTrue(result.valid, result.errors)

    def test_html_comments_preserve_top_level_and_inline_hidden_content(self) -> None:
        top_level = validate_human_post(
            "<!--\ngit status\n-->\n" + render_post(),
            "issue",
        )
        self.assertTrue(top_level.valid, top_level.errors)

        inline = validate_human_post(
            render_post(
                first=(
                    "投稿前<!-- git status -->の確認が、"
                    "人の読む本文には適用されていませんでした。"
                )
            ),
            "comment",
        )
        self.assertTrue(inline.valid, inline.errors)

    def test_line_start_html_comment_ends_at_its_list_container_boundary(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        boundaries = {
            "bullet sibling": "- <!--\n- git status\n-->",
            "ordered sibling": "1. <!--\n2. git status\n-->",
            "quoted list sibling": "> - <!--\n> - git status\n> -->",
            "list exit": "- <!--\ngit status\n-->",
        }
        for name, comment in boundaries.items():
            with self.subTest(name=name):
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{first_body}\n{comment}\n{second_heading}",
                    1,
                )
                self.assert_rejected_with(
                    body,
                    "unseparated_technical_details",
                )

    def test_line_start_html_comment_hides_same_item_indented_content(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        continuations = {
            "bullet": "- <!--\n  git status\n  -->",
            "ordered": "1. <!--\n   git status\n   -->",
            "quoted list": "> - <!--\n>   git status\n>   -->",
        }
        for name, comment in continuations.items():
            with self.subTest(name=name):
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{first_body}\n{comment}\n{second_heading}",
                    1,
                )
                result = validate_human_post(body, "issue")
                self.assertTrue(result.valid, result.errors)

    def test_mid_line_comment_ends_at_list_sibling_or_explicit_list_exit(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        boundaries = {
            "bullet sibling": "- 項目です。 <!--\n- git status\n-->",
            "ordered sibling": "1. 項目です。 <!--\n2. git status\n-->",
            "quoted list sibling": "> - 項目です。 <!--\n> - git status\n> -->",
            "list exit after blank": "- 項目です。 <!--\n\ngit status\n-->",
        }
        for name, comment in boundaries.items():
            with self.subTest(name=name):
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{first_body}\n{comment}\n{second_heading}",
                    1,
                )
                self.assert_rejected_with(
                    body,
                    "unseparated_technical_details",
                )

    def test_mid_line_comment_hides_unindented_lazy_list_continuation(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        comment = "- 項目です。 <!--\ngit status\n-->"
        body = render_post().replace(
            f"{first_body}\n\n{second_heading}",
            f"{first_body}\n{comment}\n{second_heading}",
            1,
        )
        result = validate_human_post(body, "issue")
        self.assertTrue(result.valid, result.errors)

    def test_mid_line_comment_uses_top_level_paragraph_scope(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        terminators = {
            "blank": f"{first_body} <!--\n\ngit status\n-->",
            "atx heading": (
                f"{first_body} <!--\n"
                "### 補足\n"
                "git status\n"
                "-->"
            ),
        }
        for name, comment in terminators.items():
            with self.subTest(kind="paragraph end", name=name):
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{comment}\n{second_heading}",
                    1,
                )
                self.assert_rejected_with(
                    body,
                    "unseparated_technical_details",
                )

        soft_continuation = f"{first_body} <!--\ngit status\n-->"
        body = render_post().replace(
            f"{first_body}\n\n{second_heading}",
            f"{soft_continuation}\n{second_heading}",
            1,
        )
        result = validate_human_post(body, "issue")
        self.assertTrue(result.valid, result.errors)

    def test_mid_line_comment_uses_top_level_list_interrupt_rules(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"

        non_interrupts = {
            "ordered start two": "2. git status",
            "leading-zero start two": "02. git status",
            "empty bullet": "*\ngit status",
            "empty ordered item": "1.\ngit status",
        }
        for name, continuation in non_interrupts.items():
            with self.subTest(kind="hidden", name=name):
                comment = f"{first_body} <!--\n{continuation}\n-->"
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{comment}\n{second_heading}",
                    1,
                )
                result = validate_human_post(body, "issue")
                self.assertTrue(result.valid, result.errors)

        interrupts = {
            "ordered start one": "1. git status",
            "leading-zero start one": "01. git status",
            "nonempty bullet": "- git status",
            "setext one hyphen": "-\ngit status",
            "setext two hyphens": "--\ngit status",
        }
        for name, continuation in interrupts.items():
            with self.subTest(kind="visible", name=name):
                comment = f"{first_body} <!--\n{continuation}\n-->"
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{comment}\n{second_heading}",
                    1,
                )
                self.assert_rejected_with(
                    body,
                    "unseparated_technical_details",
                )

    def test_mid_line_comment_uses_gfm_table_header_and_delimiter_boundary(self) -> None:
        second_heading = "## 何が変わるか"
        no_header = (
            "投稿前の確認が、人の読む本文には適用されていませんでした。 <!--\n"
            "| --- |\n"
            "git status\n"
            "-->"
        )
        body = render_post().replace(
            "投稿前の確認が、人の読む本文には適用されていませんでした。\n\n"
            f"{second_heading}",
            f"{no_header}\n{second_heading}",
            1,
        )
        result = validate_human_post(body, "issue")
        self.assertTrue(result.valid, result.errors)

        matching_header = (
            "| 今回の状況を日本語で詳しく説明します <!-- |\n"
            "| --- |\n"
            "git status\n"
            "-->"
        )
        body = render_post().replace(
            "投稿前の確認が、人の読む本文には適用されていませんでした。\n\n"
            f"{second_heading}",
            f"{matching_header}\n{second_heading}",
            1,
        )
        self.assert_rejected_with(body, "unseparated_technical_details")

    def test_inline_comment_on_atx_heading_does_not_cross_the_heading_line(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        headings = {
            "top level": "### 補足 <!--\ngit status\n-->",
            "quoted": "> ### 補足 <!--\n> git status\n> -->",
        }
        for name, heading in headings.items():
            with self.subTest(name=name):
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{first_body}\n{heading}\n{second_heading}",
                    1,
                )
                self.assert_rejected_with(
                    body,
                    "unseparated_technical_details",
                )

    def test_inline_comment_in_gfm_table_header_does_not_hide_next_row(self) -> None:
        body = render_post(
            second=(
                "| 見出し <!-- |\n"
                "| --- |\n"
                "| git status |"
            )
        )
        self.assert_rejected_with(body, "unseparated_technical_details")

    def test_html_comment_opener_inside_indented_code_is_literal(self) -> None:
        body = render_post(
            second=(
                "    <!--\n"
                "    git status"
            )
        )
        self.assert_rejected_with(body, "unseparated_technical_details")

    def test_all_required_sections_are_present_once_in_order_and_nonempty(self) -> None:
        valid = render_post()

        missing = valid.replace(
            "## 何は変わらないか\n\n内容が正しいかどうかは、引き続き人が判断します。\n\n",
            "",
        )
        self.assert_rejected_with(missing, "missing_section")

        duplicate = valid.replace(
            "## 何は変わらないか",
            "## 何が変わるか\n\nもう一つの説明です。\n\n## 何は変わらないか",
            1,
        )
        self.assert_rejected_with(duplicate, "duplicate_section")

        second = "## 何が変わるか\n\n人の読む本文にも、投稿前の確認を適用します。"
        third = "## 何は変わらないか\n\n内容が正しいかどうかは、引き続き人が判断します。"
        out_of_order = valid.replace(f"{second}\n\n{third}", f"{third}\n\n{second}")
        self.assert_rejected_with(out_of_order, "invalid_section_order")

        empty = render_post(second="")
        self.assert_rejected_with(empty, "empty_section")

    def test_first_section_requires_at_least_as_many_japanese_as_latin_chars(self) -> None:
        equal = validate_human_post(render_post(first="abc あいう"), "comment")
        self.assertTrue(equal.valid, equal.errors)

        self.assert_rejected_with(render_post(first="abcd あいう"), "english_lead")
        self.assert_rejected_with(render_post(first="12345"), "english_lead")

    def test_each_fixed_internal_term_accepts_an_immediate_japanese_explanation(self) -> None:
        for term in INTERNAL_TERMS:
            with self.subTest(term=term):
                result = validate_human_post(
                    render_post(
                        first=(
                            f"今回の投稿では{term}（内部の用語）が関係しました。"
                            "人が読むために日本語で状況と影響を詳しく説明します。"
                        )
                    ),
                    "issue",
                )
                self.assertTrue(result.valid, result.errors)

    def test_each_fixed_internal_term_rejects_an_unexplained_first_occurrence(self) -> None:
        for term in INTERNAL_TERMS:
            with self.subTest(term=term):
                self.assert_rejected_with(
                    render_post(
                        first=(
                            f"今回の投稿では{term}が関係しました。"
                            "人が読むために日本語で状況と影響を詳しく説明します。"
                        )
                    ),
                    "unexplained_internal_term",
                )

    def test_hyphenated_internal_terms_cannot_bypass_explanation(self) -> None:
        for term in ("Carrier-based", "Record-based", "GTP Record-based"):
            with self.subTest(term=term):
                self.assert_rejected_with(
                    render_post(
                        first=(
                            f"今回の投稿では{term}が関係しました。"
                            "人が読むために日本語で状況と影響を詳しく説明します。"
                        )
                    ),
                    "unexplained_internal_term",
                )

    def test_internal_term_explanation_is_immediate_full_width_and_japanese(self) -> None:
        for name, text in (
            ("ascii parentheses", "Carrier(内部の用語)"),
            ("intervening space", "Carrier （内部の用語）"),
            ("inline code with space", "`Carrier` （内部の用語）"),
            ("stray closing backtick", "Carrier`（内部の用語）"),
            ("unmatched opening backtick", "`Carrier（内部の用語）"),
            ("double opening single closing", "``Carrier`（内部の用語）"),
            ("single opening double closing", "`Carrier``（内部の用語）"),
            ("odd escaped opening", "\\`Carrier`（内部の用語）"),
            ("prior span closing tick", "`abc`Carrier`（内部の用語）"),
            (
                "two-tick run tail is not a closer",
                "`abc``Carrier`（内部の用語）",
            ),
            ("empty", "Carrier（）"),
            ("latin only", "Carrier（internal term）"),
        ):
            with self.subTest(name=name):
                self.assert_rejected_with(
                    render_post(
                        first=(
                            f"今回の投稿では{text}が関係しました。"
                            "人が読むために日本語で状況と影響を詳しく説明します。"
                        )
                    ),
                    "unexplained_internal_term",
                )

        inline_code = validate_human_post(
            render_post(
                first=(
                    "今回の投稿では`Carrier`（内部の用語）が関係しました。"
                    "人が読むために日本語で状況と影響を詳しく説明します。"
                )
            ),
            "pr",
        )
        self.assertTrue(inline_code.valid, inline_code.errors)

        even_escaped_opening = validate_human_post(
            render_post(
                first=(
                    "今回の投稿では\\\\`Carrier`（内部の用語）が関係しました。"
                    "人が読むために日本語で状況と影響を詳しく説明します。"
                )
            ),
            "pr",
        )
        self.assertTrue(even_escaped_opening.valid, even_escaped_opening.errors)

        escaped_then_valid_span = validate_human_post(
            render_post(
                first=(
                    "今回は\\`という記号の後で`Carrier`（内部の用語）を使います。"
                    "人が読むために日本語で状況と影響を詳しく説明します。"
                )
            ),
            "pr",
        )
        self.assertTrue(escaped_then_valid_span.valid, escaped_then_valid_span.errors)

        first_unexplained = render_post(
            first=(
                "Carrierを使い、後でCarrier（内部の用語）を説明します。"
                "人が読むために日本語で状況と影響を詳しく説明します。"
            )
        )
        self.assert_rejected_with(first_unexplained, "unexplained_internal_term")

        explained_once = validate_human_post(
            render_post(
                first=(
                    "Carrier（内部の用語）を説明し、その後はCarrierを再び使います。"
                    "人が読むために日本語で状況と影響を詳しく説明します。"
                )
            ),
            "pr",
        )
        self.assertTrue(explained_once.valid, explained_once.errors)

    def test_longest_internal_term_match_does_not_explain_a_shorter_term(self) -> None:
        longest_only = validate_human_post(
            render_post(
                first=(
                    "GTP Record（作業の記録）を確認します。"
                    "人が読むために日本語で状況と影響を詳しく説明します。"
                )
            ),
            "pr",
        )
        self.assertTrue(longest_only.valid, longest_only.errors)

        separate_shorter_term = render_post(
            first=(
                "GTP Record（作業の記録）を確認し、Recordも確認します。"
                "人が読むために日本語で状況と影響を詳しく説明します。"
            )
        )
        self.assert_rejected_with(separate_shorter_term, "unexplained_internal_term")

    def test_internal_term_rule_is_limited_to_the_first_required_section(self) -> None:
        result = validate_human_post(
            render_post(
                second="Carrierを含む変更内容を説明します。",
                third="Recordを含む対象外を説明します。",
                fourth="Done Claimを読んで判断してください。",
                technical="GTP Record",
            ),
            "issue",
        )
        self.assertTrue(result.valid, result.errors)

    def test_known_commands_are_rejected_at_the_first_prose_line(self) -> None:
        for command in KNOWN_COMMANDS:
            with self.subTest(command=command):
                self.assert_rejected_with(
                    render_post(
                        first=f"{command} status を実行した結果を日本語で説明します。"
                    ),
                    "command_lead",
                )

    def test_sha_prompt_backtick_and_markdown_prefix_leads_are_rejected(self) -> None:
        leads = (
            "abcdef0 から始まる変更について日本語で説明します。",
            "ABCDEF0123456789ABCDEF0123456789ABCDEF01 から始まる変更です。",
            "$ echo test の前に日本語の結論を書く必要があります。",
            "% echo test の前に日本語の結論を書く必要があります。",
            "`python3 -m unittest` を最初に書かず日本語で説明します。",
            "> git status の前に日本語の結論を書く必要があります。",
            ">git status の前に日本語の結論を書く必要があります。",
            ">   git status の前に日本語の結論を書く必要があります。",
            ">   - git status の前に日本語の結論を書く必要があります。",
            "1) git status の前に日本語の結論を書く必要があります。",
            "- git status の前に日本語の結論を書く必要があります。",
            "> - `pytest` の前に日本語の結論を書く必要があります。",
            "> 1) - git status の前に日本語の結論を書く必要があります。",
            "- [ ] git status の前に日本語の結論を書く必要があります。",
            "- [x] git status の前に日本語の結論を書く必要があります。",
            "- [X] git status の前に日本語の結論を書く必要があります。",
        )
        for lead in leads:
            with self.subTest(lead=lead):
                self.assert_rejected_with(render_post(first=lead), "command_lead")

    def test_command_lead_boundaries_do_not_reject_near_matches(self) -> None:
        for lead in (
            "abcdef という短い識別子から状況を日本語で説明します。",
            "Git status という表現を含む状況を日本語で説明します。",
            "gitignore の設定について日本語で状況を説明します。",
            "git-lfs という表記について日本語で状況を説明します。",
            "abcdef0xyz という識別子について日本語で状況を説明します。",
            "$variable の意味について日本語で状況を説明します。",
        ):
            with self.subTest(lead=lead):
                result = validate_human_post(render_post(first=lead), "comment")
                self.assertTrue(result.valid, result.errors)

    def test_commonmark_ordered_list_prefix_is_limited_to_nine_digits(self) -> None:
        nine_digits = render_post(
            second="変更内容を説明します。\n\n123456789) git status"
        )
        self.assert_rejected_with(nine_digits, "unseparated_technical_details")

        ten_digits = validate_human_post(
            render_post(second="変更内容を説明します。\n\n1234567890) git status"),
            "comment",
        )
        self.assertTrue(ten_digits.valid, ten_digits.errors)

    def test_task_list_commands_are_technical_outside_the_first_lead_too(self) -> None:
        for marker in ("[ ]", "[x]", "[X]"):
            with self.subTest(marker=marker):
                self.assert_rejected_with(
                    render_post(
                        second=(
                            "変更内容を説明します。\n\n"
                            f"- {marker} git status"
                        )
                    ),
                    "unseparated_technical_details",
                )

    def test_technical_signals_are_rejected_outside_the_technical_section(self) -> None:
        sha = "0123456789abcdef0123456789abcdef01234567"
        signals = (
            "```text\n成功\n```",
            sha,
            "- git diff --check",
            "stdout: success",
            "stderr: none",
            "exit code: 0",
            "検証結果: 成功",
            "実行結果: 成功",
            "https://github.com/o/r/runs/123",
            "[結果](https://github.com/o/r/runs/123)",
            "`https://github.com/o/r/runs/123`",
            f"https://github.com/o/r/blob/{sha}/src/a.py",
        )
        for signal in signals:
            with self.subTest(signal=signal):
                self.assert_rejected_with(
                    render_post(second=f"変更内容を説明します。\n\n{signal}"),
                    "unseparated_technical_details",
                )

    def test_output_label_requires_a_token_boundary(self) -> None:
        result = validate_human_post(
            render_post(second="変更内容を説明します。\n\nmystdout:value"),
            "comment",
        )
        self.assertTrue(result.valid, result.errors)

    def test_tilde_code_fence_requires_the_technical_section(self) -> None:
        fence = "~~~text\n成功\n~~~"
        self.assert_rejected_with(
            render_post(second=f"変更内容を説明します。\n\n{fence}"),
            "unseparated_technical_details",
        )

        separated = validate_human_post(
            render_post(technical=fence),
            "comment",
        )
        self.assertTrue(separated.valid, separated.errors)

    def test_quoted_code_fences_are_technical_signals(self) -> None:
        for fence in (
            "> ```text\n> 成功\n> ```",
            ">~~~text\n>成功\n>~~~",
            ">   ```text\n>   成功\n>   ```",
            ">   ~~~text\n>   成功\n>   ~~~",
        ):
            with self.subTest(fence=fence):
                self.assert_rejected_with(
                    render_post(second=f"変更内容を説明します。\n\n{fence}"),
                    "unseparated_technical_details",
                )

    def test_unclosed_html_comment_inside_quoted_technical_fence_stays_literal(self) -> None:
        technical = "> ```text\n> <!--\n> ```"
        body = render_post(technical=technical) + "\n## Appendix\n\ngit status\n"
        self.assert_rejected_with(body, "unseparated_technical_details")

    def test_short_sha_and_moving_blob_url_are_not_technical_signals(self) -> None:
        for detail in (
            "0123456789abcdef0123456789abcdef0123456",
            "https://github.com/o/r/blob/main/src/a.py",
            "https://github.com/o/r/runs/123abc",
            "https://github.com/o/r/runs/123/extra",
            "https://github.com/o/r/runs/123%2Fextra",
            "https://github.com/o/r/runs/123?check=1",
            "https://github.com/o/r/runs/123#step",
        ):
            with self.subTest(detail=detail):
                result = validate_human_post(
                    render_post(second=f"変更内容を説明します。\n\n{detail}"), "pr"
                )
                self.assertTrue(result.valid, result.errors)

    def test_runs_url_is_detected_when_followed_by_japanese_prose(self) -> None:
        self.assert_rejected_with(
            render_post(
                second=(
                    "変更内容を説明します。\n\n"
                    "https://github.com/o/r/runs/123です"
                )
            ),
            "unseparated_technical_details",
        )

    def test_runs_url_ascii_punctuation_separator_and_continuation_boundaries(self) -> None:
        url = "https://github.com/o/r/runs/123"
        for suffix in (".", ",", "; 続き", ": 続き", "! 続き", "? 続き"):
            with self.subTest(kind="separator", suffix=suffix):
                self.assert_rejected_with(
                    render_post(
                        second=f"変更内容を説明します。\n\n{url}{suffix}"
                    ),
                    "unseparated_technical_details",
                )

        for suffix in (".foo", ",foo", ";foo", ":foo", "!foo", "?foo"):
            with self.subTest(kind="continuation", suffix=suffix):
                result = validate_human_post(
                    render_post(
                        second=f"変更内容を説明します。\n\n{url}{suffix}"
                    ),
                    "pr",
                )
                self.assertTrue(result.valid, result.errors)

    def test_required_heading_literals_inside_a_technical_fence_are_not_sections(self) -> None:
        sample = "```markdown\n" + "\n".join(
            f"## {heading}" for heading in REQUIRED_HEADINGS
        ) + "\n```"
        result = validate_human_post(render_post(technical=sample), "pr")
        self.assertTrue(result.valid, result.errors)

    def test_html_comments_inside_a_technical_fence_remain_code_literals(self) -> None:
        sample = (
            "```html\n"
            "<!--\n"
            "## 何が起きたか\n"
            "-->\n"
            "```"
        )
        result = validate_human_post(render_post(technical=sample), "issue")
        self.assertTrue(result.valid, result.errors)

    def test_technical_section_must_follow_all_four_required_sections(self) -> None:
        valid = render_post()
        fourth = "## 人間が次に判断すること"
        misplaced = valid.replace(
            fourth,
            "## 技術的な検証情報\n\n`git status`\n\n" + fourth,
            1,
        )
        self.assert_rejected_with(misplaced, "invalid_technical_section_position")

    def test_invalid_fence_openers_cannot_hide_duplicate_required_headings(self) -> None:
        for opener in ("```text`bad", "    ```text", "-     ```text"):
            with self.subTest(opener=opener):
                body = render_post(
                    technical=(
                        f"{opener}\n"
                        "## 何が起きたか\n"
                        "この見出しはcodeではありません。"
                    )
                )
                self.assert_rejected_with(body, "duplicate_section")

    def test_top_level_fence_is_not_closed_by_a_blockquoted_fence_line(self) -> None:
        sample = (
            "```text\n"
            "> ```\n"
            "## 何が起きたか\n"
            "```"
        )
        result = validate_human_post(render_post(technical=sample), "pr")
        self.assertTrue(result.valid, result.errors)

    def test_list_fence_close_does_not_hide_a_later_top_level_heading(self) -> None:
        sample = (
            "- ```text\n"
            "  見本です。\n"
            "  ```\n"
            "## 何が起きたか\n"
            "この見出しはcodeではありません。"
        )
        self.assert_rejected_with(
            render_post(technical=sample),
            "duplicate_section",
        )

    def test_nested_quote_list_fence_keeps_quote_only_continuations_literal(self) -> None:
        containers = {
            "quote then list": (
                "> - ```html\n"
                ">   <!--\n"
                ">   ```"
            ),
            "list then quote": (
                "- > ```html\n"
                "  > <!--\n"
                "  > ``` "
            ),
        }
        for name, fence in containers.items():
            with self.subTest(name=name):
                sample = (
                    f"{fence}\n"
                    "## 何が起きたか\n"
                    "この見出しはcodeではありません。"
                )
                self.assert_rejected_with(
                    render_post(technical=sample),
                    "duplicate_section",
                )

    def test_raw_html_blocks_cannot_supply_a_required_section(self) -> None:
        visible_third = (
            "## 何は変わらないか\n\n"
            "内容が正しいかどうかは、引き続き人が判断します。"
        )
        for tag in ("pre", "script", "style", "textarea"):
            with self.subTest(tag=tag):
                raw_html = render_post().replace(
                    visible_third,
                    f"<{tag}>\n{visible_third}\n</{tag}>",
                    1,
                )
                self.assert_rejected_with(raw_html, "missing_section")

    def test_container_raw_html_only_required_body_is_empty(self) -> None:
        bodies = {
            "quote": "> <div>\n> </div>\n>",
            "list": "- <div>\n  </div>\n  ",
        }
        for field in ("first", "second", "third", "fourth"):
            for container, body in bodies.items():
                with self.subTest(field=field, container=container):
                    self.assert_rejected_with(
                        render_post(**{field: body}),
                        "empty_section",
                    )

    def test_container_raw_html_variants_do_not_supply_visible_prose(self) -> None:
        bodies = {
            "quoted type one": "> <pre>\n> ## 隠れた見出し\n> </pre>",
            "listed type seven": "- <span>\n  ## 隠れた見出し\n  ",
            "quoted type seven": "> <span>\n> ## 隠れた見出し\n>",
            "listed cdata": "- <![CDATA[\n  ## 隠れた見出し\n  ]]>",
            "quoted cdata": "> <![CDATA[\n> ## 隠れた見出し\n> ]]>",
        }
        for name, body in bodies.items():
            with self.subTest(name=name):
                self.assert_rejected_with(
                    render_post(second=body),
                    "empty_section",
                )

    def test_unclosed_type_one_raw_html_ends_when_its_container_ends(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        containers = {
            "quote": "> <pre>\n> 隠れた内容です。",
            "list": "- <pre>\n  隠れた内容です。",
        }
        for name, raw_html in containers.items():
            with self.subTest(name=name):
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{first_body}\n{raw_html}\n{second_heading}",
                    1,
                )
                result = validate_human_post(body, "issue")
                self.assertTrue(result.valid, result.errors)

    def test_type_one_raw_html_inherits_prior_list_continuation_container(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        continuations = {
            "unordered unclosed": (
                "- リスト項目です。\n"
                "  <pre>\n"
                f"  {second_heading}\n"
                "  隠れた内容です。"
            ),
            "unordered closed": (
                "- リスト項目です。\n"
                "  <pre>\n"
                f"  {second_heading}\n"
                "  隠れた内容です。\n"
                "  </pre>"
            ),
            "ordered unclosed": (
                "1. リスト項目です。\n"
                "   <pre>\n"
                f"   {second_heading}\n"
                "   隠れた内容です。"
            ),
            "quote then list": (
                "> - リスト項目です。\n"
                ">   <pre>\n"
                f">   {second_heading}\n"
                ">   隠れた内容です。"
            ),
            "list then quote": (
                "- > リスト項目です。\n"
                "  > <pre>\n"
                f"  > {second_heading}\n"
                "  > 隠れた内容です。"
            ),
        }
        for name, raw_html in continuations.items():
            with self.subTest(name=name):
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{first_body}\n{raw_html}\n{second_heading}",
                    1,
                )
                result = validate_human_post(body, "issue")
                self.assertTrue(result.valid, result.errors)

    def test_list_interrupt_rules_control_raw_continuation_visibility(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"

        def with_list(source: str, *, blank: bool = False) -> str:
            separator = "\n\n" if blank else "\n"
            return render_post().replace(
                f"{first_body}\n\n{second_heading}",
                f"{first_body}{separator}{source}\n{second_heading}",
                1,
            )

        active_paragraph_non_interrupts = {
            "ordered start two": (
                "2. リスト項目です。\n"
                "    <pre>\n"
                "    git status"
            ),
            "empty bullet": (
                "-\n"
                "    <pre>\n"
                "    git status"
            ),
            "empty ordered": (
                "1.\n"
                "    <pre>\n"
                "    git status"
            ),
        }
        for name, source in active_paragraph_non_interrupts.items():
            with self.subTest(kind="visible", name=name):
                self.assert_rejected_with(
                    with_list(source),
                    "unseparated_technical_details",
                )

        list_interrupts = {
            "ordered start one": (
                "1. リスト項目です。\n"
                "    <pre>\n"
                "    git status"
            ),
            "nonempty bullet": (
                "- リスト項目です。\n"
                "    <pre>\n"
                "    git status"
            ),
        }
        for name, source in list_interrupts.items():
            with self.subTest(kind="paragraph interrupt", name=name):
                result = validate_human_post(with_list(source), "issue")
                self.assertTrue(result.valid, result.errors)

        arbitrary_start = (
            "7. リスト項目です。\n"
            "    <pre>\n"
            "    git status"
        )
        result = validate_human_post(
            with_list(arbitrary_start, blank=True),
            "issue",
        )
        self.assertTrue(result.valid, result.errors)

    def test_leading_zero_ordered_markers_interrupt_only_when_numeric_start_is_one(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"

        def with_marker(marker: str, indent: int) -> str:
            source = (
                f"{marker} リスト項目です。\n"
                f"{' ' * indent}<pre>\n"
                f"{' ' * indent}git status"
            )
            return render_post().replace(
                f"{first_body}\n\n{second_heading}",
                f"{first_body}\n{source}\n{second_heading}",
                1,
            )

        numeric_one = (
            ("01.", 4),
            ("001)", 5),
            ("000000001.", 11),
        )
        for marker, indent in numeric_one:
            with self.subTest(kind="numeric one", marker=marker):
                result = validate_human_post(
                    with_marker(marker, indent),
                    "issue",
                )
                self.assertTrue(result.valid, result.errors)

        other_starts = (
            ("02.", 4),
            ("000000002)", 11),
        )
        for marker, indent in other_starts:
            with self.subTest(kind="numeric other", marker=marker):
                self.assert_rejected_with(
                    with_marker(marker, indent),
                    "unseparated_technical_details",
                )

    def test_tab_indented_list_continuations_preserve_raw_html_scope(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        continuations = {
            "unordered closed": (
                "- 日本語の項目です。\n"
                "\t<pre>\n"
                "\tCarrier\n"
                "\t</pre>"
            ),
            "unordered unclosed": (
                "- 日本語の項目です。\n"
                "\t<pre>\n"
                "\tCarrier"
            ),
            "mixed space tab": (
                "- 日本語の項目です。\n"
                " \t<pre>\n"
                " \tCarrier\n"
                " \t</pre>"
            ),
            "ordered": (
                "1. 日本語の項目です。\n"
                "\t<pre>\n"
                "\tCarrier\n"
                "\t</pre>"
            ),
            "quote then list": (
                "> - 日本語の項目です。\n"
                ">\t<pre>\n"
                ">\tCarrier\n"
                ">\t</pre>"
            ),
        }
        for name, raw_html in continuations.items():
            with self.subTest(name=name):
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{first_body}\n{raw_html}\n{second_heading}",
                    1,
                )
                result = validate_human_post(body, "issue")
                self.assertTrue(result.valid, result.errors)

    def test_ordered_list_siblings_preserve_delimiter_and_container_identity(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        same_delimiter = {
            "top level": (
                "1. 最初の項目です。\n"
                "2. 次の項目です。\n"
                "   <pre>\n"
                "   git status"
            ),
            "nested quote": (
                "> 1. 最初の項目です。\n"
                "> 2. 次の項目です。\n"
                ">    <pre>\n"
                ">    git status"
            ),
        }
        for name, raw_html in same_delimiter.items():
            with self.subTest(kind="same delimiter", name=name):
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{first_body}\n{raw_html}\n{second_heading}",
                    1,
                )
                result = validate_human_post(body, "issue")
                self.assertTrue(result.valid, result.errors)

        new_list_boundaries = {
            "bullet to ordered start above one": (
                "- 箇条書きの項目です。\n"
                "2. 番号付きの項目です。\n"
                "   <pre>\n"
                "   git status"
            ),
            "dot to parenthesis": (
                "1. 点区切りの項目です。\n"
                "2) 括弧区切りの項目です。\n"
                "   <pre>\n"
                "   git status"
            ),
            "indentation-only nested ordered sibling": (
                "- 1. 最初の入れ子項目です。\n"
                "  2. 次の入れ子項目です。\n"
                "     <pre>\n"
                "     git status"
            ),
        }
        for name, raw_html in new_list_boundaries.items():
            with self.subTest(kind="new list boundary", name=name):
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{first_body}\n{raw_html}\n{second_heading}",
                    1,
                )
                result = validate_human_post(body, "issue")
                self.assertTrue(result.valid, result.errors)

        unclosed_at_sibling = (
            "1. <pre>\n"
            "2. git status"
        )
        body = render_post().replace(
            f"{first_body}\n\n{second_heading}",
            f"{first_body}\n{unclosed_at_sibling}\n{second_heading}",
            1,
        )
        self.assert_rejected_with(body, "unseparated_technical_details")

        changed_delimiter = (
            "1. 最初の項目です。\n"
            "   <pre>\n"
            "   隠れた内容です。\n"
            "2) git status"
        )
        body = render_post().replace(
            f"{first_body}\n\n{second_heading}",
            f"{first_body}\n{changed_delimiter}\n{second_heading}",
            1,
        )
        self.assert_rejected_with(body, "unseparated_technical_details")

    def test_active_raw_html_ends_at_explicit_same_marker_siblings(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        siblings = {
            "ordered dot": "1. <pre>\n1. git status",
            "ordered parenthesis": "1) <pre>\n1) git status",
            "bullet": "- <pre>\n- git status",
            "quoted bullet": "> - <pre>\n> - git status",
        }
        for name, raw_html in siblings.items():
            with self.subTest(name=name):
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{first_body}\n{raw_html}\n{second_heading}",
                    1,
                )
                self.assert_rejected_with(
                    body,
                    "unseparated_technical_details",
                )

        nested_marker = (
            "- <pre>\n"
            "  - Carrier\n"
            "  </pre>"
        )
        body = render_post().replace(
            f"{first_body}\n\n{second_heading}",
            f"{first_body}\n{nested_marker}\n{second_heading}",
            1,
        )
        result = validate_human_post(body, "issue")
        self.assertTrue(result.valid, result.errors)

    def test_nested_child_raw_html_uses_the_child_item_depth(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        cases = {
            "bullet": (
                "- 親項目です。\n"
                "  - <pre>\n"
                "  - git status",
                "- 親項目です。\n"
                "  - <pre>\n"
                "    - git status\n"
                "    </pre>",
            ),
            "ordered": (
                "1. 親項目です。\n"
                "   1. <pre>\n"
                "   2. git status",
                "1. 親項目です。\n"
                "   1. <pre>\n"
                "      2. git status\n"
                "      </pre>",
            ),
            "quoted bullet": (
                "> - 親項目です。\n"
                ">   - <pre>\n"
                ">   - git status",
                "> - 親項目です。\n"
                ">   - <pre>\n"
                ">     - git status\n"
                ">     </pre>",
            ),
        }
        for name, (sibling, content) in cases.items():
            with self.subTest(name=name, kind="sibling"):
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{first_body}\n{sibling}\n{second_heading}",
                    1,
                )
                self.assert_rejected_with(
                    body,
                    "unseparated_technical_details",
                )

            with self.subTest(name=name, kind="raw content"):
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{first_body}\n{content}\n{second_heading}",
                    1,
                )
                result = validate_human_post(body, "issue")
                self.assertTrue(result.valid, result.errors)

    def test_quote_looking_lines_inside_list_owned_raw_html_are_literal(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        cases = {
            "bullet at content column": (
                "- <pre>\n"
                "  > git status\n"
                "  </pre>"
            ),
            "bullet after content column": (
                "- <pre>\n"
                "    > git status\n"
                "    </pre>"
            ),
            "ordered": (
                "1. <pre>\n"
                "   > git status\n"
                "   </pre>"
            ),
            "quote then list with nested quote": (
                "> - <pre>\n"
                ">   > git status\n"
                ">   </pre>"
            ),
        }
        for name, raw_html in cases.items():
            with self.subTest(name=name):
                body = render_post().replace(
                    f"{first_body}\n\n{second_heading}",
                    f"{first_body}\n{raw_html}\n{second_heading}",
                    1,
                )
                result = validate_human_post(body, "issue")
                self.assertTrue(result.valid, result.errors)

    def test_active_fence_ends_at_explicit_same_marker_siblings(self) -> None:
        siblings = {
            "ordered": "1. ```text\n1. 次の項目です。",
            "bullet": "- ```text\n- 次の項目です。",
            "quoted bullet": "> - ```text\n> - 次の項目です。",
        }
        for name, fence in siblings.items():
            with self.subTest(name=name):
                sample = (
                    f"{fence}\n"
                    "## 何が起きたか\n"
                    "この見出しはcodeではありません。"
                )
                self.assert_rejected_with(
                    render_post(technical=sample),
                    "duplicate_section",
                )

    def test_type_six_raw_html_blocks_cannot_supply_a_required_section(self) -> None:
        visible_third = (
            "## 何は変わらないか\n\n"
            "内容が正しいかどうかは、引き続き人が判断します。"
        )
        hidden_third = (
            "## 何は変わらないか\n"
            "内容が正しいかどうかは、引き続き人が判断します。"
        )
        for tag in ("div", "table", "details"):
            with self.subTest(tag=tag):
                raw_html = render_post().replace(
                    visible_third,
                    f"<{tag}>\n{hidden_third}\n</{tag}>",
                    1,
                )
                self.assert_rejected_with(raw_html, "missing_section")

    def test_raw_cdata_instruction_and_declaration_cannot_supply_a_section(self) -> None:
        visible_third = (
            "## 何は変わらないか\n\n"
            "内容が正しいかどうかは、引き続き人が判断します。"
        )
        hidden_third = (
            "## 何は変わらないか\n"
            "内容が正しいかどうかは、引き続き人が判断します。"
        )
        blocks = {
            "cdata": f"<![CDATA[\n{hidden_third}\n]]>",
            "processing instruction": f"<?check\n{hidden_third}\n?>",
            "declaration": f"<!DOCTYPE html\n{hidden_third}\n>",
        }
        for name, block in blocks.items():
            with self.subTest(name=name):
                raw_html = render_post().replace(visible_third, block, 1)
                self.assert_rejected_with(raw_html, "missing_section")

    def test_type_seven_raw_html_requires_a_block_boundary(self) -> None:
        second_body = "人の読む本文にも、投稿前の確認を適用します。"
        third_heading = "## 何は変わらないか"
        inline_html = render_post().replace(
            f"{second_body}\n\n{third_heading}",
            f"{second_body}\n<span>\n{third_heading}",
            1,
        )
        result = validate_human_post(inline_html, "issue")
        self.assertTrue(result.valid, result.errors)

        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        second_body = "人の読む本文にも、投稿前の確認を適用します。"
        lazy_quote_paragraph = render_post().replace(
            f"{first_body}\n\n{second_heading}\n\n{second_body}",
            (
                f"{first_body}\n"
                "> 引用の段落です。\n"
                "<span>\n"
                f"{second_heading}\n"
                f"{second_body}"
            ),
            1,
        )
        result = validate_human_post(lazy_quote_paragraph, "issue")
        self.assertTrue(result.valid, result.errors)

        block_boundaries = {
            "quoted atx heading": "> # 引用内の見出し",
            "quoted indented code": ">     code",
            "quoted thematic break": "> ---",
            "list indented code": "-     code",
            "setext heading": "===",
        }
        for name, preceding_block in block_boundaries.items():
            with self.subTest(name=name):
                after_block_boundary = render_post().replace(
                    f"{first_body}\n\n{second_heading}\n\n{second_body}",
                    (
                        f"{first_body}\n"
                        f"{preceding_block}\n"
                        "<span>\n"
                        f"{second_heading}\n"
                        f"{second_body}"
                    ),
                    1,
                )
                self.assert_rejected_with(after_block_boundary, "missing_section")

        after_link_reference = render_post().replace(
            f"{first_body}\n\n{second_heading}\n\n{second_body}",
            (
                f"{first_body}\n\n"
                "[参照]: /x\n"
                "<i>\n"
                f"{second_heading}\n"
                f"{second_body}"
            ),
            1,
        )
        self.assert_rejected_with(after_link_reference, "missing_section")

        after_table = render_post().replace(
            f"{first_body}\n\n{second_heading}\n\n{second_body}",
            (
                f"{first_body}\n\n"
                "| 列 |\n"
                "| --- |\n"
                "<i>\n"
                f"{second_heading}\n"
                f"{second_body}"
            ),
            1,
        )
        self.assert_rejected_with(after_table, "missing_section")

        table_boundaries = {
            "plain count mismatch": (
                "| 左 | 右 |\n"
                "| --- |",
                True,
            ),
            "escaped pipe count match": (
                "| 左 \\| 内 | 右 |\n"
                "| --- | --- |",
                False,
            ),
            "escaped pipe count mismatch": (
                "| 左 \\| 内 | 右 |\n"
                "| --- |",
                True,
            ),
        }
        for name, (table, expected_valid) in table_boundaries.items():
            with self.subTest(kind=name):
                table_then_html = render_post().replace(
                    f"{first_body}\n\n{second_heading}\n\n{second_body}",
                    (
                        f"{first_body}\n\n"
                        f"{table}\n"
                        "<i>\n"
                        f"{second_heading}\n"
                        f"{second_body}"
                    ),
                    1,
                )
                result = validate_human_post(table_then_html, "issue")
                if expected_valid:
                    self.assertTrue(result.valid, result.errors)
                else:
                    self.assertFalse(result.valid)
                    self.assertIn(
                        "missing_section",
                        [error["code"] for error in result.errors],
                    )

        for marker in ("-", "1."):
            with self.subTest(kind="blank bare marker", marker=marker):
                after_bare_marker = render_post().replace(
                    f"{first_body}\n\n{second_heading}\n\n{second_body}",
                    (
                        f"{first_body}\n\n"
                        f"{marker}\n"
                        "<i>\n"
                        f"{second_heading}\n"
                        f"{second_body}"
                    ),
                    1,
                )
                self.assert_rejected_with(after_bare_marker, "missing_section")

        paragraph_link_like = render_post().replace(
            f"{first_body}\n\n{second_heading}\n\n{second_body}",
            (
                f"{first_body}\n"
                "[参照]: /x\n"
                "<i>\n"
                f"{second_heading}\n"
                f"{second_body}"
            ),
            1,
        )
        result = validate_human_post(paragraph_link_like, "issue")
        self.assertTrue(result.valid, result.errors)

        for marker in ("-", "1."):
            with self.subTest(kind="paragraph bare marker", marker=marker):
                paragraph_marker = render_post().replace(
                    f"{first_body}\n\n{second_heading}\n\n{second_body}",
                    (
                        f"{first_body}\n"
                        f"{marker}\n"
                        "<i>\n"
                        f"{second_heading}\n"
                        f"{second_body}"
                    ),
                    1,
                )
                result = validate_human_post(paragraph_marker, "issue")
                self.assertTrue(result.valid, result.errors)

        standalone_equals = render_post().replace(
            f"{first_body}\n\n{second_heading}\n\n{second_body}",
            (
                f"{first_body}\n\n"
                "===\n"
                "<i>\n"
                f"{second_heading}\n"
                f"{second_body}"
            ),
            1,
        )
        result = validate_human_post(standalone_equals, "issue")
        self.assertTrue(result.valid, result.errors)

        visible_third = (
            "## 何は変わらないか\n\n"
            "内容が正しいかどうかは、引き続き人が判断します。"
        )
        hidden_third = (
            "## 何は変わらないか\n"
            "内容が正しいかどうかは、引き続き人が判断します。"
        )
        block_html = render_post().replace(
            visible_third,
            f"<span>\n{hidden_third}",
            1,
        )
        self.assert_rejected_with(block_html, "missing_section")

    def test_type_seven_raw_html_requires_valid_complete_tag_syntax(self) -> None:
        first_body = "投稿前の確認が、人の読む本文には適用されていませんでした。"
        second_heading = "## 何が変わるか"
        second_body = "人の読む本文にも、投稿前の確認を適用します。"

        def after_block_boundary(tag: str) -> str:
            return render_post().replace(
                f"{first_body}\n\n{second_heading}\n\n{second_body}",
                (
                    f"{first_body}\n\n"
                    f"{tag}\n"
                    f"{second_heading}\n"
                    f"{second_body}"
                ),
                1,
            )

        pseudo_tag = validate_human_post(
            after_block_boundary("<x ???>"),
            "issue",
        )
        self.assertTrue(pseudo_tag.valid, pseudo_tag.errors)

        complete_tags = (
            "<x>",
            "<x disabled>",
            '<x key="value">',
            "<x key='value'>",
            "<x key=value>",
            "</x>",
        )
        for tag in complete_tags:
            with self.subTest(tag=tag):
                self.assert_rejected_with(
                    after_block_boundary(tag),
                    "missing_section",
                )


if __name__ == "__main__":
    unittest.main()
