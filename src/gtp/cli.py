"""GTP command-line interface."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from . import __version__
from .carrier import classify_carrier
from .github import GitHubClient
from .human_post import validate_human_post
from .presentation import present_check, present_human_check, present_input_error, present_status
from .status import evaluate_issue
def _emit(lines: list[str], value: object) -> None:
    for line in lines:
        sys.stdout.write(f"{line}\n")
    json.dump(value, sys.stdout, ensure_ascii=False, sort_keys=True, indent=2)
    sys.stdout.write("\n")
def _check(path: str, target: str) -> int:
    try:
        body = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        _emit(*present_input_error(str(error), target))
        return 2
    if target == "record":
        result = classify_carrier(body)
        _emit(*present_check(result))
        return 0 if result.recognized and result.schema_valid else 1
    result = validate_human_post(body, target)
    _emit(*present_human_check(result))
    return 0 if result.valid else 1
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gtp")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="validate one complete Markdown post")
    check.add_argument("comment", metavar="file")
    check.add_argument(
        "--target",
        choices=("record", "issue", "pr", "comment"),
        default="record",
    )
    status = subparsers.add_parser("status", help="reconstruct one GitHub Issue state")
    status.add_argument("issue_url")
    return parser
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check":
        return _check(args.comment, args.target)
    result = evaluate_issue(GitHubClient(), args.issue_url)
    _emit(*present_status(result))
    return 0 if result.state is not None else 2
