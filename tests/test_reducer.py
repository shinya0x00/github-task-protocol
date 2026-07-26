from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from gtp.model import Comment, IncompleteSnapshotError
from gtp.reducer import (
    HALT_REASONS,
    current_done,
    effective_conditions,
    effective_revision,
    fold_comments,
    historical_state,
)


ISSUE = "https://github.com/o/r/issues/1"
IDS = [f"{number:08x}-0000-4000-8000-{number:012x}" for number in range(1, 40)]
SHA = "0123456789abcdef0123456789abcdef01234567"
SHA_2 = "123456789abcdef0123456789abcdef012345678"


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


def amendment(
    record_id: str,
    predecessor_ref: str,
    *,
    conditions: dict[str, dict[str, str]] | None = None,
) -> dict:
    return {
        "gtp": "1.1",
        "type": "amendment",
        "id": record_id,
        "predecessor_ref": predecessor_ref,
        "done_conditions": conditions or {
            "check": {"text": "check passes", "evidence_kind": "check"}
        },
    }


def done_11(
    record_id: str,
    revision_ref: str,
    *,
    previous_done_ref: str | None = None,
    pr_ref: str = "https://github.com/o/r/pull/7",
    head_sha: str = SHA,
    evidence: dict[str, str] | None = None,
) -> dict:
    return {
        "gtp": "1.1",
        "type": "done",
        "id": record_id,
        "revision_ref": revision_ref,
        "previous_done_ref": previous_done_ref,
        "pr_ref": pr_ref,
        "head_sha": head_sha,
        "evidence": evidence or {
            "artifact": f"https://github.com/o/r/blob/{head_sha}/acceptance/run.json"
        },
    }


def stop(record_id: str) -> dict:
    return {"gtp": "1.0", "type": "stop", "id": record_id, "reason": "abandoned", "successor_ref": None}


class ReducerTests(unittest.TestCase):
    def test_truth_table_fixture(self) -> None:
        fixture = json.loads((Path(__file__).parent / "fixtures" / "reducer-truth-table.json").read_text())
        builders = {
            "ordinary": lambda n: comment(n, None),
            "malformed": lambda n: comment(
                n, None, source="<!-- gtp-record:v1 -->\ninvalid"
            ),
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
                if "first_url_comment" in case:
                    expected = f"{ISSUE}#issuecomment-{case['first_url_comment']}"
                    self.assertEqual(expected, result.diagnostics[0].urls[0])

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

    def test_amendment_requires_start_current_tip_and_new_condition_ids(self) -> None:
        before_start = fold_comments([
            comment(1, contract(IDS[0])),
            comment(2, amendment(IDS[1], f"{ISSUE}#issuecomment-1")),
        ])
        self.assertEqual("halt", historical_state(before_start))
        self.assertEqual("invalid_transition", before_start.diagnostics[0].token)

        valid = fold_comments([
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, amendment(IDS[2], f"{ISSUE}#issuecomment-1")),
            comment(4, amendment(
                IDS[3],
                f"{ISSUE}#issuecomment-3",
                conditions={"report": {"text": "report exists", "evidence_kind": "artifact"}},
            )),
        ])
        self.assertEqual("in_progress", historical_state(valid))
        self.assertEqual(f"{ISSUE}#issuecomment-4", effective_revision(valid).comment.url)
        self.assertEqual({"artifact", "check", "report"}, set(effective_conditions(valid)))

        skipped_tip = fold_comments([
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, amendment(IDS[2], f"{ISSUE}#issuecomment-1")),
            comment(4, amendment(
                IDS[3],
                f"{ISSUE}#issuecomment-1",
                conditions={"report": {"text": "report exists", "evidence_kind": "artifact"}},
            )),
        ])
        self.assertEqual("invalid_transition", skipped_tip.diagnostics[-1].token)

        redefined = fold_comments([
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, amendment(
                IDS[2],
                f"{ISSUE}#issuecomment-1",
                conditions={"artifact": {"text": "changed", "evidence_kind": "check"}},
            )),
        ])
        self.assertEqual("invalid_transition", redefined.diagnostics[-1].token)

    def test_protocol_10_can_migrate_to_11_but_cannot_downgrade(self) -> None:
        migrated = fold_comments([
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, done_11(IDS[2], f"{ISSUE}#issuecomment-1")),
        ])
        self.assertEqual("in_progress", historical_state(migrated))
        self.assertTrue(migrated.protocol_11_seen)

        downgraded = fold_comments([
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, done_11(IDS[2], f"{ISSUE}#issuecomment-1")),
            comment(4, stop(IDS[3])),
        ])
        self.assertEqual("halt", historical_state(downgraded))
        self.assertEqual("invalid_transition", downgraded.diagnostics[-1].token)

        start_11 = dict(start(IDS[1]), gtp="1.1")
        implicit = fold_comments([
            comment(1, contract(IDS[0])),
            comment(2, start_11),
        ])
        self.assertEqual("invalid_transition", implicit.diagnostics[-1].token)

        contract_11 = dict(contract(IDS[0]), gtp="1.1")
        native = fold_comments([comment(1, contract_11), comment(2, start_11)])
        self.assertEqual("in_progress", historical_state(native))

    def test_invalid_first_11_record_locks_version_before_later_10_record(self) -> None:
        invalid_first_records = {
            "contract": dict(contract(IDS[1]), gtp="1.1"),
            "start": dict(start(IDS[1]), gtp="1.1"),
            "stop": dict(stop(IDS[1]), gtp="1.1"),
        }
        later_10_records = {
            "start": start(IDS[2]),
            "stop": stop(IDS[2]),
        }

        for first_type, first_record in invalid_first_records.items():
            for later_type, later_record in later_10_records.items():
                with self.subTest(first_type=first_type, later_type=later_type):
                    result = fold_comments([
                        comment(1, contract(IDS[0])),
                        comment(2, first_record),
                        comment(3, later_record),
                    ])

                    self.assertTrue(result.protocol_11_seen)
                    self.assertEqual(
                        ["invalid_transition", "invalid_transition"],
                        [diagnostic.token for diagnostic in result.diagnostics],
                    )
                    self.assertIsNone(result.bound_start)
                    self.assertIsNone(result.terminal_stop)
                    self.assertEqual("halt", historical_state(result))

    def test_invalid_11_contract_after_start_cannot_enable_later_10_stop(self) -> None:
        result = fold_comments([
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, dict(contract(IDS[2]), gtp="1.1")),
            comment(4, stop(IDS[3])),
        ])

        self.assertTrue(result.protocol_11_seen)
        self.assertEqual(
            ["invalid_transition", "invalid_transition"],
            [diagnostic.token for diagnostic in result.diagnostics],
        )
        self.assertIsNone(result.terminal_stop)
        self.assertEqual([], result.active["stop"])
        self.assertEqual("halt", historical_state(result))

    def test_schema_invalid_11_record_still_locks_version(self) -> None:
        invalid_11 = dict(contract(IDS[1]), gtp="1.1", scope="src/")
        result = fold_comments([
            comment(1, contract(IDS[0])),
            comment(2, invalid_11),
            comment(3, stop(IDS[2])),
        ])

        self.assertTrue(result.protocol_11_seen)
        self.assertEqual(
            ["invalid_record", "invalid_transition"],
            [diagnostic.token for diagnostic in result.diagnostics],
        )
        self.assertIsNone(result.terminal_stop)
        self.assertEqual("halt", historical_state(result))

    def test_first_done_requires_null_previous_and_redone_uses_immediate_logical_done(self) -> None:
        non_null_first = fold_comments([
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, done_11(
                IDS[2], f"{ISSUE}#issuecomment-1",
                previous_done_ref=f"{ISSUE}#issuecomment-2",
            )),
        ])
        self.assertEqual("invalid_transition", non_null_first.diagnostics[-1].token)

        first = done_11(IDS[2], f"{ISSUE}#issuecomment-1")
        redone = done_11(
            IDS[3],
            f"{ISSUE}#issuecomment-1",
            previous_done_ref=f"{ISSUE}#issuecomment-4",
            head_sha=SHA_2,
        )
        valid = fold_comments([
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, first),
            comment(4, copy.deepcopy(first)),
            comment(5, redone),
        ])
        self.assertEqual("in_progress", historical_state(valid))
        self.assertEqual(
            (f"{ISSUE}#issuecomment-3", f"{ISSUE}#issuecomment-4"),
            valid.active["done"][0].alias_urls,
        )
        self.assertEqual(f"{ISSUE}#issuecomment-5", current_done(valid).comment.url)

        skipped = fold_comments([
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, first),
            comment(4, done_11(
                IDS[3], f"{ISSUE}#issuecomment-1",
                previous_done_ref=f"{ISSUE}#issuecomment-3", head_sha=SHA_2,
            )),
            comment(5, done_11(
                IDS[4], f"{ISSUE}#issuecomment-1",
                previous_done_ref=f"{ISSUE}#issuecomment-3",
            )),
        ])
        self.assertEqual("invalid_transition", skipped.diagnostics[-1].token)

    def test_redone_stays_on_same_pr(self) -> None:
        result = fold_comments([
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, done_11(IDS[2], f"{ISSUE}#issuecomment-1")),
            comment(4, done_11(
                IDS[3], f"{ISSUE}#issuecomment-1",
                previous_done_ref=f"{ISSUE}#issuecomment-3",
                pr_ref="https://github.com/o/r/pull/8",
            )),
        ])
        self.assertEqual("halt", historical_state(result))
        self.assertEqual("invalid_binding", result.diagnostics[-1].token)

    def test_done_binds_current_revision_and_full_evidence_union(self) -> None:
        records = [
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, amendment(IDS[2], f"{ISSUE}#issuecomment-1")),
        ]
        evidence = {
            "artifact": f"https://github.com/o/r/blob/{SHA}/acceptance/run.json",
            "check": "https://github.com/o/r/runs/4",
        }
        valid = fold_comments(records + [
            comment(4, done_11(IDS[3], f"{ISSUE}#issuecomment-3", evidence=evidence)),
        ])
        self.assertEqual("in_progress", historical_state(valid))
        self.assertEqual(f"{ISSUE}#issuecomment-3", effective_revision(valid).comment.url)

        stale_revision = fold_comments(records + [
            comment(4, done_11(IDS[3], f"{ISSUE}#issuecomment-1", evidence=evidence)),
        ])
        self.assertEqual("invalid_transition", stale_revision.diagnostics[-1].token)

        missing_added = fold_comments(records + [
            comment(4, done_11(IDS[3], f"{ISSUE}#issuecomment-3")),
        ])
        self.assertEqual("invalid_evidence", missing_added.diagnostics[-1].token)

        wrong_kind = dict(evidence, check=f"https://github.com/o/r/blob/{SHA}/check.json")
        wrong_evidence = fold_comments(records + [
            comment(4, done_11(IDS[3], f"{ISSUE}#issuecomment-3", evidence=wrong_kind)),
        ])
        self.assertEqual("invalid_evidence", wrong_evidence.diagnostics[-1].token)

    def test_invalid_later_done_halts_without_falling_back(self) -> None:
        result = fold_comments([
            comment(1, contract(IDS[0])),
            comment(2, start(IDS[1])),
            comment(3, done_11(IDS[2], f"{ISSUE}#issuecomment-1")),
            comment(4, done_11(
                IDS[3], f"{ISSUE}#issuecomment-1",
                previous_done_ref=f"{ISSUE}#issuecomment-3",
                evidence={"other": f"https://github.com/o/r/blob/{SHA}/other.json"},
            )),
        ])
        self.assertEqual("halt", historical_state(result))
        self.assertEqual("invalid_evidence", result.diagnostics[-1].token)
        self.assertEqual(f"{ISSUE}#issuecomment-3", current_done(result).comment.url)

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
