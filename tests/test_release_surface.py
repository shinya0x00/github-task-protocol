from __future__ import annotations

import json
from pathlib import Path
import re
import tomllib
import unittest

import gtp


ROOT = Path(__file__).parent.parent
MATRIX = json.loads(
    (Path(__file__).parent / "fixtures" / "release" / "surface.json").read_text(
        encoding="utf-8"
    )
)
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


class ReleaseSurfaceTests(unittest.TestCase):
    def test_readme_is_plain_first_three_step_entry_to_canonical_spec(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(readme.splitlines()), MATRIX["budgets"]["README.md"])
        introduction = readme.split("## 4つのRecord", 1)[0]
        steps = re.findall(r"^[1-3]\. ", introduction, flags=re.MULTILINE)
        self.assertEqual(3, len(steps))
        self.assertIn("[`GTP.md`](GTP.md)", readme)
        self.assertIn("人間がGTPを使うためにCLIをinstallする必要はありません", readme)
        self.assertIn("package registryへ一般公開していません", readme)
        self.assertIn("PYTHONPATH=src python3 -m gtp status", readme)
        self.assertNotIn("uvx --from github-task-protocol==", readme)
        self.assertNotIn("![", readme)

    def test_readme_copies_the_canonical_adapter_exactly(self) -> None:
        spec = (ROOT / "GTP.md").read_text(encoding="utf-8")
        adapter = next(
            line
            for line in spec.splitlines()
            if line.startswith("> このrepositoryはrootの`GTP.md`")
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(adapter, readme)

    def test_root_surface_and_line_budgets(self) -> None:
        for required in MATRIX["required_root"]:
            self.assertTrue((ROOT / required).exists(), required)
        for forbidden in MATRIX["forbidden_root"]:
            self.assertFalse((ROOT / forbidden).exists(), forbidden)
        self.assertLessEqual(
            len((ROOT / "GTP.md").read_text(encoding="utf-8").splitlines()),
            MATRIX["budgets"]["GTP.md"],
        )
        production = sum(
            len(path.read_text(encoding="utf-8").splitlines())
            for path in (ROOT / "src" / "gtp").glob("*.py")
        )
        self.assertLessEqual(production, MATRIX["budgets"]["production_python"])

    def test_package_metadata_and_runtime_version_are_consistent(self) -> None:
        project = PROJECT
        self.assertEqual(MATRIX["distribution"], project["name"])
        self.assertEqual(MATRIX["python"], project["requires-python"])
        self.assertEqual(MATRIX["license"], project["license"])
        self.assertEqual([], project["dependencies"])
        self.assertEqual("gtp.cli:main", project["scripts"][MATRIX["console_script"]])
        self.assertEqual(project["version"], gtp.__version__)
        self.assertEqual(
            "https://github.com/shinya0x00/github-task-protocol",
            project["urls"]["Repository"],
        )

    def test_repository_has_one_non_publish_ci_workflow(self) -> None:
        workflows = list((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertEqual([ROOT / ".github" / "workflows" / "ci.yml"], workflows)
        workflow = workflows[0].read_text(encoding="utf-8")
        self.assertIn('python-version: ["3.11", "3.12", "3.13"]', workflow)
        self.assertIn("Build sdist and wheel without network", workflow)
        self.assertIn("Install wheel in clean environment", workflow)
        self.assertNotIn("publish", workflow.lower())


if __name__ == "__main__":
    unittest.main()
