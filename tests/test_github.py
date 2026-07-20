from __future__ import annotations

import unittest
import os
from urllib.error import URLError
from urllib.request import Request
from unittest.mock import MagicMock, patch

from gtp.github import (
    AcquisitionError,
    GitHubClient,
    _SafeRedirectHandler,
    _next_link,
)
from gtp.urls import parse_github_url


class GitHubAdapterTests(unittest.TestCase):
    def test_check_run_and_artifact_profiles_reject_mutable_or_workflow_urls(self) -> None:
        self.assertIsNotNone(parse_github_url("https://github.com/o/r/runs/8", "check"))
        self.assertIsNone(
            parse_github_url("https://github.com/o/r/actions/runs/8", "check")
        )
        self.assertIsNone(
            parse_github_url("https://github.com/o/r/blob/main/src/a.py", "artifact")
        )

    def test_token_precedence_and_anonymous_read(self) -> None:
        with patch.dict(os.environ, {"GITHUB_TOKEN": "github", "GH_TOKEN": "gh"}, clear=True):
            self.assertEqual("github", GitHubClient().token)
        with patch.dict(os.environ, {"GH_TOKEN": "gh"}, clear=True):
            self.assertEqual("gh", GitHubClient().token)
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(GitHubClient().token)

    def test_requests_disable_intermediate_cache_reuse(self) -> None:
        client = GitHubClient(token="token")
        response = MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "https://api.github.com/resource"
        response.read.return_value = b"{}"
        response.headers.items.return_value = []
        with patch("gtp.github._open", return_value=response) as mocked:
            client._request("https://api.github.com/resource")
        request = mocked.call_args.args[0]
        self.assertEqual("GET", request.get_method())
        self.assertEqual("no-cache", request.get_header("Cache-control"))

    def test_next_link_is_selected_from_multi_link_header(self) -> None:
        header = (
            '<https://api.github.com/resource?page=2>; rel="next", '
            '<https://api.github.com/resource?page=5>; rel="last"'
        )
        self.assertEqual("https://api.github.com/resource?page=2", _next_link(header))

    def test_no_next_link_ends_pagination(self) -> None:
        self.assertEqual("", _next_link('<https://api.github.com/resource?page=1>; rel="prev"'))

    def test_pages_follows_every_next_link(self) -> None:
        class PagedClient(GitHubClient):
            def __init__(self) -> None:
                super().__init__(token="token")
                self.seen: list[str] = []

            def _request(self, url):
                self.seen.append(url)
                if len(self.seen) == 1:
                    return [1, 2], {
                        "link": '<https://api.github.com/items?page=2>; rel="next"'
                    }
                return [3], {}

        client = PagedClient()
        self.assertEqual([1, 2, 3], client._pages("/items"))
        self.assertIn("per_page=100", client.seen[0])
        self.assertEqual("https://api.github.com/items?page=2", client.seen[1])

    def test_pagination_failure_is_acquisition_error(self) -> None:
        first = MagicMock()
        first.__enter__.return_value = first
        first.geturl.return_value = "https://api.github.com/items?per_page=100"
        first.read.return_value = b"[1]"
        first.headers.items.return_value = [
            ("Link", '<https://api.github.com/items?page=2>; rel="next"')
        ]
        with patch("gtp.github._open", side_effect=[first, URLError("timeout")]):
            with self.assertRaises(AcquisitionError):
                GitHubClient(token="token")._pages("/items")

    def test_pagination_completes_through_http_boundary(self) -> None:
        first = MagicMock()
        first.__enter__.return_value = first
        first.geturl.return_value = "https://api.github.com/items?per_page=100"
        first.read.return_value = b"[1, 2]"
        first.headers.items.return_value = [
            ("Link", '<https://api.github.com/items?page=2>; rel="next"')
        ]
        second = MagicMock()
        second.__enter__.return_value = second
        second.geturl.return_value = "https://api.github.com/items?page=2"
        second.read.return_value = b"[3]"
        second.headers.items.return_value = []
        with patch("gtp.github._open", side_effect=[first, second]):
            self.assertEqual([1, 2, 3], GitHubClient(token="token")._pages("/items"))

    def test_non_api_host_is_rejected_before_network(self) -> None:
        client = GitHubClient(token="token")
        with patch("gtp.github._open") as mocked, self.assertRaises(AcquisitionError):
            client._request("https://example.com/repos/o/r")
        mocked.assert_not_called()

    def test_json_decode_failure_is_acquisition_error(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "https://api.github.com/resource"
        response.read.return_value = b"{broken"
        response.headers.items.return_value = []
        with patch("gtp.github._open", return_value=response), self.assertRaises(AcquisitionError):
            GitHubClient(token=None)._request("https://api.github.com/resource")

    def test_cross_origin_redirect_drops_authorization(self) -> None:
        request = Request(
            "https://api.github.com/resource",
            headers={"Authorization": "Bearer secret"},
            method="GET",
        )
        redirected = _SafeRedirectHandler().redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://objects.githubusercontent.com/resource",
        )
        self.assertIsNotNone(redirected)
        self.assertIsNone(redirected.get_header("Authorization"))

    def test_pull_request_files_paginates(self) -> None:
        client = GitHubClient(token="token")
        with patch.object(client, "_pages", return_value=[{"filename": "src/a.py"}]) as pages:
            result = client.pull_request_files("o", "r", 7)
        self.assertEqual([{"filename": "src/a.py"}], result)
        pages.assert_called_once_with("/repos/o/r/pulls/7/files")

    def test_branch_404_is_not_silently_converted_to_proven_absence(self) -> None:
        client = GitHubClient(token="token")
        with patch.object(
            client,
            "_get",
            side_effect=AcquisitionError("branch", "not visible", 404),
        ), self.assertRaises(AcquisitionError):
            client.branch("o", "r", "task")


if __name__ == "__main__":
    unittest.main()
