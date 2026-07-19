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


@dataclass(frozen=True)
class RecordObservation:
    record: dict[str, Any]
    comment: Comment

    @property
    def type(self) -> str:
        return self.record["type"]

    @property
    def id(self) -> str:
        return self.record["id"]


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
class FoldResult:
    recognized_count: int = 0
    active: dict[str, list[RecordObservation]] = field(
        default_factory=lambda: {kind: [] for kind in ("contract", "start", "done", "stop")}
    )
    valid_by_url: dict[str, RecordObservation] = field(default_factory=dict)
    invalid_urls: set[str] = field(default_factory=set)
    ids: dict[str, list[RecordObservation]] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    started_once: bool = False
    bound_contract: RecordObservation | None = None
    bound_start: RecordObservation | None = None
    terminal_stop: RecordObservation | None = None
    unsupported: list[Diagnostic] = field(default_factory=list)
