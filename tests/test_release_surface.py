from __future__ import annotations

import copy
import json
import hashlib
from pathlib import Path
import re
import subprocess
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
ACCEPTANCE_CANDIDATE = "46103e0fdd41364f98e098518f6b91211fb1f5ea"
LOCKED_SOURCE_PATHS = {
    "DESIGN.md",
    "GTP.md",
    "README.md",
    "tests/fixtures/http/live-binding-matrix.json",
    "tests/fixtures/setup-preflight.json",
}


def _git(*arguments: str) -> subprocess.CompletedProcess[bytes] | None:
    """Run git in ROOT, or None when no git client can be executed."""
    try:
        return subprocess.run(
            ["git", "--no-replace-objects", *arguments], cwd=ROOT, capture_output=True
        )
    except OSError:
        return None


def _blob_at(commit: str, relative_path: str) -> bytes | None:
    """Exact bytes of a tracked path at a commit, ignoring any `refs/replace`."""
    result = _git("cat-file", "blob", f"{commit}:{relative_path}")
    if result is None or result.returncode != 0:
        return None
    return result.stdout


def _verification_mode(
    *, blob_readable: bool, git_available: bool, has_git_dir: bool, shallow: bool
) -> str:
    """Decide how to treat an unreadable pinned commit.

    A distributed source tree may legitimately lack a git client, a `.git`, or
    this repository's history, and none of those can verify the lock. A shallow
    checkout of this repository is different: it would silently stop verifying,
    so it must fail loudly instead.
    """
    if blob_readable:
        return "verify"
    if not git_available or not has_git_dir:
        return "skip"
    return "fail" if shallow else "skip"


def _observed_verification_mode(commit: str) -> str:
    version = _git("--version")
    shallow = _git("rev-parse", "--is-shallow-repository")
    return _verification_mode(
        blob_readable=_blob_at(commit, "GTP.md") is not None,
        git_available=version is not None and version.returncode == 0,
        has_git_dir=(ROOT / ".git").exists(),
        shallow=shallow is not None and shallow.stdout.strip() == b"true",
    )


def _locked_sources(lock: dict, candidate: str) -> list[tuple[str, str]]:
    prefix = (
        f"https://github.com/shinya0x00/github-task-protocol/blob/{candidate}/"
    )
    return [
        (source["url"][len(prefix):], source["sha256"])
        for case in lock["cases"].values()
        for source in case["sources"]
    ]


def _locked_source_mismatches(lock: dict, candidate: str) -> list[str]:
    """Relative paths whose recorded sha256 differs from the blob at the commit."""
    mismatches = []
    for relative_path, expected in _locked_sources(lock, candidate):
        blob = _blob_at(candidate, relative_path)
        if blob is None or hashlib.sha256(blob).hexdigest() != expected:
            mismatches.append(relative_path)
    return mismatches


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

    def test_verification_mode_covers_every_environment(self) -> None:
        # (blob_readable, git_available, has_git_dir, shallow) -> mode
        table = {
            (True, True, True, False): "verify",
            (True, True, True, True): "verify",
            (False, True, True, True): "fail",
            (False, True, True, False): "skip",
            (False, True, False, False): "skip",
            (False, False, True, True): "skip",
            (False, False, False, False): "skip",
        }
        for (blob, client, git_dir, shallow), expected in table.items():
            with self.subTest(blob=blob, client=client, git_dir=git_dir, shallow=shallow):
                self.assertEqual(
                    expected,
                    _verification_mode(
                        blob_readable=blob,
                        git_available=client,
                        has_git_dir=git_dir,
                        shallow=shallow,
                    ),
                )

    def test_locked_release_sources_match_their_pinned_commit(self) -> None:
        run = json.loads(
            (ROOT / "acceptance" / "problem-explanations" / "run.json").read_text(
                encoding="utf-8"
            )
        )
        candidate = run["candidate"]["sha"]
        self.assertEqual(ACCEPTANCE_CANDIDATE, candidate)
        mode = _observed_verification_mode(candidate)
        if mode == "fail":
            self.fail(
                f"commit {candidate} is unreachable in this shallow checkout, so "
                "the release lock is no longer verified; fetch the full history "
                "(actions/checkout fetch-depth: 0)"
            )
        if mode == "skip":
            self.skipTest(
                f"commit {candidate} cannot be read in this source tree, so the "
                "locked source sha256 values cannot be verified here"
            )
        self.assertEqual([], _locked_source_mismatches(run["expected_lock"], candidate))

    def test_a_self_consistent_but_wrong_lock_is_detected(self) -> None:
        run = json.loads(
            (ROOT / "acceptance" / "problem-explanations" / "run.json").read_text(
                encoding="utf-8"
            )
        )
        candidate = run["candidate"]["sha"]
        if _observed_verification_mode(candidate) != "verify":
            self.skipTest(f"commit {candidate} cannot be read in this source tree")
        # A lock regenerated from the wrong tree stays internally consistent, so
        # only comparing against the pinned blobs can reject it.
        wrong = copy.deepcopy(run["expected_lock"])
        wrong["cases"]["record"]["sources"][0]["sha256"] = "0" * 64
        corrupted = wrong["cases"]["record"]["sources"][0]["url"].rsplit(
            f"{candidate}/", 1
        )[1]
        self.assertEqual([corrupted], _locked_source_mismatches(wrong, candidate))
        canonical = json.dumps(
            wrong["cases"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        wrong["cases_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.assertNotEqual(run["expected_lock"]["cases_sha256"], wrong["cases_sha256"])
        self.assertEqual([corrupted], _locked_source_mismatches(wrong, candidate))

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
        self.assertEqual("46103e0fdd41364f98e098518f6b91211fb1f5ea", candidate)
        lock = run["expected_lock"]
        self.assertEqual(
            "b1eae2812a59e269dd17f97fc3848ee404e3d4b6ee6afe04d134c8a5b630bbb4",
            lock["cases_sha256"],
        )
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
        relative_paths = []
        for case in lock["cases"].values():
            for source in case["sources"]:
                self.assertTrue(source["url"].startswith(source_prefix))
                relative_path = Path(source["url"][len(source_prefix):])
                self.assertNotIn("..", relative_path.parts)
                self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")
                relative_paths.append(relative_path.as_posix())
        self.assertEqual(18, len(relative_paths))
        self.assertEqual(LOCKED_SOURCE_PATHS, set(relative_paths))
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

    def test_explicit_setup_run_preserves_historical_boundary_drift(self) -> None:
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
        self.assertTrue(run["delivery"]["readme_on_default_branch"])
        attempt = run["setup_probe"]["attempts"][0]
        self.assertTrue(attempt["vendored_bytes_equal"])
        self.assertTrue(attempt["default_branch_direct_push_observed"])
        self.assertTrue(attempt["default_branch_restored_to_base"])
        self.assertEqual(
            "68afc1c343ad8d394b79f9d34e9be2b7118cb04d",
            attempt["human_merge_commit"],
        )
        self.assertFalse(
            run["setup_probe"]["safety_boundary"]["gtp_enforcement_strength_evaluated"]
        )

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        branch_first_requires_no_direct_push = (
            "default branchへ直接pushしない" in readme
        )
        observed_branch_first_compliance = not attempt[
            "default_branch_direct_push_observed"
        ]
        self.assertTrue(branch_first_requires_no_direct_push)
        self.assertFalse(observed_branch_first_compliance)
        self.assertNotEqual(
            branch_first_requires_no_direct_push,
            observed_branch_first_compliance,
        )

    def test_issue_url_probe_records_safe_branch_reuse(self) -> None:
        run = json.loads(
            (
                ROOT
                / "acceptance"
                / "explicit-setup-install"
                / "run.json"
            ).read_text(encoding="utf-8")
        )
        probe = run["issue_probe"]
        self.assertEqual("passed", probe["status"])
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
        self.assertTrue(run["claim_boundary"]["issue_url_only_success"])
        self.assertFalse(run["claim_boundary"]["version_1_0_2_published"])
        self.assertFalse(run["claim_boundary"]["merge_authority"])

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
