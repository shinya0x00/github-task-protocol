"""Status application service joining prefix history with live GitHub observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote

from .github import AcquisitionError, GitHubClient
from .model import (
    ContextAcquisitionRequired,
    Diagnostic,
    FoldContext,
    IncompleteSnapshotError,
    RecordObservation,
    SuccessorFact,
)
from .reducer import fold_comments, historical_state, successor_refs
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
    pending: bool = False
    terminal_at: str | None = None


def _record_projection(observation: RecordObservation | None) -> dict[str, Any] | None:
    if observation is None:
        return None
    return {
        "id": observation.id,
        "type": observation.type,
        "url": observation.comment.url,
        "aliases": list(observation.alias_urls),
        "comment_id": observation.comment.id,
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


def _missing_is_mismatch(error: AcquisitionError) -> bool:
    return error.status == 404


def _successor_context(
    client: GitHubClient,
    comments: list[Any],
) -> dict[str, SuccessorFact]:
    facts: dict[str, SuccessorFact] = {}
    for url in successor_refs(comments):
        parsed = parse_github_url(url, "issue")
        assert parsed is not None
        repository = client.repository(parsed.owner, parsed.repo)
        try:
            issue = client.issue(parsed.owner, parsed.repo, parsed.number or 0)
        except AcquisitionError as error:
            if _missing_is_mismatch(error):
                facts[url] = SuccessorFact(url, False, repository_id=repository.get("id"))
                continue
            raise
        facts[url] = SuccessorFact(
            url,
            True,
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
) -> tuple[list[Diagnostic], bool, list[str]]:
    diagnostics: list[Diagnostic] = []
    pending = False
    completed_at: list[str] = []
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
                if _missing_is_mismatch(error):
                    diagnostics.append(_diagnostic("evidence_live_mismatch", done.comment.url, url))
                    continue
                raise
            if not isinstance(resource, dict) or resource.get("type") != "file":
                diagnostics.append(_diagnostic("evidence_live_mismatch", done.comment.url, url))
        else:
            try:
                resource = client.check_run(parsed.owner, parsed.repo, parsed.number or 0)
            except AcquisitionError as error:
                if _missing_is_mismatch(error):
                    diagnostics.append(_diagnostic("evidence_live_mismatch", done.comment.url, url))
                    continue
                raise
            if resource.get("head_sha") != head_sha:
                diagnostics.append(_diagnostic("evidence_live_mismatch", done.comment.url, url))
            elif resource.get("status") != "completed":
                pending = True
            elif resource.get("conclusion") != "success":
                diagnostics.append(_diagnostic("evidence_live_mismatch", done.comment.url, url))
            elif not isinstance(resource.get("completed_at"), str):
                raise AcquisitionError(url, "completed Check Run is missing completed_at")
            else:
                completed_at.append(resource["completed_at"])
    return diagnostics, pending, completed_at


def _evaluate_done(
    client: GitHubClient,
    repo_id: int,
    branch_name: str,
    contract: RecordObservation,
    done: RecordObservation,
) -> _DoneLive:
    result = _DoneLive(done)
    pr_url = parse_github_url(done.record["pr_ref"], "pr")
    assert pr_url is not None
    try:
        pr_repo = client.repository(pr_url.owner, pr_url.repo)
        pr = client.pull_request(pr_url.owner, pr_url.repo, pr_url.number or 0)
    except AcquisitionError as error:
        if _missing_is_mismatch(error):
            result.diagnostics.append(
                _diagnostic("pr_binding_mismatch", done.comment.url, done.record["pr_ref"])
            )
            return result
        raise
    result.pr = pr
    if not _repo_matches(pr_repo, repo_id) or not _pr_matches(pr, repo_id, branch_name):
        result.diagnostics.append(
            _diagnostic("pr_binding_mismatch", done.comment.url, done.record["pr_ref"])
        )
        return result
    if pr.get("head", {}).get("sha") != done.record["head_sha"]:
        result.diagnostics.append(
            _diagnostic("done_head_sha_mismatch", done.comment.url, done.record["pr_ref"])
        )
        return result
    evidence_diagnostics, pending, check_times = _live_evidence(
        client, repo_id, contract, done
    )
    result.pending = pending
    if evidence_diagnostics:
        if pr.get("merged_at"):
            urls = [url for item in evidence_diagnostics for url in item.urls]
            result.diagnostics.append(_diagnostic("terminal_dependency_mismatch", *urls))
        else:
            result.diagnostics.extend(evidence_diagnostics)
        return result
    merged_at = pr.get("merged_at")
    if isinstance(merged_at, str) and not pending:
        result.terminal_at = max(done.comment.created_at, merged_at, *check_times)
    return result


def _terminal_violations(
    diagnostics: list[Diagnostic],
    recognized_comments: list[Any],
    terminal_at: str,
    terminal_record: RecordObservation,
) -> list[Diagnostic]:
    result = list(diagnostics)
    terminal_aliases = set(terminal_record.alias_urls)
    for comment in recognized_comments:
        if comment.created_at > terminal_at and comment.url not in terminal_aliases:
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
        if not fact.exists or fact.repository_id != repo_id:
            diagnostics.append(
                _diagnostic("terminal_dependency_mismatch", stop.comment.url, fact.url)
            )
            return diagnostics
    if start is None:
        return diagnostics
    branch_name = start.record["branch"]
    candidates = [
        pr
        for pr in client.pull_requests(owner, repo, branch_name)
        if _pr_matches(pr, repo_id, branch_name) and isinstance(pr.get("merged_at"), str)
    ]
    for pr in candidates:
        token = "merge_before_stop" if pr["merged_at"] <= stop.comment.created_at else "merge_after_stop"
        diagnostics.append(_diagnostic(token, stop.comment.url, pr["html_url"]))
    return diagnostics


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
            successors=_successor_context(client, comments),
        )
        fold = fold_comments(comments, context)
    except IncompleteSnapshotError as error:
        return _acquisition(issue_url, AcquisitionError(issue_url, str(error)))
    except ContextAcquisitionRequired as error:
        return _acquisition(issue_url, AcquisitionError(error.resource, "successor context missing"))
    except AcquisitionError as error:
        return _acquisition(issue_url, error)

    active_contract = fold.bound_contract or (
        fold.active["contract"][0] if len(fold.active["contract"]) == 1 else None
    )
    active_done = fold.active["done"][0] if len(fold.active["done"]) == 1 else None
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
            if stop_diagnostics and stop_diagnostics[0].token == "terminal_dependency_mismatch":
                return StatusResult(issue_url, "halt", stop_diagnostics, current)
            return StatusResult(
                issue_url, "stopped", [*fold.diagnostics, *stop_diagnostics], current
            )
        return StatusResult(issue_url, "halt", list(fold.diagnostics), current)

    branch_name = fold.bound_start.record["branch"]
    current["branch"] = {"name": branch_name}
    live_by_id: dict[int, _DoneLive] = {}
    try:
        for window in fold.done_windows:
            key = id(window.observation)
            if key not in live_by_id:
                live_by_id[key] = _evaluate_done(
                    client,
                    repo_id,
                    branch_name,
                    fold.bound_contract,
                    window.observation,
                )
    except AcquisitionError as error:
        return _acquisition(issue_url, error)

    done_candidates: list[tuple[str, RecordObservation, _DoneLive]] = []
    for window in fold.done_windows:
        live = live_by_id[id(window.observation)]
        if live.terminal_at is not None and (
            window.ended_at is None or live.terminal_at <= window.ended_at
        ):
            done_candidates.append((live.terminal_at, window.observation, live))
    done_candidates.sort(key=lambda item: (item[0], item[1].comment.id))

    stop = fold.terminal_stop
    if stop is not None:
        if done_candidates and done_candidates[0][0] <= stop.comment.created_at:
            terminal_at, terminal_done, live = done_candidates[0]
            current["done"] = _record_projection(terminal_done)
            current["bound_pr"] = live.pr.get("html_url") if live.pr else terminal_done.record["pr_ref"]
            current["bound_pr_head_sha"] = live.pr.get("head", {}).get("sha") if live.pr else None
            diagnostics = _terminal_violations(
                fold.diagnostics, fold.recognized_comments, terminal_at, terminal_done
            )
            return StatusResult(issue_url, "done", diagnostics, current)
        try:
            stop_diagnostics = _stop_diagnostics(
                client,
                parsed.owner,
                parsed.repo,
                repo_id,
                stop,
                fold.bound_start,
                context,
            )
        except AcquisitionError as error:
            return _acquisition(issue_url, error)
        if stop_diagnostics and stop_diagnostics[0].token == "terminal_dependency_mismatch":
            return StatusResult(issue_url, "halt", stop_diagnostics, current)
        return StatusResult(
            issue_url, "stopped", [*fold.diagnostics, *stop_diagnostics], current
        )

    if done_candidates:
        terminal_at, terminal_done, live = done_candidates[0]
        current["done"] = _record_projection(terminal_done)
        current["bound_pr"] = live.pr.get("html_url") if live.pr else terminal_done.record["pr_ref"]
        current["bound_pr_head_sha"] = live.pr.get("head", {}).get("sha") if live.pr else None
        diagnostics = _terminal_violations(
            fold.diagnostics, fold.recognized_comments, terminal_at, terminal_done
        )
        return StatusResult(issue_url, "done", diagnostics, current)

    if fold.diagnostics:
        return StatusResult(issue_url, "halt", list(fold.diagnostics), current)

    try:
        if active_done is not None:
            live = live_by_id[id(active_done)]
            if live.pr is not None:
                current["bound_pr"] = live.pr.get("html_url")
                current["bound_pr_head_sha"] = live.pr.get("head", {}).get("sha")
            if live.diagnostics:
                return StatusResult(issue_url, "halt", live.diagnostics, current)
            current["evidence_pending"] = live.pending
            if live.pr and live.pr.get("merged_at"):
                return StatusResult(issue_url, "in_progress", [], current)
            branch = client.branch(parsed.owner, parsed.repo, branch_name)
            current["branch"]["exists"] = branch is not None
            if branch is None:
                return StatusResult(
                    issue_url,
                    "halt",
                    [_diagnostic("branch_binding_mismatch", fold.bound_start.comment.url)],
                    current,
                )
            return StatusResult(issue_url, "in_progress", [], current)

        branch = client.branch(parsed.owner, parsed.repo, branch_name)
        candidates = [
            pr
            for pr in client.pull_requests(parsed.owner, parsed.repo, branch_name)
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
            return StatusResult(
                issue_url,
                "halt",
                [_diagnostic("branch_binding_mismatch", fold.bound_start.comment.url)],
                current,
            )
        return StatusResult(issue_url, "in_progress", [], current)
    except AcquisitionError as error:
        return _acquisition(issue_url, error)
