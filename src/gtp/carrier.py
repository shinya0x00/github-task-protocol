"""Exact GTP Carrier classifier shared by check and status."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata
from typing import Any

from .schema import strict_json_loads, validate_record


MARKER = "<!-- gtp-record:v1 -->"


@dataclass(frozen=True)
class CarrierResult:
    recognized: bool
    schema_valid: bool | None
    record: dict[str, Any] | None
    errors: list[dict[str, str]]

    def projection(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "recognized": self.recognized,
            "schema_valid": self.schema_valid,
            "contextual_checks": "not_run",
        }
        if self.errors:
            result["errors"] = self.errors
        return result


def _blank(line: str) -> bool:
    return not line.strip()


def classify_carrier(body: str) -> CarrierResult:
    lines = body.split("\n")
    recognized = any(line == MARKER for line in lines)
    if not recognized:
        return CarrierResult(False, None, None, [])

    nonblank = [index for index, line in enumerate(lines) if not _blank(line)]
    format_errors: list[dict[str, str]] = []
    if len(nonblank) < 4:
        format_errors.append({"code": "invalid_carrier", "path": "$"})
        return CarrierResult(True, False, None, format_errors)

    summary_index, marker_index = nonblank[0], nonblank[1]
    summary = lines[summary_index]
    if summary != summary.strip() or any(unicodedata.category(char) == "Cc" for char in summary):
        format_errors.append({"code": "invalid_summary", "path": "$.summary"})
    if lines[marker_index] != MARKER:
        format_errors.append({"code": "invalid_marker_position", "path": "$.marker"})

    opening_candidates = [index for index in nonblank[2:] if lines[index] == "```json"]
    closing_candidates = [index for index in nonblank[2:] if lines[index] == "```"]
    if len(opening_candidates) != 1 or len(closing_candidates) != 1:
        format_errors.append({"code": "invalid_json_fence", "path": "$.fence"})
        return CarrierResult(True, False, None, format_errors)
    opening, closing = opening_candidates[0], closing_candidates[0]
    if opening <= marker_index or closing <= opening or nonblank[-1] != closing:
        format_errors.append({"code": "invalid_carrier_layout", "path": "$"})
        return CarrierResult(True, False, None, format_errors)
    if any(index not in {summary_index, marker_index, opening, closing} for index in nonblank if index < opening):
        format_errors.append({"code": "unexpected_prose", "path": "$"})
    if format_errors:
        return CarrierResult(True, False, None, format_errors)

    value, parse_errors = strict_json_loads("\n".join(lines[opening + 1 : closing]))
    if parse_errors:
        return CarrierResult(True, False, None, parse_errors)
    schema_errors = validate_record(value)
    if schema_errors:
        return CarrierResult(True, False, None, schema_errors)
    return CarrierResult(True, True, value, [])
