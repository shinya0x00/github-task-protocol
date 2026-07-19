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
        "supersedes": [],
        "pr_ref": "https://github.com/o/r/pull/7",
        "head_sha": SHA,
        "evidence": {"artifact": f"https://github.com/o/r/blob/{SHA}/acceptance/run.json"},
    }


def stop(record_id: str) -> dict:
    return {
        "gtp": "1.0",
        "type": "stop",
        "id": record_id,
        "supersedes": [],
        "reason": "abandoned",
        "successor_ref": None,
    }


class FakeGitHub:
    def __init__(self, comments, *, branch=True, candidates=None, pr=None, check=None):
        self._comments = comments
        self._branch = branch
        self._candidates = candidates or []
        self._pr = pr
        self._check = check

    def repository(self, owner, repo):
        return {"id": 99, "full_name": "o/r", "url": "https://api.github.com/repos/o/r"}

    def issue(self, owner, repo, number):
        return {"id": 1, "created_at": "2026-07-18T00:00:00Z"}

    def comments(self, owner, repo, number):
        return self._comments

    def branch(self, owner, repo, branch):
        return {"name": branch} if self._branch else None

    def pull_requests(self, owner, repo, branch):
        return self._candidates

    def pull_request(self, owner, repo, number):
        return self._pr

    def artifact(self, owner, repo, path, sha):
        return {"type": "file", "path": path, "sha": sha}

    def check_run(self, owner, repo, number):
        if self._check is None:
            raise AssertionError("not used")
        return self._check


def pr(*, merged: bool) -> dict:
    return {
        "html_url": "https://github.com/o/r/pull/7",
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
        self.assertEqual("branch_binding_mismatch", result.diagnostics[0].token)
        self.assertEqual(comments[1].url, result.diagnostics[0].urls[0])

    def test_merge_without_done_halts(self) -> None:
        comments = [comment(1, contract(IDS[0])), comment(2, start(IDS[1]))]
        result = evaluate_issue(FakeGitHub(comments, candidates=[pr(merged=True)]), ISSUE)
        self.assertEqual("halt", result.state)
        self.assertEqual("merge_without_done", result.diagnostics[0].token)

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

    def test_check_evidence_pending_is_in_progress(self) -> None:
        check_contract = contract(IDS[0])
        check_contract["done_conditions"]["artifact"]["evidence_kind"] = "check"
        check_done = done(IDS[2])
        check_done["evidence"]["artifact"] = "https://github.com/o/r/runs/8"
        comments = [comment(1, check_contract), comment(2, start(IDS[1])), comment(3, check_done)]
        check = {"head_sha": SHA, "status": "in_progress", "conclusion": None}
        result = evaluate_issue(FakeGitHub(comments, pr=pr(merged=False), check=check), ISSUE)
        self.assertEqual("in_progress", result.state)
        self.assertTrue(result.current["evidence_pending"])

    def test_failed_check_evidence_halts(self) -> None:
        check_contract = contract(IDS[0])
        check_contract["done_conditions"]["artifact"]["evidence_kind"] = "check"
        check_done = done(IDS[2])
        check_done["evidence"]["artifact"] = "https://github.com/o/r/runs/8"
        comments = [comment(1, check_contract), comment(2, start(IDS[1])), comment(3, check_done)]
        check = {"head_sha": SHA, "status": "completed", "conclusion": "failure"}
        result = evaluate_issue(FakeGitHub(comments, pr=pr(merged=False), check=check), ISSUE)
        self.assertEqual("halt", result.state)
        self.assertEqual("evidence_live_mismatch", result.diagnostics[0].token)

    def test_stop_is_stopped_without_branch_reads(self) -> None:
        comments = [comment(1, contract(IDS[0])), comment(2, stop(IDS[1]))]
        result = evaluate_issue(FakeGitHub(comments, branch=False), ISSUE)
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
                    "created_at": "2026-07-18T00:00:00Z",
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
