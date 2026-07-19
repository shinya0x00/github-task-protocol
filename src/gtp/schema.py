"""Strict JSON parsing and closed GTP v1 Record validation."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any
from urllib.parse import urlsplit

from .urls import parse_github_url


UUID_V4 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
CONDITION_ID = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class DuplicateKeyError(ValueError):
    def __init__(self, key: str):
        super().__init__(f"duplicate key: {key}")
        self.key = key


def _pairs_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def strict_json_loads(source: str) -> tuple[Any | None, list[dict[str, str]]]:
    try:
        value = json.loads(
            source,
            object_pairs_hook=_pairs_object,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
    except DuplicateKeyError as error:
        return None, [{"code": "duplicate_key", "path": f"$.{error.key}"}]
    except (json.JSONDecodeError, ValueError) as error:
        return None, [{"code": "invalid_json", "path": "$", "message": str(error)}]
    return value, []


def _error(errors: list[dict[str, str]], code: str, path: str, message: str | None = None) -> None:
    item = {"code": code, "path": path}
    if message:
        item["message"] = message
    errors.append(item)


def _closed_object(
    value: object,
    path: str,
    allowed: set[str],
    required: set[str],
    errors: list[dict[str, str]],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        _error(errors, "invalid_type", path, "expected object")
        return None
    for field in sorted(set(value) - allowed):
        _error(errors, "unknown_field", f"{path}.{field}")
    for field in sorted(required - set(value)):
        _error(errors, "missing_field", f"{path}.{field}")
    return value


def _clean_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and not any(unicodedata.category(char) == "Cc" for char in value)
    )


def _scope_path_valid(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or value.startswith("/")
        or any(character in value for character in "*?[]")
    ):
        return False
    if value == ".":
        return True
    directory = value.endswith("/")
    core = value[:-1] if directory else value
    segments = core.split("/")
    return bool(core) and all(segment and segment not in {".", ".."} for segment in segments)


def _validate_envelope(record: dict[str, Any], errors: list[dict[str, str]]) -> None:
    if record.get("gtp") != "1.0":
        _error(errors, "invalid_value", "$.gtp")
    if record.get("type") not in {"contract", "start", "done", "stop"}:
        _error(errors, "invalid_value", "$.type")
    if not isinstance(record.get("id"), str) or not UUID_V4.fullmatch(record["id"]):
        _error(errors, "invalid_value", "$.id")
    supersedes = record.get("supersedes")
    if not isinstance(supersedes, list):
        _error(errors, "invalid_type", "$.supersedes", "expected array")
    else:
        seen: set[str] = set()
        for index, url in enumerate(supersedes):
            path = f"$.supersedes[{index}]"
            if parse_github_url(url, "comment") is None:
                _error(errors, "invalid_url", path)
            elif url in seen:
                _error(errors, "duplicate_value", path)
            else:
                seen.add(url)


def _validate_contract(record: dict[str, Any], errors: list[dict[str, str]]) -> None:
    if not _clean_text(record.get("goal")):
        _error(errors, "invalid_value", "$.goal")
    scope = record.get("scope")
    if not isinstance(scope, list) or not scope:
        _error(errors, "invalid_type", "$.scope", "expected non-empty array")
    else:
        seen: set[str] = set()
        for index, item in enumerate(scope):
            path = f"$.scope[{index}]"
            if not _scope_path_valid(item):
                _error(errors, "invalid_value", path)
            elif item in seen:
                _error(errors, "duplicate_value", path)
            else:
                seen.add(item)
    conditions = record.get("done_conditions")
    if not isinstance(conditions, dict) or not conditions:
        _error(errors, "invalid_type", "$.done_conditions", "expected non-empty object")
        return
    for condition_id, condition in conditions.items():
        base = f"$.done_conditions.{condition_id}"
        if not CONDITION_ID.fullmatch(condition_id):
            _error(errors, "invalid_condition_id", base)
        item = _closed_object(condition, base, {"text", "evidence_kind"}, {"text", "evidence_kind"}, errors)
        if item is None:
            continue
        if not _clean_text(item.get("text")):
            _error(errors, "invalid_value", f"{base}.text")
        if item.get("evidence_kind") not in {"check", "artifact"}:
            _error(errors, "invalid_value", f"{base}.evidence_kind")


def _validate_start(record: dict[str, Any], errors: list[dict[str, str]]) -> None:
    branch = record.get("branch")
    parsed = urlsplit(branch) if isinstance(branch, str) else None
    if (
        not _clean_text(branch)
        or branch.startswith("refs/heads/")
        or (parsed is not None and (parsed.scheme or parsed.netloc))
    ):
        _error(errors, "invalid_value", "$.branch")


def _validate_done(record: dict[str, Any], errors: list[dict[str, str]]) -> None:
    if parse_github_url(record.get("pr_ref"), "pr") is None:
        _error(errors, "invalid_url", "$.pr_ref")
    head_sha = record.get("head_sha")
    if not isinstance(head_sha, str) or not FULL_SHA.fullmatch(head_sha):
        _error(errors, "invalid_value", "$.head_sha")
    evidence = record.get("evidence")
    if not isinstance(evidence, dict) or not evidence:
        _error(errors, "invalid_type", "$.evidence", "expected non-empty object")
        return
    for condition_id, url in evidence.items():
        path = f"$.evidence.{condition_id}"
        if not CONDITION_ID.fullmatch(condition_id):
            _error(errors, "invalid_condition_id", path)
        if parse_github_url(url, "check") is None and parse_github_url(url, "artifact") is None:
            _error(errors, "invalid_url", path)


def _validate_stop(record: dict[str, Any], errors: list[dict[str, str]]) -> None:
    reason = record.get("reason")
    successor = record.get("successor_ref")
    if reason == "abandoned":
        if successor is not None:
            _error(errors, "invalid_value", "$.successor_ref")
    elif reason == "superseded":
        if parse_github_url(successor, "issue") is None:
            _error(errors, "invalid_url", "$.successor_ref")
    else:
        _error(errors, "invalid_value", "$.reason")


_FIELDS = {
    "contract": {"gtp", "type", "id", "supersedes", "goal", "scope", "done_conditions"},
    "start": {"gtp", "type", "id", "supersedes", "branch"},
    "done": {"gtp", "type", "id", "supersedes", "pr_ref", "head_sha", "evidence"},
    "stop": {"gtp", "type", "id", "supersedes", "reason", "successor_ref"},
}


def validate_record(value: object) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(value, dict):
        return [{"code": "invalid_type", "path": "$", "message": "expected object"}]
    record_type = value.get("type")
    allowed = _FIELDS.get(record_type, {"gtp", "type", "id", "supersedes"})
    record = _closed_object(value, "$", allowed, allowed, errors)
    if record is None:
        return errors
    _validate_envelope(record, errors)
    if record_type == "contract":
        _validate_contract(record, errors)
    elif record_type == "start":
        _validate_start(record, errors)
    elif record_type == "done":
        _validate_done(record, errors)
    elif record_type == "stop":
        _validate_stop(record, errors)
    return errors
