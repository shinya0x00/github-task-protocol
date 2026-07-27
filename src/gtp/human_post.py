import re
from typing import NamedTuple


SECTIONS = {
    "issue": ("目的", "ゴール", "現在わかっていること", "守る境界", "決定事項", "完了条件", "未確認事項", "人間に求める判断"),
    "pr": ("目的", "ゴール", "変更内容", "利用者への影響", "現在地", "未確認事項", "人間に求める判断"),
}
TECHNICAL_SECTION = "技術詳細"; DECISION_FIELDS = ("採用した方針", "今回は採用しない案", "見直す条件", "根拠・履歴")
FIXED_REFERENCE = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:(?:issues|pull)/[1-9]\d*#issuecomment-[1-9]\d*|blob/[0-9a-f]{40}/[^\s?#]+)")


class HumanPostResult(NamedTuple):
    target: str; valid: bool; errors: list[dict[str, str]]


def _visible_lines(body: str) -> list[tuple[int, str]]:
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    visible: list[tuple[int, str]] = []
    fence: tuple[str, int] | None = None
    for number, line in enumerate(body.splitlines(), start=1):
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        marker = stripped[:1]
        run = len(stripped) - len(stripped.lstrip(marker)) if marker in {"`", "~"} else 0
        if indent <= 3 and run >= 3:
            if fence is None:
                fence = marker, run
            elif marker == fence[0] and run >= fence[1] and not stripped[run:].strip():
                fence = None
            continue
        if fence is None:
            visible.append((number, line))
    return visible


def validate_human_post(body: str, target: str) -> HumanPostResult:
    required = SECTIONS.get(target)
    if required is None:
        return HumanPostResult(target, False, [{"code": "invalid_target", "path": "$.target"}])
    visible = _visible_lines(body)
    headings = [(index, number, line[3:]) for index, (number, line) in enumerate(visible) if line.startswith("## ") and line == f"## {line[3:].strip()}"]
    errors: list[dict[str, str]] = []; nonblank = [(number, line) for number, line in visible if line.strip()]
    if not nonblank or nonblank[0][1] != f"## {required[0]}":
        errors.append({"code": "invalid_first_section", "path": f"$.sections.{required[0]}"})
    positions: list[int] = []
    for title in required:
        matches = [item for item in headings if item[2] == title]
        if not matches:
            errors.append({"code": "missing_section", "path": f"$.sections.{title}"})
            continue
        if len(matches) > 1:
            errors.append({"code": "duplicate_section", "path": f"$.sections.{title}"})
            continue
        position, number, _ = matches[0]
        positions.append(position)
        next_heading = next((item[0] for item in headings if item[0] > position), len(visible))
        if not any(line.strip() for _, line in visible[position + 1 : next_heading]):
            errors.append({"code": "empty_section", "path": f"$.sections.{title}@line{number}"})
    if len(positions) == len(required) and positions != sorted(positions):
        errors.append({"code": "invalid_section_order", "path": "$.sections"})
    technical = [item for item in headings if item[2] == TECHNICAL_SECTION]
    if len(technical) > 1:
        errors.append({"code": "duplicate_section", "path": f"$.sections.{TECHNICAL_SECTION}"})
    elif technical:
        position, number, _ = technical[0]
        if not positions or position < max(positions) or position != headings[-1][0]:
            errors.append({"code": "invalid_technical_position", "path": f"$.sections.{TECHNICAL_SECTION}"})
        elif not any(line.strip() for _, line in visible[position + 1 :]):
            errors.append({"code": "empty_section", "path": f"$.sections.{TECHNICAL_SECTION}@line{number}"})
    if target == "issue":
        decision = next((item for item in headings if item[2] == "決定事項"), None)
        if decision is not None:
            end = next((item[0] for item in headings if item[0] > decision[0]), len(visible))
            lines = [line.strip() for _, line in visible[decision[0] + 1 : end] if line.strip()]; values: dict[str, str] = {}
            for field in DECISION_FIELDS:
                prefix = f"- {field}:"
                matches = [line[len(prefix):].strip() for line in lines if line.startswith(prefix)]
                code = "missing_decision_field" if not matches else "duplicate_decision_field" if len(matches) > 1 else "empty_decision_field" if not matches[0] else None
                if code:
                    errors.append({"code": code, "path": f"$.sections.決定事項.{field}"})
                else:
                    values[field] = matches[0]
            references = values.get("根拠・履歴")
            valid_references = references == "none" or references and all(FIXED_REFERENCE.fullmatch(item.strip()) for item in re.split(r"[、,]", references))
            if references and not valid_references:
                errors.append({"code": "invalid_decision_reference", "path": "$.sections.決定事項.根拠・履歴"})
    return HumanPostResult(target, not errors, errors)
