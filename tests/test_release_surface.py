from __future__ import annotations

import copy
import json
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
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
SOURCE_PACKAGE_VERSION = "1.0.4"
SOURCE_PROTOCOL_VERSION = "1.1"
PUBLISHED_CLI_VERSION = "1.0.3"
PUBLISHED_CANDIDATE = "70fab3aacf8637bc1255459afb5efec7a5cf48ee"
PUBLIC_RELEASE_EVIDENCE = "acceptance/public-release-v1.0.3.json"
GITHUB_RELEASE_URL = (
    "https://github.com/shinya0x00/github-task-protocol/releases/tag/v1.0.3"
)
PYPI_RELEASE_URL = "https://pypi.org/project/github-task-protocol/1.0.3/"
PUBLISHED_SDIST_SHA256 = (
    "8fd00f8b8f90fef2207a0a6063d27bcbac5e1a99941bcad1400c1735810b9f89"
)
PUBLISHED_WHEEL_SHA256 = (
    "5a45df28bec73443b6de76e0457503579d1227ca5db933fce700bf53599f7ecc"
)
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


def _is_manifest_verified_sdist(root: Path = ROOT) -> bool:
    """True only for the exact unpacked sdist layout produced by this source."""
    expected_root = f"{PROJECT['name']}-{PROJECT['version']}"
    pkg_info = root / "PKG-INFO"
    if root.name != expected_root or not pkg_info.is_file() or pkg_info.is_symlink():
        return False
    try:
        if pkg_info.read_bytes() != build_backend._metadata():
            return False
        paths = list(root.rglob("*"))
        if any(path.is_symlink() for path in paths):
            return False
        observed = {
            path.relative_to(root).as_posix()
            for path in paths
            if path.is_file()
            and not (path.parent.name == "__pycache__" and path.suffix == ".pyc")
        }
    except (OSError, ValueError):
        return False
    expected = {*build_backend.SDIST_SOURCE_MANIFEST, "PKG-INFO"}
    return observed == expected


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


def _install_commands(text: str) -> list[tuple[str, str, str]]:
    matches = re.findall(
        r'^uvx --from "?github-task-protocol==([^" ]+)"? '
        r"gtp (status|check) (.+)$",
        text,
        flags=re.MULTILINE,
    )
    return [(version, command, argument) for version, command, argument in matches]


class ReleaseSurfaceTests(unittest.TestCase):
    def _repository_workflow(self) -> str:
        if _is_manifest_verified_sdist():
            self.skipTest(
                "repository-only workflow assertions do not apply to the "
                "manifest-verified extracted sdist"
            )
        workflows = list((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertEqual([ROOT / ".github" / "workflows" / "ci.yml"], workflows)
        return workflows[0].read_text(encoding="utf-8")

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
        introduction = readme.split("## CLIは任意の検証器", 1)[0]
        self.assertIn(
            "bare repository URLだけではsetup依頼にも変更authorizationにもなりません",
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
        self.assertIn("tagをexact commit SHAへ固定", introduction)
        self.assertIn("固定commitの`GTP.md`だけ", introduction)
        self.assertIn("異なる既存`GTP.md`を上書きしない", introduction)
        branch_guard = introduction.index("target fileを変える前に")
        vendor = introduction.index("固定commitの`GTP.md`だけ")
        adapter = introduction.index("既存instructionを変更・削除せず")
        self.assertLess(branch_guard, vendor)
        self.assertLess(branch_guard, adapter)
        self.assertIn("setup branchだけをcommit、push", introduction)
        self.assertIn("Draft setup PR", introduction)
        self.assertIn("人がsetup PRをmergeしてから", introduction)
        self.assertIn("[`GTP.md`](GTP.md)", readme)
        self.assertIn("人間がGTPを使うためにCLIをinstallする必要はありません", readme)
        commands = _install_commands(readme)
        self.assertEqual(2, len(commands))
        self.assertEqual({"status", "check"}, {command for _, command, _ in commands})
        version_tokens = {version for version, _, _ in commands}
        self.assertEqual(1, len(version_tokens))
        self.assertIsNone(
            re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", next(iter(version_tokens)))
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
        self.assertIn("fileやbranchを変える前に", readme)
        self.assertIn("read-onlyで確認", readme)
        self.assertIn("自動統合せず", readme)
        design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
        self.assertIn("setup preflight", design)
        self.assertIn("read-onlyで取得", design)

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
            "setup branchだけをcommit、push" in readme
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

    def test_readme_points_to_the_canonical_adapter(self) -> None:
        spec = (ROOT / "GTP.md").read_text(encoding="utf-8")
        adapter = next(
            line
            for line in spec.splitlines()
            if line.startswith("> このrepositoryはrootの`GTP.md`")
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("[`GTP.md`](GTP.md) §16のadapter文", readme)
        self.assertIn("protocol versionに対応するRecord", adapter)

    def test_root_surface_and_line_budgets(self) -> None:
        extracted_sdist = _is_manifest_verified_sdist()
        for required in MATRIX["required_root"]:
            if required == ".github/workflows/ci.yml" and extracted_sdist:
                self.assertFalse((ROOT / required).exists(), required)
                continue
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

    def test_baseline_and_budgets_are_explicit(self) -> None:
        self.assertEqual(
            {"README.md": 131, "GTP.md": 368, "production_python": 2500},
            MATRIX["baselines"],
        )
        self.assertEqual(
            {"README.md": 150, "GTP.md": 400, "production_python": 2500},
            MATRIX["budgets"],
        )
        for surface, baseline in MATRIX["baselines"].items():
            self.assertLessEqual(baseline, MATRIX["budgets"][surface])

    def test_package_and_protocol_versions_are_separate(self) -> None:
        self.assertEqual(
            {
                "package": {
                    "value": SOURCE_PACKAGE_VERSION,
                    "scheme": "Python packaging version identifier",
                    "semver_compatibility_claim": False,
                    "publication_claim": False,
                },
                "protocol": {
                    "value": SOURCE_PROTOCOL_VERSION,
                    "prior": "1.0",
                    "prior_meaning_changed": False,
                },
            },
            MATRIX["versions"],
        )
        self.assertEqual(SOURCE_PACKAGE_VERSION, PROJECT["version"])
        self.assertEqual(SOURCE_PACKAGE_VERSION, gtp.__version__)
        self.assertNotEqual(SOURCE_PACKAGE_VERSION, SOURCE_PROTOCOL_VERSION)
        spec = (ROOT / "GTP.md").read_text(encoding="utf-8")
        self.assertIn("protocol 1.0のRecord typeは4種類", spec)
        self.assertIn("protocol 1.1は`amendment`を加えた5種類", spec)
        self.assertIn('`gtp`は文字列`"1.0"`または`"1.1"`だけを許す', spec)
        notes = (ROOT / "acceptance" / "release-notes-v1.0.4.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Python packagingのversion identifier", notes)
        self.assertIn("Semantic Versioningのpatch互換性をClaimしない", notes)
        adr = (
            ROOT / "adr" / "0038-protocol-1-1-revisions-and-package-versioning.md"
        ).read_text(encoding="utf-8")
        self.assertIn("https://packaging.python.org/en/latest/specifications/version-specifiers/", adr)
        self.assertIn("https://semver.org/", adr)

    def test_existing_instruction_vocabulary_is_not_protocol_owned(self) -> None:
        current_public_paths = [
            "GTP.md",
            "README.md",
            "DESIGN.md",
            "adr/0037-separate-private-instructions-from-public-records.md",
            "adr/0038-protocol-1-1-revisions-and-package-versioning.md",
            "adr/0039-existing-instructions-and-issue-lifecycle-boundary.md",
            "acceptance/release-notes-v1.0.4.md",
        ]
        forbidden = (
            "Repository " + "policy",
            "Issue lifecycle " + "profile",
            "decision " + "log",
        )
        for relative_path in current_public_paths:
            text = (ROOT / relative_path).read_text(encoding="utf-8")
            for term in forbidden:
                self.assertNotIn(term.lower(), text.lower(), relative_path)
        spec = (ROOT / "GTP.md").read_text(encoding="utf-8")
        self.assertIn("既に所有するinstructionsやrulesを定義、検証、上書きしない", spec)
        self.assertIn("valid Contractが通常のGTP lifecycleを開始する", spec)

    def test_public_record_disclosure_boundary(self) -> None:
        evidence_path = ROOT / "acceptance" / "v1.0.4" / "public-record-disclosure.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        serialized = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
        self.assertIsInstance(evidence, dict)
        self.assertEqual("gtp-public-record-disclosure-v1", evidence["schema"])
        self.assertFalse(evidence["canary"]["plaintext_stored"])
        self.assertEqual(0, evidence["canary"]["match_count"])
        self.assertFalse(evidence["publication_authority_inferred"])
        for target in evidence["inspected_targets"]:
            self.assertEqual(0, target["credential_match_count"])
            self.assertEqual(0, target["private_data_match_count"])
        clean = evidence["clean_agent_probe"]
        self.assertEqual("success", clean["status"])
        self.assertEqual(
            {
                "workspace_accessed": False,
                "credentials_accessed": False,
                "private_context_accessed": False,
                "repository_code_executed": False,
            },
            {
                key: clean["input_boundary"][key]
                for key in (
                    "workspace_accessed",
                    "credentials_accessed",
                    "private_context_accessed",
                    "repository_code_executed",
                )
            },
        )
        self.assertEqual(
            {
                ("Issue", False),
                ("Issue", True),
                ("PR or ordinary task", False),
                ("PR or ordinary task", True),
            },
            {
                (case["entry"], case["valid_contract"])
                for case in clean["activation_entry_cases"]
            },
        )
        self.assertEqual(
            {"none"},
            {
                case["existing_instructions_inference"]
                for case in clean["activation_entry_cases"]
            },
        )
        self.assertEqual(
            {
                "merge_inferred": False,
                "publication_inferred": False,
                "deployment_inferred": False,
            },
            {
                key: clean["external_operation_authorization"][key]
                for key in (
                    "merge_inferred",
                    "publication_inferred",
                    "deployment_inferred",
                )
            },
        )
        self.assertIn("credential", serialized.lower())
        self.assertIn("private", serialized.lower())
        for forbidden in (
            "/" + "Users" + "/",
            "gh" + "p_",
            "github_" + "pat_",
            "-----BEGIN PRIVATE " + "KEY-----",
        ):
            self.assertNotIn(forbidden, serialized)
        notes = (ROOT / "acceptance" / "release-notes-v1.0.4.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("credential、private prompt", notes)
        self.assertIn("内部診断の原文は転記しない", notes)

    def test_candidate_metadata_is_safe_before_and_after_publication(self) -> None:
        self.assertEqual(
            {
                "source_package_version": SOURCE_PACKAGE_VERSION,
                "verified_install_sources": [
                    "GitHub latest stable Release",
                    "PyPI",
                ],
                "requires_version_agreement": True,
                "safe_before_publication": True,
                "safe_after_publication": True,
                "publication_claim": False,
            },
            MATRIX["public_metadata_boundary"],
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        commands = _install_commands(readme)
        self.assertEqual(2, len(commands))
        self.assertEqual({"$VERSION"}, {version for version, _, _ in commands})
        self.assertIn("latest stable Release", readme)
        self.assertIn("PyPIのversion page", readme)
        self.assertIn("両方で同じ値", readme)
        self.assertIn(
            f"Python distribution versionは`{SOURCE_PACKAGE_VERSION}`", readme
        )
        self.assertIn(
            "この値はpublicationのEvidenceでも、"
            "exact source commitのidentityでもありません",
            readme,
        )
        self.assertIn("source metadataのpackage versionは配布候補の識別子", readme)
        self.assertNotIn(
            "pypi.org/project/github-task-protocol/1.0.4", readme.lower()
        )
        self.assertNotIn("releases/tag/v1.0.4", readme.lower())
        notes = (ROOT / "acceptance" / "release-notes-v1.0.4.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("公開前後のどちらでもこの意味は変わらない", notes)
        self.assertIn("CIにpublish jobは置かない", notes)

    def test_v104_candidate_manifest_is_complete(self) -> None:
        expected_acceptance = [
            "acceptance/v1.0.4/walking-skeleton.json",
            "acceptance/v1.0.4/live-paths.json",
            "acceptance/v1.0.4/public-record-disclosure.json",
            "acceptance/v1.0.4/release-candidate.json",
        ]
        self.assertEqual(expected_acceptance, MATRIX["acceptance_v1_0_4"])
        manifest = set(build_backend.SDIST_SOURCE_MANIFEST)
        for relative_path in (
            *expected_acceptance,
            "acceptance/release-notes-v1.0.4.md",
            *MATRIX["release_documents"]["decisions"],
        ):
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)
            self.assertIn(relative_path, manifest)

    def test_v104_acceptance_keeps_unobserved_facts_pending(self) -> None:
        live = json.loads(
            (ROOT / "acceptance" / "v1.0.4" / "live-paths.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("gtp-live-paths-v1", live["schema"])
        self.assertEqual(
            {
                "condition_only_amendment",
                "downgrade_after_1_1",
                "malformed_later_1_1",
                "revision_bound_re_done_and_no_fallback",
                "native_merge_cutoff",
            },
            set(live["cases"]),
        )
        for name in (
            "condition_only_amendment",
            "downgrade_after_1_1",
            "malformed_later_1_1",
        ):
            case = live["cases"][name]
            self.assertEqual("success", case["status"])
            for observation in case["observations"].values():
                self.assertGreater(observation["http_get_count"], 0)
                self.assertEqual(0, observation["http_non_get_count"])
                self.assertTrue(observation["before_after_snapshot_equal"])
                self.assertEqual("none", observation["authority"])
                self.assertEqual("complete", observation["acquisition"])
        amendment = live["cases"]["condition_only_amendment"]["observations"]
        self.assertEqual("in_progress", amendment["source_cli_1_0_4"]["state"])
        self.assertEqual(
            ("halt", "invalid_record", 0),
            (
                amendment["public_cli_1_0_3"]["state"],
                amendment["public_cli_1_0_3"]["halt_reason"],
                amendment["public_cli_1_0_3"]["exit_code"],
            ),
        )
        downgrade = live["cases"]["downgrade_after_1_1"]["observations"]
        self.assertEqual(
            ("halt", "invalid_transition"),
            (
                downgrade["source_cli_1_0_4"]["state"],
                downgrade["source_cli_1_0_4"]["halt_reason"],
            ),
        )
        self.assertEqual("stopped", downgrade["public_cli_1_0_3"]["state"])
        self.assertFalse(downgrade["public_cli_1_0_3"]["completion_claimed"])
        malformed = live["cases"]["malformed_later_1_1"]["observations"]
        self.assertEqual(
            {("halt", "invalid_record")},
            {(item["state"], item["halt_reason"]) for item in malformed.values()},
        )
        redone = live["cases"]["revision_bound_re_done_and_no_fallback"]
        self.assertEqual("success", redone["status"])
        self.assertFalse(redone["fixture"]["source_candidate"])
        self.assertEqual(
            {"issue_state": "closed", "pr_state": "closed", "native_merge": False},
            redone["fixture"]["cleanup"],
        )
        self.assertEqual(
            {("in_progress", None)},
            {
                (item["state"], item["halt_reason"])
                for item in redone["stages"]["after_first_done"].values()
            },
        )
        self.assertEqual(
            {("halt", "stale_evidence")},
            {
                (item["state"], item["halt_reason"])
                for item in redone["stages"]["after_head_change_before_re_done"].values()
            },
        )
        after_redone = redone["stages"]["after_re_done"]
        self.assertEqual(
            ("1.1", "in_progress", None, redone["fixture"]["redone_1_1"]),
            (
                after_redone["source_cli_1_0_4"]["gtp"],
                after_redone["source_cli_1_0_4"]["state"],
                after_redone["source_cli_1_0_4"]["halt_reason"],
                after_redone["source_cli_1_0_4"]["current_done"],
            ),
        )
        self.assertEqual(
            ("1.0", "halt", "invalid_record", False),
            (
                after_redone["public_cli_1_0_3"]["gtp"],
                after_redone["public_cli_1_0_3"]["state"],
                after_redone["public_cli_1_0_3"]["halt_reason"],
                after_redone["public_cli_1_0_3"]["fallback_to_done_1_0"],
            ),
        )
        for stage in redone["stages"].values():
            for observation in stage.values():
                self.assertGreater(observation["http_get_count"], 0)
                self.assertEqual(0, observation["http_non_get_count"])
                self.assertTrue(observation["before_after_snapshot_equal"])
        self.assertEqual("pending", live["cases"]["native_merge_cutoff"]["status"])

        candidate = json.loads(
            (ROOT / "acceptance" / "v1.0.4" / "release-candidate.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("gtp-release-candidate-v1", candidate["schema"])
        self.assertEqual(
            {"package": SOURCE_PACKAGE_VERSION, "protocol": SOURCE_PROTOCOL_VERSION},
            candidate["versions"],
        )
        self.assertEqual(
            {
                "unit_tests": 162,
                "GTP.md_lines": 368,
                "README.md_lines": 131,
                "production_python_lines": 2500,
            },
            candidate["baseline"],
        )
        self.assertEqual(
            "https://github.com/shinya0x00/github-task-protocol/pull/136",
            candidate["source_pr"],
        )
        statuses = {
            name: section["status"]
            for name, section in candidate["candidate"].items()
        }
        self.assertEqual("pending", statuses.pop("review"))
        self.assertEqual({"success"}, set(statuses.values()))
        self.assertEqual(
            "Run exact-head CI, then obtain a fresh exact-head review.",
            candidate["candidate"]["review"]["next_action"],
        )
        self.assertEqual(
            {"native_merge": False, "tag": False, "github_release": False, "pypi": False},
            candidate["publication"],
        )

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
            (ROOT / PUBLIC_RELEASE_EVIDENCE).read_text(encoding="utf-8")
        )
        self.assertEqual(
            "github-task-protocol-public-release-evidence/v1",
            current_evidence["schema"],
        )
        self.assertNotIn("observed_at", current_evidence)
        self.assertEqual(
            "2026-07-26T03:47:49Z",
            current_evidence["public_validation"]["observed_at"],
        )
        self.assertEqual(SOURCE_PACKAGE_VERSION, PROJECT["version"])
        self.assertNotEqual(
            PROJECT["version"], current_evidence["pypi"]["package_version"]
        )
        self.assertEqual(
            PUBLISHED_CLI_VERSION, current_evidence["pypi"]["package_version"]
        )
        self.assertEqual(
            PUBLISHED_CANDIDATE,
            current_evidence["published_candidate"]["commit_sha"],
        )
        self.assertEqual(
            PUBLISHED_CANDIDATE, current_evidence["tag"]["target_commit_sha"]
        )
        self.assertEqual(
            GITHUB_RELEASE_URL, current_evidence["github_release"]["url"]
        )
        self.assertEqual(PYPI_RELEASE_URL, current_evidence["pypi"]["release_url"])
        self.assertTrue(current_evidence["github_release"]["published_at"])
        self.assertTrue(current_evidence["github_release"]["latest_stable"])
        self.assertTrue(current_evidence["pypi"]["files_redownloaded_and_hashed"])
        expected_package_hashes = {
            "github_task_protocol-1.0.3.tar.gz": PUBLISHED_SDIST_SHA256,
            "github_task_protocol-1.0.3-py3-none-any.whl": PUBLISHED_WHEEL_SHA256,
        }
        for files in (
            current_evidence["published_candidate"]["artifact"]["files"],
            current_evidence["github_release"]["assets"],
            current_evidence["pypi"]["files"],
        ):
            self.assertEqual(
                expected_package_hashes,
                {
                    file["filename"]: file["sha256"]
                    for file in files
                    if file["filename"].endswith((".tar.gz", ".whl"))
                },
            )
        self.assertTrue(
            current_evidence["public_validation"][
                "candidate_github_release_pypi_sdist_bytes_equal"
            ]
        )
        self.assertTrue(
            current_evidence["public_validation"][
                "candidate_github_release_pypi_wheel_bytes_equal"
            ]
        )
        self.assertEqual(
            "done",
            current_evidence["public_validation"]["live_status"]["issue_91"][
                "state"
            ],
        )
        offline_check = current_evidence["public_validation"]["offline_check"]
        self.assertEqual(1, offline_check["github_release_wheel_exit_code"])
        self.assertEqual(1, offline_check["pypi_wheel_exit_code"])
        self.assertTrue(offline_check["recognized"])
        self.assertFalse(offline_check["schema_valid"])
        self.assertEqual("invalid_carrier", offline_check["error_code"])
        self.assertEqual("$", offline_check["error_path"])
        self.assertEqual("none", offline_check["authority"])
        live_status = current_evidence["public_validation"]["live_status"]
        self.assertEqual("stale_evidence", live_status["issue_127"]["reason"])
        self.assertEqual(
            "https://github.com/shinya0x00/github-task-protocol/issues/127#issuecomment-5079094301",
            live_status["issue_127"]["primary_url"],
        )
        self.assertEqual(
            "https://github.com/shinya0x00/github-task-protocol/pull/92",
            live_status["issue_91"]["primary_url"],
        )
        for observation in live_status.values():
            if not isinstance(observation, dict):
                continue
            self.assertGreater(observation["http_get_count"], 0)
            self.assertEqual(0, observation["http_non_get_count"])
            self.assertEqual(0, observation["mutation_callbacks"])
            self.assertTrue(observation["before_after_snapshot_equal"])
        human_output = current_evidence["human_output_validation"]
        self.assertEqual("2026-07-26T04:59:08Z", human_output["observed_at"])
        self.assertEqual("PyPI redownloaded wheel", human_output["installed_from"])
        self.assertTrue(human_output["isolated_venv"])
        self.assertTrue(human_output["offline_install"])
        self.assertEqual("3.12.12", human_output["python_version"])
        self.assertEqual(
            {
                "url": (
                    "https://files.pythonhosted.org/packages/21/ae/"
                    "29bf4271759ec70bb708a3924241994af0955f710a20670856dedad307c4/"
                    "github_task_protocol-1.0.3-py3-none-any.whl"
                ),
                "size": 33175,
                "sha256": PUBLISHED_WHEEL_SHA256,
            },
            human_output["wheel"],
        )
        self.assertEqual(
            "human_stdout is the exact UTF-8 prefix before the machine JSON "
            "object in stdout.",
            human_output["stdout_boundary"],
        )
        expected_output = {
            "offline_check": {
                "command": "gtp check malformed-carrier.md",
                "exit_code": 1,
                "human_stdout_sha256": (
                    "9275af20369c8930f71e9ad8eefa05e79e84e9f2347861bc23602ec7661e7ded"
                ),
                "full_stdout_sha256": (
                    "c492732be22c1ad980a91c80c3b28d4824f9d4ca0a5b1255b50b99dd54261e33"
                ),
                "problem_block": "present",
                "problem_item_count": 8,
            },
            "issue_127": {
                "command": (
                    "gtp status "
                    "https://github.com/shinya0x00/github-task-protocol/issues/127"
                ),
                "exit_code": 0,
                "human_stdout_sha256": (
                    "6bc46a38a332108babe62e4c4784179f158a630648e0b7fb30549a279fcd6f21"
                ),
                "full_stdout_sha256": (
                    "ee157eed00a865a6ef1e502722b456e245989ba87f8d9a69c8d05e31f556622b"
                ),
                "problem_block": "present",
                "problem_item_count": 8,
            },
            "issue_91": {
                "command": (
                    "gtp status "
                    "https://github.com/shinya0x00/github-task-protocol/issues/91"
                ),
                "exit_code": 0,
                "human_stdout_sha256": (
                    "082bd5031664a8bfe45ab84a4f475a8471e589adddf488b4d7d59851e1dac600"
                ),
                "full_stdout_sha256": (
                    "3c1236c82db71ffe362ca7b6ff8cb211706692efdeef2815806dcfd37de1eded"
                ),
                "problem_block": "absent",
                "problem_item_count": 0,
            },
        }
        for name, expected in expected_output.items():
            observation = human_output[name]
            with self.subTest(public_human_output=name):
                for field, value in expected.items():
                    self.assertEqual(value, observation[field])
                self.assertEqual("", observation["stderr"])
                self.assertEqual(
                    observation["human_stdout_sha256"],
                    hashlib.sha256(
                        observation["human_stdout"].encode("utf-8")
                    ).hexdigest(),
                )
                self.assertEqual(
                    observation["problem_block"] == "present",
                    "問題の整理:" in observation["human_stdout"],
                )
                if observation["problem_block"] == "present":
                    lines = observation["human_stdout"].splitlines()
                    start = lines.index("問題の整理:")
                    problem_items = lines[start + 1 : start + 9]
                    self.assertEqual(
                        observation["problem_item_count"], len(problem_items)
                    )
                    for index, line in enumerate(problem_items, start=1):
                        self.assertTrue(line.startswith(f"  {index}. "))
        malformed = human_output["offline_check"]
        self.assertEqual(
            "<!-- gtp-record:v1 -->\n壊れたCarrier\n",
            malformed["exact_input"],
        )
        self.assertEqual(
            malformed["exact_input_sha256"],
            hashlib.sha256(malformed["exact_input"].encode("utf-8")).hexdigest(),
        )
        summary_prefixes = (
            "状態:",
            "停止要否:",
            "次の行動:",
            "理由:",
            "最初のURL:",
            "非許可表示:",
        )
        for name in ("issue_127", "issue_91"):
            observation = human_output[name]
            self.assertEqual(6, observation["leading_summary_item_count"])
            self.assertTrue(observation["before_after_snapshot_equal"])
            for line, prefix in zip(
                observation["human_stdout"].splitlines()[:6],
                summary_prefixes,
                strict=True,
            ):
                self.assertTrue(line.startswith(prefix))
        self.assertEqual(
            {
                "credential_value_published": False,
                "credential_deleted": False,
                "credential_updated": False,
                "credential_shape_proves_validity_or_ownership": False,
            },
            current_evidence["credential_boundary"],
        )
        published_candidate = current_evidence["published_candidate"]
        self.assertEqual(
            PUBLISHED_CANDIDATE, published_candidate["main_ci"]["head_sha"]
        )
        self.assertEqual("push", published_candidate["main_ci"]["event"])
        self.assertEqual("main", published_candidate["main_ci"]["head_branch"])
        self.assertEqual(
            f"v1.0.3-main-candidate-{PUBLISHED_CANDIDATE}",
            published_candidate["artifact"]["name"],
        )
        self.assertEqual(
            PUBLISHED_CANDIDATE,
            published_candidate["artifact"]["build_conditions"]["source_sha"],
        )
        evidence_pr = current_evidence["evidence_pr"]
        self.assertEqual(
            "https://github.com/shinya0x00/github-task-protocol/pull/132",
            evidence_pr["url"],
        )
        self.assertEqual(
            "inspection_only_not_publication", evidence_pr["artifact_role"]
        )
        self.assertIn(
            "The Evidence pull request artifact inspects its own source tree. "
            "This record does not redefine the role of a later main-push artifact; "
            "only the fixed candidate at commit "
            f"{PUBLISHED_CANDIDATE} was used for the completed 1.0.3 publication.",
            current_evidence["evidence_limits"],
        )
        self.assertFalse(
            any(
                "post-merge main artifacts" in limit
                and "not publication candidates" in limit
                for limit in current_evidence["evidence_limits"]
            )
        )
        self.assertIsNone(evidence_pr["head_sha"])
        self.assertEqual(
            "Issue #102 Done Record and GitHub pull request metadata",
            evidence_pr["final_head_owner"],
        )
        self.assertEqual(
            [
                "README.md",
                PUBLIC_RELEASE_EVIDENCE,
                "build_backend.py",
                "tests/test_build_backend.py",
                "tests/test_release_surface.py",
            ],
            evidence_pr["scope"],
        )
        self.assertFalse(evidence_pr["published_sdist_contains_this_evidence"])
        if _blob_at(PUBLISHED_CANDIDATE, "GTP.md") is not None:
            self.assertIsNone(_blob_at(PUBLISHED_CANDIDATE, PUBLIC_RELEASE_EVIDENCE))
        published_history = MATRIX["release_documents"]["published_history"]
        self.assertEqual(PUBLISHED_CLI_VERSION, published_history["package_version"])
        self.assertEqual(PUBLIC_RELEASE_EVIDENCE, published_history["evidence"])
        self.assertEqual(
            "acceptance/release-notes-v1.0.3.md", published_history["notes"]
        )
        self.assertTrue((ROOT / "acceptance" / "release-notes-v1.0.2.md").exists())
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertIn(
            "## ADR-030: CLIを任意validatorとしてPyPIへ公開する",
            decisions,
        )

    def test_release_documents_keep_published_history_distinct(self) -> None:
        self.assertEqual(
            {
                "current_design": "DESIGN.md",
                "decisions": [
                    "adr/0036-reproducible-release-artifacts.md",
                    "adr/0037-separate-private-instructions-from-public-records.md",
                    "adr/0038-protocol-1-1-revisions-and-package-versioning.md",
                    "adr/0039-existing-instructions-and-issue-lifecycle-boundary.md",
                ],
                "candidate_notes": "acceptance/release-notes-v1.0.4.md",
                "published_history": {
                    "package_version": PUBLISHED_CLI_VERSION,
                    "notes": "acceptance/release-notes-v1.0.3.md",
                    "evidence": PUBLIC_RELEASE_EVIDENCE,
                },
            },
            MATRIX["release_documents"],
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            f"このsource treeのPython distribution versionは`{SOURCE_PACKAGE_VERSION}`",
            readme,
        )
        self.assertIn(
            "この値はpublicationのEvidenceでも、"
            "exact source commitのidentityでもありません",
            readme,
        )
        self.assertIn("source metadataのpackage versionは配布候補の識別子", readme)
        self.assertNotIn("source内容のidentity", readme)
        commands = _install_commands(readme)
        self.assertEqual(2, len(commands))
        self.assertEqual({"status", "check"}, {command for _, command, _ in commands})
        version_tokens = {version for version, _, _ in commands}
        self.assertEqual(1, len(version_tokens))
        self.assertIsNone(
            re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", next(iter(version_tokens)))
        )
        self.assertNotIn("github-task-protocol==1.0.4", readme)
        self.assertNotIn("github-task-protocol==1.0.3", readme)
        self.assertNotIn("github-task-protocol==1.0.2", readme)
        self.assertIn("latest stable Release", readme)
        self.assertIn("PyPI", readme)
        self.assertIn("両方で同じ値", readme)
        self.assertNotIn("現在のsource candidate", readme)
        self.assertNotIn("まだ公開していない", readme)

        notes_path = ROOT / "acceptance" / "release-notes-v1.0.3.md"
        self.assertTrue(notes_path.exists())
        self.assertEqual(
            "f644c1df00649eaefc1c05b0ea422eb06a6d6a48fa16160f417734b56c9164d3",
            hashlib.sha256(notes_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            "2665913379f413024dadbf1a00f0f67026b82114534e79a1eaa4eeb8cff5eb07",
            hashlib.sha256((ROOT / PUBLIC_RELEASE_EVIDENCE).read_bytes()).hexdigest(),
        )
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
        candidate_notes = (
            ROOT / MATRIX["release_documents"]["candidate_notes"]
        ).read_text(encoding="utf-8")
        self.assertIn("package version `1.0.4`", candidate_notes)
        self.assertIn("protocol version `1.1`", candidate_notes)
        self.assertIn("Semantic Versioningのpatch互換性をClaimしない", candidate_notes)
        self.assertIn("publicationをClaimせず", candidate_notes)

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
        self.assertIn("acceptance/release-notes-v1.0.4.md", manifest)
        for path in MATRIX["release_documents"]["decisions"]:
            self.assertIn(path, manifest)
        for path in MATRIX["acceptance_v1_0_4"]:
            self.assertIn(path, manifest)
        for required in MATRIX["required_sdist"]:
            self.assertTrue(
                required in manifest
                or any(path.startswith(f"{required}/") for path in manifest),
                required,
            )

    def test_extracted_sdist_context_requires_pkg_info_and_exact_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / f"{PROJECT['name']}-{PROJECT['version']}"
            for member in build_backend.SDIST_SOURCE_MANIFEST:
                path = root / member
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"")
            self.assertFalse(_is_manifest_verified_sdist(root))

            (root / "PKG-INFO").write_bytes(build_backend._metadata())
            self.assertTrue(_is_manifest_verified_sdist(root))

            bytecode = root / "tests" / "__pycache__" / "test_cli.cpython-312.pyc"
            bytecode.parent.mkdir(parents=True, exist_ok=True)
            bytecode.write_bytes(b"standard unittest cache")
            self.assertTrue(_is_manifest_verified_sdist(root))

            arbitrary = root / "tests" / "unexpected.cache"
            arbitrary.write_bytes(b"not a standard bytecode cache")
            self.assertFalse(_is_manifest_verified_sdist(root))
            arbitrary.unlink()

            unexpected = root / ".github" / "workflows" / "ci.yml"
            unexpected.parent.mkdir(parents=True, exist_ok=True)
            unexpected.write_text("name: unexpected\n", encoding="utf-8")
            self.assertFalse(_is_manifest_verified_sdist(root))
            unexpected.unlink()
            repository_marker = root / ".git" / "HEAD"
            repository_marker.parent.mkdir(parents=True, exist_ok=True)
            repository_marker.write_text("ref: refs/heads/test\n", encoding="utf-8")
            self.assertFalse(_is_manifest_verified_sdist(root))

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
            self.assertIn(value, adr)
        for value in (
            "SOURCE_SHA",
            "Python 3.11",
            "Python 3.11、3.12、3.13",
            "v1.0.4-pr-verification-<SOURCE_SHA>",
            "v1.0.4-main-candidate-<SOURCE_SHA>",
            "tag、GitHub Release、PyPIを変更しない",
        ):
            self.assertIn(value, design)
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
        workflow = self._repository_workflow()
        self.assertIn('python-version: ["3.11", "3.12", "3.13"]', workflow)
        self.assertIn('GTP_RELEASE_LOCK_REQUIRED: "1"', workflow)
        if (
            os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("GITHUB_REPOSITORY")
            == "shinya0x00/github-task-protocol"
        ):
            self.assertEqual("1", os.environ.get(RELEASE_LOCK_REQUIRED_ENV))
        self.assertIn("Build twice from clean exports", workflow)
        self.assertIn("Run bundled tests from the built sdist", workflow)
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
        workflow = self._repository_workflow()
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
                "pull_request": "v1.0.4-pr-verification-<SOURCE_SHA>",
                "main_push": "v1.0.4-main-candidate-<SOURCE_SHA>",
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
        self.assertIn("Run bundled tests from the built sdist", build_job)
        self.assertIn(
            'tar -xzf "$RUNNER_TEMP/dist-a/github_task_protocol-1.0.4.tar.gz"',
            build_job,
        )
        self.assertIn(
            'cd "$RUNNER_TEMP/sdist-tests/github-task-protocol-1.0.4"',
            build_job,
        )
        self.assertIn(
            "PYTHONPATH=src python -m unittest discover -s tests",
            build_job,
        )
        ordered_build_steps = (
            "Build twice from clean exports",
            "Run bundled tests from the built sdist",
            "Rebuild the wheel from a fresh sdist environment",
            "Assemble checksummed artifact",
        )
        self.assertEqual(
            sorted(build_job.index(step) for step in ordered_build_steps),
            [build_job.index(step) for step in ordered_build_steps],
        )
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
        self.assertIn("v1.0.4-pr-verification-${SOURCE_SHA}", workflow)
        self.assertIn("v1.0.4-main-candidate-${SOURCE_SHA}", workflow)
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
