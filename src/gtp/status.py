"""Status application service joining history with live GitHub observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote

from .github import AcquisitionError, GitHubClient
from .model import Diagnostic, FoldResult, RecordObservation
from .reducer import fold_comments, historical_state
from .urls import GitHubUrl, parse_github_url


@dataclass
class StatusResult:
    issue_url: str
    state: str | None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    current: dict[str, Any] = field(default_factory=dict)
    acquisition_errors: list[dict[str, Any]] = field(default_factory=list)

    def projection(self) -> dict[str, Any]:
        return {
            "issue_url": self.issue_url,
            "state": self.state,
            "diagnostics": [item.projection() for item in self.diagnostics],
            "current": self.current,
            "acquisition": {
                "complete": not self.acquisition_errors,
                "errors": self.acquisition_errors,
            },
        }


def _record_projection(observation: RecordObservation | None) -> dict[str, Any] | None:
    if observation is None:
        return None
    return {
        "id": observation.id,
        "type": observation.type,
        "url": observation.comment.url,
        "comment_id": observation.comment.id,
    }


def _diagnostic(token: str, *urls: str, **detail: Any) -> Diagnostic:
    return Diagnostic(token, tuple(urls), detail)


def _acquisition(issue_url: str, error: AcquisitionError) -> StatusResult:
    item: dict[str, Any] = {
        "code": "acquisition_incomplete",
        "resource": error.resource,
        "message": str(error),
    }
    if error.status is not None:
        item["status"] = error.status
    return StatusResult(issue_url, None, acquisition_errors=[item])


def _repo_matches(resource: dict[str, Any], expected_id: int) -> bool:
    return isinstance(resource, dict) and resource.get("id") == expected_id


def _pr_matches(pr: dict[str, Any], repo_id: int, branch: str) -> bool:
    return (
        pr.get("base", {}).get("repo", {}).get("id") == repo_id
        and pr.get("head", {}).get("repo", {}).get("id") == repo_id
        and pr.get("head", {}).get("ref") == branch
    )


def _live_evidence(
    client: GitHubClient,
    issue_repo_id: int,
    contract: RecordObservation,
    done: RecordObservation,
) -> tuple[list[Diagnostic], bool]:
    diagnostics: list[Diagnostic] = []
    pending = False
    head_sha = done.record["head_sha"]
    for condition_id in sorted(contract.record["done_conditions"]):
        condition = contract.record["done_conditions"][condition_id]
        kind = condition["evidence_kind"]
        url = done.record["evidence"][condition_id]
        parsed = parse_github_url(url, kind)
        if parsed is None:
            diagnostics.append(_diagnostic("evidence_live_mismatch", done.comment.url, url))
            continue
        repository = client.repository(parsed.owner, parsed.repo)
        if not _repo_matches(repository, issue_repo_id):
            diagnostics.append(_diagnostic("evidence_live_mismatch", done.comment.url, url))
            continue
        if kind == "artifact":
            if parsed.sha != head_sha:
                diagnostics.append(_diagnostic("evidence_live_mismatch", done.comment.url, url))
                continue
            try:
                resource = client.artifact(
                    parsed.owner,
                    parsed.repo,
                    unquote(parsed.path or "", encoding="utf-8", errors="strict"),
                    head_sha,
                )
            except AcquisitionError as error:
                if error.status == 404:
                    diagnostics.append(_diagnostic("evidence_live_mismatch", done.comment.url, url))
                    continue
                raise
            if not isinstance(resource, dict) or resource.get("type") != "file":
                diagnostics.append(_diagnostic("evidence_live_mismatch", done.comment.url, url))
        else:
            resource = client.check_run(parsed.owner, parsed.repo, parsed.number or 0)
            if resource.get("head_sha") != head_sha:
                diagnostics.append(_diagnostic("evidence_live_mismatch", done.comment.url, url))
            elif resource.get("status") != "completed":
                pending = True
            elif resource.get("conclusion") != "success":
                diagnostics.append(_diagnostic("evidence_live_mismatch", done.comment.url, url))
    return diagnostics, pending


def _stop_live_check(
    client: GitHubClient,
    issue: dict[str, Any],
    repo_id: int,
    stop: RecordObservation,
) -> list[Diagnostic]:
    if stop.record["reason"] != "superseded":
        return []
    url = stop.record["successor_ref"]
    parsed = parse_github_url(url, "issue")
    if parsed is None:
        return [_diagnostic("terminal_dependency_mismatch", stop.comment.url, url)]
    successor_repo = client.repository(parsed.owner, parsed.repo)
    successor = client.issue(parsed.owner, parsed.repo, parsed.number or 0)
    if not _repo_matches(successor_repo, repo_id):
        return [_diagnostic("terminal_dependency_mismatch", stop.comment.url, url)]
    if successor.get("id") == issue.get("id"):
        return [_diagnostic("successor_order_invalid", stop.comment.url, url)]
    if not (issue["created_at"] < successor["created_at"] <= stop.comment.created_at):
        return [_diagnostic("successor_order_invalid", stop.comment.url, url)]
    return []


def evaluate_issue(client: GitHubClient, issue_url: str) -> StatusResult:
    parsed = parse_github_url(issue_url, "issue")
    if parsed is None:
        return StatusResult(
            issue_url,
            None,
            acquisition_errors=[{"code": "invalid_issue_url", "resource": issue_url}],
        )
    try:
        repository = client.repository(parsed.owner, parsed.repo)
        issue = client.issue(parsed.owner, parsed.repo, parsed.number or 0)
        comments = client.comments(parsed.owner, parsed.repo, parsed.number or 0)
    except AcquisitionError as error:
        return _acquisition(issue_url, error)
    if "pull_request" in issue:
        return StatusResult(
            issue_url,
            None,
            acquisition_errors=[{"code": "invalid_issue_resource", "resource": issue_url}],
        )

    fold = fold_comments(comments)
    base_state = historical_state(fold)
    current: dict[str, Any] = {
        "contract": _record_projection(fold.bound_contract or (fold.active["contract"][0] if len(fold.active["contract"]) == 1 else None)),
        "start": _record_projection(fold.bound_start),
        "done": _record_projection(fold.active["done"][0] if len(fold.active["done"]) == 1 else None),
        "stop": _record_projection(fold.terminal_stop),
    }
    if fold.unsupported:
        return StatusResult(issue_url, None, fold.unsupported, current)
    if base_state in {"unmanaged", "ready", "halt"}:
        return StatusResult(issue_url, base_state, list(fold.diagnostics), current)

    repo_id = repository.get("id")
    if not isinstance(repo_id, int):
        return StatusResult(
            issue_url,
            None,
            acquisition_errors=[{"code": "acquisition_incomplete", "resource": repository.get("url", issue_url), "message": "repository id missing"}],
        )
    if base_state == "stopped" and fold.terminal_stop is not None:
        try:
            diagnostics = _stop_live_check(client, issue, repo_id, fold.terminal_stop)
        except AcquisitionError as error:
            return _acquisition(issue_url, error)
        if diagnostics:
            token = diagnostics[0].token
            state = "halt" if token == "terminal_dependency_mismatch" else "halt"
            return StatusResult(issue_url, state, diagnostics, current)
        return StatusResult(issue_url, "stopped", list(fold.diagnostics), current)

    if fold.bound_start is None or fold.bound_contract is None:
        return StatusResult(issue_url, "halt", list(fold.diagnostics), current)
    branch_name = fold.bound_start.record["branch"]
    current["branch"] = {"name": branch_name}
    active_done = fold.active["done"][0] if len(fold.active["done"]) == 1 else None
    try:
        if active_done is None:
            branch = client.branch(parsed.owner, parsed.repo, branch_name)
            candidates = [
                pr for pr in client.pull_requests(parsed.owner, parsed.repo, branch_name)
                if _pr_matches(pr, repo_id, branch_name)
            ]
            current["branch"]["exists"] = branch is not None
            current["pr_candidates"] = [pr.get("html_url") for pr in candidates]
            if len(candidates) > 1:
                urls = [fold.bound_start.comment.url] + [pr["html_url"] for pr in candidates]
                return StatusResult(issue_url, "halt", [_diagnostic("multiple_pr_candidates", *urls)], current)
            if len(candidates) == 1 and candidates[0].get("merged_at"):
                return StatusResult(
                    issue_url,
                    "halt",
                    [_diagnostic("merge_without_done", fold.bound_start.comment.url, candidates[0]["html_url"])],
                    current,
                )
            if branch is None:
                return StatusResult(issue_url, "halt", [_diagnostic("branch_binding_mismatch", fold.bound_start.comment.url)], current)
            return StatusResult(issue_url, "in_progress", list(fold.diagnostics), current)

        pr_url = parse_github_url(active_done.record["pr_ref"], "pr")
        assert pr_url is not None
        pr_repo = client.repository(pr_url.owner, pr_url.repo)
        pr = client.pull_request(pr_url.owner, pr_url.repo, pr_url.number or 0)
        current["bound_pr"] = pr.get("html_url")
        current["bound_pr_head_sha"] = pr.get("head", {}).get("sha")
        if not _repo_matches(pr_repo, repo_id) or not _pr_matches(pr, repo_id, branch_name):
            return StatusResult(
                issue_url,
                "halt",
                [_diagnostic("pr_binding_mismatch", active_done.comment.url, active_done.record["pr_ref"])],
                current,
            )
        if pr.get("head", {}).get("sha") != active_done.record["head_sha"]:
            return StatusResult(
                issue_url,
                "halt",
                [_diagnostic("done_head_sha_mismatch", active_done.comment.url, active_done.record["pr_ref"])],
                current,
            )
        evidence_diagnostics, evidence_pending = _live_evidence(
            client, repo_id, fold.bound_contract, active_done
        )
        if evidence_diagnostics:
            if pr.get("merged_at"):
                urls = tuple(
                    dict.fromkeys(url for diagnostic in evidence_diagnostics for url in diagnostic.urls)
                )
                return StatusResult(
                    issue_url,
                    "halt",
                    [Diagnostic("terminal_dependency_mismatch", urls)],
                    current,
                )
            return StatusResult(issue_url, "halt", evidence_diagnostics, current)
        if pr.get("merged_at"):
            return StatusResult(issue_url, "done", list(fold.diagnostics), current)
        branch = client.branch(parsed.owner, parsed.repo, branch_name)
        current["branch"]["exists"] = branch is not None
        if branch is None:
            return StatusResult(issue_url, "halt", [_diagnostic("branch_binding_mismatch", fold.bound_start.comment.url)], current)
        current["evidence_pending"] = evidence_pending
        return StatusResult(issue_url, "in_progress", list(fold.diagnostics), current)
    except AcquisitionError as error:
        return _acquisition(issue_url, error)
