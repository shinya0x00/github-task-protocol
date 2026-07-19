"""Read-only GitHub REST adapter for GTP status."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .model import Comment


class AcquisitionError(RuntimeError):
    def __init__(self, resource: str, message: str, status: int | None = None):
        super().__init__(message)
        self.resource = resource
        self.status = status


class GitHubClient:
    api_root = "https://api.github.com"

    def __init__(self, token: str | None = None) -> None:
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    def _request(self, url: str) -> tuple[Any, dict[str, str]]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-task-protocol/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=30) as response:
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
        return self._get(f"/repos/{quote(owner)}/{quote(repo)}")

    def issue(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        return self._get(f"/repos/{quote(owner)}/{quote(repo)}/issues/{number}")

    def comments(self, owner: str, repo: str, number: int) -> list[Comment]:
        data = self._pages(
            f"/repos/{quote(owner)}/{quote(repo)}/issues/{number}/comments",
            {"sort": "created", "direction": "asc"},
        )
        return [
            Comment(
                id=item["id"],
                url=item["html_url"],
                body=item.get("body") or "",
                created_at=item["created_at"],
                updated_at=item["updated_at"],
                github_login=item["user"]["login"],
            )
            for item in data
        ]

    def branch(self, owner: str, repo: str, branch: str) -> dict[str, Any] | None:
        try:
            return self._get(f"/repos/{quote(owner)}/{quote(repo)}/branches/{quote(branch, safe='')}")
        except AcquisitionError as error:
            if error.status == 404:
                return None
            raise

    def pull_requests(self, owner: str, repo: str, branch: str) -> list[dict[str, Any]]:
        return self._pages(
            f"/repos/{quote(owner)}/{quote(repo)}/pulls",
            {"state": "all", "head": f"{owner}:{branch}"},
        )

    def pull_request(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        return self._get(f"/repos/{quote(owner)}/{quote(repo)}/pulls/{number}")

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
