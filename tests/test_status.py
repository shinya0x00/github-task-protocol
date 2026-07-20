from __future__ import annotations

import unittest

from gtp.github import AcquisitionError
from gtp.status import evaluate_issue

from test_reducer import IDS, ISSUE, comment, contract, start


SHA = "0123456789abcdef0123456789abcdef01234567"


def done(record_id: str) -> dict:
    return {
        "gtp": "1.0",
        "type": "done",
        "id": record_id,
        "pr_ref": "https://github.com/o/r/pull/7",
        "head_sha": SHA,
        "evidence": {"artifact": f"https://github.com/o/r/blob/{SHA}/acceptance/run.json"},
    }


def stop(record_id: str) -> dict:
    return {
        "gtp": "1.0",
        "type": "stop",
        "id": record_id,
        "reason": "abandoned",
        "successor_ref": None,
    }


class FakeGitHub:
    def __init__(self, comments, *, branch=True, candidates=None, pr=None, check=None, files=None):
        self._comments = comments
        self._branch = branch
        self._candidates = candidates or []
        self._pr = pr
        self._check = check
        self._files = files or [{"filename": "acceptance/run.json", "status": "added"}]

    def repository(self, owner, repo):
        return {
            "id": 99,
            "full_name": "o/r",
            "url": "https://api.github.com/repos/o/r",
            "default_branch": "main",
        }

    def issue(self, owner, repo, number):
        return {
            "id": 1,
            "url": ISSUE,
            "created_at": "2026-07-18T00:00:00Z",
            "updated_at": "2026-07-19T00:00:00Z",
        }

    def comments(self, owner, repo, number):
        return self._comments

    def branch(self, owner, repo, branch):
        return {"name": branch, "commit": {"sha": SHA}} if self._branch else None

    def pull_requests(self, owner, repo, branch):
        return self._candidates

    def pull_request(self, owner, repo, number):
        if self._pr is not None:
            return self._pr
        return next(
            (candidate for candidate in self._candidates if candidate.get("number") == number),
            None,
        )

    def pull_request_files(self, owner, repo, number):
        return self._files

    def artifact(self, owner, repo, path, sha):
        return {"type": "file", "path": path, "sha": sha}

    def check_run(self, owner, repo, number):
        if self._check is None:
            raise AssertionError("not used")
        return self._check


def pr(*, merged: bool) -> dict:
    return {
        "number": 7,
        "html_url": "https://github.com/o/r/pull/7",
        "created_at": "2026-07-19T00:00:02Z",
        "updated_at": "2026-07-19T00:00:02Z",
        "changed_files": 1,
        "base": {"repo": {"id": 99}},
        "head": {"repo": {"id": 99}, "ref": "codex/walking", "sha": SHA},
        "merged_at": "2026-07-19T01:00:00Z" if merged else None,
    }


class StatusTests(unittest.TestCase):
    def test_in_progress_with_branch(self) -> None:
        comments = [comment(1, contract(IDS[0])), comment(2, start(IDS[1]))]
        result = evaluate_issue(FakeGitHub(comments), ISSUE)
        self.assertEqual("in_progress", result.state)
        self.assertTrue(result.current["branch"]["exists"])

    def test_missing_branch_halts_with_start_url(self) -> None:
        comments = [comment(1, contract(IDS[0])), comment(2, start(IDS[1]))]
        result = evaluate_issue(FakeGitHub(comments, branch=False), ISSUE)
        self.assertEqual("halt", result.state)
        self.assertEqual("invalid_binding", result.diagnostics[0].token)
        self.assertEqual(comments[1].url, result.diagnostics[0].urls[0])

    def test_merge_without_done_halts(self) -> None:
        comments = [comment(1, contract(IDS[0])), comment(2, start(IDS[1]))]
        result = evaluate_issue(FakeGitHub(comments, candidates=[pr(merged=True)]), ISSUE)
        self.assertEqual("halt", result.state)
        self.assertEqual("terminal_violation", result.diagnostics[0].token)

    def test_fork_or_branch_mismatch_candidate_is_invalid_binding(self) -> None:
        comments = [comment(1, contract(IDS[0])), comment(2, start(IDS[1]))]
        fork = pr(merged=False)
        fork["head"] = dict(fork["head"])
        fork["head"]["repo"] = {"id": 100}
        fork_result = evaluate_issue(FakeGitHub(comments, candidates=[fork]), ISSUE)
        self.assertEqual("invalid_binding", fork_result.diagnostics[0].token)

        mismatch = pr(merged=False)
        mismatch["head"] = dict(mismatch["head"])
        mismatch["head"]["ref"] = "other/branch"
        mismatch_result = evaluate_issue(
            FakeGitHub(comments, candidates=[mismatch]), ISSUE
        )
        self.assertEqual("invalid_binding", mismatch_result.diagnostics[0].token)

    def test_done_before_merge_remains_in_progress(self) -> None:
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, done(IDS[2])),
        ]
        result = evaluate_issue(FakeGitHub(comments, pr=pr(merged=False)), ISSUE)
        self.assertEqual("in_progress", result.state)
        self.assertEqual(SHA, result.current["bound_pr_head_sha"])

    def test_native_merge_of_done_head_is_done(self) -> None:
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, done(IDS[2])),
        ]
        result = evaluate_issue(FakeGitHub(comments, branch=False, pr=pr(merged=True)), ISSUE)
        self.assertEqual("done", result.state)

    def test_identical_contract_and_start_retries_after_terminal_are_safe(self) -> None:
        contract_record = contract(IDS[0])
        start_record = start(IDS[1])
        merged = pr(merged=True)
        merged["merged_at"] = "2026-07-19T00:00:03Z"

        for retried_record in (contract_record, start_record):
            with self.subTest(record_type=retried_record["type"]):
                comments = [
                    comment(1, contract_record),
                    comment(2, start_record),
                    comment(3, done(IDS[2])),
                    comment(4, retried_record),
                ]
                result = evaluate_issue(
                    FakeGitHub(comments, branch=False, pr=merged), ISSUE
                )
                self.assertEqual("done", result.state)
                self.assertEqual([], result.diagnostics)

    def test_fresh_record_after_done_terminal_halts_at_fresh_comment(self) -> None:
        merged = pr(merged=True)
        merged["merged_at"] = "2026-07-19T00:00:03Z"
        for fresh in (contract(IDS[3]), start(IDS[3]), done(IDS[3])):
            with self.subTest(record_type=fresh["type"]):
                comments = [
                    comment(1, contract(IDS[0])),
                    comment(2, start(IDS[1])),
                    comment(3, done(IDS[2])),
                    comment(4, fresh),
                ]
                result = evaluate_issue(
                    FakeGitHub(comments, branch=False, pr=merged), ISSUE
                )
                self.assertEqual("halt", result.state)
                self.assertEqual("terminal_violation", result.diagnostics[0].token)
                self.assertEqual(comments[3].url, result.diagnostics[0].urls[0])

    def test_check_evidence_pending_is_invalid(self) -> None:
        check_contract = contract(IDS[0])
        check_contract["done_conditions"]["artifact"]["evidence_kind"] = "check"
        check_done = done(IDS[2])
        check_done["evidence"]["artifact"] = "https://github.com/o/r/runs/8"
        comments = [comment(1, check_contract), comment(2, start(IDS[1])), comment(3, check_done)]
        check = {"head_sha": SHA, "status": "in_progress", "conclusion": None}
        result = evaluate_issue(FakeGitHub(comments, pr=pr(merged=False), check=check), ISSUE)
        self.assertEqual("halt", result.state)
        self.assertEqual("invalid_evidence", result.diagnostics[0].token)

    def test_failed_check_evidence_halts(self) -> None:
        check_contract = contract(IDS[0])
        check_contract["done_conditions"]["artifact"]["evidence_kind"] = "check"
        check_done = done(IDS[2])
        check_done["evidence"]["artifact"] = "https://github.com/o/r/runs/8"
        comments = [comment(1, check_contract), comment(2, start(IDS[1])), comment(3, check_done)]
        check = {"head_sha": SHA, "status": "completed", "conclusion": "failure"}
        result = evaluate_issue(FakeGitHub(comments, pr=pr(merged=False), check=check), ISSUE)
        self.assertEqual("halt", result.state)
        self.assertEqual("invalid_evidence", result.diagnostics[0].token)

    def test_successful_check_and_native_merge_is_done(self) -> None:
        check_contract = contract(IDS[0])
        check_contract["done_conditions"]["artifact"]["evidence_kind"] = "check"
        check_done = done(IDS[2])
        check_done["evidence"]["artifact"] = "https://github.com/o/r/runs/8"
        comments = [
            comment(1, check_contract),
            comment(2, start(IDS[1])),
            comment(3, check_done),
        ]
        check = {
            "head_sha": SHA,
            "status": "completed",
            "conclusion": "success",
            "completed_at": "2026-07-19T00:00:04Z",
        }
        result = evaluate_issue(
            FakeGitHub(comments, pr=pr(merged=True), check=check), ISSUE
        )
        self.assertEqual("done", result.state)

    def test_check_from_another_head_is_stale(self) -> None:
        check_contract = contract(IDS[0])
        check_contract["done_conditions"]["artifact"]["evidence_kind"] = "check"
        check_done = done(IDS[2])
        check_done["evidence"]["artifact"] = "https://github.com/o/r/runs/8"
        comments = [
            comment(1, check_contract),
            comment(2, start(IDS[1])),
            comment(3, check_done),
        ]
        check = {"head_sha": "f" * 40, "status": "completed", "conclusion": "success"}
        result = evaluate_issue(FakeGitHub(comments, pr=pr(merged=False), check=check), ISSUE)
        self.assertEqual("stale_evidence", result.diagnostics[0].token)

    def test_evidence_from_another_repository_is_invalid(self) -> None:
        foreign_done = done(IDS[2])
        foreign_done["evidence"]["artifact"] = (
            f"https://github.com/x/y/blob/{SHA}/acceptance/run.json"
        )
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, foreign_done),
        ]

        class ForeignRepository(FakeGitHub):
            def repository(self, owner, repo):
                if (owner, repo) == ("x", "y"):
                    return {"id": 100, "full_name": "x/y"}
                return super().repository(owner, repo)

        result = evaluate_issue(ForeignRepository(comments, pr=pr(merged=False)), ISSUE)
        self.assertEqual("invalid_evidence", result.diagnostics[0].token)

    def test_artifact_404_is_acquisition_incomplete_when_absence_is_not_proven(self) -> None:
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, done(IDS[2])),
        ]

        class MissingArtifact(FakeGitHub):
            def artifact(self, owner, repo, path, sha):
                raise AcquisitionError("artifact", "not found", 404)

        result = evaluate_issue(MissingArtifact(comments, pr=pr(merged=False)), ISSUE)
        self.assertIsNone(result.state)
        self.assertEqual("acquisition_incomplete", result.acquisition_errors[0]["code"])

    def test_artifact_from_another_head_is_stale(self) -> None:
        stale_done = done(IDS[2])
        stale_done["evidence"]["artifact"] = (
            "https://github.com/o/r/blob/ffffffffffffffffffffffffffffffffffffffff/acceptance/run.json"
        )
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, stale_done),
        ]
        result = evaluate_issue(FakeGitHub(comments, pr=pr(merged=False)), ISSUE)
        self.assertEqual("halt", result.state)
        self.assertEqual("stale_evidence", result.diagnostics[0].token)

    def test_candidate_file_outside_contract_scope_is_invalid_binding(self) -> None:
        scoped_contract = contract(IDS[0])
        scoped_contract["scope"] = ["src/"]
        comments = [comment(1, scoped_contract), comment(2, start(IDS[1]))]
        result = evaluate_issue(
            FakeGitHub(
                comments,
                candidates=[pr(merged=False)],
                files=[{"filename": "README.md", "status": "modified"}],
            ),
            ISSUE,
        )
        self.assertEqual("halt", result.state)
        self.assertEqual("invalid_binding", result.diagnostics[0].token)
        self.assertEqual(["README.md"], result.diagnostics[0].detail["paths"])

    def test_incomplete_pr_file_collection_is_acquisition_error(self) -> None:
        scoped_contract = contract(IDS[0])
        scoped_contract["scope"] = ["src/"]
        comments = [comment(1, scoped_contract), comment(2, start(IDS[1]))]
        candidate = pr(merged=False)
        candidate["changed_files"] = 3001
        result = evaluate_issue(
            FakeGitHub(
                comments,
                candidates=[candidate],
                pr=candidate,
                files=[{"filename": "src/a.py", "status": "modified"}],
            ),
            ISSUE,
        )
        self.assertIsNone(result.state)
        self.assertEqual("acquisition_incomplete", result.acquisition_errors[0]["code"])

    def test_rename_checks_previous_and_current_paths(self) -> None:
        scoped_contract = contract(IDS[0])
        scoped_contract["scope"] = ["src/"]
        comments = [comment(1, scoped_contract), comment(2, start(IDS[1]))]
        result = evaluate_issue(
            FakeGitHub(
                comments,
                candidates=[pr(merged=False)],
                files=[{
                    "filename": "src/new.py",
                    "previous_filename": "outside.py",
                    "status": "renamed",
                }],
            ),
            ISSUE,
        )
        self.assertEqual("invalid_binding", result.diagnostics[0].token)
        self.assertEqual(["outside.py"], result.diagnostics[0].detail["paths"])

    def test_bound_pr_head_change_is_acquisition_error(self) -> None:
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, done(IDS[2])),
        ]

        class MovingHead(FakeGitHub):
            def __init__(self):
                super().__init__(comments, pr=pr(merged=False))
                self.pr_reads = 0

            def pull_request(self, owner, repo, number):
                self.pr_reads += 1
                value = dict(self._pr)
                value["head"] = dict(value["head"])
                if self.pr_reads > 1:
                    value["head"]["sha"] = "f" * 40
                return value

        result = evaluate_issue(MovingHead(), ISSUE)
        self.assertIsNone(result.state)
        self.assertEqual("acquisition_incomplete", result.acquisition_errors[0]["code"])

    def test_bound_branch_change_during_done_read_is_acquisition_error(self) -> None:
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, done(IDS[2])),
        ]

        class MovingBranch(FakeGitHub):
            def __init__(self):
                super().__init__(comments, pr=pr(merged=False))
                self.branch_reads = 0

            def branch(self, owner, repo, branch):
                self.branch_reads += 1
                value = super().branch(owner, repo, branch)
                if self.branch_reads > 1 and value is not None:
                    value = {"name": branch, "commit": {"sha": "f" * 40}}
                return value

        result = evaluate_issue(MovingBranch(), ISSUE)
        self.assertIsNone(result.state)
        self.assertEqual("acquisition_incomplete", result.acquisition_errors[0]["code"])

    def test_issue_change_during_read_is_acquisition_error(self) -> None:
        comments = [comment(1, contract(IDS[0]))]

        class MovingIssue(FakeGitHub):
            def __init__(self):
                super().__init__(comments)
                self.issue_reads = 0

            def issue(self, owner, repo, number):
                self.issue_reads += 1
                value = super().issue(owner, repo, number)
                if self.issue_reads > 1:
                    value["updated_at"] = "2026-07-19T00:00:01Z"
                return value

        result = evaluate_issue(MovingIssue(), ISSUE)
        self.assertIsNone(result.state)
        self.assertEqual("acquisition_incomplete", result.acquisition_errors[0]["code"])

    def test_pr_candidate_collection_change_during_read_is_acquisition_error(self) -> None:
        comments = [comment(1, contract(IDS[0])), comment(2, start(IDS[1]))]

        class MovingCandidates(FakeGitHub):
            def __init__(self):
                super().__init__(comments)
                self.candidate_reads = 0

            def pull_requests(self, owner, repo, branch):
                self.candidate_reads += 1
                return [] if self.candidate_reads == 1 else [pr(merged=False)]

        result = evaluate_issue(MovingCandidates(), ISSUE)
        self.assertIsNone(result.state)
        self.assertEqual("acquisition_incomplete", result.acquisition_errors[0]["code"])

    def test_merge_before_done_is_terminal_violation(self) -> None:
        merged = pr(merged=True)
        merged["merged_at"] = "2026-07-19T00:00:02Z"
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, done(IDS[2])),
        ]
        result = evaluate_issue(FakeGitHub(comments, pr=merged), ISSUE)
        self.assertEqual("halt", result.state)
        self.assertEqual("terminal_violation", result.diagnostics[0].token)

    def test_successor_must_be_other_issue_in_time_window(self) -> None:
        successor = "https://github.com/o/r/issues/2"
        stopped = stop(IDS[1])
        stopped["reason"] = "superseded"
        stopped["successor_ref"] = successor
        comments = [comment(1, contract(IDS[0])), comment(2, stopped)]

        class SuccessorGitHub(FakeGitHub):
            def issue(self, owner, repo, number):
                if number == 2:
                    return {
                        "id": 2,
                        "url": successor,
                        "created_at": "2026-07-19T00:00:01Z",
                        "updated_at": "2026-07-19T00:00:01Z",
                    }
                return super().issue(owner, repo, number)

        self.assertEqual("stopped", evaluate_issue(SuccessorGitHub(comments), ISSUE).state)

        invalid_stop = stop(IDS[1])
        invalid_stop["reason"] = "superseded"
        invalid_stop["successor_ref"] = ISSUE
        invalid_comments = [comment(1, contract(IDS[0])), comment(2, invalid_stop)]
        invalid = evaluate_issue(FakeGitHub(invalid_comments), ISSUE)
        self.assertEqual("halt", invalid.state)
        self.assertEqual("invalid_binding", invalid.diagnostics[0].token)

    def test_stop_is_stopped_without_branch_reads(self) -> None:
        comments = [comment(1, contract(IDS[0])), comment(2, stop(IDS[1]))]
        result = evaluate_issue(FakeGitHub(comments, branch=False), ISSUE)
        self.assertEqual("stopped", result.state)

    def test_fresh_record_after_stop_is_terminal_violation(self) -> None:
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, stop(IDS[1])),
            comment(3, contract(IDS[2])),
        ]
        result = evaluate_issue(FakeGitHub(comments), ISSUE)
        self.assertEqual("halt", result.state)
        self.assertEqual("terminal_violation", result.diagnostics[0].token)
        self.assertEqual(comments[2].url, result.diagnostics[0].urls[0])

    def test_irrelevant_successor_after_stop_is_not_acquired(self) -> None:
        fresh_stop = stop(IDS[2])
        fresh_stop["reason"] = "superseded"
        fresh_stop["successor_ref"] = "https://github.com/x/y/issues/9"
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, stop(IDS[1])),
            comment(3, fresh_stop),
        ]

        class InaccessibleSuccessor(FakeGitHub):
            def repository(self, owner, repo):
                if (owner, repo) == ("x", "y"):
                    raise AcquisitionError("successor", "not visible", 404)
                return super().repository(owner, repo)

        result = evaluate_issue(InaccessibleSuccessor(comments), ISSUE)
        self.assertEqual("halt", result.state)
        self.assertEqual("terminal_violation", result.diagnostics[0].token)
        self.assertEqual(comments[2].url, result.diagnostics[0].urls[0])

    def test_future_pr_reusing_stopped_branch_is_irrelevant(self) -> None:
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, stop(IDS[2])),
        ]
        reused = pr(merged=True)
        reused["created_at"] = "2026-07-19T00:00:05Z"
        reused["merged_at"] = "2026-07-19T00:00:06Z"
        result = evaluate_issue(FakeGitHub(comments, candidates=[reused]), ISSUE)
        self.assertEqual("stopped", result.state)
        self.assertEqual([], result.diagnostics)

    def test_default_branch_start_halts_without_continue_work(self) -> None:
        start_record = start(IDS[1])
        start_record["branch"] = "main"
        comments = [comment(1, contract(IDS[0])), comment(2, start_record)]
        result = evaluate_issue(FakeGitHub(comments), ISSUE)
        self.assertEqual("halt", result.state)
        self.assertEqual("invalid_binding", result.diagnostics[0].token)

    def test_stop_safely_closes_default_branch_binding(self) -> None:
        start_record = start(IDS[1])
        start_record["branch"] = "main"
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start_record),
            comment(3, stop(IDS[2])),
        ]
        result = evaluate_issue(FakeGitHub(comments), ISSUE)
        self.assertEqual("stopped", result.state)

    def test_stop_before_done_terminal_wins(self) -> None:
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, done(IDS[2])),
            comment(4, stop(IDS[3])),
        ]
        result = evaluate_issue(FakeGitHub(comments, pr=pr(merged=False)), ISSUE)
        self.assertEqual("stopped", result.state)

    def test_stop_after_done_terminal_is_terminal_violation(self) -> None:
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, done(IDS[2])),
            comment(4, stop(IDS[3])),
        ]
        merged = pr(merged=True)
        merged["merged_at"] = "2026-07-19T00:00:03Z"
        result = evaluate_issue(FakeGitHub(comments, pr=merged), ISSUE)
        self.assertEqual("halt", result.state)
        self.assertEqual("terminal_violation", result.diagnostics[0].token)
        self.assertEqual(comments[3].url, result.diagnostics[0].urls[0])

    def test_stop_closes_merge_without_done_when_merge_precedes_stop(self) -> None:
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, stop(IDS[2])),
        ]
        merged = pr(merged=True)
        merged["merged_at"] = "2026-07-19T00:00:02Z"
        result = evaluate_issue(FakeGitHub(comments, candidates=[merged]), ISSUE)
        self.assertEqual("stopped", result.state)

    def test_merge_after_final_stop_is_terminal_violation(self) -> None:
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, stop(IDS[2])),
        ]
        merged = pr(merged=True)
        merged["merged_at"] = "2026-07-19T00:00:04Z"
        result = evaluate_issue(FakeGitHub(comments, candidates=[merged]), ISSUE)
        self.assertEqual("halt", result.state)
        self.assertEqual("terminal_violation", result.diagnostics[0].token)

    def test_acquisition_error_has_no_state(self) -> None:
        class Broken(FakeGitHub):
            def comments(self, owner, repo, number):
                raise AcquisitionError("comments", "timeout")

        result = evaluate_issue(Broken([]), ISSUE)
        self.assertIsNone(result.state)
        self.assertFalse(result.projection()["acquisition"]["complete"])

    def test_issue_url_resolving_to_pull_request_is_rejected(self) -> None:
        class PullIssue(FakeGitHub):
            def issue(self, owner, repo, number):
                return {
                    "id": 1,
                    "url": ISSUE,
                    "created_at": "2026-07-18T00:00:00Z",
                    "updated_at": "2026-07-19T00:00:00Z",
                    "pull_request": {"url": "https://api.github.com/repos/o/r/pulls/1"},
                }

        result = evaluate_issue(PullIssue([]), ISSUE)
        self.assertIsNone(result.state)
        self.assertEqual("invalid_issue_resource", result.acquisition_errors[0]["code"])

    def test_repository_404_during_pr_binding_is_acquisition_failure(self) -> None:
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, done(IDS[2])),
        ]

        class RepositoryDisappears(FakeGitHub):
            def __init__(self):
                super().__init__(comments, pr=pr(merged=False))
                self.calls = 0

            def repository(self, owner, repo):
                self.calls += 1
                if self.calls > 1:
                    raise AcquisitionError("repository", "not visible", 404)
                return super().repository(owner, repo)

        result = evaluate_issue(RepositoryDisappears(), ISSUE)
        self.assertIsNone(result.state)
        self.assertEqual("acquisition_incomplete", result.acquisition_errors[0]["code"])


if __name__ == "__main__":
    unittest.main()
