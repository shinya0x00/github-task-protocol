"""Plain-first Japanese and machine-exact CLI projections."""

from __future__ import annotations

from typing import Any

from .carrier import CarrierResult
from .status import StatusResult


AUTHORITY_NOTICE = "この出力は変更・完了・mergeの許可を与えません"
HALT_MESSAGES = {
    "invalid_record": "GTP Recordの形式、内容、編集状態のいずれかが不正です",
    "conflicting_records": "同じ役割のRecordが競合しています",
    "invalid_transition": "Recordの順序または参照関係が成立していません",
    "invalid_binding": "Issue、branch、PR、scopeの束縛が一致しません",
    "invalid_evidence": "Done Conditionに対応するEvidenceを確認できません",
    "stale_evidence": "EvidenceがDoneのsource head SHAと一致しません",
    "terminal_violation": "terminal stateの前後関係に違反するRecordまたはmergeがあります",
}


def _record(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    observation = {
        key: value[key]
        for key in ("url", "aliases", "comment_id")
        if key in value
    }
    return {
        "type": value.get("type"),
        "id": value.get("id"),
        "observation": observation,
    }


def _branch(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    observation = {"exists": value["exists"]} if "exists" in value else {}
    return {"name": value.get("name"), "observation": observation}


def _next_action(result: StatusResult) -> str:
    if result.state is None:
        return "retry_acquisition"
    if result.state == "unmanaged":
        return "post_contract"
    if result.state == "ready":
        return "post_start"
    if result.state == "halt":
        return "inspect_halt"
    if result.state == "done":
        return "none_done"
    if result.state == "stopped":
        return "none_stopped"
    if result.current.get("done") is not None:
        return "await_merge"
    if result.current.get("bound_pr") or result.current.get("pr_candidates"):
        return "post_done"
    return "continue_work"


def _primary_url(result: StatusResult) -> str:
    if result.acquisition_errors:
        resource = result.acquisition_errors[0].get("resource")
        return resource if isinstance(resource, str) else result.issue_url
    if result.diagnostics and result.diagnostics[0].urls:
        return result.diagnostics[0].urls[0]
    current = result.current
    if isinstance(current.get("bound_pr"), str):
        return current["bound_pr"]
    candidates = current.get("pr_candidates")
    if isinstance(candidates, list) and candidates and isinstance(candidates[0], str):
        return candidates[0]
    for kind in ("stop", "done", "start", "contract"):
        value = current.get(kind)
        if isinstance(value, dict) and isinstance(value.get("url"), str):
            return value["url"]
    return result.issue_url


def status_projection(result: StatusResult) -> dict[str, Any]:
    diagnostics = [item.projection() for item in result.diagnostics]
    current = result.current
    candidates = current.get("pr_candidates")
    candidate = candidates[0] if isinstance(candidates, list) and len(candidates) == 1 else None
    return {
        "gtp": "1.0",
        "command": "status",
        "issue_url": result.issue_url,
        "state": result.state,
        "halt_reason": diagnostics[0]["token"] if result.state == "halt" and diagnostics else None,
        "details": [item["detail"] for item in diagnostics if "detail" in item],
        "next_action": _next_action(result),
        "primary_url": _primary_url(result),
        "authority": "none",
        "acquisition": "incomplete" if result.acquisition_errors else "complete",
        "contract": _record(current.get("contract")),
        "start": _record(current.get("start")),
        "done": _record(current.get("done")),
        "stop": _record(current.get("stop")),
        "branch": _branch(current.get("branch")),
        "pr_candidate": candidate,
        "bound_pr": current.get("bound_pr"),
        "diagnostics": diagnostics,
        "acquisition_errors": result.acquisition_errors,
    }


def _status_text(machine: dict[str, Any]) -> list[str]:
    state = machine["state"] if machine["state"] is not None else "不明"
    action = machine["next_action"]
    branch = machine.get("branch")
    branch_name = branch.get("name") if isinstance(branch, dict) else None
    stop_text = {
        "unmanaged": "停止は不要です。Contractを記録する段階です",
        "ready": "停止は不要です。作業開始前です",
        "in_progress": "停止は不要です。作業中です",
        "halt": "このtransitionは進められません",
        "done": "停止は不要です。完了状態です",
        "stopped": "このIssueでは作業を再開しません",
        None: "状態を決められないため、このtransitionは進められません",
    }[machine["state"]]
    action_text = {
        "post_contract": "目的・変更範囲・完了条件をContractとして記録してください",
        "post_start": "Contractと作業branchをStartで束縛してください",
        "continue_work": "束縛されたbranchで作業を続けてください",
        "post_done": "完了条件を確認し、source headとEvidenceをDoneで提示してください",
        "await_merge": "Done ClaimとEvidenceを確認し、人間のnative merge判断を待ってください",
        "inspect_halt": "最初のURLを確認し、記録を推測で補わず人間へ戻してください",
        "none_done": "追加のprotocol actionはありません",
        "none_stopped": "必要なら新しいIssueでContractから開始してください",
        "retry_acquisition": "GitHub情報を再取得してください",
    }[action]
    if machine["state"] is None:
        errors = machine["acquisition_errors"]
        code = errors[0].get("code", "acquisition_incomplete") if errors else "acquisition_incomplete"
        reason = f"{code} — GitHub情報を完全に取得できず、stateを決定していません"
    elif machine["state"] == "halt":
        token = machine["halt_reason"]
        reason = f"{token} — {HALT_MESSAGES.get(token, 'protocol上の矛盾または不適合を確認しました')}"
    elif action == "await_merge":
        reason = "Done Claimは確認済みですが、native mergeはまだ確認できません"
    elif action == "post_done":
        reason = f"Start、作業branch {branch_name or '（名前不明）'}、PR candidateを確認しました"
    elif action == "continue_work":
        reason = f"Startと作業branch {branch_name or '（名前不明）'}を確認しました"
    else:
        reason = {
            "unmanaged": "有効なContractがありません",
            "ready": "有効なContractがあり、Startはまだありません",
            "done": "Done Claimのsource head、Evidence、native mergeを確認しました",
            "stopped": "有効なStop Recordを確認しました",
        }[machine["state"]]
    return [
        f"状態: {state}",
        f"停止要否: {stop_text}",
        f"次の行動: {action_text}",
        f"理由: {reason}",
        f"最初のURL: {machine['primary_url']}",
        f"非許可表示: {AUTHORITY_NOTICE}",
    ]


def present_status(result: StatusResult) -> tuple[list[str], dict[str, Any]]:
    machine = status_projection(result)
    return _status_text(machine), machine


def check_projection(result: CarrierResult) -> dict[str, Any]:
    record = None
    if result.record is not None:
        record = {"type": result.record["type"], "id": result.record["id"]}
    return {
        "gtp": "1.0",
        "command": "check",
        "recognized": result.recognized,
        "schema_valid": result.schema_valid,
        "contextual_checks": "not_run",
        "projected_state": None,
        "record": record,
        "errors": result.errors,
        "authority": "none",
    }


def present_check(result: CarrierResult) -> tuple[list[str], dict[str, Any]]:
    machine = check_projection(result)
    if not result.recognized:
        summary = "通常commentであり、GTP Carrierではありません"
    elif result.schema_valid:
        summary = "GTP Carrierとして認識し、offline schemaに適合しました"
    else:
        summary = "GTP Carrierとして認識しましたが、形式・JSON・schemaに適合しません"
    return [
        f"検査結果: {summary}",
        "contextual checks: Issue上の参照関係とstateは検査していません",
        f"非許可表示: {AUTHORITY_NOTICE}",
    ], machine


def present_input_error(message: str) -> tuple[list[str], dict[str, Any]]:
    return [
        "検査結果: 入力ファイルをUTF-8のMarkdown commentとして読めません",
        "contextual checks: 実行していません",
        f"非許可表示: {AUTHORITY_NOTICE}",
    ], {
        "gtp": "1.0",
        "command": "check",
        "recognized": None,
        "schema_valid": None,
        "contextual_checks": "not_run",
        "projected_state": None,
        "record": None,
        "errors": [{"code": "input_error", "message": message}],
        "authority": "none",
    }
