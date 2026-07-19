from __future__ import annotations

import copy
import json
import unittest

from gtp.github import AcquisitionError
from gtp.model import Comment, FoldContext, SuccessorFact
from gtp.reducer import fold_comments, historical_state
from gtp.status import evaluate_issue


ISSUE = "https://github.com/o/r/issues/1"
SHA = "0123456789abcdef0123456789abcdef01234567"


def rid(number: int) -> str:
    return f"00000000-0000-4000-8000-{number:012x}"


def carrier(record: dict) -> str:
    return "要約\n\n<!-- gtp-record:v1 -->\n\n```json\n" + json.dumps(record, ensure_ascii=False) + "\n```\n"


def observed(number: int, record: dict | None = None, *, body: str | None = None, edited: bool = False) -> Comment:
    created = f"2026-07-19T00:00:{number:02d}Z"
    updated = f"2026-07-19T00:01:{number:02d}Z" if edited else created
    return Comment(
        number,
        f"{ISSUE}#issuecomment-{number}",
        body if body is not None else carrier(record or {}),
        created,
        updated,
        "agent",
    )


def contract(number: int, supersedes: list[str] | None = None, *, kind: str = "artifact") -> dict:
    return {
        "gtp": "1.0",
        "type": "contract",
        "id": rid(number),
        "supersedes": supersedes or [],
        "goal": "GTP v1 conformance",
        "scope": ["."],
        "done_conditions": {
            "release": {"text": "release evidence exists", "evidence_kind": kind}
        },
    }


def start(number: int, supersedes: list[str] | None = None) -> dict:
    return {
        "gtp": "1.0",
        "type": "start",
        "id": rid(number),
        "supersedes": supersedes or [],
        "branch": "codex/v1",
    }


def done(number: int, supersedes: list[str] | None = None, *, kind: str = "artifact") -> dict:
    evidence = (
        "https://github.com/o/r/runs/8"
        if kind == "check"
        else f"https://github.com/o/r/blob/{SHA}/acceptance/v1.json"
    )
    return {
        "gtp": "1.0",
        "type": "done",
        "id": rid(number),
        "supersedes": supersedes or [],
        "pr_ref": "https://github.com/o/r/pull/7",
        "head_sha": SHA,
        "evidence": {"release": evidence},
    }


def stop(number: int, supersedes: list[str] | None = None, *, successor: str | None = None) -> dict:
    return {
        "gtp": "1.0",
        "type": "stop",
        "id": rid(number),
        "supersedes": supersedes or [],
        "reason": "superseded" if successor else "abandoned",
        "successor_ref": successor,
    }


class LiveGitHub:
    def __init__(
        self,
        comments: list[Comment],
        *,
        merged_at: str | None = None,
        branch: bool = True,
        check: dict | None = None,
        artifact_missing: bool = False,
    ) -> None:
        self._comments = comments
        self._merged_at = merged_at
        self._branch = branch
        self._check = check
        self._artifact_missing = artifact_missing

    def repository(self, owner, repo):
        return {"id": 99, "url": "https://api.github.com/repos/o/r"}

    def issue(self, owner, repo, number):
        return {"id": number, "created_at": "2026-07-18T00:00:00Z"}

    def comments(self, owner, repo, number):
        return self._comments

    def branch(self, owner, repo, branch):
        return {"name": branch} if self._branch else None

    def pull_requests(self, owner, repo, branch):
        return []

    def pull_request(self, owner, repo, number):
        return {
            "html_url": "https://github.com/o/r/pull/7",
            "base": {"repo": {"id": 99}},
            "head": {"repo": {"id": 99}, "ref": "codex/v1", "sha": SHA},
            "merged_at": self._merged_at,
        }

    def artifact(self, owner, repo, path, sha):
        if self._artifact_missing:
            raise AcquisitionError("artifact", "not found", 404)
        return {"type": "file", "path": path}

    def check_run(self, owner, repo, number):
        assert self._check is not None
        return self._check


class PrefixFoldConformanceTests(unittest.TestCase):
    def test_api_retry_alias_is_one_logical_record(self) -> None:
        record = contract(1)
        result = fold_comments([observed(1, record), observed(2, copy.deepcopy(record))])
        self.assertEqual("ready", historical_state(result))
        self.assertEqual(1, len(result.active["contract"]))
        self.assertEqual(
            (f"{ISSUE}#issuecomment-1", f"{ISSUE}#issuecomment-2"),
            result.active["contract"][0].alias_urls,
        )

    def test_delayed_retry_does_not_revive_superseded_record(self) -> None:
        first_record = contract(1)
        first = observed(1, first_record)
        replacement = observed(2, contract(2, [first.url]))
        retry = observed(3, copy.deepcopy(first_record))
        result = fold_comments([first, replacement, retry])
        self.assertEqual([replacement.url], [item.comment.url for item in result.active["contract"]])

    def test_arbitrary_leaf_join_recovers_conflict(self) -> None:
        leaves = [observed(number, contract(number)) for number in range(1, 4)]
        replacement = observed(4, contract(4, [item.url for item in leaves]))
        result = fold_comments([*leaves, replacement])
        self.assertEqual("ready", historical_state(result))
        self.assertEqual([replacement.url], [item.comment.url for item in result.active["contract"]])

    def test_malformed_carrier_repair(self) -> None:
        broken = observed(
            1,
            body="要約\n\n<!-- gtp-record:v1 -->\n\n```json\n{broken\n```\n",
        )
        repair = observed(2, contract(2, [broken.url]))
        result = fold_comments([broken, repair])
        self.assertEqual("ready", historical_state(result))
        self.assertFalse(result.diagnostics)

    def test_edited_carrier_repair(self) -> None:
        edited = observed(1, contract(1), edited=True)
        repair = observed(2, contract(2, [edited.url]))
        result = fold_comments([edited, repair])
        self.assertEqual("ready", historical_state(result))
        self.assertFalse(result.diagnostics)

    def test_collision_requires_complete_repair_group(self) -> None:
        first_record = contract(1)
        second_record = start(1)
        first = observed(1, first_record)
        second = observed(2, second_record)
        partial = observed(3, contract(3, [first.url]))
        result = fold_comments([first, second, partial])
        self.assertEqual("halt", historical_state(result))
        self.assertIn("identity_collision", [item.token for item in result.diagnostics])
        self.assertIn("incomplete_repair_group", [item.token for item in result.diagnostics])

    def test_collision_complete_cross_type_repair(self) -> None:
        first = observed(1, contract(1))
        second = observed(2, start(1))
        repair = observed(3, contract(3, [first.url, second.url]))
        result = fold_comments([first, second, repair])
        self.assertEqual("ready", historical_state(result))
        self.assertFalse(result.diagnostics)

    def test_contextual_invalid_done_can_be_repaired_after_start(self) -> None:
        c = observed(1, contract(1))
        early = observed(2, done(2))
        s = observed(3, start(3))
        repair = observed(4, done(4, [early.url]))
        result = fold_comments([c, early, s, repair])
        self.assertEqual("in_progress", historical_state(result))
        self.assertFalse(result.diagnostics)
        self.assertEqual([repair.url], [item.comment.url for item in result.active["done"]])

    def test_successor_order_invalid_is_repairable(self) -> None:
        successor = "https://github.com/o/r/issues/2"
        context = FoldContext(
            issue_id=1,
            issue_created_at="2026-07-19T00:00:00Z",
            repository_id=99,
            successors={
                successor: SuccessorFact(
                    successor,
                    True,
                    repository_id=99,
                    issue_id=2,
                    created_at="2026-07-19T00:00:03Z",
                )
            },
        )
        c = observed(1, contract(1))
        invalid = observed(2, stop(2, successor=successor))
        repair = observed(4, stop(4, [invalid.url], successor=successor))
        result = fold_comments([c, invalid, repair], context)
        self.assertEqual("stopped", historical_state(result))
        self.assertFalse(result.diagnostics)


class TerminalConformanceTests(unittest.TestCase):
    def test_done_before_stop_wins(self) -> None:
        comments = [observed(1, contract(1)), observed(2, start(2)), observed(3, done(3)), observed(5, stop(5))]
        result = evaluate_issue(LiveGitHub(comments, merged_at="2026-07-19T00:00:04Z"), ISSUE)
        self.assertEqual("done", result.state)

    def test_done_stop_timestamp_tie_prefers_done(self) -> None:
        comments = [observed(1, contract(1)), observed(2, start(2)), observed(3, done(3)), observed(5, stop(5))]
        result = evaluate_issue(LiveGitHub(comments, merged_at="2026-07-19T00:00:05Z"), ISSUE)
        self.assertEqual("done", result.state)

    def test_check_completion_after_stop_keeps_stopped(self) -> None:
        comments = [
            observed(1, contract(1, kind="check")),
            observed(2, start(2)),
            observed(3, done(3, kind="check")),
            observed(5, stop(5)),
        ]
        check = {
            "head_sha": SHA,
            "status": "completed",
            "conclusion": "success",
            "completed_at": "2026-07-19T00:00:06Z",
        }
        result = evaluate_issue(
            LiveGitHub(comments, merged_at="2026-07-19T00:00:04Z", check=check), ISSUE
        )
        self.assertEqual("stopped", result.state)

    def test_merged_pr_with_pending_check_is_not_done(self) -> None:
        comments = [
            observed(1, contract(1, kind="check")),
            observed(2, start(2)),
            observed(3, done(3, kind="check")),
        ]
        check = {"head_sha": SHA, "status": "in_progress", "conclusion": None}
        result = evaluate_issue(
            LiveGitHub(comments, merged_at="2026-07-19T00:00:04Z", branch=False, check=check), ISSUE
        )
        self.assertEqual("in_progress", result.state)
        self.assertTrue(result.current["evidence_pending"])

    def test_late_done_establishes_terminal_at_comment_time(self) -> None:
        comments = [observed(1, contract(1)), observed(2, start(2)), observed(6, done(3))]
        result = evaluate_issue(LiveGitHub(comments, merged_at="2026-07-19T00:00:04Z", branch=False), ISSUE)
        self.assertEqual("done", result.state)

    def test_missing_terminal_artifact_halts(self) -> None:
        comments = [observed(1, contract(1)), observed(2, start(2)), observed(3, done(3))]
        result = evaluate_issue(
            LiveGitHub(comments, merged_at="2026-07-19T00:00:04Z", artifact_missing=True), ISSUE
        )
        self.assertEqual("halt", result.state)
        self.assertEqual("terminal_dependency_mismatch", result.diagnostics[0].token)

    def test_aliases_are_projected_in_server_order(self) -> None:
        record = contract(1)
        comments = [observed(1, record), observed(2, copy.deepcopy(record))]
        result = evaluate_issue(LiveGitHub(comments), ISSUE)
        self.assertEqual("ready", result.state)
        self.assertEqual(
            [f"{ISSUE}#issuecomment-1", f"{ISSUE}#issuecomment-2"],
            result.current["contract"]["aliases"],
        )

    def test_unordered_snapshot_is_acquisition_failure(self) -> None:
        comments = [observed(2, contract(2)), observed(1, contract(1))]
        result = evaluate_issue(LiveGitHub(comments), ISSUE)
        self.assertIsNone(result.state)
        self.assertEqual("acquisition_incomplete", result.acquisition_errors[0]["code"])


if __name__ == "__main__":
    unittest.main()
