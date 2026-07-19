from __future__ import annotations

import copy
import unittest

from gtp.model import Comment
from gtp.reducer import fold_comments, historical_state
from gtp.status import evaluate_issue

from test_reducer import IDS, ISSUE, comment, contract, start


class MinimalLiveGitHub:
    def __init__(self, comments: list[Comment]) -> None:
        self._comments = comments

    def repository(self, owner, repo):
        return {"id": 99, "url": "https://api.github.com/repos/o/r"}

    def issue(self, owner, repo, number):
        return {"id": number, "created_at": "2026-07-18T00:00:00Z"}

    def comments(self, owner, repo, number):
        return self._comments

    def branch(self, owner, repo, branch):
        return {"name": branch}

    def pull_requests(self, owner, repo, branch):
        return []


class V1ConformanceTests(unittest.TestCase):
    def test_alias_projection_preserves_server_order(self) -> None:
        record = contract(IDS[0])
        comments = [comment(1, record), comment(2, copy.deepcopy(record))]
        result = evaluate_issue(MinimalLiveGitHub(comments), ISSUE)
        self.assertEqual("ready", result.state)
        self.assertEqual(
            [f"{ISSUE}#issuecomment-1", f"{ISSUE}#issuecomment-2"],
            result.current["contract"]["aliases"],
        )

    def test_start_freezes_contract(self) -> None:
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, contract(IDS[2])),
        ]
        result = fold_comments(comments)
        self.assertEqual("halt", historical_state(result))
        self.assertEqual("invalid_transition", result.diagnostics[0].token)
        self.assertEqual(comments[0].url, result.bound_contract.comment.url)

    def test_two_starts_are_conflicting_records(self) -> None:
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, start(IDS[2])),
        ]
        result = fold_comments(comments)
        self.assertEqual("conflicting_records", result.diagnostics[0].token)

    def test_unordered_snapshot_is_acquisition_failure(self) -> None:
        comments = [comment(2, contract(IDS[1])), comment(1, contract(IDS[0]))]
        result = evaluate_issue(MinimalLiveGitHub(comments), ISSUE)
        self.assertIsNone(result.state)
        self.assertEqual("acquisition_incomplete", result.acquisition_errors[0]["code"])


if __name__ == "__main__":
    unittest.main()
