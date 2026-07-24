"""Deterministic offline validation for human-facing GitHub Markdown."""
from __future__ import annotations
import re
from typing import NamedTuple
REQUIRED_SECTIONS = ("何が起きたか", "何が変わるか", "何は変わらないか", "人間が次に判断すること")
TECHNICAL_SECTION = "技術的な検証情報"
INTERNAL_TERMS = ("Acquisition Error", "terminal_violation", "invalid_binding", "stale_evidence", "invalid_record", "schema_valid", "Done Condition", "Exact Marker", "GTP Record", "closed schema", "strict JSON", "Done Claim", "halt_reason", "head_sha", "Carrier", "Contract", "Evidence", "Records", "Record", "binding", "scope", "Start", "Done", "Stop", "halt")
COMMANDS = ("python3", "unittest", "pytest", "python", "docker", "kubectl", "cargo", "curl", "wget", "pnpm", "yarn", "node", "make", "git", "gh", "gtp", "uvx", "uv", "pip", "npm", "go")
JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff々〆ヵヶ]")
LATIN_RE = re.compile(r"[A-Za-z]")
TERM_RE = re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(re.escape(term) for term in sorted(INTERNAL_TERMS, key=len, reverse=True)) + r")(?![A-Za-z0-9_])")
EXPLANATION_RE = re.compile(r"^（[^）]*[\u3040-\u30ff\u3400-\u9fff々〆ヵヶ][^）]*）")
COMMAND_RE = re.compile(r"^(?:[$%]\s+|`?(?:" + "|".join(re.escape(command) for command in COMMANDS) + r")(?![A-Za-z0-9_-]))")
SHA_LEAD_RE = re.compile(r"^`?[0-9A-Fa-f]{7,40}`?(?![A-Za-z0-9_])")
FULL_SHA_RE = re.compile(r"(?<![A-Za-z0-9_])[0-9A-Fa-f]{40}(?![A-Za-z0-9_])")
TECHNICAL_URL_RE = re.compile(r"https://github\.com/[^\s/]+/[^\s/]+/(?:runs/[1-9][0-9]*(?=$|[\s\u3040-\u30ff\u3400-\u9fff々〆ヵヶ、。！？）」』】〉》)\]}>`]|[.,;:!?](?:\s|$))|blob/[0-9A-Fa-f]{40}/[^\s?#]+)")
OUTPUT_RE = re.compile(r"(?<![A-Za-z0-9_])(?:stdout|stderr|exit code|検証結果|実行結果)\s*[:：]", re.I)
PREFIX_RE = re.compile(r"^(?:(?:>\s*|[-*+]\s+|[0-9]{1,9}[.)]\s+))+(?:\[[ xX]\]\s+)?")
RAW_HTML_RE = re.compile(r"^ {0,3}<(?P<tag>pre|script|style|textarea)(?:[\s>]|$)", re.I)
RAW_BLOCK_RE = re.compile(r"^ {0,3}</?(?:address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)(?:[\s/>]|$)", re.I)
RAW_TAG_RE = re.compile(r'''^ {0,3}(?:</[A-Za-z][A-Za-z0-9-]*[ \t]*>|<[A-Za-z][A-Za-z0-9-]*(?:[ \t]+[A-Za-z_:][A-Za-z0-9_.:-]*(?:[ \t]*=[ \t]*(?:[^\s"'=<>`]+|'[^']*'|"[^"]*"))?)*[ \t]*/?>)[ \t]*$''')
def _code_spans(text: str) -> list[tuple[int, int, int]]:
    spans, cursor = [], 0
    while cursor < len(text):
        start = text.find("`", cursor)
        if start < 0: break
        opening = start + 1
        while opening < len(text) and text[opening] == "`": opening += 1
        size = opening - start
        if (start - len(text[:start].rstrip("\\"))) % 2: cursor = opening; continue
        limit = text.find("\n", opening); limit = len(text) if limit < 0 else limit
        search = opening
        while (closing := text.find("`" * size, search, limit)) >= 0:
            if (closing == 0 or text[closing - 1] != "`") and (closing + size == len(text) or text[closing + size] != "`"):
                spans.append((start, closing + size, size)); cursor = closing + size; break
            search = closing + 1
        else: cursor = opening
    return spans
class HumanPostResult(NamedTuple): target: str; valid: bool; errors: list[dict[str, str]]
def _section_end(lines: list[str], start: int) -> int: return next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
def _prose(line: str) -> str: return re.sub(r"^\|[ \t]*", "", PREFIX_RE.sub("", line.lstrip()).lstrip()).lstrip()
def _block_leaf(line: str) -> str:
    text = line
    while True:
        quote = re.match(r"^ {0,3}>[ \t]?", text); item = re.match(r"^ {0,3}(?:[-*+]|[0-9]{1,9}[.)])[ \t]", text)
        if not (match := quote or item): return text
        text = text[match.end() :]
def _pipe_cells(line: str) -> list[str]:
    text = line.strip(); cells, start, found = [], 0, False
    for index, char in enumerate(text):
        if char == "|" and (index - len(text[:index].rstrip("\\"))) % 2 == 0:
            cells.append(text[start:index]); start = index + 1; found = True
    if not found: return []
    cells.append(text[start:]); return cells[1 if not cells[0].strip() else 0 : len(cells) - (1 if not cells[-1].strip() else 0)]
def _table_delimiter(line: str) -> int: cells = _pipe_cells(line); return len(cells) if cells and all(re.fullmatch(r"[ \t]*:?-{3,}:?[ \t]*", cell) for cell in cells) else 0
def _fence_parts(line: str) -> tuple[tuple[str, ...], str, int]:
    text, containers = line, []
    while True:
        quote = re.match(r"^ {0,3}(>)[ \t]?", text); item = re.match(r"^ {0,3}([-*+]|[0-9]{1,9}[.)])[ \t]{1,4}(?![ \t])", text)
        if not (match := quote or item): return tuple(containers), text, len(line[: len(line) - len(text)].expandtabs(4))
        containers.append(match.group(1)); text = text[match.end() :]
def _after_indent(text: str, start: int, target: int) -> str | None:
    if not text.strip(): return ""
    column = start
    for index, char in enumerate(text):
        if column >= target or char not in " \t": return text[index:] if column >= target else None
        column = column + 1 if char == " " else column + 4 - column % 4
    return "" if column >= target else None
def _container_columns(line: str) -> list[int]:
    text, columns = line, []
    while True:
        quote = re.match(r"^ {0,3}(>)[ \t]?", text); item = re.match(r"^ {0,3}([-*+]|[0-9]{1,9}[.)])[ \t]{1,4}(?![ \t])", text); match = quote or item
        if not match: return columns
        columns.append(len(line[: len(line) - len(text) + match.start(1)].expandtabs(4))); text = text[match.end() :]
def _fence_open(line: str) -> tuple[tuple[str, ...], str, int, int] | None:
    containers, text, indent = _fence_parts(line); match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", text)
    return None if not match or (match.group(1)[0] == "`" and "`" in match.group(2)) else (containers, match.group(1)[0], len(match.group(1)), indent)
def _container_content(line: str, opened: tuple[str, ...], opened_indent: int, siblings: bool = False) -> str | None:
    containers, text, indent = _fence_parts(line)
    if not opened: return line
    current = tuple(re.sub(r"^[0-9]+", "#", marker) for marker in containers); expected = tuple(re.sub(r"^[0-9]+", "#", marker) for marker in opened)
    exact = containers == opened; has_list = any(marker != ">" for marker in opened); columns = _container_columns(line)
    if (not siblings and has_list and any(column >= opened_indent for column in columns)) or (exact and (siblings or not has_list)) or (siblings and (current == expected or (current and expected[-len(current) :] == current and indent >= opened_indent))): return text
    outer = tuple(marker for marker in opened if marker == ">") if has_list else None
    if outer is not None and containers == outer: return _after_indent(text, indent, opened_indent)
    return None
def _fence_content(line: str, fence: tuple[tuple[str, ...], str, int, int]) -> str | None: return _container_content(line, fence[0], fence[3])
def _fence_close(line: str, fence: tuple[tuple[str, ...], str, int, int]) -> bool: text = _fence_content(line, fence); return text is not None and bool(re.fullmatch(rf" {{0,3}}{re.escape(fence[1])}{{{fence[2]},}}[ \t]*", text))
def _raw_open(line: str, type7: bool) -> tuple[str, bool] | None:
    if match := RAW_HTML_RE.match(line): return rf"</{match.group('tag')}\s*>", True
    if match := re.match(r"^ {0,3}(<!--|<\?)", line): return (r"-->" if match.group(1) == "<!--" else r"\?>"), False
    if re.match(r"^ {0,3}<!\[CDATA\[", line): return r"\]\]>", False
    if re.match(r"^ {0,3}<![A-Z]", line): return r">", False
    if RAW_BLOCK_RE.match(line) or (type7 and RAW_TAG_RE.match(line)): return "", False
    return None
def _lazy_line(line: str, previous: str) -> bool:
    leaf = _block_leaf(line); parts = _fence_parts(line); markers = [marker for marker in parts[0] if marker != ">"]
    interrupt = ">" in parts[0] or bool(markers and parts[1].strip() and (markers[0] in "-*+" or (markers[0][:-1].isdigit() and int(markers[0][:-1]) == 1)))
    return bool(leaf.strip()) and not interrupt and not _fence_open(line) and not _raw_open(line, False) and not bool(re.match(r"^ {0,3}(?:#{1,6}(?:[ \t]+|$)|(?:-+|=+)[ \t]*$)", leaf)) and not bool(re.fullmatch(r" {0,3}(?:(?:\*[ \t]*){3,}|(?:_[ \t]*){3,})", leaf)) and not ((count := _table_delimiter(leaf)) > 0 and count == len(_pipe_cells(previous)))
def _comment_continues(line: str, owner: tuple[tuple[str, ...], int], previous: str) -> bool:
    if not owner[0]: return _lazy_line(line, previous)
    content = _container_content(line, *owner); columns = _container_columns(line)
    if content is None: return not columns and _lazy_line(line, previous)
    return not any(column >= owner[1] for column in columns) and _lazy_line(content, previous)
def _raw_closed(line: str, raw: tuple[str, bool]) -> bool: return not line.strip() if not raw[0] else bool(re.search(raw[0], line, re.I if raw[1] else 0))
def _visible_markdown(body: str) -> str:
    output, comment, comment_container, comment_previous, fence, raw_block, paragraph, previous_leaf, list_state = [], False, None, "", None, None, False, "", None
    for raw in body.splitlines(keepends=True):
        line = raw.rstrip("\r\n"); ending = raw[len(line) :]
        list_text = _container_content(line, *list_state, True) if list_state else None
        list_ended = bool(list_state and list_text is None and line.strip())
        if list_ended: list_state = None
        if comment and comment_container and not _comment_continues(line, comment_container, comment_previous): comment = False; comment_container = None; comment_previous = ""
        if fence is not None and _fence_content(line, fence) is not None:
            output.append(raw); fence = None if _fence_close(line, fence) else fence; paragraph = False; previous_leaf = ""; continue
        fence = None
        if raw_block and (raw_text := _container_content(line, raw_block[2], raw_block[3])) is not None:
            output.append(" " * len(line) + ending); raw_block = None if _raw_closed(raw_text, raw_block[:2]) else raw_block; paragraph = False; previous_leaf = ""; continue
        raw_block = None
        if opening := (None if comment else _fence_open(line)): fence = opening; output.append(raw); paragraph = False; previous_leaf = ""; continue
        containers, raw_text, indent = _fence_parts(line)
        if list_state and list_text is not None and not (any(marker != ">" for marker in containers) and indent > list_state[1]): containers, raw_text, indent = list_state[0], list_text, list_state[1]
        if raw_rule := (None if comment else _raw_open(raw_text, not paragraph)): raw_block = (*raw_rule, containers, indent); output.append(" " * len(line) + ending); raw_block = None if _raw_closed(raw_text, raw_rule) else raw_block; paragraph = False; previous_leaf = ""; continue
        chars, cursor, code_spans = list(line), 0, [(start, end) for start, end, _ in _code_spans(line)]
        comment_persists = comment; comments_allowed = paragraph or not raw_text.startswith(("    ", "\t"))
        while cursor < len(line):
            if comment:
                end = line.find("-->", cursor); boundary = len(line) if end < 0 else end + 3
                chars[cursor:boundary] = " " * (boundary - cursor); cursor = boundary
                if end < 0: break
                comment = False; comment_container = None; comment_previous = ""
            else:
                if not comments_allowed: break
                start = line.find("<!--", cursor)
                if start < 0: break
                if code_span := next((span for span in code_spans if span[0] <= start < span[1]), None): cursor = code_span[1]; continue
                cursor, comment = start, True
                comment_container = (containers, indent); comment_previous = raw_text
                comment_persists = _lazy_line(raw_text, previous_leaf)
        if comment and comment_persists: comment_previous = raw_text
        if comment and not comment_persists: comment = False; comment_container = None; comment_previous = ""
        visible_line = "".join(chars); output.append(visible_line + ending); leaf = _block_leaf(visible_line)
        was_paragraph = paragraph; table = paragraph and (count := _table_delimiter(leaf)) > 0 and count == len(_pipe_cells(previous_leaf)); setext = paragraph and bool(re.fullmatch(r" {0,3}=+[ \t]*", leaf)); boundary = not paragraph and bool(re.match(r"^ {0,3}(?:\[[^\]]+\]:[ \t]+\S|[-+*][ \t]*$|[0-9]{1,9}[.)][ \t]*$)", leaf))
        block = leaf.startswith(("    ", "\t")) or bool(re.match(r"^ {0,3}#{1,6}(?:[ \t]+|$)", leaf)) or bool(re.fullmatch(r" {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})", leaf)) or table or setext or boundary
        paragraph = bool(leaf.strip()) and not block; previous_leaf = leaf
        parts = _fence_parts(visible_line)
        markers = [marker for marker in parts[0] if marker != ">"]
        if markers and (not was_paragraph or list_ended or (parts[1].strip() and (markers[0] in "-*+" or (markers[0][:-1].isdigit() and int(markers[0][:-1]) == 1)))): list_state = (parts[0], parts[2])
    return "".join(output)
def _heading_lines(lines: list[str]) -> list[str]:
    headings, fence = list(lines), None
    for index, line in enumerate(lines):
        if fence is not None and _fence_content(line, fence) is not None:
            headings[index] = ""; fence = None if _fence_close(line, fence) else fence; continue
        fence = None
        opening = _fence_open(line)
        if opening: fence = opening; headings[index] = ""
    return headings
def validate_human_post(body: str, target: str) -> HumanPostResult:
    """Validate explicit Markdown structure without inferring prose meaning."""
    visible = _visible_markdown(body)
    lines, errors = visible.splitlines(), []
    headings = _heading_lines(lines)
    def add(code: str, path: str) -> None:
        error = {"code": code, "path": path}
        if error not in errors: errors.append(error)
    first_nonblank = next((line for line in lines if line.strip()), "")
    if first_nonblank != f"## {REQUIRED_SECTIONS[0]}": add("invalid_first_heading", "$.headings[0]")
    occurrences = {name: [i for i, line in enumerate(headings) if line == f"## {name}"] for name in (*REQUIRED_SECTIONS, TECHNICAL_SECTION)}
    positions = []
    for number, name in enumerate(REQUIRED_SECTIONS):
        found, path = occurrences[name], f"$.sections[{number}]"
        if not found: add("missing_section", path); continue
        if len(found) > 1: add("duplicate_section", path); continue
        positions.append(found[0])
        if not any(_prose(line).strip() for line in lines[found[0] + 1 : _section_end(headings, found[0])]): add("empty_section", path)
    if len(positions) == len(REQUIRED_SECTIONS) and positions != sorted(positions): add("invalid_section_order", "$.sections")
    lead_positions = occurrences[REQUIRED_SECTIONS[0]]
    if len(lead_positions) == 1:
        start = lead_positions[0]
        lead_lines = lines[start + 1 : _section_end(headings, start)]
        lead = "\n".join(lead_lines)
        first_prose = next((_prose(line) for line in lead_lines if _prose(line).strip()), "")
        if first_prose and (COMMAND_RE.search(first_prose) or SHA_LEAD_RE.search(first_prose)): add("command_lead", "$.sections[0].lead")
        japanese = len(JAPANESE_RE.findall(lead))
        if japanese == 0 or len(LATIN_RE.findall(lead)) > japanese: add("english_lead", "$.sections[0]")
        explained: set[str] = set()
        code_spans = _code_spans(lead)
        inline_terms = {(start + 1, end - 1) for start, end, size in code_spans if size == 1}
        for match in TERM_RE.finditer(lead):
            term = match.group(0)
            if term in explained: continue
            suffix = lead[match.end() :]
            key = (match.start(), match.end())
            if key in inline_terms: suffix = suffix[1:]
            elif (match.start() and lead[match.start() - 1] == "`") or suffix.startswith("`") or any(start < match.start() < end for start, end, _ in code_spans): suffix = ""
            if EXPLANATION_RE.match(suffix):
                explained.add(term); continue
            add("unexplained_internal_term", "$.sections[0]"); break
    technical = occurrences[TECHNICAL_SECTION]
    if len(technical) > 1: add("duplicate_section", "$.sections[4]")
    technical_range = None
    if len(technical) == 1:
        start = technical[0]
        if len(positions) != len(REQUIRED_SECTIONS) or start < max(positions): add("invalid_technical_section_position", "$.sections[4]")
        technical_range = range(start + 1, _section_end(headings, start))
    for index, line in enumerate(lines):
        stripped = _prose(line)
        signal = _fence_open(line) or FULL_SHA_RE.search(line) or COMMAND_RE.search(stripped) or OUTPUT_RE.search(line) or TECHNICAL_URL_RE.search(line)
        if signal and (technical_range is None or index not in technical_range): add("unseparated_technical_details", f"$.lines[{index + 1}]"); break
    return HumanPostResult(target, not errors, errors)
