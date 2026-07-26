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
def effective_revision(result: FoldResult) -> RecordObservation | None:
    return result.active["amendment"][-1] if result.active["amendment"] else result.bound_contract
def effective_conditions(result: FoldResult) -> dict[str, dict[str, str]]:
    return conditions_at_revision(result, effective_revision(result))
def conditions_at_revision(result: FoldResult, revision: RecordObservation | None) -> dict[str, dict[str, str]]:
    conditions = dict(result.bound_contract.record["done_conditions"]) if result.bound_contract else {}
    for amendment in result.active["amendment"]:
        if revision is result.bound_contract:
            break
        conditions.update(amendment.record["done_conditions"])
        if amendment is revision:
            break
    return conditions
def current_done(result: FoldResult) -> RecordObservation | None:
    done = result.active["done"]
    return done[-1] if result.protocol_11_seen and done else done[0] if len(done) == 1 else None
def revision_for_done(result: FoldResult, done: RecordObservation) -> RecordObservation | None:
    if done.record["gtp"] == "1.0":
        return result.bound_contract
    return result.observations_by_url.get(done.record["revision_ref"])
def _expect_ref(result: FoldResult, observation: RecordObservation, field: str,
                expected: RecordObservation) -> bool:
    ref = observation.record[field]
    if ref in expected.alias_urls:
        return True
    target = result.observations_by_url.get(ref)
    urls = (observation.comment.url, ref) if isinstance(ref, str) else (observation.comment.url,)
    _diagnose(result, "invalid_transition" if target is not None else "invalid_binding", *urls)
    return False
def _evidence_matches(result: FoldResult, observation: RecordObservation) -> bool:
    expected = effective_conditions(result)
    actual = observation.record["evidence"]
    if set(expected) != set(actual):
        _diagnose(result, "invalid_evidence", observation.comment.url)
        return False
    for condition_id, condition in expected.items():
        if parse_github_url(actual[condition_id], condition["evidence_kind"]) is None:
            _diagnose(result, "invalid_evidence", observation.comment.url, actual[condition_id])
            return False
    return True
def _accept_context(result: FoldResult, observation: RecordObservation) -> None:
    record_type = observation.type
    url = observation.comment.url
    if result.protocol_11_seen and observation.record["gtp"] == "1.0":
        _diagnose(result, "invalid_transition", url)
        return
    prior_10 = any(
        item is not observation and item.record["gtp"] == "1.0"
        for members in result.ids.values() for item in members
    )
    if observation.record["gtp"] == "1.1" and not result.protocol_11_seen and prior_10 and record_type not in {"amendment", "done"}:
        _diagnose(result, "invalid_transition", url)
        return
    if observation.record["gtp"] == "1.1":
        result.protocol_11_seen = True
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
    if record_type == "amendment":
        if not result.started_once or result.bound_contract is None:
            _diagnose(result, "invalid_transition", url)
            return
        revision = effective_revision(result)
        assert revision is not None
        if not _expect_ref(result, observation, "predecessor_ref", revision):
            return
        if set(observation.record["done_conditions"]) & set(effective_conditions(result)):
            _diagnose(result, "invalid_transition", url)
            return
        result.active[record_type].append(observation)
        return
    if record_type == "done" and observation.record["gtp"] == "1.0":
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
        _evidence_matches(result, observation)
        return
    if record_type == "done":
        if not result.started_once or result.bound_contract is None:
            _diagnose(result, "invalid_transition", url)
            return
        revision = effective_revision(result)
        assert revision is not None
        if not _expect_ref(result, observation, "revision_ref", revision):
            return
        prior = current_done(result)
        previous_ref = observation.record["previous_done_ref"]
        if prior is None and previous_ref is not None:
            _diagnose(result, "invalid_transition", url, previous_ref)
            return
        if prior is not None:
            if not _expect_ref(result, observation, "previous_done_ref", prior):
                return
            if observation.record["pr_ref"] != prior.record["pr_ref"]:
                _diagnose(result, "invalid_binding", url, observation.record["pr_ref"])
                return
        if _evidence_matches(result, observation):
            result.active[record_type].append(observation)
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
            if carrier.observed_gtp == "1.1":
                result.protocol_11_seen = True
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
            if result.protocol_11_seen or observation.record["gtp"] == "1.1":
                result.protocol_11_seen = True
            else:
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
