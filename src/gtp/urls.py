"""Canonical GitHub URL profiles used by GTP v1."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import unquote_to_bytes, urlsplit


_DECIMAL = r"[1-9][0-9]*"
_SHA = r"[0-9a-f]{40}"
_RESOURCE_PATTERNS = {
    "issue": re.compile(rf"^/([^/]+)/([^/]+)/issues/({_DECIMAL})$"),
    "pr": re.compile(rf"^/([^/]+)/([^/]+)/pull/({_DECIMAL})$"),
    "check": re.compile(rf"^/([^/]+)/([^/]+)/runs/({_DECIMAL})$"),
    "artifact": re.compile(rf"^/([^/]+)/([^/]+)/blob/({_SHA})/(.+)$"),
}
_COMMENT_PATTERN = re.compile(rf"^/([^/]+)/([^/]+)/issues/({_DECIMAL})$")
_COMMENT_FRAGMENT = re.compile(rf"^issuecomment-({_DECIMAL})$")


@dataclass(frozen=True)
class GitHubUrl:
    kind: str
    owner: str
    repo: str
    number: int | None = None
    sha: str | None = None
    path: str | None = None


def _literal_segment(value: str) -> bool:
    return bool(value) and value not in {".", ".."} and not any(
        char in value for char in ("%", "/", "\\", "\x00")
    )


def _artifact_path_valid(raw_path: str) -> bool:
    if not raw_path or "\\" in raw_path or "\x00" in raw_path:
        return False
    for raw_segment in raw_path.split("/"):
        if not raw_segment:
            return False
        if re.search(r"%(?![0-9A-Fa-f]{2})", raw_segment):
            return False
        try:
            decoded = unquote_to_bytes(raw_segment).decode("utf-8", errors="strict")
        except UnicodeError:
            return False
        if decoded in {".", ".."} or "/" in decoded or "\\" in decoded or "\x00" in decoded:
            return False
    return True


def parse_github_url(value: object, expected: str | None = None) -> GitHubUrl | None:
    if not isinstance(value, str):
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if (
        parts.scheme != "https"
        or parts.hostname != "github.com"
        or parts.username is not None
        or parts.password is not None
        or parts.port is not None
        or parts.query
    ):
        return None

    if expected == "comment" or (expected is None and parts.fragment):
        match = _COMMENT_PATTERN.fullmatch(parts.path)
        fragment = _COMMENT_FRAGMENT.fullmatch(parts.fragment)
        if not match or not fragment:
            return None
        owner, repo, issue_number = match.groups()
        if not _literal_segment(owner) or not _literal_segment(repo):
            return None
        return GitHubUrl("comment", owner, repo, int(issue_number), path=fragment.group(1))

    if parts.fragment:
        return None
    kinds = [expected] if expected else list(_RESOURCE_PATTERNS)
    for kind in kinds:
        if kind not in _RESOURCE_PATTERNS:
            continue
        match = _RESOURCE_PATTERNS[kind].fullmatch(parts.path)
        if not match:
            continue
        owner, repo, third, *rest = match.groups()
        if not _literal_segment(owner) or not _literal_segment(repo):
            return None
        if kind == "artifact":
            artifact_path = rest[0]
            if not _artifact_path_valid(artifact_path):
                return None
            return GitHubUrl(kind, owner, repo, sha=third, path=artifact_path)
        return GitHubUrl(kind, owner, repo, number=int(third))
    return None
