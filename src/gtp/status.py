"""Status application service joining prefix history with live GitHub observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import unquote

from .github import AcquisitionError, GitHubClient
from .model import (
    Diagnostic,
    FoldContext,
    IncompleteSnapshotError,
    RecordObservation,
    SuccessorFact,
)
from .reducer import fold_comments, historical_state
from .urls import parse_github_url


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


@dataclass
class _DoneLive:
    observation: RecordObservation
    pr: dict[str, Any] | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    terminal_at: str | None = None


def _record_projection(observation: RecordObservation | None) -> dict[str, Any] | None:
    if observation is None:
        return None
    content_fields = {
        "contract": ("goal", "scope", "done_conditions"),
        "start": ("contract_ref", "branch"),
        "done": ("pr_ref", "head_sha", "evidence"),
        "stop": ("reason", "successor_ref"),
    }
    return {
        "id": observation.id,
        "type": observation.type,
        "url": observation.comment.url,
        "aliases": list(observation.alias_urls),
        "comment_id": observation.comment.id,
        "content": {
            key: observation.record[key]
            for key in content_fields[observation.type]
        },
    }


def _diagnostic(token: str, *urls: str, **detail: Any) -> Diagnostic:
    return Diagnostic(token, tuple(dict.fromkeys(urls)), detail)


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


def _branch_snapshot_key(
    branch: dict[str, Any] | None,
    resource: str,
) -> tuple[str, str] | None:
    if branch is None:
        return None
    name = branch.get("name")
    sha = branch.get("commit", {}).get("sha")
    if not isinstance(name, str) or not isinstance(sha, str):
        raise AcquisitionError(resource, "branch snapshot fields missing")
    return name, sha


def _pr_snapshot_key(pr: dict[str, Any], resource: str) -> tuple[Any, ...]:
    number = pr.get("number")
    url = pr.get("html_url")
    base = pr.get("base", {})
    base_repo_id = base.get("repo", {}).get("id")
    base_ref = base.get("ref")
    base_sha = base.get("sha")
    head = pr.get("head", {})
    head_repo_id = head.get("repo", {}).get("id")
    head_ref = head.get("ref")
    head_sha = head.get("sha")
    merged_at = pr.get("merged_at")
    state = pr.get("state")
    changed_files = pr.get("changed_files")
    if (
        not isinstance(number, int)
        or not isinstance(url, str)
        or not isinstance(base_repo_id, int)
        or not isinstance(base_ref, str)
        or not isinstance(base_sha, str)
        or not isinstance(head_repo_id, int)
        or not isinstance(head_ref, str)
        or not isinstance(head_sha, str)
        or not isinstance(state, str)
        or (merged_at is not None and not isinstance(merged_at, str))
        or (
            changed_files is not None
            and (not isinstance(changed_files, int) or changed_files < 0)
        )
    ):
        raise AcquisitionError(resource, "pull request snapshot fields missing")
    return (
        number,
        url,
        base_repo_id,
        base_ref,
        base_sha,
        head_repo_id,
        head_ref,
        head_sha,
        state,
        merged_at,
        changed_files,
    )


def _pr_collection_snapshot(
    prs: list[dict[str, Any]],
    resource: str,
) -> tuple[tuple[Any, ...], ...]:
    return tuple(sorted(_pr_snapshot_key(pr, resource) for pr in prs))


def _path_in_scope(path: str, scope: list[str]) -> bool:
    for entry in scope:
        if entry == "." or path == entry or (entry.endswith("/") and path.startswith(entry)):
            return True
    return False


def _scope_diagnostics(
    client: GitHubClient,
    owner: str,
    repo: str,
    contract: RecordObservation,
    pr: dict[str, Any],
    anchor_url: str,
) -> list[Diagnostic]:
    number = pr.get("number")
    pr_url = pr.get("html_url")
    if not isinstance(number, int) or not isinstance(pr_url, str):
        raise AcquisitionError(anchor_url, "pull request identity missing")
    listed_key = _pr_snapshot_key(pr, pr_url)
    detail = client.pull_request(owner, repo, number)
    detail_key = _pr_snapshot_key(detail, pr_url)
    if listed_key[:-1] != detail_key[:-1] or (
        listed_key[-1] is not None and listed_key[-1] != detail_key[-1]
    ):
        raise AcquisitionError(pr_url, "pull request changed during acquisition")
    changed_files = detail_key[-1]
    if not isinstance(changed_files, int) or changed_files < 0:
        raise AcquisitionError(pr_url, "pull request changed_files missing")
    files = client.pull_request_files(owner, repo, number)
    detail_after = client.pull_request(owner, repo, number)
    if _pr_snapshot_key(detail_after, pr_url) != detail_key:
        raise AcquisitionError(pr_url, "pull request changed during file acquisition")
    if len(files) != changed_files:
        raise AcquisitionError(pr_url, "pull request file collection is incomplete")
    observed_paths: list[str] = []
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
            raise AcquisitionError(pr_url, "pull request file entry is incomplete")
        observed_paths.append(item["filename"])
        previous = item.get("previous_filename")
        if previous is not None:
            if not isinstance(previous, str):
                raise AcquisitionError(pr_url, "pull request rename entry is incomplete")
            observed_paths.append(previous)
    outside = sorted(
        {path for path in observed_paths if not _path_in_scope(path, contract.record["scope"])}
    )
    if outside:
        return [_diagnostic("invalid_binding", anchor_url, pr_url, paths=outside)]
    return []


def _pr_not_after_start(
    pr: dict[str, Any],
    start: RecordObservation,
    resource: str,
) -> bool:
    created_at = pr.get("created_at")
    if not isinstance(created_at, str):
        raise AcquisitionError(resource, "pull request created_at missing")
    try:
        created_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        start_time = datetime.fromisoformat(
            start.comment.created_at.replace("Z", "+00:00")
        )
    except ValueError as error:
        raise AcquisitionError(resource, "pull request ordering timestamp invalid") from error
    return created_time <= start_time


def _successor_context(
    client: GitHubClient,
    refs: list[str],
) -> dict[str, SuccessorFact]:
    facts: dict[str, SuccessorFact] = {}
    for url in refs:
        parsed = parse_github_url(url, "issue")
        assert parsed is not None
        repository = client.repository(parsed.owner, parsed.repo)
        issue = client.issue(parsed.owner, parsed.repo, parsed.number or 0)
        facts[url] = SuccessorFact(
            url,
            "pull_request" not in issue,
            repository_id=repository.get("id"),
            issue_id=issue.get("id"),
            created_at=issue.get("created_at"),
        )
    return facts


def _live_evidence(
    client: GitHubClient,
    issue_repo_id: int,
    contract: RecordObservation,
    done: RecordObservation,
) -> tuple[list[Diagnostic], list[str]]:
    diagnostics: list[Diagnostic] = []
    completed_at: list[str] = []
    head_sha = done.record["head_sha"]
    for condition_id in sorted(contract.record["done_conditions"]):
        condition = contract.record["done_conditions"][condition_id]
        kind = condition["evidence_kind"]
        url = done.record["evidence"][condition_id]
        parsed = parse_github_url(url, kind)
        if parsed is None:
            diagnostics.append(_diagnostic("invalid_evidence", done.comment.url, url))
            continue
        repository = client.repository(parsed.owner, parsed.repo)
        if not _repo_matches(repository, issue_repo_id):
            diagnostics.append(_diagnostic("invalid_evidence", done.comment.url, url))
            continue
        if kind == "artifact":
            if parsed.sha != head_sha:
                diagnostics.append(_diagnostic("stale_evidence", done.comment.url, url))
                continue
            resource = client.artifact(
                parsed.owner,
                parsed.repo,
                unquote(parsed.path or "", encoding="utf-8", errors="strict"),
                head_sha,
            )
            if not isinstance(resource, dict) or resource.get("type") != "file":
                diagnostics.append(_diagnostic("invalid_evidence", done.comment.url, url))
        else:
            resource = client.check_run(parsed.owner, parsed.repo, parsed.number or 0)
            if resource.get("head_sha") != head_sha:
                diagnostics.append(_diagnostic("stale_evidence", done.comment.url, url))
            elif resource.get("status") != "completed":
                diagnostics.append(_diagnostic("invalid_evidence", done.comment.url, url))
            elif resource.get("conclusion") != "success":
                diagnostics.append(_diagnostic("invalid_evidence", done.comment.url, url))
            elif not isinstance(resource.get("completed_at"), str):
                raise AcquisitionError(url, "completed Check Run is missing completed_at")
            else:
                completed_at.append(resource["completed_at"])
    return diagnostics, completed_at


def _evaluate_done(
    client: GitHubClient,
    repo_id: int,
    branch_name: str,
    start: RecordObservation,
    contract: RecordObservation,
    done: RecordObservation,
) -> _DoneLive:
    result = _DoneLive(done)
    pr_url = parse_github_url(done.record["pr_ref"], "pr")
    assert pr_url is not None
    pr_repo = client.repository(pr_url.owner, pr_url.repo)
    pr = client.pull_request(pr_url.owner, pr_url.repo, pr_url.number or 0)
    result.pr = pr
    if (
        not _repo_matches(pr_repo, repo_id)
        or not _pr_matches(pr, repo_id, branch_name)
        or _pr_not_after_start(pr, start, done.record["pr_ref"])
    ):
        result.diagnostics.append(
            _diagnostic("invalid_binding", done.comment.url, done.record["pr_ref"])
        )
        return result
    if pr.get("head", {}).get("sha") != done.record["head_sha"]:
        result.diagnostics.append(
            _diagnostic("stale_evidence", done.comment.url, done.record["pr_ref"])
        )
        return result
    merged_at = pr.get("merged_at")
    if isinstance(merged_at, str) and merged_at < done.comment.created_at:
        result.diagnostics.append(
            _diagnostic("terminal_violation", done.comment.url, done.record["pr_ref"])
        )
        return result
    scope_diagnostics = _scope_diagnostics(
        client,
        pr_url.owner,
        pr_url.repo,
        contract,
        pr,
        done.comment.url,
    )
    evidence_diagnostics: list[Diagnostic] = []
    check_times: list[str] = []
    if not scope_diagnostics:
        evidence_diagnostics, check_times = _live_evidence(
            client, repo_id, contract, done
        )
    pr_after = client.pull_request(pr_url.owner, pr_url.repo, pr_url.number or 0)
    if _pr_snapshot_key(pr_after, done.record["pr_ref"]) != _pr_snapshot_key(
        pr, done.record["pr_ref"]
    ):
        raise AcquisitionError(done.record["pr_ref"], "bound pull request head changed during acquisition")
    result.pr = pr_after
    if scope_diagnostics:
        result.diagnostics.extend(scope_diagnostics)
        return result
    if evidence_diagnostics:
        if pr.get("merged_at"):
            urls = [url for item in evidence_diagnostics for url in item.urls]
            result.diagnostics.append(_diagnostic("invalid_evidence", *urls))
        else:
            result.diagnostics.extend(evidence_diagnostics)
        return result
    merged_at = pr_after.get("merged_at")
    if isinstance(merged_at, str):
        result.terminal_at = max(done.comment.created_at, merged_at, *check_times)
    return result


def _terminal_violations(
    diagnostics: list[Diagnostic],
    recognized_comments: list[Any],
    terminal_at: str,
    safe_retry_urls: set[str],
) -> list[Diagnostic]:
    violating_urls = {
        comment.url
        for comment in recognized_comments
        if comment.created_at > terminal_at and comment.url not in safe_retry_urls
    }
    result = [
        diagnostic
        for diagnostic in diagnostics
        if not any(url in violating_urls for url in diagnostic.urls)
    ]
    for comment in recognized_comments:
        if comment.url in violating_urls:
            item = _diagnostic("terminal_violation", comment.url)
            if item not in result:
                result.append(item)
    return result


def _stop_diagnostics(
    client: GitHubClient,
    owner: str,
    repo: str,
    repo_id: int,
    stop: RecordObservation,
    start: RecordObservation | None,
    context: FoldContext,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if stop.record["reason"] == "superseded":
        fact = context.successors[stop.record["successor_ref"]]
        if (
            not fact.exists
            or fact.repository_id != repo_id
            or fact.issue_id == context.issue_id
            or context.issue_created_at is None
            or fact.created_at is None
            or not (context.issue_created_at < fact.created_at <= stop.comment.created_at)
        ):
            diagnostics.append(
                _diagnostic("invalid_binding", stop.comment.url, fact.url)
            )
            return diagnostics
    if start is None:
        return diagnostics
    branch_name = start.record["branch"]
    resource = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    candidates = client.pull_requests(owner, repo, branch_name)
    candidates_after = client.pull_requests(owner, repo, branch_name)
    if _pr_collection_snapshot(candidates, resource) != _pr_collection_snapshot(
        candidates_after, resource
    ):
        raise AcquisitionError(resource, "pull request collection changed during acquisition")
    for pr in candidates_after:
        if not _pr_matches(pr, repo_id, branch_name):
            continue
        created_at = pr.get("created_at")
        pr_url = pr.get("html_url")
        if not isinstance(created_at, str) or not isinstance(pr_url, str):
            raise AcquisitionError(stop.comment.url, "pull request ordering fields missing")
        if _pr_not_after_start(pr, start, pr_url):
            diagnostics.append(
                _diagnostic("invalid_binding", start.comment.url, pr_url)
            )
            continue
        if created_at > stop.comment.created_at:
            continue
        merged_at = pr.get("merged_at")
        if not isinstance(merged_at, str):
            continue
        if merged_at == stop.comment.created_at:
            raise AcquisitionError(pr_url, "merge and Stop ordering is ambiguous")
        if merged_at > stop.comment.created_at:
            diagnostics.append(
                _diagnostic("terminal_violation", stop.comment.url, pr_url)
            )
    return diagnostics


def _has_terminal_violation(diagnostics: list[Diagnostic]) -> bool:
    return any(item.token == "terminal_violation" for item in diagnostics)


def _done_can_be_evaluated(
    contract: RecordObservation,
    done: RecordObservation,
) -> bool:
    expected = contract.record["done_conditions"]
    actual = done.record["evidence"]
    if set(expected) != set(actual):
        return False
    return all(
        parse_github_url(actual[condition_id], condition["evidence_kind"])
        is not None
        for condition_id, condition in expected.items()
    )


def _evaluate_acquired(
    client: GitHubClient,
    issue_url: str,
    parsed: Any,
    repository: dict[str, Any],
    issue: dict[str, Any],
    comments: list[Any],
) -> StatusResult:
    if "pull_request" in issue:
        return StatusResult(
            issue_url,
            None,
            acquisition_errors=[{"code": "invalid_issue_resource", "resource": issue_url}],
        )
    repo_id = repository.get("id")
    if not isinstance(repo_id, int):
        return StatusResult(
            issue_url,
            None,
            acquisition_errors=[{
                "code": "acquisition_incomplete",
                "resource": repository.get("url", issue_url),
                "message": "repository id missing",
            }],
        )

    try:
        context = FoldContext(
            issue_url=issue_url,
            issue_id=issue.get("id"),
            issue_created_at=issue.get("created_at"),
            repository_id=repo_id,
        )
        fold = fold_comments(comments, context)
        if fold.terminal_stop is not None and not _has_terminal_violation(
            fold.diagnostics
        ):
            stop_record = fold.terminal_stop.record
            if stop_record["reason"] == "superseded":
                context.successors = _successor_context(
                    client, [stop_record["successor_ref"]]
                )
    except IncompleteSnapshotError as error:
        return _acquisition(issue_url, AcquisitionError(issue_url, str(error)))
    except AcquisitionError as error:
        return _acquisition(issue_url, error)

    active_contract = fold.bound_contract or (
        fold.active["contract"][0] if len(fold.active["contract"]) == 1 else None
    )
    active_done = fold.active["done"][0] if len(fold.active["done"]) == 1 else None
    terminal_done = fold.active["done"][0] if fold.active["done"] else None
    current: dict[str, Any] = {
        "contract": _record_projection(active_contract),
        "start": _record_projection(fold.bound_start),
        "done": _record_projection(active_done),
        "stop": _record_projection(fold.terminal_stop),
    }
    base_state = historical_state(fold)
    if base_state in {"unmanaged", "ready"}:
        return StatusResult(issue_url, base_state, list(fold.diagnostics), current)
    if fold.bound_start is None or fold.bound_contract is None:
        if fold.terminal_stop is not None:
            if _has_terminal_violation(fold.diagnostics):
                return StatusResult(issue_url, "halt", list(fold.diagnostics), current)
            try:
                stop_diagnostics = _stop_diagnostics(
                    client,
                    parsed.owner,
                    parsed.repo,
                    repo_id,
                    fold.terminal_stop,
                    fold.bound_start,
                    context,
                )
            except AcquisitionError as error:
                return _acquisition(issue_url, error)
            if stop_diagnostics:
                return StatusResult(issue_url, "halt", stop_diagnostics, current)
            return StatusResult(
                issue_url, "stopped", [*fold.diagnostics, *stop_diagnostics], current
            )
        return StatusResult(issue_url, "halt", list(fold.diagnostics), current)

    branch_name = fold.bound_start.record["branch"]
    current["branch"] = {"name": branch_name}
    if fold.terminal_stop is not None:
        if _has_terminal_violation(fold.diagnostics):
            return StatusResult(issue_url, "halt", list(fold.diagnostics), current)
        try:
            if terminal_done is not None and _done_can_be_evaluated(
                fold.bound_contract, terminal_done
            ):
                live_done = _evaluate_done(
                    client,
                    repo_id,
                    branch_name,
                    fold.bound_start,
                    fold.bound_contract,
                    terminal_done,
                )
                if live_done.terminal_at == fold.terminal_stop.comment.created_at:
                    raise AcquisitionError(
                        terminal_done.record["pr_ref"],
                        "Done terminal and Stop ordering is ambiguous",
                    )
                if (
                    live_done.terminal_at is not None
                    and live_done.terminal_at < fold.terminal_stop.comment.created_at
                ):
                    return StatusResult(
                        issue_url,
                        "halt",
                        [
                            _diagnostic(
                                "terminal_violation",
                                fold.terminal_stop.comment.url,
                                terminal_done.record["pr_ref"],
                            )
                        ],
                        current,
                    )
            stop_diagnostics = _stop_diagnostics(
                client, parsed.owner, parsed.repo, repo_id, fold.terminal_stop, fold.bound_start, context
            )
        except AcquisitionError as error:
            return _acquisition(issue_url, error)
        if stop_diagnostics:
            return StatusResult(issue_url, "halt", [*fold.diagnostics, *stop_diagnostics], current)
        return StatusResult(issue_url, "stopped", list(fold.diagnostics), current)

    default_branch = repository.get("default_branch")
    if not isinstance(default_branch, str):
        return _acquisition(
            issue_url,
            AcquisitionError(issue_url, "repository default_branch missing"),
        )
    if branch_name == default_branch:
        return StatusResult(
            issue_url,
            "halt",
            [_diagnostic("invalid_binding", fold.bound_start.comment.url)],
            current,
        )

    try:
        if terminal_done is not None and _done_can_be_evaluated(
            fold.bound_contract, terminal_done
        ):
            live = _evaluate_done(
                client,
                repo_id,
                branch_name,
                fold.bound_start,
                fold.bound_contract,
                terminal_done,
            )
            if live.pr is not None:
                current["bound_pr"] = live.pr.get("html_url")
                current["bound_pr_head_sha"] = live.pr.get("head", {}).get("sha")
            if live.diagnostics:
                return StatusResult(
                    issue_url,
                    "halt",
                    [*fold.diagnostics, *live.diagnostics],
                    current,
                )
            if live.terminal_at is not None:
                safe_retry_urls = {
                    url
                    for observations in fold.ids.values()
                    for observation in observations
                    if len(observation.alias_urls) > 1
                    for url in observation.alias_urls
                }
                diagnostics = _terminal_violations(
                    fold.diagnostics,
                    fold.recognized_comments,
                    live.terminal_at,
                    safe_retry_urls,
                )
                return StatusResult(
                    issue_url,
                    "halt" if diagnostics else "done",
                    diagnostics,
                    current,
                )
            if fold.diagnostics:
                return StatusResult(issue_url, "halt", list(fold.diagnostics), current)
            if live.pr and live.pr.get("merged_at"):
                return StatusResult(issue_url, "in_progress", [], current)
            branch = client.branch(parsed.owner, parsed.repo, branch_name)
            branch_after = client.branch(parsed.owner, parsed.repo, branch_name)
            branch_resource = (
                f"https://api.github.com/repos/{parsed.owner}/{parsed.repo}/branches/"
                f"{branch_name}"
            )
            if _branch_snapshot_key(branch, branch_resource) != _branch_snapshot_key(
                branch_after, branch_resource
            ):
                raise AcquisitionError(
                    branch_resource, "bound branch changed during acquisition"
                )
            branch_key = _branch_snapshot_key(branch_after, branch_resource)
            pr_head = live.pr.get("head", {}).get("sha") if live.pr else None
            if (
                branch_key is None
                or branch_key[1] != pr_head
                or pr_head != terminal_done.record["head_sha"]
            ):
                raise AcquisitionError(
                    branch_resource, "bound branch and pull request head disagree"
                )
            current["branch"]["exists"] = branch is not None
            if branch is None:
                return StatusResult(
                    issue_url,
                    "halt",
                    [_diagnostic("invalid_binding", fold.bound_start.comment.url)],
                    current,
                )
            return StatusResult(issue_url, "in_progress", [], current)

        if fold.diagnostics:
            return StatusResult(issue_url, "halt", list(fold.diagnostics), current)

        branch = client.branch(parsed.owner, parsed.repo, branch_name)
        observed_candidates = client.pull_requests(parsed.owner, parsed.repo, branch_name)
        invalid_candidates = [
            pr
            for pr in observed_candidates
            if not _pr_matches(pr, repo_id, branch_name)
            or _pr_not_after_start(pr, fold.bound_start, pr.get("html_url", issue_url))
        ]
        if invalid_candidates:
            urls = [fold.bound_start.comment.url] + [
                pr.get("html_url", issue_url) for pr in invalid_candidates
            ]
            return StatusResult(
                issue_url,
                "halt",
                [_diagnostic("invalid_binding", *urls)],
                current,
            )
        candidates = observed_candidates
        current["branch"]["exists"] = branch is not None
        current["pr_candidates"] = [pr.get("html_url") for pr in candidates]
        if len(candidates) > 1:
            urls = [fold.bound_start.comment.url] + [pr["html_url"] for pr in candidates]
            return StatusResult(issue_url, "halt", [_diagnostic("invalid_binding", *urls)], current)
        if len(candidates) == 1 and candidates[0].get("merged_at"):
            return StatusResult(
                issue_url,
                "halt",
                [_diagnostic("terminal_violation", fold.bound_start.comment.url, candidates[0]["html_url"])],
                current,
            )
        if len(candidates) == 1:
            scope_diagnostics = _scope_diagnostics(
                client,
                parsed.owner,
                parsed.repo,
                fold.bound_contract,
                candidates[0],
                fold.bound_start.comment.url,
            )
            if scope_diagnostics:
                return StatusResult(issue_url, "halt", scope_diagnostics, current)
        branch_after = client.branch(parsed.owner, parsed.repo, branch_name)
        candidates_after = client.pull_requests(parsed.owner, parsed.repo, branch_name)
        branch_resource = (
            f"https://api.github.com/repos/{parsed.owner}/{parsed.repo}/branches/"
            f"{branch_name}"
        )
        pulls_resource = (
            f"https://api.github.com/repos/{parsed.owner}/{parsed.repo}/pulls"
        )
        if _branch_snapshot_key(branch, branch_resource) != _branch_snapshot_key(
            branch_after, branch_resource
        ) or _pr_collection_snapshot(
            observed_candidates, pulls_resource
        ) != _pr_collection_snapshot(candidates_after, pulls_resource):
            raise AcquisitionError(
                issue_url, "branch or pull request collection changed during acquisition"
            )
        if branch is None:
            return StatusResult(
                issue_url,
                "halt",
                [_diagnostic("invalid_binding", fold.bound_start.comment.url)],
                current,
            )
        return StatusResult(issue_url, "in_progress", [], current)
    except AcquisitionError as error:
        return _acquisition(issue_url, error)


def _issue_snapshot_key(issue: dict[str, Any]) -> tuple[int, str, str]:
    issue_id = issue.get("id")
    created_at = issue.get("created_at")
    updated_at = issue.get("updated_at", created_at)
    if not isinstance(issue_id, int) or not isinstance(created_at, str) or not isinstance(updated_at, str):
        raise AcquisitionError(str(issue.get("url", "issue")), "issue snapshot fields missing")
    return issue_id, created_at, updated_at


def _repository_snapshot_key(
    repository: dict[str, Any], resource: str
) -> tuple[int, str, str]:
    repo_id = repository.get("id")
    full_name = repository.get("full_name")
    default_branch = repository.get("default_branch")
    if (
        not isinstance(repo_id, int)
        or not isinstance(full_name, str)
        or not isinstance(default_branch, str)
    ):
        raise AcquisitionError(resource, "repository snapshot fields missing")
    return repo_id, full_name, default_branch


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
        repository_resource = (
            f"https://api.github.com/repos/{parsed.owner}/{parsed.repo}"
        )
        repository_key = _repository_snapshot_key(
            repository, repository_resource
        )
        issue = client.issue(parsed.owner, parsed.repo, parsed.number or 0)
        initial_key = _issue_snapshot_key(issue)
        comments = client.comments(parsed.owner, parsed.repo, parsed.number or 0)
    except AcquisitionError as error:
        return _acquisition(issue_url, error)

    result = _evaluate_acquired(client, issue_url, parsed, repository, issue, comments)
    if result.state is None:
        return result
    try:
        repository_after = client.repository(parsed.owner, parsed.repo)
        if _repository_snapshot_key(
            repository_after, repository_resource
        ) != repository_key:
            raise AcquisitionError(
                repository_resource, "repository snapshot changed during acquisition"
            )
        issue_after = client.issue(parsed.owner, parsed.repo, parsed.number or 0)
        if _issue_snapshot_key(issue_after) != initial_key:
            raise AcquisitionError(issue_url, "issue snapshot changed during acquisition")
    except AcquisitionError as error:
        return _acquisition(issue_url, error)
    return result
