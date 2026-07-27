from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import re
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from unittest.mock import MagicMock, patch

import gtp
from gtp.cli import build_parser, main
from gtp.model import Diagnostic
from gtp.presentation import SECTIONS, validate_human_post
from gtp.status import StatusResult


FIXTURE = Path(__file__).parent / "fixtures" / "carriers" / "contract-valid.md"
HTTP_FIXTURES = Path(__file__).parent / "fixtures" / "http"
CLI_FIXTURES = Path(__file__).parent / "fixtures" / "cli"


def human_body(target: str, *, technical: bool = False) -> str:
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

    def problem_values(self, human: list[str], labels: list[str]) -> list[str]:
        start = human.index("問題の整理:")
        values = []
        for index, label in enumerate(labels, start=1):
            prefix = f"  {index}. {label}: "
            line = human[start + index]
            self.assertTrue(line.startswith(prefix), line)
            values.append(line[len(prefix):])
        return values

    def call_http_fixture(self, name: str | Path) -> tuple[int, list[str], dict]:
        fixture_path = name if isinstance(name, Path) else HTTP_FIXTURES / name
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
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
            "branch": case.get("start_branch", "agent/test"),
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
        amendment = {
            "gtp": "1.1",
            "type": "amendment",
            "id": "41234567-89ab-4def-8123-456789abcdef",
            "predecessor_ref": f"{issue_url}#issuecomment-101",
            "done_conditions": {
                "extra": {
                    "text": "extra proof exists",
                    "evidence_kind": "artifact",
                }
            },
        }
        records = {
            "contract": contract,
            "start": start,
            "done": done,
            "stop": stop,
            "amendment": amendment,
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

        repository_reads = 0
        issue_reads = 0
        pr_reads = 0
        pull_reads = 0
        file_reads = 0

        def response(request, timeout):
            nonlocal repository_reads, issue_reads, pr_reads, pull_reads, file_reads
            self.assertEqual("GET", request.get_method())
            self.assertEqual(30, timeout)
            url = request.full_url
            parsed = urlsplit(url)
            body = None
            headers = {}
            if parsed.path == "/repos/o/r":
                repository_reads += 1
                body = {
                    "id": 99,
                    "full_name": "o/r",
                    "default_branch": (
                        "trunk"
                        if case.get("repository_moves") and repository_reads > 1
                        else "main"
                    ),
                }
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
            elif parsed.path == (
                "/repos/o/r/branches/"
                + quote(start["branch"], safe="")
            ):
                if case.get("branch_exists", True):
                    body = {
                        "name": start["branch"],
                        "commit": {"sha": case.get("branch_sha", sha)},
                    }
                else:
                    raise HTTPError(url, 404, "not found", {}, None)
            elif parsed.path == "/repos/o/r/pulls":
                pull_reads += 1
                default_count = 1 if "done" in case["records"] else 0
                count = (
                    1
                    if case.get("candidate_moves") and pull_reads > 1
                    else case.get("candidate_count", default_count)
                )
                body = [self._matrix_pr(case, sha, number) for number in range(7, 7 + count)]
            elif parsed.path == "/repos/o/r/pulls/7":
                pr_reads += 1
                body = self._matrix_pr(case, sha, 7)
                if case.get("pr_moves") and pr_reads > 1:
                    body["head"]["sha"] = "f" * 40
                if case.get("base_moves_during_files") and file_reads:
                    body["base"]["sha"] = "c" * 40
            elif parsed.path == "/repos/o/r/pulls/7/files":
                file_reads += 1
                body = case.get("files", [{"filename": "src/a.py", "status": "added"}])
            elif parsed.path == "/repos/o/r/check-runs/8":
                body = {
                    "head_sha": case.get("check_sha", sha),
                    "status": case.get("check_status", "completed"),
                    "conclusion": case.get("check_conclusion", "success"),
                    "completed_at": "2026-07-19T00:00:04Z",
                }
                if case.get("check_status_missing"):
                    body.pop("status")
                if case.get("check_conclusion_missing"):
                    body.pop("conclusion")
                if case.get("check_completed_at_missing"):
                    body.pop("completed_at")
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
            "created_at": case.get(
                "pr_created_at", "2026-07-19T00:00:02.500000Z"
            ),
            "updated_at": "2026-07-19T00:00:02Z",
            "changed_files": case.get(
                "changed_files",
                len(case.get("files", [{"filename": "src/a.py", "status": "added"}])),
            ),
            "base": {
                "repo": {"id": 99},
                "ref": "main",
                "sha": case.get("base_sha", "b" * 40),
            },
            "head": {
                "repo": {"id": 100 if case.get("fork") else 99},
                "ref": case.get(
                    "pr_branch", case.get("start_branch", "agent/test")
                ),
                "sha": case.get("pr_sha", sha),
            },
            "merged_at": case.get("merged_at"),
            "state": "closed" if case.get("merged_at") else "open",
        }

    def test_check_valid_carrier_exits_zero(self) -> None:
        code, human, output = self.call(["check", str(FIXTURE)])
        self.assertEqual(0, code)
        self.assertTrue(output["schema_valid"])
        self.assertIn("offline schemaに適合", human[0])
        self.assertNotIn("問題の整理:", human)
        self.assertEqual(
            {
                "gtp", "command", "recognized", "schema_valid", "contextual_checks",
                "projected_state", "record", "errors", "authority",
            },
            set(output),
        )

    def test_check_projects_protocol_11_for_valid_and_invalid_records(self) -> None:
        record = {
            "gtp": "1.1",
            "type": "amendment",
            "id": "41234567-89ab-4def-8123-456789abcdef",
            "predecessor_ref": "https://github.com/o/r/issues/1#issuecomment-1",
            "done_conditions": {
                "extra": {"text": "extra proof", "evidence_kind": "artifact"}
            },
        }
        carrier = (
            "<!-- gtp-record:v1 -->\nprotocol 1.1\n\n"
            "<details><summary>記録(JSON)</summary>\n\n```json\n"
            + json.dumps(record)
            + "\n```\n\n</details>\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "v11.md"
            path.write_text(carrier, encoding="utf-8")
            valid_code, _, valid = self.call(["check", str(path)])
            record["unexpected"] = True
            path.write_text(carrier.replace(json.dumps({k: v for k, v in record.items() if k != "unexpected"}), json.dumps(record)), encoding="utf-8")
            invalid_code, _, invalid = self.call(["check", str(path)])
        self.assertEqual((0, "1.1", True), (valid_code, valid["gtp"], valid["schema_valid"]))
        self.assertEqual((1, "1.1", False), (invalid_code, invalid["gtp"], invalid["schema_valid"]))

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

    def test_check_human_issue_and_pr_targets_preserve_record_default(self) -> None:
        sections = {
            "issue": ("目的", "ゴール", "現在わかっていること", "守る境界", "決定事項", "完了条件", "未確認事項", "人間に求める判断"),
            "pr": ("目的", "ゴール", "変更内容", "利用者への影響", "現在地", "未確認事項", "人間に求める判断"),
        }
        with tempfile.TemporaryDirectory() as directory:
            for target, headings in sections.items():
                path = Path(directory) / f"{target}.md"
                contents = []
                for heading in headings:
                    explanation = "説明です。"
                    if heading == "決定事項":
                        explanation = (
                            "- 採用した方針: 既存契約どおりに修正する。\n"
                            "- 今回は採用しない案: none\n"
                            "- 見直す条件: 契約との衝突を再現した場合。\n"
                            "- 根拠・履歴: none"
                        )
                    contents.append(f"## {heading}\n\n{explanation}")
                path.write_text("\n\n".join(contents), encoding="utf-8")
                code, human, output = self.call(["check", "--target", target, str(path)])
                self.assertEqual(0, code)
                self.assertTrue(output["valid"])
                self.assertEqual(target, output["target"])
                self.assertEqual({"gtp", "command", "target", "valid", "errors", "contextual_checks", "authority"}, set(output))
                self.assertIn("内容の真実性や人間の理解は判定していません", human[1])
            default = self.capture(["check", str(FIXTURE)])
            explicit = self.capture(["check", "--target", "record", str(FIXTURE)])
        self.assertEqual(default, explicit)

    def test_check_human_target_invalid_and_input_error_are_distinct(self) -> None:
        labels = json.loads((CLI_FIXTURES / "problem-explanations.json").read_text(encoding="utf-8"))["labels"]
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.md"
            invalid.write_text("## 目的\n\n目的だけです。\n", encoding="utf-8")
            invalid_code, invalid_human, invalid_output = self.call(["check", "--target", "pr", str(invalid)])
            missing_code, missing_human, missing_output = self.call(["check", "--target", "issue", str(Path(directory) / "missing.md")])
        self.assertEqual(1, invalid_code)
        self.assertFalse(invalid_output["valid"])
        self.assertIn("missing_section", [error["code"] for error in invalid_output["errors"]])
        self.assertEqual(8, len(self.problem_values(invalid_human, labels)))
        self.assertEqual(2, missing_code)
        self.assertIsNone(missing_output["valid"])
        self.assertEqual("input_error", missing_output["errors"][0]["code"])
        self.assertIn("問題の整理:", missing_human)

    def test_only_status_and_check_are_public_commands(self) -> None:
        actions = build_parser()._subparsers._group_actions
        self.assertEqual(1, len(actions))
        self.assertEqual({"status", "check"}, set(actions[0].choices))

    def test_version_prints_package_version_and_exits_zero(self) -> None:
        output = StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            build_parser().parse_args(["--version"])
        self.assertEqual(0, raised.exception.code)
        self.assertEqual(f"{gtp.__version__}\n", output.getvalue())

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

    def test_problem_explanation_walking_skeleton_fires_all_three_cli_paths(self) -> None:
        labels = [
            "何が問題か",
            "どこが問題か",
            "なぜそう判断したか",
            "どこを直すか",
            "何を直さないか",
            "次の安全な一手",
            "最初に確認するURL",
            "解決したと判断する条件",
        ]
        observed = StatusResult(
            "https://github.com/o/r/issues/1",
            "halt",
            [Diagnostic("invalid_binding", ("https://github.com/o/r/pull/7",))],
        )
        with patch("gtp.cli.evaluate_issue", return_value=observed):
            _, status_human, _ = self.call(["status", observed.issue_url])
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.md"
            invalid.write_text("<!-- gtp-record:v1 -->\n壊れたCarrier\n", encoding="utf-8")
            _, check_human, _ = self.call(["check", str(invalid)])
            _, input_human, _ = self.call(
                ["check", str(Path(directory) / "missing.md")]
            )
        for human in (status_human, check_human, input_human):
            self.assertIn("問題の整理:", human)
            for index, label in enumerate(labels, start=1):
                self.assertTrue(any(line.startswith(f"  {index}. {label}:") for line in human))
        self.assertEqual("問題の整理:", status_human[6])

        normal = StatusResult(observed.issue_url, "unmanaged")
        with patch("gtp.cli.evaluate_issue", return_value=normal):
            _, normal_human, _ = self.call(["status", normal.issue_url])
        self.assertNotIn("問題の整理:", normal_human)

    def test_problem_explanation_matrix_covers_all_blockers(self) -> None:
        matrix = json.loads(
            (CLI_FIXTURES / "problem-explanations.json").read_text(encoding="utf-8")
        )
        labels = matrix["labels"]
        issue_url = "https://github.com/o/r/issues/1"
        cause_url = matrix["diagnostic_url"]
        for token, expected in matrix["halt"].items():
            observed = StatusResult(
                issue_url,
                "halt",
                [Diagnostic(token, (cause_url,))],
            )
            with self.subTest(token=token), patch(
                "gtp.cli.evaluate_issue", return_value=observed
            ):
                _, human, output = self.call(["status", issue_url])
                self.assertEqual(expected, self.problem_values(human, labels))
                self.assertNotIn("diagnostic token", expected[2])
                self.assertEqual(cause_url, output["primary_url"])

        acquisition = StatusResult(
            issue_url,
            None,
            acquisition_errors=[{
                "code": "acquisition_incomplete",
                "resource": "https://api.github.com/repos/o/r/issues/1",
            }],
        )
        with patch("gtp.cli.evaluate_issue", return_value=acquisition):
            _, human, _ = self.call(["status", issue_url])
        self.assertEqual(matrix["acquisition"], self.problem_values(human, labels))

        invalid_inputs = {
            "unrecognized": "ordinary comment\n",
            "format": "<!-- gtp-record:v1 -->\n壊れたCarrier\n",
            "json": (
                "<!-- gtp-record:v1 -->\nsummary\n\n"
                "<details><summary>記録(JSON)</summary>\n\n```json\n{\n```\n\n</details>\n"
            ),
            "schema": (
                "<!-- gtp-record:v1 -->\nsummary\n\n"
                "<details><summary>記録(JSON)</summary>\n\n```json\n"
                '{"gtp":"1.0","type":"contract","id":"01234567-89ab-4def-8123-456789abcdef",'
                '"goal":"x","scope":["x"],"done_conditions":{},"unexpected":true}'
                "\n```\n\n</details>\n"
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, body in invalid_inputs.items():
                path = root / f"{name}.md"
                path.write_text(body, encoding="utf-8")
                with self.subTest(check=name):
                    _, human, _ = self.call(["check", str(path)])
                    self.assertEqual(
                        matrix["check"][name], self.problem_values(human, labels)
                    )
            _, human, _ = self.call(["check", str(root / "missing.md")])
            self.assertNotIn(str(root), "\n".join(human))
        self.assertEqual(
            matrix["check"]["input_error"], self.problem_values(human, labels)
        )

    def test_status_problem_whitelists_safe_observations(self) -> None:
        matrix = json.loads(
            (CLI_FIXTURES / "problem-explanations.json").read_text(encoding="utf-8")
        )
        labels = matrix["labels"]
        issue_url = "https://github.com/o/r/issues/1"
        scope = matrix["safe_observations"]["scope_outside"]
        observed = StatusResult(
            issue_url,
            "halt",
            [Diagnostic(
                "invalid_binding",
                (matrix["diagnostic_url"],),
                {
                    "paths": scope["paths"],
                    "message": scope["private_message"],
                    "exception": scope["private_exception"],
                    "provider": "private-provider",
                },
            )],
        )
        with patch("gtp.cli.evaluate_issue", return_value=observed):
            _, human, _ = self.call(["status", issue_url])
        reason = self.problem_values(human, labels)[2]
        self.assertEqual(scope["reason"], reason)
        self.assertNotIn("diagnostic token", reason)
        problem = "\n".join(self.problem_values(human, labels))
        self.assertNotIn("binding", problem)
        self.assertNotIn("束縛", problem)
        self.assertNotIn("4 Record、6 state、7 halt reason", problem)
        self.assertNotIn(scope["private_message"], "\n".join(human))
        self.assertNotIn(scope["private_exception"], "\n".join(human))
        self.assertNotIn("private-provider", "\n".join(human))

        acquisition = matrix["safe_observations"]["http_403"]
        observed = StatusResult(
            issue_url,
            None,
            acquisition_errors=[{
                "code": acquisition["code"],
                "status": acquisition["status"],
                "message": acquisition["private_message"],
            }],
        )
        with patch("gtp.cli.evaluate_issue", return_value=observed):
            _, human, _ = self.call(["status", issue_url])
        reason = self.problem_values(human, labels)[2]
        self.assertEqual(acquisition["reason"], reason)
        self.assertNotIn(acquisition["private_message"], "\n".join(human))

    def test_problem_explanation_falls_back_to_existing_primary_url(self) -> None:
        fallback = "https://github.com/o/r/issues/1#issuecomment-3"
        observed = StatusResult(
            "https://github.com/o/r/issues/1",
            "halt",
            [Diagnostic("invalid_record", ())],
            {"contract": {"url": fallback}},
        )
        with patch("gtp.cli.evaluate_issue", return_value=observed):
            _, human, output = self.call(["status", observed.issue_url])
        labels = json.loads(
            (CLI_FIXTURES / "problem-explanations.json").read_text(encoding="utf-8")
        )["labels"]
        self.assertEqual(fallback, output["primary_url"])
        self.assertEqual(fallback, self.problem_values(human, labels)[6])

    def test_invalid_record_causes_share_a_non_speculative_human_reason(self) -> None:
        labels = json.loads(
            (CLI_FIXTURES / "problem-explanations.json").read_text(encoding="utf-8")
        )["labels"]
        expected = "Issue commentを、変更されていない一意のGTP記録として確定できませんでした"
        issue_url = "https://github.com/o/r/issues/1"
        for cause in ("malformed", "edited", "id_collision"):
            observed = StatusResult(
                issue_url,
                "halt",
                [Diagnostic("invalid_record", (f"{issue_url}#issuecomment-1",), {"cause": cause})],
            )
            with self.subTest(cause=cause), patch(
                "gtp.cli.evaluate_issue", return_value=observed
            ):
                _, human, output = self.call(["status", issue_url])
                values = self.problem_values(human, labels)
                self.assertEqual(expected, values[2])
                self.assertEqual("invalid_record", output["diagnostics"][0]["token"])

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
                if case["state"] in {None, "halt"}:
                    self.assertIn("問題の整理:", human)
                else:
                    self.assertNotIn("問題の整理:", human)
                self.assertEqual(
                    {
                        "gtp", "command", "issue_url", "state", "halt_reason",
                        "details", "next_action", "primary_url", "authority",
                        "acquisition", "contract", "start", "done", "stop",
                        "branch", "pr_candidate", "bound_pr", "diagnostics",
                        "acquisition_errors", "task_context",
                    },
                    set(output),
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
        self.assertTrue(
            plain_installed["plain_summary"]["human_machine_boundary_presented"]
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

    def test_protocol_11_walking_skeleton_fires_public_status_path(self) -> None:
        code, _, output = self.call_http_fixture(
            Path(__file__).parent / "fixtures/protocol-1.1/walking-skeleton.json"
        )
        self.assertEqual(0, code)
        self.assertEqual("in_progress", output["state"])
        self.assertEqual("1.1", output["gtp"])
        self.assertIsNone(output["amendment"])
        self.assertEqual("Protocol 1.1 walking skeleton", output["task_context"]["goal"])

    def test_protocol_11_compound_stale_repair_names_every_re_done_binding(self) -> None:
        issue_url = "https://github.com/o/r/issues/1"
        done_url = f"{issue_url}#issuecomment-3"
        amendment_url = f"{issue_url}#issuecomment-4"
        pr_url = "https://github.com/o/r/pull/7"
        old_head = "0" * 40
        current_head = "f" * 40
        observed = StatusResult(
            issue_url,
            "halt",
            [Diagnostic("stale_evidence", (done_url, pr_url))],
            {
                "contract": {
                    "id": "01234567-89ab-4def-8123-456789abcdef",
                    "type": "contract",
                    "url": f"{issue_url}#issuecomment-1",
                    "content": {
                        "goal": "compound stale repair",
                        "scope": ["src/"],
                        "done_conditions": {
                            "proof": {
                                "text": "proof exists",
                                "evidence_kind": "artifact",
                            }
                        },
                    },
                },
                "start": {
                    "id": "12345678-9abc-4def-8123-456789abcdef",
                    "type": "start",
                    "url": f"{issue_url}#issuecomment-2",
                    "content": {
                        "contract_ref": f"{issue_url}#issuecomment-1",
                        "branch": "agent/test",
                    },
                },
                "done": {
                    "id": "22345678-9abc-4def-8123-456789abcdef",
                    "type": "done",
                    "url": done_url,
                    "content": {
                        "pr_ref": pr_url,
                        "head_sha": old_head,
                        "evidence": {
                            "proof": f"https://github.com/o/r/blob/{old_head}/proof.txt"
                        },
                    },
                },
                "amendment": {
                    "id": "32345678-9abc-4def-8123-456789abcdef",
                    "type": "amendment",
                    "url": amendment_url,
                    "content": {
                        "predecessor_ref": f"{issue_url}#issuecomment-1",
                        "done_conditions": {
                            "extra": {
                                "text": "extra proof exists",
                                "evidence_kind": "artifact",
                            }
                        },
                    },
                },
                "stop": None,
                "branch": {"name": "agent/test"},
                "bound_pr": pr_url,
                "bound_pr_head_sha": current_head,
            },
            _effective_done_conditions={
                "proof": {"text": "proof exists", "evidence_kind": "artifact"},
                "extra": {
                    "text": "extra proof exists",
                    "evidence_kind": "artifact",
                },
            },
            protocol_version="1.1",
        )
        with patch("gtp.cli.evaluate_issue", return_value=observed):
            code, human, output = self.call(["status", issue_url])

        labels = json.loads(
            (CLI_FIXTURES / "problem-explanations.json").read_text(encoding="utf-8")
        )["labels"]
        problem = self.problem_values(human, labels)
        self.assertEqual(0, code)
        self.assertEqual("stale_evidence", output["halt_reason"])
        self.assertEqual(
            "not_presented",
            output["task_context"]["conditions"]["extra"]["evidence_status"],
        )
        for value in (problem[3], problem[7]):
            self.assertIn("現在の完了条件", value)
            self.assertIn("現在のPRの最新commit", value)
            self.assertIn("すべての完了条件", value)
            self.assertIn("確認資料", value)
        self.assertIn("Doneを出し直す", problem[3])
        self.assertIn(
            "merge済みなら同じIssueではDoneを出し直せない",
            problem[7],
        )

    def test_protocol_11_simple_stale_does_not_invent_amendment(self) -> None:
        issue_url = "https://github.com/o/r/issues/1"
        done_url = f"{issue_url}#issuecomment-3"
        pr_url = "https://github.com/o/r/pull/7"
        observed = StatusResult(
            issue_url,
            "halt",
            [Diagnostic("stale_evidence", (done_url, pr_url))],
            {"done": {"type": "done", "url": done_url}, "bound_pr": pr_url},
            protocol_version="1.1",
        )
        with patch("gtp.cli.evaluate_issue", return_value=observed):
            code, human, output = self.call(["status", issue_url])
        labels = json.loads((CLI_FIXTURES / "problem-explanations.json").read_text(encoding="utf-8"))["labels"]
        problem = self.problem_values(human, labels)
        self.assertEqual(0, code)
        self.assertEqual("stale_evidence", output["halt_reason"])
        text = "\n".join(problem)
        self.assertIn("現在のPRの最新commit", text)
        self.assertIn("すべての完了条件", text)
        self.assertIn("merge済みなら同じIssueではDoneを出し直せない", text)
        self.assertNotIn("追加後", text)
        self.assertNotIn("完了条件が追加", text)

    def test_protocol_11_compound_stale_http_path_explains_complete_repair_in_plain_japanese(self) -> None:
        current_head = "f" * 40
        code, human, output = self.call_http_matrix_case({
            "records": ["contract", "start", "done", "amendment"],
            "branch_sha": current_head,
            "pr_sha": current_head,
        })

        labels = json.loads(
            (CLI_FIXTURES / "problem-explanations.json").read_text(encoding="utf-8")
        )["labels"]
        problem = self.problem_values(human, labels)

        self.assertEqual(0, code)
        self.assertEqual("1.1", output["gtp"])
        self.assertEqual("halt", output["state"])
        self.assertEqual("stale_evidence", output["halt_reason"])
        self.assertEqual(
            ["stale_evidence", "invalid_transition"],
            [diagnostic["token"] for diagnostic in output["diagnostics"]],
        )
        self.assertEqual(
            [
                "https://github.com/o/r/issues/1#issuecomment-103",
                "https://github.com/o/r/pull/7",
            ],
            output["diagnostics"][0]["urls"],
        )
        self.assertEqual(
            "not_presented",
            output["task_context"]["conditions"]["extra"]["evidence_status"],
        )
        self.assertEqual(
            {
                "acquisition",
                "acquisition_errors",
                "amendment",
                "authority",
                "bound_pr",
                "branch",
                "command",
                "contract",
                "details",
                "diagnostics",
                "done",
                "gtp",
                "halt_reason",
                "issue_url",
                "next_action",
                "pr_candidate",
                "primary_url",
                "start",
                "state",
                "stop",
                "task_context",
            },
            set(output),
        )

        repair = problem[3]
        resolution = problem[7]
        self.assertIn("完了条件を追加した後", human[3])
        self.assertIn("PRの内容が変わり", human[3])
        self.assertIn("完了条件を追加した後", problem[0])
        self.assertIn("PRの内容が変わり", problem[0])
        self.assertIn("前回のDone", problem[1])
        self.assertIn("追加後の現在の完了条件", problem[1])
        self.assertIn("現在のPR", problem[1])
        self.assertIn("条件ごとの確認資料", problem[1])
        self.assertIn("変更前のcommit", problem[2])
        self.assertIn("完了条件が追加", problem[2])
        self.assertNotIn("EvidenceがDoneのsource head SHAと一致しません", problem[0])
        self.assertNotIn("Evidenceが示すcommitとDoneが示すsource headが異なります", problem[2])
        for expected in (
            "現在の完了条件",
            "現在のPRの最新commit",
            "すべての完了条件",
            "確認資料",
        ):
            self.assertIn(expected, repair)
            self.assertIn(expected, resolution)
        self.assertIn("Doneを出し直す", repair)
        self.assertIn("merge済みなら同じIssueではDoneを出し直せない", resolution)
        self.assertIn("PRの内容", repair)
        self.assertIn("人が確認する", repair)
        self.assertIn("必要なPR修正", repair)
        self.assertIn("書き換えない", problem[4])
        self.assertIn("GTPだけで決めない", problem[4])
        self.assertIn("最初のURLを開き", problem[5])
        self.assertIn("現在のPRの最新commit", problem[5])
        self.assertNotIn("current effective revision", repair)
        self.assertNotIn("current PR head", repair)
        self.assertNotIn("effective Done Condition", repair)

        probe = (
            Path(__file__).parent.parent / "acceptance" / "v1.0.4" / "human-probe.md"
        ).read_text(encoding="utf-8")
        match = re.search(
            r"## 提示した複合halt\n\nPresented SHA-256: `([0-9a-f]{64})`"
            r"\n\n```text\n(.*?)\n```",
            probe,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match)
        presented_hash, presented_text = match.groups()
        self.assertEqual(
            hashlib.sha256(presented_text.encode()).hexdigest(), presented_hash
        )
        start = human.index("問題の整理:")
        self.assertEqual("\n".join(human[start:start + 9]), presented_text)

    def test_status_done_http_fixture_uses_all_production_logic(self) -> None:
        code, human, output = self.call_http_fixture("done-success.json")
        self.assertEqual(0, code)
        self.assertEqual("done", output["state"])
        self.assertEqual("complete", output["acquisition"])
        self.assertEqual("HTTP fixture acceptance", output["task_context"]["goal"])
        self.assertIn(
            "  結論: Done ClaimのEvidence bindingとnative mergeを確認しました。"
            "条件内容の充足はEvidenceを読んで判断してください。",
            human,
        )
        self.assertIn("  この作業の目的: HTTP fixture acceptance", human)
        self.assertIn(
            "  ここまでが人向けの説明です。続くJSONは機械処理用です。",
            human,
        )

    def test_purpose_alignment_walking_skeleton_fires_all_attachments(self) -> None:
        code, human, output = self.call_http_fixture(
            "purpose-alignment-walking-skeleton.json"
        )
        self.assertEqual(0, code)
        self.assertEqual("done", output["state"])
        self.assertEqual("none", output["authority"])
        self.assertIn(
            "Done Conditionの自然言語上の充足は自動判定していない",
            output["task_context"]["not_proven"],
        )
        self.assertEqual(
            [
                "Check RunがDone Conditionの内容を十分に検査したこと",
                "Artifactの内容がDone Conditionを満たすこと",
                "Issue本文・通常commentに未解決事項がないこと",
                "actor本人性",
                "credential安全性",
                "GitHub外情報を参照しなかったこと",
            ],
            output["task_context"]["evidence_limits"],
        )
        self.assertTrue(
            any("Evidence bindingを確認した条件" in line for line in human)
        )
        self.assertTrue(
            any("条件内容の充足は自動判定していません" in line for line in human)
        )
        self.assertEqual(
            "https://github.com/o/r/issues/1",
            output["task_context"]["handoff_url"],
        )
        self.assertTrue(any("未確認事項の確認先" in line for line in human))
        self.assertEqual([], output["diagnostics"])
        self.assertIsNone(output["halt_reason"])
        self.assertEqual("none_done", output["next_action"])

    def test_purpose_safety_walking_skeleton_halts_after_stop(self) -> None:
        code, human, output = self.call_http_fixture(
            "purpose-safety-walking-skeleton.json"
        )
        cause = "https://github.com/o/r/issues/1#issuecomment-103"
        self.assertEqual(0, code)
        self.assertEqual("halt", output["state"])
        self.assertEqual("terminal_violation", output["halt_reason"])
        self.assertEqual("inspect_halt", output["next_action"])
        self.assertEqual(cause, output["primary_url"])
        self.assertEqual(f"最初のURL: {cause}", human[4])

    def test_status_required_live_binding_http_matrix(self) -> None:
        matrix = json.loads(
            (HTTP_FIXTURES / "live-binding-matrix.json").read_text(encoding="utf-8")
        )
        for case in matrix:
            with self.subTest(case=case["name"]):
                code, human, output = self.call_http_matrix_case(case)
                self.assertEqual(case["state"], output["state"])
                if case["state"] in {None, "halt"}:
                    self.assertIn("問題の整理:", human)
                else:
                    self.assertNotIn("問題の整理:", human)
                if case.get("reason"):
                    self.assertEqual(case["reason"], output["diagnostics"][0]["token"])
                if case.get("next_action"):
                    self.assertEqual(case["next_action"], output["next_action"])
                if case["name"] == "scope outside":
                    values = self.problem_values(
                        human,
                        json.loads(
                            (CLI_FIXTURES / "problem-explanations.json").read_text(
                                encoding="utf-8"
                            )
                        )["labels"],
                    )
                    self.assertIn("README.md", values[0])
                    self.assertIn(
                        "このIssueで変更してよい範囲はsrc/ですが、"
                        "PRに範囲外のfile README.mdが含まれています",
                        "\n".join(human),
                    )
                    problem = "\n".join(values)
                    self.assertNotIn("binding", problem)
                    self.assertNotIn("束縛", problem)
                if case["name"] in {"default branch is rejected", "late successor"}:
                    values = self.problem_values(
                        human,
                        json.loads(
                            (CLI_FIXTURES / "problem-explanations.json").read_text(
                                encoding="utf-8"
                            )
                        )["labels"],
                    )
                    problem = "\n".join(values)
                    self.assertIn(
                        "Issueの記録が指す対象とGitHub上の対象が一致しません",
                        values[0],
                    )
                    self.assertNotIn("PRの変更file", problem)
                    self.assertNotIn("変更してよい範囲", problem)
                if case.get("first_url"):
                    self.assertEqual(case["first_url"], output["primary_url"])
                    if output["diagnostics"]:
                        self.assertEqual(
                            case["first_url"], output["diagnostics"][0]["urls"][0]
                        )
                if case.get("pending_check"):
                    self.assertEqual(0, code)
                    self.assertEqual([], output["diagnostics"])
                    self.assertIsNone(output["halt_reason"])
                    self.assertEqual("none", output["authority"])
                    self.assertEqual("complete", output["acquisition"])
                    self.assertEqual(
                        {
                            "gtp", "command", "issue_url", "state", "halt_reason",
                            "details", "next_action", "primary_url", "authority",
                            "acquisition", "contract", "start", "done", "stop",
                            "branch", "pr_candidate", "bound_pr", "diagnostics",
                            "acquisition_errors", "task_context",
                        },
                        set(output),
                    )
                    self.assertIn("Check Run未完了", output["task_context"]["not_proven"])
                    if case.get("native_merge_observed"):
                        self.assertNotIn("native merge未確認", output["task_context"]["not_proven"])
                    else:
                        self.assertIn("native merge未確認", output["task_context"]["not_proven"])
                    text = "\n".join(human)
                    self.assertIn("Check Runは未完了です", text)
                    self.assertIn("変更やmergeをせず", text)
                    self.assertIn("同じURLをread-onlyで再確認", text)
                    self.assertNotIn("Evidence bindingを確認", text)
                    self.assertNotIn("native merge判断待ち", text)
                    self.assertNotIn("作業を止め", text)
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
                    self.assertIn("  この作業の目的: HTTP matrix", human)
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
                if case.get("acquisition_code"):
                    self.assertEqual(
                        case["acquisition_code"], output["acquisition_errors"][0]["code"]
                    )
                    self.assertEqual("incomplete", output["acquisition"])
                    self.assertEqual(2, code)


class HumanPostTests(unittest.TestCase):
    def assert_error(self, source: str, target: str, code: str) -> None:
        result = validate_human_post(source, target)
        self.assertFalse(result.valid)
        self.assertIn(code, [error["code"] for error in result.errors])

    def test_issue_and_pr_contracts_are_distinct_and_valid(self) -> None:
        for target in ("issue", "pr"):
            with self.subTest(target=target):
                result = validate_human_post(human_body(target, technical=True), target)
                self.assertTrue(result.valid, result.errors)
        self.assertIn("現在わかっていること", SECTIONS["issue"])
        self.assertIn("変更内容", SECTIONS["pr"])
        self.assertIn("利用者への影響", SECTIONS["pr"])
        self.assertNotIn("何が問題か", SECTIONS["pr"])

    def test_required_relationship_rejects_missing_duplicate_order_and_empty(self) -> None:
        valid = human_body("pr")
        self.assert_error(valid.replace("## ゴール\n\nゴールについて人が判断できる説明です。\n\n", ""), "pr", "missing_section")
        self.assert_error(valid + "\n## 目的\n\n重複です。\n", "pr", "duplicate_section")
        swapped = valid.replace("## 目的", "## TEMP", 1).replace("## ゴール", "## 目的", 1).replace("## TEMP", "## ゴール", 1)
        self.assert_error(swapped, "pr", "invalid_first_section")
        self.assert_error(valid.replace("## 現在地\n\n現在地について人が判断できる説明です。", "## 現在地"), "pr", "empty_section")

    def test_technical_details_are_optional_but_last(self) -> None:
        valid = human_body("issue")
        self.assertTrue(validate_human_post(valid, "issue").valid)
        misplaced = valid.replace("## ゴール", "## 技術詳細\n\n先行した技術情報です。\n\n## ゴール", 1)
        self.assert_error(misplaced, "issue", "invalid_technical_position")
        self.assert_error(valid + "\n## 技術詳細\n", "issue", "empty_section")

    def test_decision_record_requires_four_nonempty_unique_ordered_fields(self) -> None:
        valid = human_body("issue")
        for field in ("採用した方針", "今回は採用しない案", "見直す条件", "根拠・履歴"):
            with self.subTest(field=field):
                line = next(line for line in valid.splitlines() if line.startswith(f"- {field}:"))
                self.assert_error(valid.replace(line + "\n", ""), "issue", "missing_decision_field")
                self.assert_error(valid.replace(line, f"- {field}:"), "issue", "empty_decision_field")
                self.assert_error(valid.replace(line, f"{line}\n{line}"), "issue", "duplicate_decision_field")
        expected = (
            "- 採用した方針: 既存の公開契約どおりに修正する。新しい設計判断は行わない。\n"
            "- 今回は採用しない案: none\n"
            "- 見直す条件: 既存契約と実際のbehaviorが衝突していることを再現した場合。\n"
            "- 根拠・履歴: none"
        )
        self.assert_error(valid.replace(expected, "\n".join(reversed(expected.splitlines()))), "issue", "invalid_decision_field_order")

    def test_decision_reference_is_none_or_fixed_github_permalink(self) -> None:
        valid = human_body("issue")
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
        source = human_body("issue").replace("- 採用した方針:", "判断の背景です。\n\n- 採用した方針:")
        result = validate_human_post(source, "issue")
        self.assertTrue(result.valid, result.errors)

    def test_fenced_and_commented_headings_cannot_satisfy_contract(self) -> None:
        source = "```markdown\n" + human_body("issue") + "```\n<!--\n" + human_body("issue") + "-->\n"
        result = validate_human_post(source, "issue")
        self.assertFalse(result.valid)
        self.assertEqual("invalid_first_section", result.errors[0]["code"])
        self.assertIn("missing_section", [error["code"] for error in result.errors])
        self.assert_error("<!--\n" + human_body("issue"), "issue", "invalid_first_section")
        fenced_comment = human_body("pr").replace("## ゴール", "```html\n<!--\n```\n\n## ゴール", 1)
        result = validate_human_post(fenced_comment, "pr")
        self.assertTrue(result.valid, result.errors)
        commented_fence = human_body("pr").replace("## ゴール", "<!--\n```text\n-->\n## ゴール", 1)
        result = validate_human_post(commented_fence, "pr")
        self.assertTrue(result.valid, result.errors)
        closing_fence = human_body("pr").replace("## ゴール", "<!--\n``` -->\n## ゴール", 1)
        result = validate_human_post(closing_fence, "pr")
        self.assertTrue(result.valid, result.errors)
        for literal in ("`<!--`", "``<!--``", "\\<!--"):
            with self.subTest(literal=literal):
                source = human_body("pr").replace("目的について人が判断できる説明です。", f"literal {literal} を説明します。")
                result = validate_human_post(source, "pr")
                self.assertTrue(result.valid, result.errors)
        synthesized = human_body("pr").replace("## 目的", "<!-- instruction -->## 目的", 1)
        self.assert_error(synthesized, "pr", "invalid_first_section")
        repeated = human_body("pr").replace("目的について人が判断できる説明です。", "visible <!-- closed --> <!--")
        result = validate_human_post(repeated, "pr")
        self.assertTrue(result.valid, result.errors)
        for prefix in ("unmatched ` ", "escaped \\` "):
            with self.subTest(prefix=prefix):
                source = human_body("pr").replace("目的について人が判断できる説明です。", prefix + "<!--")
                result = validate_human_post(source, "pr")
                self.assertTrue(result.valid, result.errors)
        for mismatched in ("`<!--``", "``<!--`"):
            with self.subTest(mismatched=mismatched):
                source = human_body("pr").replace("目的について人が判断できる説明です。", mismatched)
                result = validate_human_post(source, "pr")
                self.assertTrue(result.valid, result.errors)

    def test_commonmark_heading_indentation_obeys_visible_boundaries(self) -> None:
        indented = human_body("pr").replace("## ", "   ## ")
        result = validate_human_post(indented, "pr")
        self.assertTrue(result.valid, result.errors)
        self.assert_error(human_body("pr").replace("## ", "    ## "), "pr", "invalid_first_section")
        self.assert_error(human_body("pr", technical=True) + "\n  ## Appendix\n\nvisible\n", "pr", "invalid_technical_position")
        empty = human_body("pr").replace("## 現在地\n\n現在地について人が判断できる説明です。", "## 現在地\n\n  ## Appendix\n\nvisible")
        self.assert_error(empty, "pr", "empty_section")

    def test_contract_does_not_require_language_issue_or_gtp_record(self) -> None:
        source = human_body("pr").replace("について人が判断できる説明です。", " section is complete.")
        result = validate_human_post(source, "pr")
        self.assertTrue(result.valid, result.errors)
        self.assertNotIn("Issue", source)
        self.assertNotIn("gtp-record", source)


if __name__ == "__main__":
    unittest.main()
