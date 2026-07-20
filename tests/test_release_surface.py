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
    def test_private_planning_metadata_is_absent(self) -> None:
        marker = "doc" + "trine"
        forbidden = (
            marker,
            "a5ad793c" + "7c8bc52eae82645799b621356e3e6650",
            f"github.com/shinya0x00/{marker}",
            f"github.com/shinya-reiji/{marker}",
        )
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8").lower()
            except UnicodeError:
                continue
            for value in forbidden:
                self.assertNotIn(value, text, str(path.relative_to(ROOT)))

    def test_readme_requires_explicit_setup_request_before_mutation(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(readme.splitlines()), MATRIX["budgets"]["README.md"])
        introduction = readme.split("## 4つのRecord", 1)[0]
        self.assertIn("## 推奨: 明示的にsetupを依頼", introduction)
        self.assertIn(
            "bare GTP repository URLだけではsetup依頼にもrepository変更のauthorizationにもなりません",
            introduction,
        )
        self.assertIn(
            "このrepositoryへGTPを導入するDraft setup PRを作ってください。",
            introduction,
        )
        self.assertIn("https://github.com/shinya0x00/github-task-protocol", introduction)
        self.assertIn("latest stable Release", introduction)
        self.assertIn("`draft: false`", introduction)
        self.assertIn("`prerelease: false`", introduction)
        self.assertIn("tagをcommit SHAまでdereference", introduction)
        self.assertIn("そのcommitの`GTP.md`だけ", introduction)
        self.assertIn(
            "https://raw.githubusercontent.com/shinya0x00/"
            "github-task-protocol/<commit-sha>/GTP.md",
            introduction,
        )
        self.assertIn("上書きせず停止", introduction)
        self.assertIn("`gtp/setup-<tag>-<short-sha>`", introduction)
        branch_guard = introduction.index("target fileを変更する前に")
        vendor = introduction.index("そのcommitの`GTP.md`だけ")
        adapter = introduction.index("root `AGENTS.md`がなければ作成")
        self.assertLess(branch_guard, vendor)
        self.assertLess(branch_guard, adapter)
        self.assertIn("現在branchがdefault branchではなくsetup branch", introduction)
        self.assertIn("commitとpushはsetup branchだけ", introduction)
        self.assertIn("setup開始前に記録したSHA", introduction)
        self.assertIn("GitHub branch protectionまたはruleset", introduction)
        self.assertIn(
            "agentが手順を理解できることと、実行中ずっと意図の境界内に留まり続けることは別の能力",
            introduction,
        )
        self.assertIn("GTP単独の強制力はこの手順の受入対象にしません", introduction)
        self.assertIn("setup agentは保護設定を変更せず", introduction)
        self.assertIn("Draft setup PR", introduction)
        self.assertIn("人間がsetup PRをmergeするまで導入完了としません", introduction)
        manual = introduction.split("## 手動導入", 1)[1]
        steps = re.findall(r"^[1-3]\. ", manual, flags=re.MULTILINE)
        self.assertEqual(3, len(steps))
        self.assertIn("[`GTP.md`](GTP.md)", readme)
        self.assertIn("人間がGTPを使うためにCLIをinstallする必要はありません", readme)
        self.assertIn(
            f"uvx --from github-task-protocol=={PROJECT['version']} gtp status",
            readme,
        )
        self.assertNotIn("package registryへ一般公開していません", readme)
        self.assertNotIn("![", readme)

    def test_explicit_setup_delivery_defers_external_acceptance_until_merge(self) -> None:
        evidence = json.loads(
            (
                ROOT
                / "acceptance"
                / "explicit-setup-install"
                / "delivery.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            "github-task-protocol-explicit-setup-delivery/v1",
            evidence["schema"],
        )
        self.assertEqual("delivery_candidate_pending_merge", evidence["status"])
        self.assertFalse(
            evidence["delivery_boundary"]["external_acceptance_required_for_delivery_done"]
        )
        self.assertEqual(
            "after native merge in a separate Issue and pull request",
            evidence["delivery_boundary"]["external_acceptance_activation"],
        )
        self.assertFalse(evidence["external_acceptance"]["dedicated_acceptance_repository"])
        self.assertEqual(
            "pending_after_delivery_merge",
            evidence["external_acceptance"]["status"],
        )
        self.assertEqual(
            "explain_or_request_purpose_without_repository_mutation",
            evidence["input_boundary"]["bare_repository_url"],
        )
        self.assertEqual(
            {
                "external_setup_success": False,
                "version_1_0_2_published": False,
                "merge_authority": False,
            },
            evidence["claim_boundary"],
        )
        self.assertEqual(
            "description_only_no_repository_mutation",
            evidence["observed_probes"][0]["result"],
        )
        self.assertFalse((ROOT / "acceptance" / "url-only-install").exists())

    def test_explicit_setup_external_run_starts_pending_without_success_claim(self) -> None:
        run = json.loads(
            (
                ROOT
                / "acceptance"
                / "explicit-setup-install"
                / "run.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            "github-task-protocol-explicit-setup-acceptance/v1",
            run["schema"],
        )
        self.assertEqual("pending_issue_url_probe", run["status"])
        self.assertTrue(run["delivery"]["readme_on_default_branch"])
        self.assertEqual(
            "passed",
            run["setup_probe"]["status"],
        )
        self.assertEqual("pending", run["issue_probe"]["status"])
        attempt = run["setup_probe"]["attempts"][0]
        self.assertTrue(attempt["vendored_bytes_equal"])
        self.assertTrue(attempt["default_branch_direct_push_observed"])
        self.assertEqual(
            "passed_with_observed_boundary_drift",
            attempt["verdict"],
        )
        self.assertTrue(attempt["merge_allowed"])
        self.assertEqual(
            "68afc1c343ad8d394b79f9d34e9be2b7118cb04d",
            attempt["human_merge_commit"],
        )
        self.assertFalse(
            run["setup_probe"]["safety_boundary"]["gtp_enforcement_strength_evaluated"]
        )
        self.assertEqual(
            {
                "external_setup_success": True,
                "issue_url_only_success": False,
                "version_1_0_2_published": False,
                "merge_authority": False,
            },
            run["claim_boundary"],
        )

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

    def test_release_plan_resolves_to_public_evidence_and_policy_decision(self) -> None:
        release_plan = json.loads(
            (ROOT / "acceptance" / "release.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            "superseded_by_public_release_evidence", release_plan["status"]
        )
        self.assertEqual(
            "acceptance/public-release-v1.0.1.json",
            release_plan["superseded_by"],
        )
        public_evidence = json.loads(
            (ROOT / release_plan["superseded_by"]).read_text(encoding="utf-8")
        )
        self.assertEqual(
            "github-task-protocol-public-release-evidence/v1",
            public_evidence["schema"],
        )
        self.assertEqual(
            release_plan["package_version"],
            public_evidence["pypi"]["package_version"],
        )
        self.assertTrue(public_evidence["github_release"]["published"])
        self.assertTrue(public_evidence["pypi"]["files_redownloaded_and_hashed"])
        self.assertNotEqual(PROJECT["version"], public_evidence["pypi"]["package_version"])
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("現在のsource candidateは`1.0.2`", readme)
        self.assertIn("公開確認前", readme)
        self.assertTrue((ROOT / "acceptance" / "release-notes-v1.0.2.md").exists())
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertIn(
            "## ADR-030: CLIを任意validatorとしてPyPIへ公開する",
            decisions,
        )

    def test_repository_has_one_non_publish_ci_workflow(self) -> None:
        workflows = list((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertEqual([ROOT / ".github" / "workflows" / "ci.yml"], workflows)
        workflow = workflows[0].read_text(encoding="utf-8")
        self.assertIn('python-version: ["3.11", "3.12", "3.13"]', workflow)
        self.assertIn("Build sdist and wheel without network", workflow)
        self.assertIn("Install wheel in clean environment", workflow)
        self.assertIn("Run installed status E2E", workflow)
        self.assertIn(
            ".venv-check/bin/python -m unittest discover -s tests -p 'test_cli.py'",
            workflow,
        )
        self.assertNotIn("publish", workflow.lower())


if __name__ == "__main__":
    unittest.main()
