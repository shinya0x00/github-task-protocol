"""GTP command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .carrier import classify_carrier
from .github import GitHubClient
from .status import evaluate_issue


def _emit(value: object) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False, sort_keys=True, indent=2)
    sys.stdout.write("\n")


def _check(path: str) -> int:
    try:
        body = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        _emit({"error": {"code": "input_error", "message": str(error)}})
        return 2
    result = classify_carrier(body)
    _emit(result.projection())
    return 0 if result.recognized and result.schema_valid else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gtp")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="validate one complete Markdown comment")
    check.add_argument("comment")
    status = subparsers.add_parser("status", help="reconstruct one GitHub Issue state")
    status.add_argument("issue_url")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check":
        return _check(args.comment)
    result = evaluate_issue(GitHubClient(), args.issue_url)
    _emit(result.projection())
    return 0 if result.state is not None else 2
