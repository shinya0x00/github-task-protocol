from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gtp.cli import main
from gtp.status import StatusResult


FIXTURE = Path(__file__).parent / "fixtures" / "carriers" / "contract-valid.md"


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


if __name__ == "__main__":
    unittest.main()
