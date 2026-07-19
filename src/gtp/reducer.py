"""Pure Server Order fold for GTP v1 Records."""

from __future__ import annotations

from .carrier import classify_carrier
from .model import Comment, Diagnostic, FoldContext, FoldResult, IncompleteSnapshotError, RecordObservation
from .urls import parse_github_url


HALT_REASONS = frozenset(
    {
        "invalid_record",
        "conflicting_records",
        "invalid_transition",
        "invalid_binding",
        "invalid_evidence",
        "stale_evidence",
        "terminal_violation",
    }
)


def _diagnose(result: FoldResult, token: str, *urls: str) -> None:
    diagnostic = Diagnostic(token, tuple(dict.fromkeys(urls)))
    if diagnostic not in result.diagnostics:
        result.diagnostics.append(diagnostic)


def _remove_observation(result: FoldResult, target: RecordObservation) -> None:
    result.active[target.type] = [item for item in result.active[target.type] if item is not target]
    if result.bound_contract is target:
        result.bound_contract = None
    if result.bound_start is target:
        result.bound_start = None
        result.started_once = False
    if result.terminal_stop is target:
        result.terminal_stop = None


def _accept_context(result: FoldResult, observation: RecordObservation) -> None:
    record_type = observation.type
    url = observation.comment.url

    if record_type == "contract":
        result.active[record_type].append(observation)
        if result.started_once:
            _diagnose(result, "invalid_transition", url)
        elif len(result.active[record_type]) > 1:
            _diagnose(
                result,
                "conflicting_records",
                *(item.comment.url for item in result.active[record_type]),
            )
        return

    if record_type == "start":
        result.active[record_type].append(observation)
        if len(result.active[record_type]) > 1:
            _diagnose(
                result,
                "conflicting_records",
                *(item.comment.url for item in result.active[record_type]),
            )
            return
        contracts = result.active["contract"]
        if len(contracts) != 1:
            _diagnose(result, "invalid_transition", url, *(item.comment.url for item in contracts))
            return
        contract = contracts[0]
        if observation.record["contract_ref"] not in contract.alias_urls:
            _diagnose(result, "invalid_binding", url, observation.record["contract_ref"])
            return
        result.started_once = True
        result.bound_contract = contract
        result.bound_start = observation
        return

    if record_type == "done":
        result.active[record_type].append(observation)
        if len(result.active[record_type]) > 1:
            _diagnose(
                result,
                "conflicting_records",
                *(item.comment.url for item in result.active[record_type]),
            )
            return
        if not result.started_once or result.bound_contract is None:
            _diagnose(result, "invalid_transition", url)
            return
        expected = result.bound_contract.record["done_conditions"]
        actual = observation.record["evidence"]
        if set(expected) != set(actual):
            _diagnose(result, "invalid_evidence", url)
            return
        for condition_id, condition in expected.items():
            if parse_github_url(actual[condition_id], condition["evidence_kind"]) is None:
                _diagnose(result, "invalid_evidence", url, actual[condition_id])
                return
        return

    if record_type == "stop":
        result.active[record_type].append(observation)
        result.terminal_stop = observation


def successor_refs(comments: list[Comment]) -> list[str]:
    refs: list[str] = []
    for comment in comments:
        carrier = classify_carrier(comment.body)
        if comment.updated_at != comment.created_at or not carrier.schema_valid or carrier.record is None:
            continue
        record = carrier.record
        if record["type"] == "stop" and record["reason"] == "superseded":
            refs.append(record["successor_ref"])
    return list(dict.fromkeys(refs))


def fold_comments(comments: list[Comment], context: FoldContext | None = None) -> FoldResult:
    """Fold a complete, strictly ordered issue-comment snapshot without live I/O."""

    del context  # Live successor facts belong to the status adapter, not the pure fold.
    ids = [comment.id for comment in comments]
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise IncompleteSnapshotError("comment IDs must be strictly ascending and unique")

    result = FoldResult()
    for comment in comments:
        carrier = classify_carrier(comment.body)
        if not carrier.recognized:
            continue
        result.recognized_count += 1
        result.recognized_comments.append(comment)

        if comment.updated_at != comment.created_at or not carrier.schema_valid or carrier.record is None:
            if result.terminal_stop is not None:
                _diagnose(result, "terminal_violation", comment.url)
            else:
                _diagnose(result, "invalid_record", comment.url)
            continue

        observation = RecordObservation(carrier.record, comment)
        same_id = result.ids.get(observation.id, [])
        identical = next((item for item in same_id if item.record == observation.record), None)
        if identical is not None:
            identical.add_alias(comment)
            result.observations_by_url[comment.url] = identical
            continue

        if result.terminal_stop is not None:
            result.ids.setdefault(observation.id, []).append(observation)
            result.observations_by_url[comment.url] = observation
            _diagnose(result, "terminal_violation", comment.url)
            continue

        if same_id:
            members = [url for item in same_id for url in item.alias_urls] + [comment.url]
            for item in same_id:
                _remove_observation(result, item)
            result.ids[observation.id].append(observation)
            result.observations_by_url[comment.url] = observation
            _diagnose(result, "invalid_record", *members)
            continue

        result.ids.setdefault(observation.id, []).append(observation)
        result.observations_by_url[comment.url] = observation
        _accept_context(result, observation)

    return result


def historical_state(result: FoldResult) -> str:
    if result.recognized_count == 0:
        return "unmanaged"
    if result.terminal_stop is not None:
        if any(item.token == "terminal_violation" for item in result.diagnostics):
            return "halt"
        return "stopped"
    if result.diagnostics:
        return "halt"
    if not result.started_once and len(result.active["contract"]) == 1:
        return "ready"
    if result.started_once:
        return "in_progress"
    return "halt"
