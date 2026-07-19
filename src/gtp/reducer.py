"""Intrinsic prepass and Server Order incremental prefix fold."""

from __future__ import annotations

from .carrier import classify_carrier
from .model import (
    Comment,
    ContextAcquisitionRequired,
    Diagnostic,
    DoneWindow,
    FoldContext,
    FoldResult,
    RecordObservation,
    RepairGroup,
    IncompleteSnapshotError,
)
from .urls import parse_github_url


REPAIRABLE_CONTEXT = {
    "invalid_supersession",
    "incomplete_repair_group",
    "start_contract_binding_failed",
    "done_before_start",
    "done_condition_keys_mismatch",
    "done_evidence_kind_mismatch",
    "stop_without_contract",
    "successor_order_invalid",
}


def _append_unique(result: FoldResult, diagnostic: Diagnostic) -> None:
    if diagnostic not in result.diagnostics:
        result.diagnostics.append(diagnostic)


def _set_group_diagnostic(
    result: FoldResult, group: RepairGroup, urls: tuple[str, ...]
) -> None:
    anchor = group.urls[0]
    result.diagnostics = [
        item
        for item in result.diagnostics
        if not (item.token == group.token and item.urls and item.urls[0] == anchor)
    ]
    _append_unique(result, Diagnostic(group.token, urls))


def _new_group(result: FoldResult, token: str, urls: list[str]) -> RepairGroup:
    group = RepairGroup(token, list(dict.fromkeys(urls)))
    result.repair_groups.append(group)
    for url in group.urls:
        result.invalid_urls.add(url)
    _append_unique(result, Diagnostic(token, tuple(group.urls)))
    return group


def _group_for_url(result: FoldResult, url: str) -> RepairGroup | None:
    for group in result.repair_groups:
        if not group.resolved and url in group.urls:
            return group
    return None


def _resolve_group(result: FoldResult, group: RepairGroup) -> None:
    group.resolved = True
    for url in group.urls:
        result.invalid_urls.discard(url)
    anchor = group.urls[0]
    result.diagnostics = [
        item
        for item in result.diagnostics
        if not (item.token == group.token and item.urls and item.urls[0] == anchor)
    ]


def _close_done_window(result: FoldResult, at: str) -> None:
    if result.open_done_window is not None:
        result.open_done_window.ended_at = at
        result.open_done_window = None


def _refresh_done_window(
    result: FoldResult, before: tuple[int, ...], after: tuple[int, ...], at: str
) -> None:
    if before == after:
        return
    _close_done_window(result, at)
    if len(after) == 1:
        observation = result.active["done"][0]
        window = DoneWindow(observation, at)
        result.done_windows.append(window)
        result.open_done_window = window


def _remove_active(result: FoldResult, target: RecordObservation) -> None:
    target.superseded = True
    result.active[target.type] = [item for item in result.active[target.type] if item is not target]


def _context_invalid(
    result: FoldResult, observation: RecordObservation, token: str, extra_urls: tuple[str, ...] = ()
) -> None:
    urls = (observation.comment.url, *extra_urls)
    group = _new_group(result, token, list(urls[:1]))
    if extra_urls:
        _set_group_diagnostic(result, group, urls)


def _validate_supersession(
    result: FoldResult, observation: RecordObservation, fresh_id: bool
) -> tuple[list[RecordObservation], list[RepairGroup]] | None:
    urls = observation.record["supersedes"]
    targets: list[RecordObservation] = []
    groups: list[RepairGroup] = []
    referenced = set(urls)
    for url in urls:
        group = _group_for_url(result, url)
        if group is not None:
            if group not in groups:
                groups.append(group)
            continue
        target = result.valid_by_url.get(url)
        if target is None or target.comment.id >= observation.comment.id or target.type != observation.type:
            _context_invalid(result, observation, "invalid_supersession", (url,))
            return None
        if target not in targets:
            targets.append(target)

    for group in groups:
        required = {
            url
            for url in group.urls
            if (item := result.observations_by_url.get(url)) is None
            or item.comment.id < observation.comment.id
        }
        if not fresh_id or not required.issubset(referenced):
            _context_invalid(
                result,
                observation,
                "incomplete_repair_group",
                tuple(sorted(required - referenced)),
            )
            return None
    return targets, groups


def _apply_supersession(
    result: FoldResult,
    observation: RecordObservation,
    targets: list[RecordObservation],
    groups: list[RepairGroup],
) -> None:
    before_done = tuple(id(item) for item in result.active["done"])
    for target in targets:
        _remove_active(result, target)
    for group in groups:
        for url in group.urls:
            target = result.observations_by_url.get(url)
            if target is not None:
                _remove_active(result, target)
        _resolve_group(result, group)
    after_done = tuple(id(item) for item in result.active["done"])
    _refresh_done_window(result, before_done, after_done, observation.comment.created_at)


def _accept_record(result: FoldResult, observation: RecordObservation) -> None:
    result.valid_by_url[observation.comment.url] = observation
    result.observations_by_url[observation.comment.url] = observation


def _record_context(
    result: FoldResult,
    observation: RecordObservation,
    fresh_id: bool,
    context: FoldContext,
) -> bool:
    record = observation.record
    record_type = observation.type
    if result.terminal_stop is not None:
        _append_unique(result, Diagnostic("terminal_violation", (observation.comment.url,)))
        return False

    if record_type == "contract" and result.started_once:
        _append_unique(result, Diagnostic("contract_freeze_violation", (observation.comment.url,)))
        return False
    if record_type == "start" and result.started_once:
        _append_unique(result, Diagnostic("start_redefinition", (observation.comment.url,)))
        return False

    checked = _validate_supersession(result, observation, fresh_id)
    if checked is None:
        return False
    targets, groups = checked

    if record_type == "contract":
        _apply_supersession(result, observation, targets, groups)
        result.had_valid_contract = True
        return True

    if record_type == "start":
        contracts = result.active["contract"]
        if len(contracts) != 1:
            _context_invalid(
                result,
                observation,
                "start_contract_binding_failed",
                tuple(item.comment.url for item in contracts),
            )
            return False
        _apply_supersession(result, observation, targets, groups)
        result.started_once = True
        result.bound_contract = contracts[0]
        result.bound_start = observation
        result.active["start"] = [observation]
        return False

    if record_type == "done":
        if not result.started_once or result.bound_contract is None:
            _context_invalid(result, observation, "done_before_start")
            return False
        expected = set(result.bound_contract.record["done_conditions"])
        actual = set(record["evidence"])
        if expected != actual:
            _context_invalid(result, observation, "done_condition_keys_mismatch")
            return False
        for condition_id, url in record["evidence"].items():
            kind = result.bound_contract.record["done_conditions"][condition_id]["evidence_kind"]
            if parse_github_url(url, kind) is None:
                _context_invalid(result, observation, "done_evidence_kind_mismatch", (url,))
                return False
        before = tuple(id(item) for item in result.active["done"])
        _apply_supersession(result, observation, targets, groups)
        result.active["done"].append(observation)
        after = tuple(id(item) for item in result.active["done"])
        _refresh_done_window(result, before, after, observation.comment.created_at)
        return False

    if record_type == "stop":
        if not result.had_valid_contract:
            _context_invalid(result, observation, "stop_without_contract")
            return False
        if record["reason"] == "superseded":
            url = record["successor_ref"]
            fact = context.successors.get(url)
            if fact is None:
                raise ContextAcquisitionRequired(url)
            if fact.exists and (
                fact.issue_id == context.issue_id
                or context.issue_created_at is None
                or fact.created_at is None
                or not (context.issue_created_at < fact.created_at <= observation.comment.created_at)
            ):
                _context_invalid(result, observation, "successor_order_invalid", (url,))
                return False
        _apply_supersession(result, observation, targets, groups)
        _close_done_window(result, observation.comment.created_at)
        result.terminal_stop = observation
        result.active["stop"] = [observation]
        return False
    return True


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
    context = context or FoldContext()
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
        if comment.updated_at != comment.created_at:
            _new_group(result, "edited_carrier", [comment.url])
            continue
        if not carrier.schema_valid or carrier.record is None:
            _new_group(result, "invalid_record", [comment.url])
            continue

        observation = RecordObservation(carrier.record, comment)
        result.observations_by_url[comment.url] = observation
        same_id = result.ids.get(observation.id, [])
        identical = next((item for item in same_id if item.record == observation.record), None)
        if identical is not None:
            identical.add_alias(comment)
            result.observations_by_url[comment.url] = identical
            collision = next(
                (group for group in result.repair_groups if group.token == "identity_collision" and any(url in group.urls for url in identical.alias_urls)),
                None,
            )
            if collision is not None and not collision.resolved:
                collision.urls.append(comment.url)
                result.invalid_urls.add(comment.url)
                _set_group_diagnostic(result, collision, tuple(collision.urls))
            elif identical.comment.url in result.valid_by_url:
                result.valid_by_url[comment.url] = identical
            continue

        if same_id:
            members = [url for item in same_id for url in item.alias_urls] + [comment.url]
            group = next(
                (item for item in result.repair_groups if item.token == "identity_collision" and not item.resolved and set(item.urls) & set(members)),
                None,
            )
            if group is None:
                group = _new_group(result, "identity_collision", members)
            else:
                for url in members:
                    if url not in group.urls:
                        group.urls.append(url)
                _set_group_diagnostic(result, group, tuple(group.urls))
            before = tuple(id(item) for item in result.active["done"])
            for item in same_id:
                _remove_active(result, item)
                for url in item.alias_urls:
                    result.invalid_urls.add(url)
                    result.valid_by_url.pop(url, None)
            result.invalid_urls.add(comment.url)
            after = tuple(id(item) for item in result.active["done"])
            _refresh_done_window(result, before, after, comment.created_at)
            result.ids.setdefault(observation.id, []).append(observation)
            continue

        result.ids.setdefault(observation.id, []).append(observation)
        accepted_active = _record_context(result, observation, True, context)
        accepted = (
            accepted_active
            or result.bound_start is observation
            or result.terminal_stop is observation
            or any(observation is item for items in result.active.values() for item in items)
        )
        if accepted:
            _accept_record(result, observation)
        if accepted_active:
            result.active[observation.type].append(observation)

    for record_type, records in result.active.items():
        if record_type != "stop" and len(records) > 1:
            _append_unique(
                result,
                Diagnostic("conflicting_records", tuple(item.comment.url for item in records)),
            )
    return result


def historical_state(result: FoldResult) -> str:
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
