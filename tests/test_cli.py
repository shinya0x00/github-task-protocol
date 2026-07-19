from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.parse import urlsplit
from unittest.mock import MagicMock, patch

from gtp.cli import build_parser, main
from gtp.model import Diagnostic
from gtp.status import StatusResult


FIXTURE = Path(__file__).parent / "fixtures" / "carriers" / "contract-valid.md"
HTTP_FIXTURES = Path(__file__).parent / "fixtures" / "http"
CLI_FIXTURES = Path(__file__).parent / "fixtures" / "cli"


class CliTests(unittest.TestCase):
    def capture(self, argv: list[str]) -> tuple[int, str]:
        output = StringIO()
        with redirect_stdout(output):
            code = main(argv)
        return code, output.getvalue()

    def call(self, argv: list[str]) -> tuple[int, list[str], dict]:
        code, text = self.capture(argv)
        lines = text.splitlines(keepends=True)
        json_line = next(index for index, line in enumerate(lines) if line.rstrip("\n") == "{")
        human = [line.rstrip("\n") for line in lines[:json_line]]
        return code, human, json.loads("".join(lines[json_line:]))

    def call_http_fixture(self, name: str) -> tuple[int, list[str], dict]:
        fixture = json.loads((HTTP_FIXTURES / name).read_text(encoding="utf-8"))
        pending = list(fixture["requests"])

        def materialize(value):
            if not isinstance(value, dict) or "_records" not in value:
                return value
            comments = []
            for index, record in enumerate(value["_records"], start=1):
                comment_id = 100 + index
                timestamp = f"2026-07-19T00:00:{index:02d}Z"
                body = (
                    "<!-- gtp-record:v1 -->\n"
                    "fixture record\n\n"
                    "<details><summary>記録(JSON)</summary>\n\n"
                    "```json\n"
                    + json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                    + "\n```\n\n</details>\n"
                )
                comments.append({
                    "id": comment_id,
                    "html_url": f"{fixture['issue_url']}#issuecomment-{comment_id}",
                    "body": body,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    "user": {"login": "fixture"},
                })
            return comments

        def open_fixture(request, timeout):
            self.assertEqual("GET", request.get_method())
            self.assertEqual(30, timeout)
            expected = pending.pop(0)
            self.assertEqual(expected["url"], request.full_url)
            response = MagicMock()
            response.__enter__.return_value = response
            response.geturl.return_value = request.full_url
            response.read.return_value = json.dumps(materialize(expected["body"])).encode("utf-8")
            response.headers.items.return_value = expected.get("headers", {}).items()
            return response

        with patch.dict("os.environ", {}, clear=True), patch(
            "gtp.github._open", side_effect=open_fixture
        ):
            code, human, output = self.call(["status", fixture["issue_url"]])
        self.assertEqual([], pending)
        return code, human, output

    def call_http_matrix_case(self, case: dict) -> tuple[int, list[str], dict]:
        issue_url = "https://github.com/o/r/issues/1"
        sha = "0123456789abcdef0123456789abcdef01234567"
        contract = {
            "gtp": "1.0",
            "type": "contract",
            "id": "01234567-89ab-4def-8123-456789abcdef",
            "goal": "HTTP matrix",
            "scope": case.get("scope", ["src/"]),
            "done_conditions": {
                "proof": {
                    "text": "proof exists",
                    "evidence_kind": case.get("evidence_kind", "artifact"),
                }
            },
        }
        if case.get("missing_evidence_key"):
            contract["done_conditions"]["proof_b"] = {
                "text": "second proof exists",
                "evidence_kind": "artifact",
            }
        start = {
            "gtp": "1.0",
            "type": "start",
            "id": "11234567-89ab-4def-8123-456789abcdef",
            "contract_ref": f"{issue_url}#issuecomment-101",
            "branch": "agent/test",
        }
        evidence = (
            "https://github.com/o/r/runs/8"
            if case.get("evidence_kind") == "check"
            else f"https://github.com/{case.get('evidence_repo', 'o/r')}/blob/{case.get('evidence_sha', sha)}/src/a.py"
        )
        done = {
            "gtp": "1.0",
            "type": "done",
            "id": "21234567-89ab-4def-8123-456789abcdef",
            "pr_ref": "https://github.com/o/r/pull/7",
            "head_sha": sha,
            "evidence": {"proof": evidence},
        }
        stop = {
            "gtp": "1.0",
            "type": "stop",
            "id": "31234567-89ab-4def-8123-456789abcdef",
            "reason": "superseded" if case.get("successor") else "abandoned",
            "successor_ref": "https://github.com/o/r/issues/2" if case.get("successor") else None,
        }
        records = {
            "contract": contract,
            "start": start,
            "done": done,
            "stop": stop,
        }

        def carrier(record):
            return (
                "<!-- gtp-record:v1 -->\nfixture record\n\n"
                "<details><summary>記録(JSON)</summary>\n\n```json\n"
                + json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                + "\n```\n\n</details>\n"
            )

        comments = []
        for index, name in enumerate(case["records"], start=1):
            timestamp = f"2026-07-19T00:00:{index:02d}Z"
            comments.append({
                "id": 100 + index,
                "html_url": f"{issue_url}#issuecomment-{100 + index}",
                "body": carrier(records[name]),
                "created_at": timestamp,
                "updated_at": timestamp,
                "user": {"login": "fixture"},
            })

        issue_reads = 0
        pr_reads = 0

        def response(request, timeout):
            nonlocal issue_reads, pr_reads
            self.assertEqual("GET", request.get_method())
            self.assertEqual(30, timeout)
            url = request.full_url
            parsed = urlsplit(url)
            body = None
            headers = {}
            if parsed.path == "/repos/o/r":
                body = {"id": 99, "full_name": "o/r"}
            elif parsed.path == "/repos/x/y":
                body = {"id": 100, "full_name": "x/y"}
            elif parsed.path == "/repos/o/r/issues/1":
                issue_reads += 1
                body = {
                    "id": 1,
                    "created_at": "2026-07-18T00:00:00Z",
                    "updated_at": (
                        "2026-07-19T00:00:01Z"
                        if case.get("issue_moves") and issue_reads > 1
                        else "2026-07-19T00:00:00Z"
                    ),
                }
                if case.get("issue_is_pr"):
                    body["pull_request"] = {"url": "https://api.github.com/repos/o/r/pulls/1"}
            elif parsed.path == "/repos/o/r/issues/2":
                body = {
                    "id": 2,
                    "created_at": case.get("successor_created_at", "2026-07-19T00:00:01Z"),
                    "updated_at": "2026-07-19T00:00:01Z",
                }
            elif parsed.path == "/repos/o/r/issues/1/comments":
                body = comments
            elif parsed.path == "/repos/o/r/branches/agent%2Ftest":
                if case.get("branch_exists", True):
                    body = {"name": "agent/test"}
                else:
                    raise HTTPError(url, 404, "not found", {}, None)
            elif parsed.path == "/repos/o/r/pulls":
                count = case.get("candidate_count", 0)
                body = [self._matrix_pr(case, sha, number) for number in range(7, 7 + count)]
            elif parsed.path == "/repos/o/r/pulls/7":
                pr_reads += 1
                body = self._matrix_pr(case, sha, 7)
                if case.get("pr_moves") and pr_reads > 1:
                    body["head"]["sha"] = "f" * 40
            elif parsed.path == "/repos/o/r/pulls/7/files":
                body = case.get("files", [{"filename": "src/a.py", "status": "added"}])
            elif parsed.path == "/repos/o/r/check-runs/8":
                body = {
                    "head_sha": case.get("check_sha", sha),
                    "status": case.get("check_status", "completed"),
                    "conclusion": case.get("check_conclusion", "success"),
                    "completed_at": "2026-07-19T00:00:04Z",
                }
            elif parsed.path == "/repos/o/r/contents/src/a.py":
                if case.get("artifact_missing"):
                    raise HTTPError(url, 404, "not found", {}, None)
                body = {"type": "file", "path": "src/a.py"}
            else:
                self.fail(f"unexpected HTTP request: {url}")
            mocked = MagicMock()
            mocked.__enter__.return_value = mocked
            mocked.geturl.return_value = url
            mocked.read.return_value = json.dumps(body).encode("utf-8")
            mocked.headers.items.return_value = headers.items()
            return mocked

        with patch.dict("os.environ", {}, clear=True), patch(
            "gtp.github._open", side_effect=response
        ):
            code, human, output = self.call(["status", issue_url])
            return code, human, output

    def _matrix_pr(self, case: dict, sha: str, number: int) -> dict:
        return {
            "number": number,
            "html_url": f"https://github.com/o/r/pull/{number}",
            "base": {"repo": {"id": 99}},
            "head": {
                "repo": {"id": 100 if case.get("fork") else 99},
                "ref": case.get("pr_branch", "agent/test"),
                "sha": case.get("pr_sha", sha),
            },
            "merged_at": case.get("merged_at"),
        }

    def test_check_valid_carrier_exits_zero(self) -> None:
        code, human, output = self.call(["check", str(FIXTURE)])
        self.assertEqual(0, code)
        self.assertTrue(output["schema_valid"])
        self.assertIn("offline schemaに適合", human[0])

    def test_check_normal_comment_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "comment.md"
            path.write_text("ordinary comment\n", encoding="utf-8")
            code, human, output = self.call(["check", str(path)])
        self.assertEqual(1, code)
        self.assertFalse(output["recognized"])
        self.assertIn("通常comment", human[0])

    def test_check_invalid_carrier_and_input_error_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.md"
            invalid.write_text("<!-- gtp-record:v1 -->\n壊れたCarrier\n", encoding="utf-8")
            invalid_code, invalid_human, invalid_output = self.call(["check", str(invalid)])
            missing_code, missing_human, missing_output = self.call(
                ["check", str(Path(directory) / "missing.md")]
            )
            non_utf8 = Path(directory) / "non-utf8.md"
            non_utf8.write_bytes(b"\xff")
            encoding_code, _, encoding_output = self.call(["check", str(non_utf8)])
        self.assertEqual(1, invalid_code)
        self.assertTrue(invalid_output["recognized"])
        self.assertFalse(invalid_output["schema_valid"])
        self.assertIn("適合しません", invalid_human[0])
        self.assertEqual(2, missing_code)
        self.assertIsNone(missing_output["recognized"])
        self.assertEqual("input_error", missing_output["errors"][0]["code"])
        self.assertIn("読めません", missing_human[0])
        self.assertEqual(2, encoding_code)
        self.assertEqual("input_error", encoding_output["errors"][0]["code"])

    def test_only_status_and_check_are_public_commands(self) -> None:
        actions = build_parser()._subparsers._group_actions
        self.assertEqual(1, len(actions))
        self.assertEqual({"status", "check"}, set(actions[0].choices))

    def test_version_prints_package_version_and_exits_zero(self) -> None:
        output = StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            build_parser().parse_args(["--version"])
        self.assertEqual(0, raised.exception.code)
        self.assertEqual("1.0.0\n", output.getvalue())

    def test_status_halt_is_successful_observation(self) -> None:
        observed = StatusResult(
            "https://github.com/o/r/issues/1",
            "halt",
            [Diagnostic("invalid_binding", ("https://github.com/o/r/pull/7",))],
        )
        with patch("gtp.cli.evaluate_issue", return_value=observed):
            code, human, output = self.call(["status", observed.issue_url])
        self.assertEqual(0, code)
        self.assertEqual("halt", output["state"])
        self.assertEqual("invalid_binding", output["halt_reason"])
        self.assertEqual("状態: halt", human[0])
        self.assertTrue(human[5].startswith("非許可表示:"))

    def test_status_without_state_exits_two(self) -> None:
        observed = StatusResult(
            "https://github.com/o/r/issues/1",
            None,
            acquisition_errors=[{"code": "acquisition_incomplete"}],
        )
        with patch("gtp.cli.evaluate_issue", return_value=observed):
            code, human, output = self.call(["status", observed.issue_url])
        self.assertEqual(2, code)
        self.assertIsNone(output["state"])
        self.assertEqual("状態: 不明", human[0])
        self.assertIn(
            "  大事な点: 情報を取得できないことと、記録に矛盾があることは別です。",
            human,
        )

    def test_status_human_and_machine_matrix(self) -> None:
        matrix = json.loads((CLI_FIXTURES / "status-matrix.json").read_text(encoding="utf-8"))
        issue_url = "https://github.com/o/r/issues/1"
        for case in matrix["states"]:
            diagnostic = case.get("diagnostic")
            diagnostics = (
                [Diagnostic(diagnostic, ("https://github.com/o/r/pull/7",), {"sample": True})]
                if diagnostic
                else []
            )
            errors = [case["acquisition_error"]] if case.get("acquisition_error") else []
            observed = StatusResult(
                issue_url,
                case["state"],
                diagnostics,
                case.get("current", {}),
                errors,
            )
            with self.subTest(case=case["name"]), patch(
                "gtp.cli.evaluate_issue", return_value=observed
            ):
                code, human, output = self.call(["status", issue_url])
                self.assertEqual(2 if case["state"] is None else 0, code)
                self.assertGreaterEqual(len(human), 7)
                self.assertEqual(
                    ["状態", "停止要否", "次の行動", "理由", "最初のURL", "非許可表示"],
                    [line.split(":", 1)[0] for line in human[:6]],
                )
                self.assertIn(case["reason_contains"], human[3])
                self.assertEqual(case["state"], output["state"])
                self.assertEqual(case["next_action"], output["next_action"])
                self.assertEqual("none", output["authority"])
                self.assertEqual(
                    "incomplete" if case["state"] is None else "complete",
                    output["acquisition"],
                )
                self.assertTrue(
                    {
                        "gtp", "command", "issue_url", "state", "halt_reason",
                        "details", "next_action", "primary_url", "authority",
                        "acquisition", "contract", "start", "done", "stop",
                        "branch", "pr_candidate", "bound_pr", "diagnostics",
                    }.issubset(output)
                )
                if diagnostic:
                    self.assertEqual([{"sample": True}], output["details"])
                if case["name"] == "in_progress awaiting merge":
                    self.assertEqual(
                        3, output["done"]["observation"]["comment_id"]
                    )
                    self.assertNotIn("comment_id", output["done"])
                if case["name"] == "in_progress":
                    self.assertEqual(
                        {"exists": True}, output["branch"]["observation"]
                    )
                    self.assertNotIn("exists", output["branch"])

        installed = matrix["installed_live_observation"]
        self.assertEqual(0, installed["exit_code"])
        self.assertEqual("stopped", installed["state"])
        self.assertTrue(installed["task_context"]["goal_presented"])
        self.assertTrue(installed["task_context"]["scope_presented"])
        self.assertEqual(
            ["proof_b"], installed["task_context"]["missing_evidence_keys"]
        )
        self.assertTrue(installed["task_context"]["not_proven_presented"])

        plain_installed = matrix["plain_summary_installed_live_observation"]
        self.assertEqual(0, plain_installed["exit_code"])
        self.assertEqual("stopped", plain_installed["state"])
        self.assertTrue(plain_installed["plain_summary"]["conclusion_presented"])
        self.assertEqual(
            ["proof_a"],
            plain_installed["plain_summary"]["evidence_link_presented_without_completion_claim"],
        )
        self.assertEqual(
            ["proof_b"],
            plain_installed["plain_summary"]["missing_evidence_link_explained"],
        )

    def test_all_halt_reasons_have_specific_japanese_and_first_url(self) -> None:
        matrix = json.loads((CLI_FIXTURES / "status-matrix.json").read_text(encoding="utf-8"))
        issue_url = "https://github.com/o/r/issues/1"
        cause_url = "https://github.com/o/r/issues/1#issuecomment-9"
        for case in matrix["halt_reasons"]:
            observed = StatusResult(
                issue_url,
                "halt",
                [Diagnostic(case["token"], (cause_url,))],
            )
            with self.subTest(reason=case["token"]), patch(
                "gtp.cli.evaluate_issue", return_value=observed
            ):
                code, human, output = self.call(["status", issue_url])
                self.assertEqual(0, code)
                self.assertEqual(f"理由: {case['token']} — {case['message']}", human[3])
                self.assertEqual(f"最初のURL: {cause_url}", human[4])
                self.assertEqual(case["token"], output["halt_reason"])
                self.assertEqual(cause_url, output["primary_url"])

    def test_stdout_is_deterministic_and_human_text_precedes_json(self) -> None:
        observed = StatusResult("https://github.com/o/r/issues/1", "unmanaged")
        with patch("gtp.cli.evaluate_issue", return_value=observed):
            first_code, first = self.capture(["status", observed.issue_url])
            second_code, second = self.capture(["status", observed.issue_url])
        self.assertEqual(0, first_code)
        self.assertEqual(first_code, second_code)
        self.assertEqual(first, second)
        self.assertLess(first.index("状態: unmanaged"), first.index("{\n"))

    def test_status_http_walking_skeleton_uses_production_path(self) -> None:
        code, human, output = self.call_http_fixture("walking-skeleton.json")
        self.assertEqual(0, code)
        self.assertEqual("unmanaged", output["state"])
        self.assertEqual("complete", output["acquisition"])
        self.assertNotIn("タスクの目的", "\n".join(human))

    def test_status_done_http_fixture_uses_all_production_logic(self) -> None:
        code, human, output = self.call_http_fixture("done-success.json")
        self.assertEqual(0, code)
        self.assertEqual("done", output["state"])
        self.assertEqual("complete", output["acquisition"])
        self.assertEqual("HTTP fixture acceptance", output["task_context"]["goal"])
        self.assertIn("  結論: このIssueの完了を確認しました。", human)
        self.assertIn("  目的: HTTP fixture acceptance", human)
        self.assertIn("技術的な詳細（必要な人だけ）:", human)

    def test_status_required_live_binding_http_matrix(self) -> None:
        matrix = json.loads(
            (HTTP_FIXTURES / "live-binding-matrix.json").read_text(encoding="utf-8")
        )
        for case in matrix:
            with self.subTest(case=case["name"]):
                code, human, output = self.call_http_matrix_case(case)
                self.assertEqual(case["state"], output["state"])
                if case.get("reason"):
                    self.assertEqual(case["reason"], output["diagnostics"][0]["token"])
                if case.get("first_url"):
                    self.assertEqual(case["first_url"], output["primary_url"])
                    self.assertEqual(
                        case["first_url"], output["diagnostics"][0]["urls"][0]
                    )
                if case.get("missing_evidence_key"):
                    context = output["task_context"]
                    self.assertEqual("HTTP matrix", context["goal"])
                    self.assertEqual(["src/"], context["scope"])
                    self.assertEqual("agent/test", context["branch"])
                    self.assertEqual("https://github.com/o/r/pull/7", context["pr"])
                    self.assertEqual(
                        "presented",
                        context["conditions"]["proof"]["evidence_status"],
                    )
                    self.assertEqual(
                        "not_presented",
                        context["conditions"]["proof_b"]["evidence_status"],
                    )
                    self.assertIn("proof_b: Evidence未提示", context["not_proven"])
                    self.assertIn("  目的: HTTP matrix", human)
                    self.assertIn("かんたんな説明:", human)
                    self.assertIn(
                        "  結論: このIssueの完了は確認できません。作業を止めて人が確認してください。",
                        human,
                    )
                    self.assertTrue(
                        any(
                            "記録に確認資料へのリンクがある条件" in line
                            for line in human
                        )
                    )
                    self.assertTrue(
                        any("proof exists（識別子: proof）" in line for line in human)
                    )
                    self.assertIn("  確認資料が足りない条件:", human)
                    self.assertTrue(
                        any("second proof exists（識別子: proof_b）" in line for line in human)
                    )
                    self.assertTrue(
                        any("不足しているもの: 条件を確認するための証拠リンク" in line for line in human)
                    )
                    self.assertTrue(
                        any("達成済みとはまだ断定しません" in line for line in human)
                    )
                    self.assertTrue(
                        any(
                            "proof_b:" in line and "Evidence: 未提示" in line
                            for line in human
                        )
                    )
                if case.get("acquisition_code"):
                    self.assertEqual(
                        case["acquisition_code"], output["acquisition_errors"][0]["code"]
                    )
                    self.assertEqual("incomplete", output["acquisition"])
                    self.assertEqual(2, code)


if __name__ == "__main__":
    unittest.main()
