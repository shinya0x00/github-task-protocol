"""Exact GTP Carrier classifier shared by check and status."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata
from typing import Any

from .schema import strict_json_loads, validate_record


MARKER = "<!-- gtp-record:v1 -->"
DETAILS_OPEN = "<details><summary>記録(JSON)</summary>"
DETAILS_CLOSE = "</details>"
JSON_OPEN = "```json"
JSON_CLOSE = "```"


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
    if len(nonblank) < 7:
        format_errors.append({"code": "invalid_carrier", "path": "$"})
        return CarrierResult(True, False, None, format_errors)

    marker_index, summary_index = nonblank[0], nonblank[1]
    summary = lines[summary_index]
    if (
        not summary
        or summary != summary.strip()
        or any(unicodedata.category(char) == "Cc" for char in summary)
    ):
        format_errors.append({"code": "invalid_summary", "path": "$.summary"})
    if lines[marker_index] != MARKER:
        format_errors.append({"code": "invalid_marker_position", "path": "$.marker"})

    details_open_candidates = [index for index in nonblank if lines[index] == DETAILS_OPEN]
    details_close_candidates = [index for index in nonblank if lines[index] == DETAILS_CLOSE]
    if len(details_open_candidates) != 1 or len(details_close_candidates) != 1:
        format_errors.append({"code": "invalid_details_wrapper", "path": "$.details"})
        return CarrierResult(True, False, None, format_errors)

    opening_candidates = [index for index in nonblank if lines[index] == JSON_OPEN]
    closing_candidates = [index for index in nonblank if lines[index] == JSON_CLOSE]
    if len(opening_candidates) != 1 or len(closing_candidates) != 1:
        format_errors.append({"code": "invalid_json_fence", "path": "$.fence"})
        return CarrierResult(True, False, None, format_errors)

    details_open = details_open_candidates[0]
    details_close = details_close_candidates[0]
    opening = opening_candidates[0]
    closing = closing_candidates[0]
    expected_prefix = [marker_index, summary_index, details_open, opening]
    expected_suffix = [closing, details_close]
    if (
        nonblank[:4] != expected_prefix
        or nonblank[-2:] != expected_suffix
        or not (marker_index < summary_index < details_open < opening < closing < details_close)
    ):
        format_errors.append({"code": "invalid_carrier_layout", "path": "$"})
        return CarrierResult(True, False, None, format_errors)

    required_spacing = (
        summary_index == marker_index + 1
        and details_open == summary_index + 2
        and opening == details_open + 2
        and details_close == closing + 2
    )
    if not required_spacing:
        format_errors.append({"code": "invalid_carrier_spacing", "path": "$"})
    if format_errors:
        return CarrierResult(True, False, None, format_errors)

    value, parse_errors = strict_json_loads("\n".join(lines[opening + 1 : closing]))
    if parse_errors:
        return CarrierResult(True, False, None, parse_errors)
    schema_errors = validate_record(value)
    if schema_errors:
        return CarrierResult(True, False, None, schema_errors)
    return CarrierResult(True, True, value, [])
