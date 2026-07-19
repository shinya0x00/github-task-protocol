from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Comment:
    id: int
    url: str
    body: str
    created_at: str
    updated_at: str
    github_login: str


@dataclass
class RecordObservation:
    record: dict[str, Any]
    comment: Comment
    aliases: list[Comment] = field(default_factory=list)
    superseded: bool = False

    @property
    def type(self) -> str:
        return self.record["type"]

    @property
    def id(self) -> str:
        return self.record["id"]

    @property
    def alias_urls(self) -> tuple[str, ...]:
        return tuple([self.comment.url, *(item.url for item in self.aliases)])

    def add_alias(self, comment: Comment) -> None:
        self.aliases.append(comment)


@dataclass(frozen=True)
class Diagnostic:
    token: str
    urls: tuple[str, ...]
    detail: dict[str, Any] = field(default_factory=dict)

    def projection(self) -> dict[str, Any]:
        result: dict[str, Any] = {"token": self.token, "urls": list(self.urls)}
        if self.detail:
            result["detail"] = self.detail
        return result


@dataclass
class RepairGroup:
    token: str
    urls: list[str]
    resolved: bool = False


@dataclass
class DoneWindow:
    observation: RecordObservation
    started_at: str
    ended_at: str | None = None


@dataclass(frozen=True)
class SuccessorFact:
    url: str
    exists: bool
    repository_id: int | None = None
    issue_id: int | None = None
    created_at: str | None = None


@dataclass
class FoldContext:
    issue_url: str | None = None
    issue_id: int | None = None
    issue_created_at: str | None = None
    repository_id: int | None = None
    successors: dict[str, SuccessorFact] = field(default_factory=dict)


@dataclass
class FoldResult:
    recognized_count: int = 0
    recognized_comments: list[Comment] = field(default_factory=list)
    active: dict[str, list[RecordObservation]] = field(
        default_factory=lambda: {kind: [] for kind in ("contract", "start", "done", "stop")}
    )
    valid_by_url: dict[str, RecordObservation] = field(default_factory=dict)
    observations_by_url: dict[str, RecordObservation] = field(default_factory=dict)
    invalid_urls: set[str] = field(default_factory=set)
    ids: dict[str, list[RecordObservation]] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    repair_groups: list[RepairGroup] = field(default_factory=list)
    started_once: bool = False
    had_valid_contract: bool = False
    bound_contract: RecordObservation | None = None
    bound_start: RecordObservation | None = None
    terminal_stop: RecordObservation | None = None
    done_windows: list[DoneWindow] = field(default_factory=list)
    open_done_window: DoneWindow | None = None


class IncompleteSnapshotError(ValueError):
    pass


class ContextAcquisitionRequired(ValueError):
    def __init__(self, resource: str):
        super().__init__(resource)
        self.resource = resource
