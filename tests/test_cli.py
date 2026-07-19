from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from gtp.cli import main
from gtp.status import StatusResult


FIXTURE = Path(__file__).parent / "fixtures" / "carriers" / "contract-valid.md"
HTTP_FIXTURES = Path(__file__).parent / "fixtures" / "http"


class CliTests(unittest.TestCase):
    def call(self, argv: list[str]) -> tuple[int, dict]:
        output = StringIO()
        with redirect_stdout(output):
            code = main(argv)
        return code, json.loads(output.getvalue())

    def test_check_valid_carrier_exits_zero(self) -> None:
        code, output = self.call(["check", str(FIXTURE)])
        self.assertEqual(0, code)
        self.assertTrue(output["schema_valid"])

    def test_check_normal_comment_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "comment.md"
            path.write_text("ordinary comment\n", encoding="utf-8")
            code, output = self.call(["check", str(path)])
        self.assertEqual(1, code)
        self.assertFalse(output["recognized"])

    def test_status_halt_is_successful_observation(self) -> None:
        observed = StatusResult("https://github.com/o/r/issues/1", "halt")
        with patch("gtp.cli.evaluate_issue", return_value=observed):
            code, output = self.call(["status", observed.issue_url])
        self.assertEqual(0, code)
        self.assertEqual("halt", output["state"])

    def test_status_without_state_exits_two(self) -> None:
        observed = StatusResult(
            "https://github.com/o/r/issues/1",
            None,
            acquisition_errors=[{"code": "acquisition_incomplete"}],
        )
        with patch("gtp.cli.evaluate_issue", return_value=observed):
            code, output = self.call(["status", observed.issue_url])
        self.assertEqual(2, code)
        self.assertIsNone(output["state"])

    def test_status_http_walking_skeleton_uses_production_path(self) -> None:
        fixture = json.loads(
            (HTTP_FIXTURES / "walking-skeleton.json").read_text(encoding="utf-8")
        )
        pending = list(fixture["requests"])

        def open_fixture(request, timeout):
            self.assertEqual("GET", request.get_method())
            self.assertEqual(30, timeout)
            expected = pending.pop(0)
            self.assertEqual(expected["url"], request.full_url)
            response = MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = json.dumps(expected["body"]).encode("utf-8")
            response.headers.items.return_value = expected.get("headers", {}).items()
            return response

        with patch.dict("os.environ", {}, clear=True), patch(
            "gtp.github.urlopen", side_effect=open_fixture
        ):
            code, output = self.call(["status", fixture["issue_url"]])

        self.assertEqual([], pending)
        self.assertEqual(0, code)
        self.assertEqual("unmanaged", output["state"])
        self.assertTrue(output["acquisition"]["complete"])


if __name__ == "__main__":
    unittest.main()
