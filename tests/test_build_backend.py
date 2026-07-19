from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

import build_backend
import gtp


class BuildBackendTests(unittest.TestCase):
    def test_runtime_and_package_versions_match_v1_release(self) -> None:
        self.assertEqual("1.0.0", build_backend._project()["version"])
        self.assertEqual(build_backend._project()["version"], gtp.__version__)

    def test_wheel_contains_package_entrypoint_and_complete_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            filename = build_backend.build_wheel(directory)
            with ZipFile(Path(directory) / filename) as wheel:
                names = set(wheel.namelist())
                self.assertIn("gtp/cli.py", names)
                self.assertIn("gtp/presentation.py", names)
                self.assertIn(
                    "github_task_protocol-1.0.0.dist-info/entry_points.txt", names
                )
                record_name = "github_task_protocol-1.0.0.dist-info/RECORD"
                rows = list(csv.reader(StringIO(wheel.read(record_name).decode("utf-8"))))
                self.assertEqual(names, {row[0] for row in rows})

    def test_installed_console_script_runs_status_and_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel_dir = root / "dist"
            wheel_dir.mkdir()
            filename = build_backend.build_wheel(str(wheel_dir))
            environment = root / "venv"
            subprocess.run(
                [sys.executable, "-m", "venv", str(environment)],
                check=True,
                capture_output=True,
                text=True,
            )
            python = environment / "bin" / "python"
            command = environment / "bin" / "gtp"
            subprocess.run(
                [str(python), "-m", "pip", "install", "--no-deps", str(wheel_dir / filename)],
                check=True,
                capture_output=True,
                text=True,
            )
            checked = subprocess.run(
                [str(command), "check", str(Path(__file__).parent / "fixtures" / "carriers" / "contract-valid.md")],
                check=False,
                capture_output=True,
                text=True,
            )
            status = subprocess.run(
                [str(command), "status", "not-a-github-issue-url"],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(0, checked.returncode)
        self.assertIn("offline schemaに適合", checked.stdout)
        self.assertIn('"command": "check"', checked.stdout)
        self.assertEqual(2, status.returncode)
        self.assertIn("状態: 不明", status.stdout)
        self.assertIn('"command": "status"', status.stdout)


if __name__ == "__main__":
    unittest.main()
