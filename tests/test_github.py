from __future__ import annotations

import unittest

from gtp.github import GitHubClient, _next_link


class GitHubAdapterTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
