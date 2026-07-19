"""Read-only GitHub REST adapter for GTP status."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .model import Comment


class AcquisitionError(RuntimeError):
    def __init__(self, resource: str, message: str, status: int | None = None):
        super().__init__(message)
        self.resource = resource
        self.status = status


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(url)
    return parsed.scheme, parsed.hostname or "", parsed.port


def _validate_api_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
    except ValueError as error:
        raise AcquisitionError(url, "invalid GitHub API URL") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.github.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.fragment
    ):
        raise AcquisitionError(url, "GitHub API host is not allowed")


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(request, fp, code, msg, headers, newurl)
        if redirected is not None and _origin(request.full_url) != _origin(newurl):
            redirected.remove_header("Authorization")
            redirected.unredirected_hdrs.pop("Authorization", None)
        return redirected


_OPENER = build_opener(_SafeRedirectHandler())


def _open(request: Request, timeout: int):
    return _OPENER.open(request, timeout=timeout)


class GitHubClient:
    api_root = "https://api.github.com"

    def __init__(self, token: str | None = None) -> None:
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    def _request(self, url: str) -> tuple[Any, dict[str, str]]:
        _validate_api_url(url)
        headers = {
            "Accept": "application/vnd.github+json",
            "Cache-Control": "no-cache",
            "User-Agent": "github-task-protocol/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers, method="GET")
        try:
            with _open(request, timeout=30) as response:
                final_url = response.geturl()
                if isinstance(final_url, str):
                    _validate_api_url(final_url)
                data = json.loads(response.read().decode("utf-8"))
                return data, {key.lower(): value for key, value in response.headers.items()}
        except HTTPError as error:
            raise AcquisitionError(url, f"GitHub API returned HTTP {error.code}", error.code) from error
        except (URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as error:
            raise AcquisitionError(url, str(error)) from error

    def _get(self, path: str, query: dict[str, str] | None = None) -> Any:
        url = f"{self.api_root}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        return self._request(url)[0]

    def _pages(self, path: str, query: dict[str, str] | None = None) -> list[Any]:
        url = f"{self.api_root}{path}"
        params = dict(query or {})
        params.setdefault("per_page", "100")
        url = f"{url}?{urlencode(params)}"
        values: list[Any] = []
        while url:
            data, headers = self._request(url)
            if not isinstance(data, list):
                raise AcquisitionError(url, "expected a JSON array")
            values.extend(data)
            url = _next_link(headers.get("link", ""))
        return values

    def repository(self, owner: str, repo: str) -> dict[str, Any]:
        resource = self._get(f"/repos/{quote(owner)}/{quote(repo)}")
        if not isinstance(resource, dict) or not isinstance(resource.get("id"), int):
            raise AcquisitionError(
                f"{self.api_root}/repos/{quote(owner)}/{quote(repo)}",
                "repository identity missing",
            )
        return resource

    def issue(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        resource = self._get(f"/repos/{quote(owner)}/{quote(repo)}/issues/{number}")
        if (
            not isinstance(resource, dict)
            or not isinstance(resource.get("id"), int)
            or not isinstance(resource.get("created_at"), str)
            or not isinstance(resource.get("updated_at"), str)
        ):
            raise AcquisitionError(
                f"{self.api_root}/repos/{quote(owner)}/{quote(repo)}/issues/{number}",
                "issue snapshot fields missing",
            )
        return resource

    def comments(self, owner: str, repo: str, number: int) -> list[Comment]:
        data = self._pages(
            f"/repos/{quote(owner)}/{quote(repo)}/issues/{number}/comments",
            {"sort": "created", "direction": "asc"},
        )
        comments: list[Comment] = []
        for item in data:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("id"), int)
                or not isinstance(item.get("html_url"), str)
                or not isinstance(item.get("created_at"), str)
                or not isinstance(item.get("updated_at"), str)
                or not isinstance(item.get("user"), dict)
                or not isinstance(item["user"].get("login"), str)
            ):
                raise AcquisitionError(
                    f"{self.api_root}/repos/{quote(owner)}/{quote(repo)}/issues/{number}/comments",
                    "comment snapshot entry is incomplete",
                )
            body = item.get("body")
            if body is not None and not isinstance(body, str):
                raise AcquisitionError(item["html_url"], "comment body is not text")
            comments.append(
                Comment(
                    id=item["id"],
                    url=item["html_url"],
                    body=body or "",
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    github_login=item["user"]["login"],
                )
            )
        return comments

    def branch(self, owner: str, repo: str, branch: str) -> dict[str, Any] | None:
        try:
            return self._get(f"/repos/{quote(owner)}/{quote(repo)}/branches/{quote(branch, safe='')}")
        except AcquisitionError as error:
            if error.status == 404:
                return None
            raise

    def pull_requests(self, owner: str, repo: str, branch: str) -> list[dict[str, Any]]:
        resources = self._pages(
            f"/repos/{quote(owner)}/{quote(repo)}/pulls",
            {"state": "all", "head": f"{owner}:{branch}"},
        )
        if not all(isinstance(item, dict) for item in resources):
            raise AcquisitionError(
                f"{self.api_root}/repos/{quote(owner)}/{quote(repo)}/pulls",
                "pull request collection entry is incomplete",
            )
        return resources

    def pull_request(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        resource = self._get(f"/repos/{quote(owner)}/{quote(repo)}/pulls/{number}")
        if not isinstance(resource, dict):
            raise AcquisitionError(
                f"{self.api_root}/repos/{quote(owner)}/{quote(repo)}/pulls/{number}",
                "pull request snapshot is incomplete",
            )
        return resource

    def pull_request_files(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        return self._pages(f"/repos/{quote(owner)}/{quote(repo)}/pulls/{number}/files")

    def check_run(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        return self._get(f"/repos/{quote(owner)}/{quote(repo)}/check-runs/{number}")

    def artifact(self, owner: str, repo: str, path: str, sha: str) -> dict[str, Any]:
        return self._get(
            f"/repos/{quote(owner)}/{quote(repo)}/contents/{quote(path, safe='/')}",
            {"ref": sha},
        )


def _next_link(header: str) -> str:
    for value in header.split(","):
        match = re.match(r'\s*<([^>]+)>;\s*rel="([^"]+)"', value)
        if match and match.group(2) == "next":
            return match.group(1)
    return ""
