from __future__ import annotations

import json
import hashlib
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
PUBLISHED_CLI_VERSION = "1.0.2"


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
            f"uvx --from github-task-protocol=={PUBLISHED_CLI_VERSION} gtp status",
            readme,
        )
        self.assertNotIn("package registryへ一般公開していません", readme)
        self.assertNotIn("![", readme)

    def test_setup_preflight_contract(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        fixture = json.loads(
            (ROOT / "tests" / "fixtures" / "setup-preflight.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("gtp-setup-preflight/v1", fixture["schema"])
        self.assertEqual(
            [
                "instructionなし",
                "両立可能",
                "未接続dependency",
                "別authority／意味衝突",
            ],
            [case["result"] for case in fixture["cases"]],
        )
        self.assertEqual(
            [True, True, False, False],
            [case["continue_setup"] for case in fixture["cases"]],
        )
        self.assertEqual(
            [
                "working_tree",
                "branches",
                "commits",
                "pushes",
                "issue",
                "comments",
                "labels",
                "pull_requests",
            ],
            fixture["mutation_surface"],
        )
        blocker_labels = [
            "何が問題か",
            "どこが問題か",
            "なぜそう判断したか",
            "どこを直すか",
            "何を直さないか",
            "次の安全な一手",
            "最初に確認するURL",
            "解決したと判断する条件",
        ]
        for case in fixture["cases"]:
            self.assertEqual(case["before_snapshot"], case["after_snapshot"])
            self.assertEqual(
                fixture["mutation_surface"], list(case["mutation_callbacks"])
            )
            self.assertTrue(
                all(count == 0 for count in case["mutation_callbacks"].values())
            )
            self.assertEqual(0, case["mutation_callbacks"]["commits"])
            self.assertEqual(0, case["mutation_callbacks"]["pushes"])
            self.assertIn(f"`{case['result']}`", readme)
            if case["continue_setup"]:
                self.assertIsInstance(case["expected_display"], str)
            else:
                self.assertEqual(blocker_labels, list(case["expected_display"]))
        external, conflict = fixture["cases"][2:]
        self.assertTrue(
            external["expected_display"]["最初に確認するURL"].startswith(
                "https://github.com/"
            )
        )
        self.assertEqual(
            "修正先Issue未確認",
            conflict["expected_display"]["最初に確認するURL"],
        )
        self.assertIn(
            "test／mock providerによるproduction代用",
            external["expected_display"]["何を直さないか"],
        )
        preflight = readme.index("### file・branch変更前のpreflight")
        branch_creation = readme.index("target fileを変更する前にrepositoryのdefault branch")
        self.assertLess(preflight, branch_creation)
        for label in blocker_labels:
            self.assertIn(f"「{label}」", readme)
        self.assertIn(
            "test／mock providerでproduction dependencyを代用せず", readme
        )
        self.assertIn(
            "working tree、branch、commit、push、Issue、comment、label、PRを変更せず",
            readme,
        )
        self.assertIn("repair Issueも自動作成しません", readme)
        self.assertIn("owner URLはread-only取得で確認できた場合だけ", readme)
        self.assertIn("`修正先Issue未確認`", readme)

    def test_problem_explanation_acceptance_is_bound_and_non_mutating(self) -> None:
        root = ROOT / "acceptance" / "problem-explanations"
        run = json.loads((root / "run.json").read_text(encoding="utf-8"))
        probe = (root / "human-probe.md").read_text(encoding="utf-8")
        self.assertEqual(
            "github-task-protocol-problem-explanation-acceptance/v2",
            run["schema"],
        )
        self.assertEqual("accepted", run["status"])
        self.assertEqual("1.0.3", run["candidate"]["version"])
        self.assertEqual("1.0", run["candidate"]["protocol"])
        self.assertTrue(run["candidate"]["clean_install"])
        self.assertEqual(131, run["candidate"]["installed_test_count"])
        candidate = run["candidate"]["sha"]
        lock = run["expected_lock"]
        canonical = json.dumps(
            lock["cases"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.assertEqual(
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            lock["cases_sha256"],
        )
        self.assertEqual(
            "https://github.com/shinya0x00/github-task-protocol/"
            "issues/113#issuecomment-5068513697",
            lock["evidence_url"],
        )
        source_prefix = (
            "https://github.com/shinya0x00/github-task-protocol/blob/"
            f"{candidate}/"
        )
        for case in lock["cases"].values():
            for source in case["sources"]:
                self.assertTrue(source["url"].startswith(source_prefix))
                path = ROOT / source["url"][len(source_prefix):]
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), source["sha256"]
                )
        record_input = lock["cases"]["record"]["exact_input"]
        self.assertEqual({"malformed", "edited", "id_collision"}, set(record_input))
        self.assertIn("<!-- gtp-record:v1 -->", record_input["malformed"][0]["body"])
        self.assertNotEqual(
            record_input["edited"][0]["created_at"],
            record_input["edited"][0]["updated_at"],
        )
        self.assertEqual(2, len(record_input["id_collision"]))
        self.assertNotEqual(
            record_input["id_collision"][0]["body"],
            record_input["id_collision"][1]["body"],
        )
        self.assertEqual(
            {"record", "binding", "evidence", "acquisition", "carrier", "setup", "normal"},
            set(run["cases"]),
        )

        def observed_reason(machine):
            if machine is None:
                return None
            if machine.get("halt_reason"):
                return machine["halt_reason"]
            if machine.get("acquisition_errors"):
                return machine["acquisition_errors"][0]["code"]
            if machine.get("errors"):
                return machine["errors"][0]["code"]
            return None

        def problem_present(stdout):
            return "問題の整理:" in stdout

        def problem_block(stdout):
            lines = stdout.splitlines()
            start = lines.index("問題の整理:")
            return "\n".join(lines[start:start + 9])

        comparisons = []
        for name, case in run["cases"].items():
            with self.subTest(case=name):
                expected = lock["cases"][name]["expected_result"]
                machine = case["machine_json"]
                observed_state = machine.get("state") if machine else None
                values = [
                    case["exact_input"] == lock["cases"][name]["exact_input"],
                    case["expected_result"] == expected,
                    observed_state == expected["state"],
                    observed_reason(machine) == expected["reason"],
                    case["exit_code"] == expected["exit_code"],
                    problem_present(case["stdout"])
                    == (expected["problem_block"] == "present"),
                ]
                self.assertTrue(all(values))
                comparisons.extend(values)
                self.assertTrue(case["owner_evidence"].startswith("https://github.com/"))
                self.assertTrue(case["not_inferred"])
        for variant in run["cases"]["record"]["variant_observations"].values():
            self.assertEqual("halt", variant["machine_json"]["state"])
            self.assertEqual("invalid_record", variant["machine_json"]["halt_reason"])
            self.assertEqual(0, variant["exit_code"])
            self.assertTrue(problem_present(variant["stdout"]))

        boundary = run["mutation_boundary"]
        before = boundary["local_worktree_before"]
        after = boundary["local_worktree_after"]
        self.assertEqual(
            hashlib.sha256(before.encode()).hexdigest(),
            boundary["local_worktree_before_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(after.encode()).hexdigest(),
            boundary["local_worktree_after_sha256"],
        )
        self.assertEqual(before, after)
        methods = [
            method
            for case_methods in boundary["http_methods"].values()
            for method in case_methods
        ]
        self.assertTrue(all(method == "GET" for method in methods))
        self.assertEqual(
            run["cases"]["setup"]["mutation_callbacks"],
            boundary["setup_callbacks"],
        )
        self.assertTrue(all(value == 0 for value in boundary["setup_callbacks"].values()))
        self.assertEqual(boundary["live_before"], boundary["live_after"])
        self.assertEqual(
            run["cases"]["normal"]["before_snapshot"], boundary["live_before"]
        )
        self.assertEqual(
            run["cases"]["normal"]["after_snapshot"], boundary["live_after"]
        )
        self.assertEqual(
            "halt / invalid_record", run["self_regression_guard"]["observed"]
        )
        self.assertFalse(
            run["self_regression_guard"]["unmanaged_crash_or_missing_output"]
        )
        self.assertEqual("accepted", run["human_probe"]["status"])
        self.assertEqual("問題なし", run["human_probe"]["A"])
        self.assertEqual("問題なし", run["human_probe"]["B"])
        for label, case_name in (("A", "record"), ("B", "binding")):
            match = re.search(
                rf"## {label}\n\nPresented SHA-256: `([0-9a-f]{{64}})`"
                rf"\n\n```text\n(.*?)\n```",
                probe,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(match)
            presented_hash, presented_text = match.groups()
            self.assertEqual(
                hashlib.sha256(presented_text.encode()).hexdigest(), presented_hash
            )
            self.assertEqual(
                problem_block(run["cases"][case_name]["stdout"]), presented_text
            )
            self.assertEqual(
                run["human_probe"]["presented_problem_sha256"][label],
                presented_hash,
            )
        self.assertEqual(
            all(comparisons),
            run["claim_boundary"]["production_outputs_match_expected"],
        )
        self.assertTrue(run["claim_boundary"]["production_outputs_match_expected"])
        self.assertTrue(run["claim_boundary"]["human_comprehension_accepted"])
        self.assertFalse(run["claim_boundary"]["production_code_changed"])
        self.assertFalse(run["claim_boundary"]["merge_authority"])
        self.assertIn("Status: accepted", probe)
        self.assertEqual(2, probe.count("回答: 問題なし"))
        self.assertNotIn("回答: pending", probe)

    def test_problem_explanation_recovery_recalculates_merged_evidence(self) -> None:
        root = ROOT / "acceptance" / "problem-explanations"
        recovery = json.loads((root / "recovery.json").read_text(encoding="utf-8"))
        self.assertEqual(
            "github-task-protocol-problem-explanation-recovery/v1",
            recovery["schema"],
        )
        self.assertEqual("candidate_pending_done_and_merge", recovery["status"])
        self.assertEqual(
            "https://github.com/shinya0x00/github-task-protocol/issues/116",
            recovery["source_issue"],
        )

        predecessor = recovery["predecessor"]
        observation = predecessor["gtp_observation"]
        snapshot = predecessor["github_snapshot"]
        canonical = json.dumps(
            snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.assertEqual(
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            predecessor["snapshot_sha256"],
        )
        self.assertEqual("halt", observation["state"])
        self.assertEqual("terminal_violation", observation["halt_reason"])
        self.assertFalse(observation["done_present"])
        self.assertFalse(observation["stop_present"])
        self.assertEqual(113, snapshot["issue"]["number"])
        self.assertEqual("open", snapshot["issue"]["state"])
        self.assertEqual(
            len(snapshot["comments"]), snapshot["issue"]["comment_count"]
        )
        self.assertEqual(
            ["contract_record", "start_record", "expected_lock"],
            [comment["role"] for comment in snapshot["comments"]],
        )
        self.assertEqual(
            observation["primary_url"],
            "https://github.com/shinya0x00/github-task-protocol/"
            "issues/113#issuecomment-5064223276",
        )

        pull_request = snapshot["pull_request"]
        self.assertEqual(115, pull_request["number"])
        self.assertTrue(pull_request["merged"])
        self.assertEqual("closed", pull_request["state"])
        self.assertEqual(
            "4df2eaf7515010ec2c6c40cb92e5e0d9455e119c",
            pull_request["head_sha"],
        )
        self.assertEqual(
            "3082c6d573391bc0913f8ba13e0d966ce806b5e5",
            pull_request["merge_commit_sha"],
        )
        self.assertIn(
            recovery["merged_acceptance"]["source_pr"],
            observation["diagnostic_urls"],
        )
        self.assertEqual(
            pull_request["merge_commit_sha"],
            recovery["merged_acceptance"]["main_merge_sha"],
        )

        merged_files = {
            item["path"]: item for item in recovery["merged_acceptance"]["files"]
        }
        for path in (
            "acceptance/problem-explanations/run.json",
            "acceptance/problem-explanations/human-probe.md",
        ):
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                merged_files[path]["sha256"],
            )
        base_test = merged_files["tests/test_release_surface.py"]
        self.assertIn(
            recovery["merged_acceptance"]["main_merge_sha"],
            base_test["content_url"],
        )
        self.assertRegex(base_test["sha256"], r"^[0-9a-f]{64}$")

        self.test_problem_explanation_acceptance_is_bound_and_non_mutating()
        boundary = recovery["claim_boundary"]
        self.assertFalse(boundary["predecessor_repaired"])
        self.assertFalse(boundary["production_code_changed"])
        self.assertFalse(boundary["human_response_reinterpreted"])
        self.assertFalse(boundary["merge_authority"])
        self.assertTrue(
            boundary["successor_completion_requires_done_before_native_merge"]
        )

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

    def test_explicit_setup_external_run_records_both_passed_probes(self) -> None:
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
        self.assertEqual("passed", run["status"])
        self.assertTrue(run["delivery"]["readme_on_default_branch"])
        self.assertEqual(
            "passed",
            run["setup_probe"]["status"],
        )
        self.assertEqual("passed", run["issue_probe"]["status"])
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
        probe = run["issue_probe"]
        self.assertEqual("target Issue URL only", probe["input_boundary"])
        self.assertEqual("Cursor / Grok 4.5", probe["provider_model"])
        self.assertFalse(probe["preflight"]["default_branch_protected"])
        self.assertEqual([], probe["preflight"]["default_branch_rules"])
        self.assertEqual(
            "add the second required line to issue-url-probe.txt",
            probe["observed_result"]["reported_first_task_action"],
        )
        self.assertTrue(probe["observed_result"]["existing_branch_reused"])
        self.assertTrue(probe["observed_result"]["existing_pull_request_reused"])
        self.assertFalse(probe["observed_result"]["duplicate_branch_created"])
        self.assertFalse(probe["observed_result"]["duplicate_pull_request_created"])
        self.assertTrue(probe["observed_result"]["default_branch_unchanged"])
        self.assertTrue(probe["observed_result"]["done_binding_valid"])
        self.assertFalse(probe["observed_result"]["native_merge_complete"])
        self.assertEqual(
            {
                "external_setup_success": True,
                "issue_url_only_success": True,
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
        current_evidence = json.loads(
            (ROOT / "acceptance" / "public-release-v1.0.2.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("1.0.3", PROJECT["version"])
        self.assertEqual(
            PUBLISHED_CLI_VERSION, current_evidence["pypi"]["package_version"]
        )
        self.assertTrue(current_evidence["github_release"]["published_at"])
        self.assertTrue(current_evidence["github_release"]["latest_stable"])
        self.assertTrue(current_evidence["pypi"]["files_redownloaded_and_hashed"])
        self.assertTrue(
            current_evidence["public_validation"][
                "github_release_and_pypi_bytes_equal_to_build"
            ]
        )
        self.assertEqual(
            "done",
            current_evidence["public_validation"]["authenticated_live_status"][
                "state"
            ],
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("CLI `1.0.2`は[PyPI]", readme)
        self.assertIn("public-release-v1.0.2.json", readme)
        self.assertIn("現在のsource candidateは`1.0.3`（公開前）", readme)
        self.assertIn("利用commandは検証済みの`1.0.2`に固定", readme)
        self.assertNotIn("github-task-protocol==1.0.3", readme)
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
