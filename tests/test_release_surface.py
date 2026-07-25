from __future__ import annotations

import copy
import json
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tomllib
import unittest
from unittest.mock import patch

import build_backend
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
RELEASE_LOCK_REQUIRED_ENV = "GTP_RELEASE_LOCK_REQUIRED"
GIT_TIMEOUT_SECONDS = 10
LOCKED_SOURCE_PATHS = {
    "DESIGN.md",
    "GTP.md",
    "README.md",
    "tests/fixtures/http/live-binding-matrix.json",
    "tests/fixtures/setup-preflight.json",
}


def _git(*arguments: str) -> subprocess.CompletedProcess[bytes] | None:
    """Run bounded, non-fetching git in ROOT, or None when it cannot finish."""
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(
        GIT_CEILING_DIRECTORIES=str(ROOT.resolve().parent),
        GIT_NO_LAZY_FETCH="1",
        GIT_TERMINAL_PROMPT="0",
    )
    try:
        return subprocess.run(
            ["git", "--no-replace-objects", "--no-lazy-fetch", *arguments],
            cwd=ROOT,
            capture_output=True,
            env=environment,
            stdin=subprocess.DEVNULL,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _blob_at(commit: str, relative_path: str) -> bytes | None:
    """Exact bytes of a tracked path at a commit, ignoring any `refs/replace`."""
    result = _git("cat-file", "blob", f"{commit}:{relative_path}")
    if result is None or result.returncode != 0:
        return None
    return result.stdout


def _verification_mode(*, blob_readable: bool, required: bool) -> str:
    """Decide from explicit policy how to treat an unreadable pinned commit."""
    if blob_readable:
        return "verify"
    return "fail" if required else "skip"


def _release_lock_required() -> bool:
    value = os.environ.get(RELEASE_LOCK_REQUIRED_ENV)
    if value is None:
        return False
    if value == "1":
        return True
    raise ValueError(f"{RELEASE_LOCK_REQUIRED_ENV} must be 1 when set")


def _observed_verification_mode(commit: str) -> str:
    required = _release_lock_required()
    return _verification_mode(
        blob_readable=_blob_at(commit, "GTP.md") is not None,
        required=required,
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


def _workflow_job(workflow: str, name: str) -> str:
    """Return one top-level workflow job without parsing unrelated YAML."""
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)",
        workflow,
    )
    if match is None:
        raise AssertionError(f"workflow job not found: {name}")
    return match.group("body")


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
            "uvx --from github-task-protocol==1.0.2 gtp status",
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

    def test_verification_mode_requires_explicit_policy(self) -> None:
        # (blob_readable, required) -> mode
        table = {
            (True, True): "verify",
            (True, False): "verify",
            (False, True): "fail",
            (False, False): "skip",
        }
        for (blob, required), expected in table.items():
            with self.subTest(blob=blob, required=required):
                self.assertEqual(
                    expected,
                    _verification_mode(
                        blob_readable=blob,
                        required=required,
                    ),
                )

    def test_observed_verification_mode_uses_required_signal(self) -> None:
        missing = "0" * 40
        with patch.dict(os.environ, {RELEASE_LOCK_REQUIRED_ENV: "1"}):
            self.assertEqual("fail", _observed_verification_mode(missing))
        with patch.dict(os.environ):
            os.environ.pop(RELEASE_LOCK_REQUIRED_ENV, None)
            self.assertEqual("skip", _observed_verification_mode(missing))

    def test_release_lock_requirement_rejects_unknown_value(self) -> None:
        with patch.dict(os.environ, {RELEASE_LOCK_REQUIRED_ENV: "0"}):
            with self.assertRaisesRegex(ValueError, "must be 1 when set"):
                _observed_verification_mode("0" * 40)

    def test_git_subprocess_is_bounded_and_hermetic(self) -> None:
        with patch.dict(os.environ, {"GIT_DIR": "/unrelated/repository"}):
            with patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(
                    ["git", "--version"], GIT_TIMEOUT_SECONDS
                ),
            ) as run:
                self.assertIsNone(_git("--version"))
        call = run.call_args
        self.assertEqual(
            ["git", "--no-replace-objects", "--no-lazy-fetch", "--version"],
            call.args[0],
        )
        self.assertEqual(ROOT, call.kwargs["cwd"])
        self.assertEqual(subprocess.DEVNULL, call.kwargs["stdin"])
        self.assertTrue(call.kwargs["capture_output"])
        self.assertEqual(GIT_TIMEOUT_SECONDS, call.kwargs["timeout"])
        git_environment = {
            key: value
            for key, value in call.kwargs["env"].items()
            if key.startswith("GIT_")
        }
        self.assertEqual(
            {
                "GIT_CEILING_DIRECTORIES": str(ROOT.resolve().parent),
                "GIT_NO_LAZY_FETCH": "1",
                "GIT_TERMINAL_PROMPT": "0",
            },
            git_environment,
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
                f"commit {candidate} cannot be read although release lock "
                "verification is required; fetch the pinned commit "
                "(actions/checkout fetch-depth: 0)"
            )
        if mode == "skip":
            self.skipTest(
                f"commit {candidate} cannot be read in this source tree, so the "
                "locked source sha256 values cannot be verified here"
            )
        original = _blob_at(candidate, "GTP.md")
        self.assertIsNotNone(original)
        with patch.dict(
            os.environ,
            {
                "GIT_DIR": str(ROOT / "missing-git-dir"),
                "GIT_OBJECT_DIRECTORY": str(ROOT / "missing-object-directory"),
            },
        ):
            self.assertEqual(original, _blob_at(candidate, "GTP.md"))
        self.assertEqual([], _locked_source_mismatches(run["expected_lock"], candidate))

    def test_a_self_consistent_but_wrong_lock_is_detected(self) -> None:
        run = json.loads(
            (ROOT / "acceptance" / "problem-explanations" / "run.json").read_text(
                encoding="utf-8"
            )
        )
        candidate = run["candidate"]["sha"]
        mode = _observed_verification_mode(candidate)
        if mode == "fail":
            self.fail(
                f"commit {candidate} cannot be read although release lock "
                "verification is required; fetch the pinned commit "
                "(actions/checkout fetch-depth: 0)"
            )
        if mode == "skip":
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
        self.assertIn(
            "`pyproject.toml`は、このsourceからbuildするpackage versionとして"
            "`1.0.3`を宣言しています",
            readme,
        )
        self.assertIn(
            "この値はpublicationのEvidenceでも、exact source commitのidentityでもありません",
            readme,
        )
        self.assertNotIn("source内容のidentity", readme)
        self.assertNotIn("現在のsource candidate", readme)
        self.assertTrue((ROOT / "acceptance" / "release-notes-v1.0.2.md").exists())
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertIn(
            "## ADR-030: CLIを任意validatorとしてPyPIへ公開する",
            decisions,
        )

    def test_v103_release_documents_are_time_stable(self) -> None:
        self.assertEqual(
            {
                "current_design": "DESIGN.md",
                "decision": "adr/0036-reproducible-release-artifacts.md",
                "notes": "acceptance/release-notes-v1.0.3.md",
            },
            MATRIX["release_documents"],
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "`pyproject.toml`は、このsourceからbuildするpackage versionとして"
            "`1.0.3`を宣言しています",
            readme,
        )
        self.assertIn(
            "この値はpublicationのEvidenceでも、exact source commitのidentityでもありません",
            readme,
        )
        self.assertNotIn("source内容のidentity", readme)
        public_commands = re.findall(
            r"^uvx --from github-task-protocol==[^ ]+ gtp (?:status|check) .+$",
            readme,
            flags=re.MULTILINE,
        )
        self.assertEqual(
            [
                "uvx --from github-task-protocol==1.0.2 gtp status <issue-url>",
                "uvx --from github-task-protocol==1.0.2 gtp check <comment.md>",
            ],
            public_commands,
        )
        self.assertEqual(2, readme.count("github-task-protocol==1.0.2"))
        self.assertNotIn("github-task-protocol==1.0.3", readme)
        self.assertNotIn("github-task-protocol==X.Y.Z", readme)
        self.assertIn(
            "https://pypi.org/project/github-task-protocol/X.Y.Z/", readme
        )
        self.assertIn(
            "https://github.com/shinya0x00/github-task-protocol/"
            "releases/tag/vX.Y.Z",
            readme,
        )
        self.assertIn("両方が解決できることを確認した後だけです", readme)
        self.assertIn("下の2つのcommandの`1.0.2`だけを", readme)
        self.assertIn("public-release-v1.0.2.json", readme)
        cli_section = readme.split("## CLIは任意の検証器", 1)[1].split(
            "## 仕様と判断記録", 1
        )[0]
        for line in cli_section.splitlines():
            if "1.0.2" not in line:
                continue
            for unstable_label in (
                "latest",
                "recommended",
                "current",
                "最新",
                "推奨",
                "現行",
            ):
                self.assertNotIn(unstable_label, line.lower())
        for unstable in (
            "現在のsource candidate",
            "`1.0.3`（公開前）",
            "まだ公開していない",
            "利用commandは検証済みの`1.0.2`に固定",
        ):
            self.assertNotIn(unstable, readme)

        notes_path = ROOT / "acceptance" / "release-notes-v1.0.3.md"
        self.assertTrue(notes_path.exists())
        notes = notes_path.read_text(encoding="utf-8")
        self.assertIn("# GitHub Task Protocol 1.0.3 release notes", notes)
        self.assertIn("publicationをClaimしない", notes)
        self.assertIn("PR artifactは検証専用", notes)
        self.assertIn("main artifactだけを公開候補", notes)
        self.assertIn("SOURCE_SHA", notes)
        self.assertIn("SOURCE_DATE_EPOCH", notes)
        self.assertIn("8項目の「問題の整理」", notes)
        self.assertIn("machine JSONのkey集合", notes)
        self.assertIn("`DESIGN.md`、`DECISIONS.md`、`adr/`", notes)
        for excluded in (
            "generic Contract amendment semantics",
            "human-post checker／gate",
            "line-budgetの置き換えまたはstatus split",
            "publication operation",
        ):
            self.assertIn(excluded, notes)

    def test_sdist_release_surface_is_explicit(self) -> None:
        self.assertEqual(
            [
                "GTP.md",
                "README.md",
                "DESIGN.md",
                "DECISIONS.md",
                "LICENSE",
                "pyproject.toml",
                "build_backend.py",
                "adr",
                "src",
                "tests",
                "acceptance",
            ],
            MATRIX["required_sdist"],
        )
        manifest = set(build_backend.SDIST_SOURCE_MANIFEST)
        self.assertNotIn(".gitignore", manifest)
        self.assertFalse(any(path.startswith(".github/") for path in manifest))
        self.assertIn("adr/0036-reproducible-release-artifacts.md", manifest)
        self.assertIn("acceptance/release-notes-v1.0.3.md", manifest)
        for required in MATRIX["required_sdist"]:
            self.assertTrue(
                required in manifest
                or any(path.startswith(f"{required}/") for path in manifest),
                required,
            )

    def test_reproducible_release_design_and_adr_are_current(self) -> None:
        design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
        adr_path = ROOT / "adr" / "0036-reproducible-release-artifacts.md"
        self.assertTrue(adr_path.exists())
        adr = adr_path.read_text(encoding="utf-8")
        self.assertIn(
            "[ADR-036](adr/0036-reproducible-release-artifacts.md)", design
        )
        for value in (
            "SOURCE_SHA",
            "SOURCE_DATE_EPOCH",
            "BUILD-INFO",
            "SHA256SUMS",
            "Python 3.11",
            "Python 3.12",
            "Python 3.13",
            "90日",
        ):
            self.assertIn(value, design)
            self.assertIn(value, adr)
        self.assertIn("PR artifactは検証専用", design)
        self.assertIn("main artifactだけを公開候補", design)
        self.assertIn("同じmanifest oracle", design)
        self.assertIn("merge tree", design)
        self.assertIn("公開候補sdist／wheel", design)
        self.assertIn("producer処理は実行しない", design)
        self.assertIn("temporary directory", design)
        self.assertIn("full 40文字のlowercase commit SHAだけ", design)
        self.assertIn("2つのclean source export", adr)
        self.assertIn("tag作成、GitHub Release、PyPI uploadは行わない", adr)
        self.assertIn("GTP Record、state、halt reason", adr)
        self.assertIn("同じmanifest oracle", adr)
        self.assertIn("merge tree", adr)
        self.assertIn("公開候補sdist／wheel", adr)
        self.assertIn("producer処理は実行しない", adr)
        self.assertIn("temporary directory", adr)
        self.assertIn("full 40文字のlowercase commit SHAだけ", adr)

        notes = (ROOT / "acceptance" / "release-notes-v1.0.3.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("同じmanifest oracle", notes)
        self.assertIn("merge tree", notes)
        self.assertIn("公開候補sdist／wheel", notes)
        self.assertIn("producer処理は実行しない", notes)
        self.assertIn("temporary directory", notes)

    def test_repository_has_one_non_publish_ci_workflow(self) -> None:
        workflows = list((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertEqual([ROOT / ".github" / "workflows" / "ci.yml"], workflows)
        workflow = workflows[0].read_text(encoding="utf-8")
        self.assertIn('python-version: ["3.11", "3.12", "3.13"]', workflow)
        self.assertIn('GTP_RELEASE_LOCK_REQUIRED: "1"', workflow)
        if (
            os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("GITHUB_REPOSITORY")
            == "shinya0x00/github-task-protocol"
        ):
            self.assertEqual("1", os.environ.get(RELEASE_LOCK_REQUIRED_ENV))
        self.assertIn("Build twice from clean exports", workflow)
        self.assertIn("Rebuild the wheel from a fresh sdist environment", workflow)
        self.assertIn("Assemble checksummed artifact", workflow)
        self.assertIn("Install wheel in clean environment", workflow)
        self.assertIn("Run all tests against the installed artifact", workflow)
        self.assertIn(
            '"$RUNNER_TEMP/venv-check/bin/python" -m unittest discover -s tests',
            workflow,
        )
        self.assertNotIn("publish", workflow.lower())

    def test_ci_builds_exact_source_once_and_fans_out_one_artifact(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        pins = {
            "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
            "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
            "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
            "actions/download-artifact": "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
        }
        self.assertEqual(
            {action.removeprefix("actions/"): pin for action, pin in pins.items()},
            MATRIX["ci_release"]["actions"],
        )
        self.assertEqual("3.11", MATRIX["ci_release"]["producer_python"])
        self.assertEqual(
            ["3.11", "3.12", "3.13"],
            MATRIX["ci_release"]["consumer_python"],
        )
        self.assertEqual(
            {
                "pull_request": "github.event.pull_request.head.sha",
                "main_push": "github.sha",
            },
            MATRIX["ci_release"]["source_sha"],
        )
        self.assertEqual(
            {
                "pull_request": "v1.0.3-pr-verification-<SOURCE_SHA>",
                "main_push": "v1.0.3-main-candidate-<SOURCE_SHA>",
                "sidecars": ["BUILD-INFO", "SHA256SUMS"],
                "retention_days": 90,
            },
            MATRIX["ci_release"]["artifacts"],
        )
        for pin in pins.values():
            self.assertRegex(pin, r"\A[0-9a-f]{40}\Z")
        for action, pin in pins.items():
            self.assertIn(f"{action}@{pin}", workflow)
        uses_line_count = sum(
            1
            for line in workflow.splitlines()
            if re.match(r"^\s*(?:-\s*)?uses:", line)
        )
        action_uses = re.findall(
            r"^\s*(?:-\s*)?uses:\s+actions/([^@\s]+)@([0-9a-f]{40})\s*$",
            workflow,
            flags=re.MULTILINE,
        )
        self.assertEqual(uses_line_count, len(action_uses))
        expected_uses = {
            action.removeprefix("actions/"): pin for action, pin in pins.items()
        }
        self.assertEqual(set(expected_uses), {action for action, _ in action_uses})
        for action, execution_identity in action_uses:
            self.assertEqual(expected_uses[action], execution_identity)
        for mutable_ref in (
            "actions/checkout@v",
            "actions/setup-python@v",
            "actions/upload-artifact@v",
            "actions/download-artifact@v",
        ):
            self.assertNotIn(mutable_ref, workflow)

        self.assertIn("github.event.pull_request.head.sha", workflow)
        self.assertIn("github.sha", workflow)
        self.assertIn('PYTHONDONTWRITEBYTECODE: "1"', workflow)
        self.assertIn('[[ "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]', workflow)
        self.assertGreaterEqual(workflow.count("ref: ${{ env.SOURCE_SHA }}"), 2)
        self.assertEqual(3, workflow.count("persist-credentials: false"))
        self.assertIn('git show -s --format=%ct "$SOURCE_SHA"', workflow)
        self.assertGreaterEqual(workflow.count('git archive "$SOURCE_SHA"'), 2)
        self.assertIn("SOURCE_DATE_EPOCH", workflow)

        build_job = _workflow_job(workflow, "build")
        integration_job = _workflow_job(workflow, "integration")
        oracle = "build_backend._validate_tracked_source_manifest"
        self.assertEqual(2, workflow.count(oracle))
        self.assertEqual(1, build_job.count(oracle))
        self.assertEqual(1, integration_job.count(oracle))
        self.assertIn('git ls-tree -r --name-only "$SOURCE_SHA"', build_job)
        self.assertNotIn("git ls-tree -r --name-only HEAD", build_job)
        self.assertIn("git ls-tree -r --name-only HEAD", integration_job)
        self.assertNotIn('git ls-tree -r --name-only "$SOURCE_SHA"', integration_job)
        # Full unit tests exercise the backend with temporary archives.  This
        # boundary excludes the release-candidate producer pipeline itself.
        for forbidden in (
            "Build twice from clean exports",
            "Rebuild the wheel from a fresh sdist environment",
            "Check distribution metadata with Twine",
            "Assemble checksummed artifact",
            "actions/upload-artifact",
            "needs: build",
            "release-artifact",
            "SHA256SUMS",
            "BUILD-INFO",
        ):
            self.assertNotIn(forbidden, integration_job)

        self.assertIn('python-version: "3.11"', workflow)
        self.assertIn('python-version: ["3.11", "3.12", "3.13"]', workflow)
        self.assertIn("needs: build", workflow)
        self.assertIn("integration:", workflow)
        self.assertIn("GitHub's synthetic merge", workflow)
        self.assertIn(
            'test "$(git rev-parse HEAD)" = "${{ github.sha }}"', workflow
        )
        self.assertIn(
            'test "$(git rev-parse HEAD^2)" = '
            '"${{ github.event.pull_request.head.sha }}"',
            workflow,
        )
        self.assertIn("Run merge-result integration tests", workflow)
        self.assertIn("release-ready:", workflow)
        self.assertIn("needs: [build, integration, test]", workflow)
        self.assertIn("Gate the complete release-ready result", workflow)
        self.assertIn('test "${{ needs.build.result }}" = "success"', workflow)
        self.assertIn('test "${{ needs.test.result }}" = "success"', workflow)
        self.assertIn(
            'test "${{ needs.integration.result }}" = "success"', workflow
        )
        self.assertIn("v1.0.3-pr-verification-${SOURCE_SHA}", workflow)
        self.assertIn("v1.0.3-main-candidate-${SOURCE_SHA}", workflow)
        self.assertIn("retention-days: 90", workflow)
        self.assertIn("BUILD-INFO", workflow)
        self.assertIn("SHA256SUMS", workflow)
        for build_info_field in (
            "SOURCE_SHA",
            "SOURCE_DATE_EPOCH",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "ARTIFACT_NAME",
        ):
            self.assertIn(
                f'f"{build_info_field}={{os.environ[\'{build_info_field}\']}}"',
                workflow,
            )
        self.assertIn("sha256sum -c SHA256SUMS", workflow)
        self.assertIn("pip wheel --no-index --no-deps", workflow)
        self.assertNotIn("--no-build-isolation", workflow)
        self.assertIn("python -m twine check", workflow)
        self.assertIn("cmp", workflow)


if __name__ == "__main__":
    unittest.main()
