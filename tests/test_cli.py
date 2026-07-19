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

from gtp.cli import main
from gtp.status import StatusResult


FIXTURE = Path(__file__).parent / "fixtures" / "carriers" / "contract-valid.md"
HTTP_FIXTURES = Path(__file__).parent / "fixtures" / "http"


class CliTests(unittest.TestCase):
    def call(self, argv: list[str]) -> tuple[int, list[str], dict]:
        output = StringIO()
        with redirect_stdout(output):
            code = main(argv)
        text = output.getvalue()
        json_start = text.index("{")
        human = text[:json_start].rstrip("\n").splitlines()
        return code, human, json.loads(text[json_start:])

    def call_http_fixture(self, name: str) -> tuple[int, dict]:
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
            code, _, output = self.call(["status", fixture["issue_url"]])
        self.assertEqual([], pending)
        return code, output

    def call_http_matrix_case(self, case: dict) -> tuple[int, dict]:
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
            code, _, output = self.call(["status", issue_url])
            return code, output

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

    def test_status_halt_is_successful_observation(self) -> None:
        observed = StatusResult("https://github.com/o/r/issues/1", "halt")
        with patch("gtp.cli.evaluate_issue", return_value=observed):
            code, human, output = self.call(["status", observed.issue_url])
        self.assertEqual(0, code)
        self.assertEqual("halt", output["state"])
        self.assertEqual("状態: halt", human[0])
        self.assertTrue(human[-1].startswith("非許可表示:"))

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

    def test_status_http_walking_skeleton_uses_production_path(self) -> None:
        code, output = self.call_http_fixture("walking-skeleton.json")
        self.assertEqual(0, code)
        self.assertEqual("unmanaged", output["state"])
        self.assertEqual("complete", output["acquisition"])

    def test_status_done_http_fixture_uses_all_production_logic(self) -> None:
        code, output = self.call_http_fixture("done-success.json")
        self.assertEqual(0, code)
        self.assertEqual("done", output["state"])
        self.assertEqual("complete", output["acquisition"])

    def test_status_required_live_binding_http_matrix(self) -> None:
        matrix = json.loads(
            (HTTP_FIXTURES / "live-binding-matrix.json").read_text(encoding="utf-8")
        )
        for case in matrix:
            with self.subTest(case=case["name"]):
                code, output = self.call_http_matrix_case(case)
                self.assertEqual(case["state"], output["state"])
                if case.get("reason"):
                    self.assertEqual(case["reason"], output["diagnostics"][0]["token"])
                if case.get("acquisition_code"):
                    self.assertEqual(
                        case["acquisition_code"], output["acquisition_errors"][0]["code"]
                    )
                    self.assertEqual("incomplete", output["acquisition"])
                    self.assertEqual(2, code)


if __name__ == "__main__":
    unittest.main()
