"""Server-ordered, prefix-local fold for the first GTP walking skeleton."""

from __future__ import annotations

from typing import Iterable

from .carrier import classify_carrier
from .model import Comment, Diagnostic, FoldResult, RecordObservation
from .urls import parse_github_url


def _append_unique(result: FoldResult, diagnostic: Diagnostic) -> None:
    if diagnostic not in result.diagnostics:
        result.diagnostics.append(diagnostic)


def _unsupported(result: FoldResult, urls: Iterable[str], feature: str) -> None:
    item = Diagnostic("unsupported_slice", tuple(urls), {"feature": feature})
    if item not in result.unsupported:
        result.unsupported.append(item)


def _active_urls(result: FoldResult, record_type: str) -> tuple[str, ...]:
    return tuple(item.comment.url for item in result.active[record_type])


def _validate_supersession(
    result: FoldResult, observation: RecordObservation
) -> list[RecordObservation] | None:
    urls = observation.record["supersedes"]
    if len(urls) > 2:
        _unsupported(result, urls + [observation.comment.url], "more_than_two_supersession_targets")
        return None
    targets: list[RecordObservation] = []
    for url in urls:
        parsed = parse_github_url(url, "comment")
        if parsed is None or url not in result.valid_by_url:
            if url in result.invalid_urls:
                _unsupported(result, [url, observation.comment.url], "invalid_carrier_repair")
            else:
                _append_unique(result, Diagnostic("invalid_supersession", (observation.comment.url, url)))
            return None
        target = result.valid_by_url[url]
        if target.comment.id >= observation.comment.id or target.type != observation.type:
            _append_unique(result, Diagnostic("invalid_supersession", (observation.comment.url, url)))
            return None
        targets.append(target)

    if len(urls) == 2:
        active_urls = set(_active_urls(result, observation.type))
        if observation.type != "contract" or set(urls) != active_urls or len(active_urls) != 2:
            _unsupported(result, urls + [observation.comment.url], "general_multiple_leaf_supersession")
            return None
    return targets


def _apply_supersession(result: FoldResult, targets: list[RecordObservation]) -> None:
    for target in targets:
        result.active[target.type] = [item for item in result.active[target.type] if item.id != target.id]


def _record_context(result: FoldResult, observation: RecordObservation) -> bool:
    record = observation.record
    record_type = observation.type
    if result.terminal_stop is not None:
        _append_unique(result, Diagnostic("terminal_violation", (observation.comment.url,)))
        return False
    targets = _validate_supersession(result, observation)
    if targets is None:
        return False

    if record_type == "contract":
        if result.started_once:
            _append_unique(result, Diagnostic("contract_freeze_violation", (observation.comment.url,)))
            return False
        _apply_supersession(result, targets)
        return True

    if record_type == "start":
        if result.started_once:
            _append_unique(result, Diagnostic("start_redefinition", (observation.comment.url,)))
            return False
        contracts = result.active["contract"]
        if len(contracts) != 1:
            urls = (observation.comment.url,) + tuple(item.comment.url for item in contracts)
            _append_unique(result, Diagnostic("start_contract_binding_failed", urls))
            return False
        result.started_once = True
        result.bound_contract = contracts[0]
        result.bound_start = observation
        _apply_supersession(result, targets)
        result.active["start"] = [observation]
        return False

    if record_type == "done":
        if not result.started_once or result.bound_contract is None:
            _append_unique(result, Diagnostic("done_before_start", (observation.comment.url,)))
            return False
        expected = set(result.bound_contract.record["done_conditions"])
        actual = set(record["evidence"])
        if expected != actual:
            _append_unique(result, Diagnostic("done_condition_keys_mismatch", (observation.comment.url,)))
            return False
        for condition_id, url in record["evidence"].items():
            kind = result.bound_contract.record["done_conditions"][condition_id]["evidence_kind"]
            if parse_github_url(url, kind) is None:
                _append_unique(result, Diagnostic("done_evidence_kind_mismatch", (observation.comment.url, url)))
                return False
        _apply_supersession(result, targets)
        return True

    if record_type == "stop":
        if not result.valid_by_url or not any(item.type == "contract" for item in result.valid_by_url.values()):
            _append_unique(result, Diagnostic("stop_without_contract", (observation.comment.url,)))
            return False
        if result.terminal_stop is not None:
            _append_unique(result, Diagnostic("terminal_violation", (observation.comment.url,)))
            return False
        if result.active["done"]:
            _unsupported(
                result,
                [result.active["done"][0].comment.url, observation.comment.url],
                "done_stop_terminal_ordering",
            )
        _apply_supersession(result, targets)
        result.terminal_stop = observation
        result.active["stop"] = [observation]
        return False
    return True


def fold_comments(comments: list[Comment]) -> FoldResult:
    result = FoldResult()
    ids = [comment.id for comment in comments]
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        _unsupported(result, [comment.url for comment in comments], "incomplete_or_unordered_comment_snapshot")
        return result

    for comment in comments:
        carrier = classify_carrier(comment.body)
        if not carrier.recognized:
            continue
        result.recognized_count += 1
        if comment.updated_at != comment.created_at:
            _unsupported(result, [comment.url], "edited_carrier")
            continue
        if not carrier.schema_valid or carrier.record is None:
            result.invalid_urls.add(comment.url)
            _append_unique(result, Diagnostic("invalid_record", (comment.url,)))
            continue

        observation = RecordObservation(carrier.record, comment)
        prior_same_id = result.ids.get(observation.id, [])
        if prior_same_id:
            if any(item.record == observation.record for item in prior_same_id):
                _unsupported(result, [item.comment.url for item in prior_same_id] + [comment.url], "api_retry_alias")
            else:
                urls = tuple(item.comment.url for item in prior_same_id) + (comment.url,)
                _append_unique(result, Diagnostic("identity_collision", urls))
            result.ids.setdefault(observation.id, []).append(observation)
            continue
        result.ids.setdefault(observation.id, []).append(observation)
        active_record = _record_context(result, observation)
        accepted = (
            active_record
            or result.bound_start is observation
            or result.terminal_stop is observation
        )
        if accepted:
            result.valid_by_url[comment.url] = observation
        if active_record:
            result.active[observation.type].append(observation)
            if len(result.active[observation.type]) > 2:
                _unsupported(result, _active_urls(result, observation.type), "more_than_two_active_leaves")

    for record_type, records in result.active.items():
        if record_type != "stop" and len(records) > 1:
            _append_unique(result, Diagnostic("conflicting_records", tuple(item.comment.url for item in records)))
    return result


def historical_state(result: FoldResult) -> str | None:
    if result.unsupported:
        return None
    if result.recognized_count == 0:
        return "unmanaged"
    if result.terminal_stop is not None:
        return "stopped"
    if result.diagnostics:
        return "halt"
    if not result.started_once and len(result.active["contract"]) == 1:
        return "ready"
    if result.started_once:
        return "in_progress"
    return "halt"
