from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from gtp.model import Comment, IncompleteSnapshotError
from gtp.reducer import HALT_REASONS, fold_comments, historical_state


ISSUE = "https://github.com/o/r/issues/1"
IDS = [f"{number:08x}-0000-4000-8000-{number:012x}" for number in range(1, 8)]
SHA = "0123456789abcdef0123456789abcdef01234567"


def body(record: dict) -> str:
    return (
        "<!-- gtp-record:v1 -->\n"
        "要約\n\n"
        "<details><summary>記録(JSON)</summary>\n\n"
        "```json\n"
        + json.dumps(record, ensure_ascii=False, indent=2)
        + "\n```\n\n</details>\n"
    )


def comment(number: int, record: dict | None, *, edited: bool = False, source: str | None = None) -> Comment:
    url = f"{ISSUE}#issuecomment-{number}"
    created = f"2026-07-19T00:00:{number:02d}Z"
    updated = f"2026-07-19T00:01:{number:02d}Z" if edited else created
    return Comment(number, url, source if source is not None else body(record) if record else "ordinary", created, updated, "agent")


def contract(record_id: str) -> dict:
    return {
        "gtp": "1.0",
        "type": "contract",
        "id": record_id,
        "goal": "walking skeleton",
        "scope": ["."],
        "done_conditions": {"artifact": {"text": "artifact exists", "evidence_kind": "artifact"}},
    }


def start(record_id: str, contract_ref: str | None = None) -> dict:
    return {
        "gtp": "1.0",
        "type": "start",
        "id": record_id,
        "contract_ref": contract_ref or f"{ISSUE}#issuecomment-1",
        "branch": "codex/walking",
    }


def done(record_id: str, *, evidence: dict[str, str] | None = None) -> dict:
    return {
        "gtp": "1.0",
        "type": "done",
        "id": record_id,
        "pr_ref": "https://github.com/o/r/pull/7",
        "head_sha": SHA,
        "evidence": evidence or {"artifact": f"https://github.com/o/r/blob/{SHA}/acceptance/run.json"},
    }


def stop(record_id: str) -> dict:
    return {"gtp": "1.0", "type": "stop", "id": record_id, "reason": "abandoned", "successor_ref": None}


class ReducerTests(unittest.TestCase):
    def test_truth_table_fixture(self) -> None:
        fixture = json.loads((Path(__file__).parent / "fixtures" / "reducer-truth-table.json").read_text())
        builders = {
            "ordinary": lambda n: comment(n, None),
            "contract": lambda n: comment(n, contract(IDS[n - 1])),
            "start": lambda n: comment(n, start(IDS[n - 1])),
            "done": lambda n: comment(n, done(IDS[n - 1])),
            "stop": lambda n: comment(n, stop(IDS[n - 1])),
        }
        for case in fixture:
            with self.subTest(case=case["name"]):
                comments = [builders[kind](index + 1) for index, kind in enumerate(case["records"])]
                result = fold_comments(comments)
                self.assertEqual(case["state"], historical_state(result))
                self.assertEqual(case["reasons"], [item.token for item in result.diagnostics])

    def test_retry_alias_is_one_logical_record(self) -> None:
        record = contract(IDS[0])
        result = fold_comments([comment(1, record), comment(2, copy.deepcopy(record))])
        self.assertEqual("ready", historical_state(result))
        self.assertEqual((f"{ISSUE}#issuecomment-1", f"{ISSUE}#issuecomment-2"), result.active["contract"][0].alias_urls)

    def test_identity_collision_is_invalid_record(self) -> None:
        first = contract(IDS[0])
        second = dict(first, goal="different")
        result = fold_comments([comment(1, first), comment(2, second)])
        self.assertEqual("halt", historical_state(result))
        self.assertEqual(["invalid_record"], [item.token for item in result.diagnostics])

    def test_edited_and_malformed_carriers_are_invalid_record(self) -> None:
        edited = fold_comments([comment(1, contract(IDS[0]), edited=True)])
        malformed = fold_comments([comment(1, None, source="<!-- gtp-record:v1 -->\ninvalid")])
        self.assertEqual(["invalid_record"], [item.token for item in edited.diagnostics])
        self.assertEqual(["invalid_record"], [item.token for item in malformed.diagnostics])

    def test_start_binding_uses_contract_alias_urls(self) -> None:
        record = contract(IDS[0])
        result = fold_comments([
            comment(1, record),
            comment(2, copy.deepcopy(record)),
            comment(3, start(IDS[1], f"{ISSUE}#issuecomment-2")),
        ])
        self.assertEqual("in_progress", historical_state(result))

    def test_wrong_start_binding_and_done_evidence_are_canonical_reasons(self) -> None:
        binding = fold_comments([comment(1, contract(IDS[0])), comment(2, start(IDS[1], f"{ISSUE}#issuecomment-99"))])
        evidence = fold_comments([
            comment(1, contract(IDS[0])), comment(2, start(IDS[1])),
            comment(3, done(IDS[2], evidence={"other": f"https://github.com/o/r/blob/{SHA}/x"})),
        ])
        self.assertEqual("invalid_binding", binding.diagnostics[0].token)
        self.assertEqual("invalid_evidence", evidence.diagnostics[0].token)

    def test_final_stop_overrides_preterminal_failure(self) -> None:
        result = fold_comments([
            comment(1, None, source="<!-- gtp-record:v1 -->\nbroken"),
            comment(2, stop(IDS[1])),
        ])
        self.assertEqual("stopped", historical_state(result))

    def test_record_after_stop_is_terminal_violation(self) -> None:
        result = fold_comments([comment(1, stop(IDS[0])), comment(2, contract(IDS[1]))])
        self.assertEqual("halt", historical_state(result))
        self.assertEqual("terminal_violation", result.diagnostics[-1].token)

    def test_reason_vocabulary_is_exact(self) -> None:
        self.assertEqual(
            {"invalid_record", "conflicting_records", "invalid_transition", "invalid_binding", "invalid_evidence", "stale_evidence", "terminal_violation"},
            set(HALT_REASONS),
        )

    def test_snapshot_order_must_be_complete(self) -> None:
        with self.assertRaises(IncompleteSnapshotError):
            fold_comments([comment(2, contract(IDS[0])), comment(1, contract(IDS[1]))])


if __name__ == "__main__":
    unittest.main()
