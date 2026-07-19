from __future__ import annotations

import json
import unittest

from gtp.model import Comment
from gtp.reducer import fold_comments, historical_state


ISSUE = "https://github.com/o/r/issues/1"
IDS = [
    "01234567-89ab-4def-8123-456789abcdef",
    "11234567-89ab-4def-8123-456789abcdef",
    "21234567-89ab-4def-8123-456789abcdef",
    "31234567-89ab-4def-8123-456789abcdef",
    "41234567-89ab-4def-8123-456789abcdef",
]


def body(record: dict) -> str:
    return "summary\n\n<!-- gtp-record:v1 -->\n\n```json\n" + json.dumps(record, ensure_ascii=False, indent=2) + "\n```\n"


def comment(number: int, record: dict | None) -> Comment:
    url = f"{ISSUE}#issuecomment-{number}"
    timestamp = f"2026-07-19T00:00:{number:02d}Z"
    return Comment(number, url, body(record) if record else "ordinary", timestamp, timestamp, "agent")


def contract(record_id: str, supersedes: list[str] | None = None) -> dict:
    return {
        "gtp": "1.0",
        "type": "contract",
        "id": record_id,
        "supersedes": supersedes or [],
        "goal": "walking skeleton",
        "scope": ["."],
        "done_conditions": {
            "artifact": {"text": "artifact exists", "evidence_kind": "artifact"}
        },
    }


def start(record_id: str) -> dict:
    return {
        "gtp": "1.0",
        "type": "start",
        "id": record_id,
        "supersedes": [],
        "branch": "codex/walking",
    }


class ReducerTests(unittest.TestCase):
    def test_unmanaged_and_ready(self) -> None:
        self.assertEqual("unmanaged", historical_state(fold_comments([comment(1, None)])))
        self.assertEqual("ready", historical_state(fold_comments([comment(1, contract(IDS[0]))])))

    def test_two_contract_conflict_reports_both_urls(self) -> None:
        result = fold_comments([comment(1, contract(IDS[0])), comment(2, contract(IDS[1]))])
        self.assertEqual("halt", historical_state(result))
        diagnostic = next(item for item in result.diagnostics if item.token == "conflicting_records")
        self.assertEqual(
            (f"{ISSUE}#issuecomment-1", f"{ISSUE}#issuecomment-2"), diagnostic.urls
        )

    def test_two_contract_conflict_recovers(self) -> None:
        first = comment(1, contract(IDS[0]))
        second = comment(2, contract(IDS[1]))
        replacement = comment(3, contract(IDS[2], [first.url, second.url]))
        result = fold_comments([first, second, replacement])
        self.assertEqual("ready", historical_state(result))
        self.assertEqual([replacement.url], [item.comment.url for item in result.active["contract"]])
        self.assertFalse(result.diagnostics)

    def test_start_binds_the_one_contract(self) -> None:
        first = comment(1, contract(IDS[0]))
        second = comment(2, start(IDS[1]))
        result = fold_comments([first, second])
        self.assertEqual("in_progress", historical_state(result))
        self.assertEqual(first.url, result.bound_contract.comment.url)
        self.assertEqual(second.url, result.bound_start.comment.url)

    def test_contract_freeze_keeps_original_binding(self) -> None:
        first = comment(1, contract(IDS[0]))
        started = comment(2, start(IDS[1]))
        late = comment(3, contract(IDS[2], [first.url]))
        result = fold_comments([first, started, late])
        self.assertEqual("halt", historical_state(result))
        self.assertEqual(first.url, result.bound_contract.comment.url)
        self.assertEqual([first.url], [item.comment.url for item in result.active["contract"]])

    def test_record_after_stop_is_terminal_diagnostic_only(self) -> None:
        stopped = {
            "gtp": "1.0",
            "type": "stop",
            "id": IDS[1],
            "supersedes": [],
            "reason": "abandoned",
            "successor_ref": None,
        }
        comments = [
            comment(1, contract(IDS[0])),
            comment(2, stopped),
            comment(3, contract(IDS[2])),
        ]
        result = fold_comments(comments)
        self.assertEqual("stopped", historical_state(result))
        self.assertIn("terminal_violation", [item.token for item in result.diagnostics])
        self.assertEqual([comments[0].url], [item.comment.url for item in result.active["contract"]])


if __name__ == "__main__":
    unittest.main()
