from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

import build_backend


class BuildBackendTests(unittest.TestCase):
    def test_wheel_contains_package_entrypoint_and_complete_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            filename = build_backend.build_wheel(directory)
            with ZipFile(Path(directory) / filename) as wheel:
                names = set(wheel.namelist())
                self.assertIn("gtp/cli.py", names)
                self.assertIn(
                    "github_task_protocol-0.1.0.dist-info/entry_points.txt", names
                )
                record_name = "github_task_protocol-0.1.0.dist-info/RECORD"
                rows = list(csv.reader(StringIO(wheel.read(record_name).decode("utf-8"))))
                self.assertEqual(names, {row[0] for row in rows})


if __name__ == "__main__":
    unittest.main()
