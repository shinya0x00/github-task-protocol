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
HALT_OBSERVATIONS = {
    "invalid_record": "Issue commentをGTP Recordとして読み取れませんでした",
    "conflicting_records": "Issueに同じ役割のGTP Recordが複数あります",
    "invalid_transition": "GTP Recordの順序または参照先を確認できませんでした",
    "invalid_binding": "Issueに記録されたbranch、PR、変更範囲の対応を確認できませんでした",
    "invalid_evidence": "Done Conditionに対応するEvidence URLまたは成功状態を確認できませんでした",
    "stale_evidence": "Evidenceが示すcommitとDoneが示すsource headが異なります",
    "terminal_violation": "完了または停止の後に追加のGTP Recordまたはmergeが見つかりました",
}
EVIDENCE_LIMITS = [
    "Check RunがDone Conditionの内容を十分に検査したこと",
    "Artifactの内容がDone Conditionを満たすこと",
    "Issue本文・通常commentに未解決事項がないこと",
    "actor本人性",
    "credential安全性",
    "GitHub外情報を参照しなかったこと",
]
PROBLEM_LABELS = ("何が問題か", "どこが問題か", "なぜそう判断したか", "どこを直すか", "何を直さないか", "次の安全な一手", "最初に確認するURL", "解決したと判断する条件")
HALT_PROBLEMS = {
    "invalid_record": ("対象IssueのGTP記録があるcomment", "最初のURLのcomment内容を確認し、過去commentは直さず、人間が必要ならStopと後継Issueを選ぶ（修正候補。根本的な修正責任は未確定）", "過去のIssue commentを編集・削除しない。GTPの仕様を変更しない", "最初のURLのcommentと前後のGTP記録をread-onlyで確認する", "過去commentを変更せず、人間判断後のvalid Stopで元Issueをstoppedにし、必要なら後継Issueで再開する"),
    "conflicting_records": ("対象IssueのRecord履歴", "競合したRecord履歴を確認し、人間がStopと後継Issueを選ぶ（修正候補。根本的な修正責任は未確定）", "既存Carrierの編集・削除、Recordのjoin、Record grammar", "最初のURLから同じ役割のLogical Recordをread-onlyで確認する", "既存Recordを変更せず、人間判断後のvalid Stopで元Issueをstoppedにし、後継Issueで一意のContractから再開する"),
    "invalid_transition": ("対象IssueのRecord履歴", "Record順序と参照を確認し、人間がStopと後継Issueを選ぶ（修正候補。根本的な修正責任は未確定）", "既存Carrierの編集・削除、Record順序の書換え、state語彙", "最初のURLと先行Recordをread-onlyで時系列確認する", "既存Recordを変更せず、人間判断後のvalid Stopで元Issueをstoppedにし、後継Issueで正しい順序から再開する"),
    "invalid_binding": ("Issueで変更してよい範囲とbranch・PRの対応", "最初のURLでIssueの変更範囲とPRの変更fileを比較する（修正候補。根本的な修正責任は未確定）", "Issueに既に投稿された記録とGTP.mdの仕様", "最初のURLでIssueの変更範囲とPRの変更fileをread-onlyで比較する", "再取得でIssueに記録されたbranch、PR、変更範囲の対応を確認できる、または人間判断後に後継Issueへ移る"),
    "invalid_evidence": ("Done Claim、Evidence resource、source head", "Evidenceのkey、kind、resource状態、source head binding（修正候補。根本的な修正責任は未確定）", "Contract、state語彙、既存Done Carrierの編集・削除", "最初のURLでEvidence resourceの状態とSHAをread-onlyで確認する", "Evidence resourceが成功状態でDoneのsource headと一致してhaltが消える、または人間判断後に後継Issueへ移る"),
    "stale_evidence": ("Done Claim、Evidence resource、source head", "新しいsource headを扱う通常の後継Issue（修正候補。根本的な修正責任は未確定）", "既存Done Carrier、Evidence URL、source履歴の書換え", "最初のURLでDone、Evidence、現在のPR headをread-onlyで比較する", "元のDoneと履歴を変更せずvalid Stopで元Issueをstoppedにし、後継Issueで新しいheadへ束縛する"),
    "terminal_violation": ("terminal履歴と後続Recordまたはmerge", "必要作業を扱う通常の別Issue（修正候補。元Issueの修正責任は確定しない）", "元Issueのterminal履歴、新Record追加、元Issueの回復claim", "先に成立したterminal resultを保持し、別Issueの確認条件を人間と決める", "元Issueでは解消不能。terminal resultとviolationを保持し、別IssueのContract、PR、Evidence、native mergeを確認する"),
}
CHECK_PROBLEMS = {
    "unrecognized": ("投稿前MarkdownにExact MarkerがなくGTP Carrierとして認識できません", "投稿前Carrier", "投稿予定MarkdownのExact MarkerとCarrier全体（修正候補。根本的な修正責任は未確定）", "未確認のIssue、branch、PR、protocol vocabulary", "入力fileに完全なCarrierを作成してgtp checkを再実行する", "recognizedとschema_validがともにtrueになる"),
    "format": ("投稿前GTP CarrierのMarkdown構造が形式に適合しません", "投稿前Carrier", "error pathが示すCarrier構造（修正候補。根本的な修正責任は未確定）", "未確認のIssue、branch、PR、Record grammar", "error codeとpathの入力箇所を修正してgtp checkを再実行する", "recognizedとschema_validがともにtrueになる"),
    "json": ("投稿前GTP CarrierのJSONをstrict JSONとして読めません", "投稿前CarrierのJSON", "error pathが示すJSON（修正候補。根本的な修正責任は未確定）", "未確認のIssue、branch、PR、GTP state", "error codeとpathのJSONを修正してgtp checkを再実行する", "recognizedとschema_validがともにtrueになる"),
    "schema": ("投稿前GTP Recordがclosed schemaに適合しません", "投稿前CarrierのRecord JSON", "error pathが示すschema不適合箇所（修正候補。根本的な修正責任は未確定）", "未確認のIssue、branch、PR、公開protocol vocabulary", "error codeとpathのfieldだけを修正してgtp checkを再実行する", "recognizedとschema_validがともにtrueになる"),
}
SCHEMA_ERROR_CODES = {"duplicate_value", "invalid_condition_id", "invalid_type", "invalid_url", "invalid_value", "missing_field", "unknown_field"}


def _problem_lines(values: tuple[str, ...]) -> list[str]:
    return ["問題の整理:"] + [
        f"  {index}. {label}: {value}"
        for index, (label, value) in enumerate(zip(PROBLEM_LABELS, values), start=1)
    ]


def _halt_observation(machine: dict[str, Any], token: str) -> str:
    diagnostics = machine.get("diagnostics")
    diagnostic = (
        diagnostics[0] if isinstance(diagnostics, list) and diagnostics else None
    )
    detail = diagnostic.get("detail") if isinstance(diagnostic, dict) else None
    paths = detail.get("paths") if isinstance(detail, dict) else None
    safe_paths = (
        [path for path in paths if isinstance(path, str)]
        if isinstance(paths, list)
        else []
    )
    if token == "invalid_binding" and safe_paths:
        task_context = machine.get("task_context")
        scope = task_context.get("scope") if isinstance(task_context, dict) else None
        safe_scope = (
            [path for path in scope if isinstance(path, str)]
            if isinstance(scope, list)
            else []
        )
        if safe_scope:
            return (
                f"このIssueで変更してよい範囲は{', '.join(safe_scope)}ですが、"
                f"PRに範囲外のfile {', '.join(safe_paths)}が含まれています"
            )
        return f"PRに変更範囲外のfile {', '.join(safe_paths)}が含まれています"
    return HALT_OBSERVATIONS.get(token, "protocol上の不適合を観測しました")


def _acquisition_observation(error: dict[str, Any] | None) -> str:
    code = (
        error.get("code", "acquisition_incomplete")
        if error
        else "acquisition_incomplete"
    )
    observation = f"acquisition error: {code}"
    status = error.get("status") if error else None
    if isinstance(status, int) and not isinstance(status, bool):
        observation += f"; status: {status}"
    return observation


def _status_problem(machine: dict[str, Any]) -> tuple[str, ...] | None:
    if machine["state"] == "halt":
        token = machine["halt_reason"] or "unknown"
        layer, repair, excluded, next_step, resolution = HALT_PROBLEMS.get(
            token,
            (
                "所有層未確定",
                "修正責任未確定",
                "未確認のresource、Record grammar、state語彙",
                "最初のURLをread-onlyで確認して人間へ戻す",
                "同じresourceを再取得し、期待するstateまたは別Issueの確認条件を確認する",
            ),
        )
        if token == "invalid_binding":
            diagnostics = machine.get("diagnostics")
            diagnostic = (
                diagnostics[0]
                if isinstance(diagnostics, list) and diagnostics
                else None
            )
            detail = diagnostic.get("detail") if isinstance(diagnostic, dict) else None
            paths = detail.get("paths") if isinstance(detail, dict) else None
            safe_paths = (
                [path for path in paths if isinstance(path, str)]
                if isinstance(paths, list)
                else []
            )
            if safe_paths:
                what = f"PRに、このIssueで変更してよい範囲外のfile {', '.join(safe_paths)}があります"
                repair = (
                    "範囲外のfileをこのPRから外すか、必要なら通常の後継Issueで扱う"
                    "（修正候補。最終判断は人間）"
                )
            else:
                what = "Issueに記録されたbranch、PR、変更範囲の対応を確認できません"
        else:
            what = HALT_MESSAGES.get(token, "protocol上の不適合を確認しました")
        return (
            what,
            layer,
            _halt_observation(machine, token),
            repair,
            excluded,
            next_step,
            machine["primary_url"],
            resolution,
        )
    if machine["state"] is None:
        errors = machine["acquisition_errors"]
        error = errors[0] if errors and isinstance(errors[0], dict) else None
        return (
            "GitHub情報を完全に取得できずstateを決定できません",
            "GitHub取得経路",
            _acquisition_observation(error),
            "取得・認証・snapshot経路（修正責任未確定）",
            "GTP Record、state、halt reason",
            "同じresourceをread-onlyで再取得する",
            machine["primary_url"],
            "取得がcompleteとなりstateを再構成できる",
        )
    return None


def _check_problem(result: CarrierResult) -> tuple[str, ...] | None:
    if result.recognized and result.schema_valid:
        return None
    if not result.recognized:
        category = "unrecognized"
        why = "check result: recognized=false"
    else:
        error = result.errors[0] if result.errors else {}
        code = error.get("code", "invalid_carrier")
        path = error.get("path", "$")
        category = (
            "json"
            if code in {"duplicate_key", "invalid_json"}
            else "schema"
            if code in SCHEMA_ERROR_CODES
            else "format"
        )
        why = f"check error: {code} at {path}"
    what, layer, repair, excluded, next_step, resolution = CHECK_PROBLEMS[category]
    return (
        what,
        layer,
        why,
        repair,
        excluded,
        next_step,
        "URLなし（投稿前入力）",
        resolution,
    )


def _input_error_problem() -> tuple[str, ...]:
    return (
        "入力fileをUTF-8のMarkdown commentとして取得できません",
        "投稿前入力の取得経路",
        "input_errorを観測しました",
        "入力fileの存在、読取権限、UTF-8 encoding（修正候補。根本的な修正責任は未確定）",
        "未確認のIssue、branch、PR、GTP Record",
        "入力fileを読める状態にしてgtp checkを再実行する",
        "URLなし（投稿前入力）",
        "input_errorがなくなりCarrier検査結果を取得できる",
    )


def _record(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    observation = {
        key: value[key]
        for key in ("url", "aliases", "comment_id")
        if key in value
    }
    result = {
        "type": value.get("type"),
        "id": value.get("id"),
        "observation": observation,
    }
    if isinstance(value.get("content"), dict):
        result["content"] = value["content"]
    return result


def _content(record: dict[str, Any] | None) -> dict[str, Any]:
    value = record.get("content") if isinstance(record, dict) else None
    return value if isinstance(value, dict) else {}


def _task_context(
    *,
    issue_url: str,
    state: str | None,
    acquisition_complete: bool,
    contract: dict[str, Any] | None,
    start: dict[str, Any] | None,
    done: dict[str, Any] | None,
    branch: dict[str, Any] | None,
    pr: str | None,
) -> dict[str, Any]:
    contract_content = _content(contract)
    start_content = _content(start)
    done_content = _content(done)
    done_conditions = contract_content.get("done_conditions")
    evidence = done_content.get("evidence")
    conditions: dict[str, dict[str, Any]] = {}
    if isinstance(done_conditions, dict):
        evidence_map = evidence if isinstance(evidence, dict) else {}
        for condition_id in sorted(done_conditions):
            condition = done_conditions[condition_id]
            if not isinstance(condition, dict):
                continue
            evidence_url = evidence_map.get(condition_id)
            conditions[condition_id] = {
                "text": condition.get("text"),
                "evidence_kind": condition.get("evidence_kind"),
                "evidence_url": evidence_url if isinstance(evidence_url, str) else None,
                "evidence_status": (
                    "presented" if isinstance(evidence_url, str) else "not_presented"
                ),
            }

    not_proven: list[str] = []
    if not acquisition_complete:
        not_proven.append("GitHub情報の取得が不完全なためtask context未確認")
    elif not contract_content:
        not_proven.append("Contract未確認")
    else:
        missing = [
            f"{condition_id}: Evidence未提示"
            for condition_id, condition in conditions.items()
            if condition["evidence_status"] == "not_presented"
        ]
        not_proven.extend(missing)
        if done is None:
            not_proven.append("Done Claim未提示")
        else:
            if state in {"in_progress", "done"} and not missing:
                not_proven.append(
                    "Done Conditionの自然言語上の充足は自動判定していない"
                )
            if state == "in_progress":
                not_proven.append("native merge未確認")
            elif state == "halt" and not missing:
                not_proven.append("protocol不適合が未解決")
            elif state == "stopped":
                not_proven.append("このIssueは完了を証明せず停止済み")

    branch_name = branch.get("name") if isinstance(branch, dict) else None
    if not isinstance(branch_name, str):
        candidate = start_content.get("branch")
        branch_name = candidate if isinstance(candidate, str) else None
    scope = contract_content.get("scope")
    return {
        "goal": contract_content.get("goal"),
        "scope": scope if isinstance(scope, list) else [],
        "handoff_url": issue_url,
        "handoff_semantics": "Issue本文・通常commentの意味は自動判定しない",
        "branch": branch_name,
        "pr": pr,
        "conditions": conditions,
        "not_proven": not_proven,
        "evidence_limits": list(EVIDENCE_LIMITS),
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
    contract = _record(current.get("contract"))
    start = _record(current.get("start"))
    done = _record(current.get("done"))
    stop = _record(current.get("stop"))
    branch = _branch(current.get("branch"))
    bound_pr = current.get("bound_pr")
    done_pr = _content(done).get("pr_ref")
    pr = (
        bound_pr
        if isinstance(bound_pr, str)
        else candidate
        if isinstance(candidate, str)
        else done_pr
        if isinstance(done_pr, str)
        else None
    )
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
        "contract": contract,
        "start": start,
        "done": done,
        "stop": stop,
        "branch": branch,
        "pr_candidate": candidate,
        "bound_pr": bound_pr,
        "diagnostics": diagnostics,
        "acquisition_errors": result.acquisition_errors,
        "task_context": _task_context(
            issue_url=result.issue_url,
            state=result.state,
            acquisition_complete=not result.acquisition_errors,
            contract=contract,
            start=start,
            done=done,
            branch=branch,
            pr=pr,
        ),
    }


def _plain_summary(machine: dict[str, Any], context: dict[str, Any]) -> list[str]:
    state = machine["state"]
    conclusion = (
        "GitHub情報を最後まで取得できていないため、まだ判断できません。"
        if state is None
        else "このIssueの完了は確認できません。作業を止めて人が確認してください。"
        if state == "halt"
        else (
            "Done ClaimのEvidence bindingとnative mergeを確認しました。"
            "条件内容の充足はEvidenceを読んで判断してください。"
        )
        if state == "done"
        else "このIssueは完了を主張せず終了しています。"
        if state == "stopped"
        else (
            "Done ClaimのEvidence bindingを確認しましたが、マージはまだです。"
            "条件内容の充足はEvidenceを読んで判断してください。"
        )
        if machine["next_action"] == "await_merge"
        else "このIssueはまだ作業途中です。"
    )
    lines = ["かんたんな説明:", f"  結論: {conclusion}"]
    if state is None:
        lines.extend(
            [
                f"  次にすること: GitHub情報をもう一度取得してください。最初の確認先: {machine['primary_url']}",
                "  大事な点: 情報を取得できないことと、記録に矛盾があることは別です。",
                "  ここまでが人向けの説明です。続くJSONは機械処理用です。",
            ]
        )
        return lines
    if state == "halt":
        lines.append(f"  次にすること: 原因の記録を開いてください: {machine['primary_url']}")

    goal = context.get("goal")
    if isinstance(goal, str):
        scope = context.get("scope")
        scope_text = "、".join(scope) if isinstance(scope, list) and scope else "記録なし"
        lines.extend(
            [
                f"  この作業の目的: {goal}",
                f"  変更してよい場所: {scope_text}",
                f"  作業場所: branch {context.get('branch') or '未確認'}"
                f" / PR {context.get('pr') or '未確認'}",
                "  未確認事項の確認先: "
                f"{context.get('handoff_url') or machine['issue_url']}"
                "（Issue本文・通常commentの意味は自動判定していません）",
            ]
        )

    conditions = context.get("conditions")
    if not isinstance(conditions, dict) or not conditions:
        lines.append("  ここまでが人向けの説明です。続くJSONは機械処理用です。")
        return lines
    presented = [
        (condition_id, condition)
        for condition_id, condition in conditions.items()
        if condition.get("evidence_status") == "presented"
    ]
    missing = [
        (condition_id, condition)
        for condition_id, condition in conditions.items()
        if condition.get("evidence_status") == "not_presented"
    ]
    evidence_confirmed = state == "done" or machine["next_action"] == "await_merge"
    if presented:
        lines.append(
            "  Evidence bindingを確認した条件（条件内容の充足は自動判定していません）:"
            if evidence_confirmed
            else "  記録に確認資料へのリンクがある条件（達成済みとはまだ断定しません）:"
        )
        for condition_id, condition in presented:
            lines.extend(
                [
                    f"    - {condition.get('text') or '説明未記録'}（識別子: {condition_id}）",
                    f"      確認資料: {condition.get('evidence_url')}",
                ]
            )
    if missing:
        lines.append("  確認資料が足りない条件:")
        for condition_id, condition in missing:
            lines.extend(
                [
                    f"    - {condition.get('text') or '説明未記録'}（識別子: {condition_id}）",
                    "      不足しているもの: 条件を確認するための証拠リンク",
                ]
            )
    if state == "halt":
        lines.append(
            "  大事な点: 足りない記録を推測で補わないでください。"
            "この表示だけでは変更・完了・mergeできません。"
        )
    lines.append("  ここまでが人向けの説明です。続くJSONは機械処理用です。")
    return lines


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
        "post_done": (
            "Issue本文・通常commentの未確認事項と完了条件を確認し、"
            "source headとEvidenceをDoneで提示してください"
        ),
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
        reason = "Done ClaimのEvidence bindingは確認済みですが、native mergeはまだ確認できません"
    elif action == "post_done":
        reason = f"Start、作業branch {branch_name or '（名前不明）'}、PR candidateを確認しました"
    elif action == "continue_work":
        reason = f"Startと作業branch {branch_name or '（名前不明）'}を確認しました"
    else:
        reason = {
            "unmanaged": "有効なContractがありません",
            "ready": "有効なContractがあり、Startはまだありません",
            "done": "Done Claimのsource head、Evidence binding、native mergeを確認しました",
            "stopped": "有効なStop Recordを確認しました",
        }[machine["state"]]
    lines = [
        f"状態: {state}",
        f"停止要否: {stop_text}",
        f"次の行動: {action_text}",
        f"理由: {reason}",
        f"最初のURL: {machine['primary_url']}",
        f"非許可表示: {AUTHORITY_NOTICE}",
    ]
    context = machine["task_context"]
    lines.extend(_plain_summary(machine, context))
    goal = context.get("goal")
    if not isinstance(goal, str):
        return lines
    return lines


def present_status(result: StatusResult) -> tuple[list[str], dict[str, Any]]:
    machine = status_projection(result)
    lines = _status_text(machine)
    problem = _status_problem(machine)
    if problem is not None:
        lines[6:6] = _problem_lines(problem)
    return lines, machine


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
    lines = [
        f"検査結果: {summary}",
        "contextual checks: Issue上の参照関係とstateは検査していません",
        f"非許可表示: {AUTHORITY_NOTICE}",
    ]
    problem = _check_problem(result)
    if problem is not None:
        lines.extend(_problem_lines(problem))
    return lines, machine


def present_input_error(message: str) -> tuple[list[str], dict[str, Any]]:
    lines = [
        "検査結果: 入力ファイルをUTF-8のMarkdown commentとして読めません",
        "contextual checks: 実行していません",
        f"非許可表示: {AUTHORITY_NOTICE}",
    ]
    lines.extend(_problem_lines(_input_error_problem()))
    return lines, {
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
