#!/bin/sh

set -eu

program=${0##*/}
repo_root=.
base_ref=
head_ref=
pr_body=
change_reference=

print_usage() {
    printf '%s\n' \
        "Usage: $program --base-ref REF [OPTIONS]" \
        '' \
        'Validate GTP pull-request mappings and changed history entries.' \
        '' \
        'Options:' \
        '  --base-ref REF          History comparison commit (required).' \
        '  --head-ref REF          Commit containing current Decision Records.' \
        '                          Required with --pr-body; otherwise optional.' \
        '  --repo-root DIR         Any directory in the Git work tree (default: .).' \
        '  --pr-body FILE          Regular file containing the pull-request body.' \
        '  --change-reference URL  Exact literal link target for changed history.' \
        '                          Required with --pr-body.' \
        '  -h, --help              Show this help.' \
        '' \
        'Without --head-ref, history-only validation reads the work tree.' \
        'With --head-ref, current histories are read from that exact commit.' \
        '' \
        'Exit status:' \
        '  0  Conforming.' \
        '  1  GTP content is nonconforming.' \
        '  2  Arguments or the execution environment are invalid.'
}

usage_error() {
    printf '%s: %s\n' "$program" "$1" >&2
    print_usage >&2
    exit 2
}

while [ "$#" -gt 0 ]; do
    case $1 in
        --repo-root)
            [ "$#" -ge 2 ] || usage_error "--repo-root requires a directory"
            repo_root=$2
            shift 2
            ;;
        --base-ref)
            [ "$#" -ge 2 ] || usage_error "--base-ref requires a Git ref"
            base_ref=$2
            shift 2
            ;;
        --head-ref)
            [ "$#" -ge 2 ] || usage_error "--head-ref requires a Git ref"
            head_ref=$2
            shift 2
            ;;
        --pr-body)
            [ "$#" -ge 2 ] || usage_error "--pr-body requires a file"
            pr_body=$2
            shift 2
            ;;
        --change-reference)
            [ "$#" -ge 2 ] || usage_error "--change-reference requires a link target"
            change_reference=$2
            shift 2
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            usage_error "unknown argument: $1"
            ;;
    esac
done

[ -n "$base_ref" ] || usage_error "--base-ref is required"
command -v git >/dev/null 2>&1 || usage_error "git is required"
command -v awk >/dev/null 2>&1 || usage_error "awk is required"
[ -d "$repo_root" ] || usage_error "repository directory does not exist: $repo_root"

requested_repo_root=$repo_root
repo_root=$(CDPATH= cd "$requested_repo_root" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null) || \
    usage_error "not a Git work tree: $requested_repo_root"
repo_root=$(CDPATH= cd "$repo_root" 2>/dev/null && pwd) || \
    usage_error "cannot resolve repository root: $repo_root"

base_commit=$(git -C "$repo_root" rev-parse --verify "${base_ref}^{commit}" 2>/dev/null) || \
    usage_error "base ref is not a commit: $base_ref"

head_commit=
if [ -n "$head_ref" ]; then
    head_commit=$(git -C "$repo_root" rev-parse --verify "${head_ref}^{commit}" 2>/dev/null) || \
        usage_error "head ref is not a commit: $head_ref"
fi

if [ -n "$pr_body" ]; then
    [ -n "$head_commit" ] || usage_error "--head-ref is required when --pr-body is used"
    [ -f "$pr_body" ] || usage_error "PR body is not a regular file: $pr_body"
    [ -r "$pr_body" ] || usage_error "PR body is not readable: $pr_body"
    [ -n "$change_reference" ] || usage_error "--change-reference is required when --pr-body is used"
fi

tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/gtp-validate.XXXXXX") || \
    usage_error "cannot create a temporary directory"
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM
errors=0

validate_pr_body() {
    body_file=$1
    mapped_paths=$2

    awk -v mapped_paths="$mapped_paths" -v body_label="$body_file" '
        function defect(at, message) {
            printf "%s:%d: %s\n", body_label, at, message > "/dev/stderr"
            defects++
        }

        function finish_summary() {
            if (pending_summary) {
                defect(summary_line, "decision summary must map to exactly one nested relative path")
                pending_summary = 0
            }
        }

        function fence_length(value, marker, count) {
            marker = substr(value, 1, 1)
            if (marker != "`" && marker != "~") return 0
            count = 0
            while (substr(value, count + 1, 1) == marker) count++
            return count >= 3 ? count : 0
        }

        function fence_probe(value) {
            if (substr(value, 1, 3) == "   ") return substr(value, 4)
            if (substr(value, 1, 2) == "  ") return substr(value, 3)
            if (substr(value, 1, 1) == " ") return substr(value, 2)
            return value
        }

        function outside_code_marker(value, marker, i, run, ticks, in_code) {
            i = 1
            while (i <= length(value)) {
                if (substr(value, i, 1) == "`") {
                    run = 1
                    while (substr(value, i + run, 1) == "`") run++
                    if (!in_code) { in_code = 1; ticks = run }
                    else if (run == ticks) { in_code = 0; ticks = 0 }
                    i += run
                    continue
                }
                if (!in_code && substr(value, i, length(marker)) == marker) return i
                i++
            }
            return 0
        }

        {
            line = $0
            sub(/\r$/, "", line)
            has_path = line ~ /(^|[^A-Za-z0-9._\/-])gtp\/decisions\/[a-z0-9]+(-[a-z0-9]+)*\.md([^A-Za-z0-9._\/-]|$)/
            probe = fence_probe(line)
            run = fence_length(probe)

            if (in_fence) {
                if (has_path) defect(NR, "Decision Record mapping is inside a fenced code block")
                remainder = substr(probe, run + 1)
                if (substr(probe, 1, 1) == fence_marker && run >= opening_run && remainder ~ /^[ \t]*$/) {
                    in_fence = 0
                }
                next
            }

            if (in_comment) {
                if (has_path) defect(NR, "Decision Record mapping is inside an HTML comment")
                if (index(line, "-->") > 0) in_comment = 0
                next
            }

            comment_open = outside_code_marker(line, "<!--")
            comment_close = outside_code_marker(line, "-->")
            if (comment_open || comment_close) {
                finish_summary()
                if (has_path || (in_related && line ~ /^[ \t]*-/)) {
                    defect(NR, "Decision Record mapping uses an HTML comment boundary")
                }
                if (comment_open && !comment_close) in_comment = 1
                next
            }

            if (run >= 3) {
                finish_summary()
                in_fence = 1
                fence_marker = substr(probe, 1, 1)
                opening_run = run
                next
            }

            if (line ~ /^## 関連する判断[ \t]*$/) {
                finish_summary()
                related_sections++
                if (related_sections > 1) defect(NR, "duplicate ## 関連する判断 section")
                in_related = 1
                next
            }

            if (line ~ /^##[ \t]+/) {
                finish_summary()
                in_related = 0
                if (has_path) defect(NR, "Decision Record path is outside ## 関連する判断")
                next
            }

            if (!in_related) {
                if (has_path) defect(NR, "Decision Record path is outside ## 関連する判断")
                next
            }

            if (line ~ /^- /) {
                finish_summary()
                if (has_path) {
                    defect(NR, "path-only Decision Record reference; add a summary and nest its path")
                    next
                }
                summary = line
                sub(/^- /, "", summary)
                if (summary ~ /^[ \t]*$/) {
                    defect(NR, "decision summary is empty")
                    next
                }
                pending_summary = 1
                summary_line = NR
                next
            }

            if (line ~ /^(  |   |    )- `gtp\/decisions\/[a-z0-9]+(-[a-z0-9]+)*\.md`[ \t]*$/) {
                if (!pending_summary) {
                    defect(NR, "Decision Record path has no summary")
                    next
                }
                path = line
                sub(/^(  |   |    )- `/, "", path)
                sub(/`[ \t]*$/, "", path)
                print path >> mapped_paths
                pending_summary = 0
                next
            }

            if (has_path) {
                defect(NR, "Decision Record path must be one nested repository-relative code span")
                next
            }

            if (line ~ /^[ \t]+-[ \t]+/) {
                defect(NR, "decision summary may contain only one nested Decision Record path")
                pending_summary = 0
                next
            }

            if (pending_summary && line !~ /^[ \t]*$/) finish_summary()
        }

        END {
            finish_summary()
            if (defects) exit 1
        }
    ' < "$body_file"
}

mapped_paths=$tmp_dir/mapped-paths
: > "$mapped_paths"

if [ -n "$pr_body" ]; then
    if validate_pr_body "$pr_body" "$mapped_paths"; then
        :
    else
        status=$?
        [ "$status" -eq 1 ] || usage_error "cannot inspect PR body: $pr_body"
        errors=1
    fi

    if awk '
        seen[$0]++ {
            printf "PR body: duplicate Decision Record mapping: %s\n", $0 > "/dev/stderr"
            duplicates = 1
        }
        END { if (duplicates) exit 1 }
    ' "$mapped_paths"; then
        :
    else
        status=$?
        [ "$status" -eq 1 ] || usage_error "cannot inspect PR Decision Record mappings"
        errors=1
    fi

    while IFS= read -r path; do
        [ -n "$path" ] || continue
        type=$(git -C "$repo_root" cat-file -t "${head_commit}:${path}" 2>/dev/null || :)
        if [ "$type" != blob ]; then
            printf '%s: mapped Decision Record does not exist at head ref %s: %s\n' \
                "$pr_body" "$head_ref" "$path" >&2
            errors=1
        fi
    done < "$mapped_paths"
fi

extract_history_entries() {
    source=$1
    destination=$2
    numbered=$3
    issues=$4

    : > "$issues"

    awk -v numbered="$numbered" -v issues="$issues" '
        function defect(at, message, key, separator, signature) {
            if (key == "") key = raw
            separator = sprintf("%c", 29)
            signature = message separator key
            if (numbered) printf "%d\t%s\n", at, signature >> issues
            else print signature >> issues
        }

        function flush() {
            if (entry == "") return
            if (numbered) printf "%d\t%s\n", entry_line, entry
            else print entry
            entry = ""
            pending_blank = 0
            comment_entry = 0
        }

        function finish_section() {
            flush()
            if (in_history && section_entries == 0) {
                defect(section_line, "malformed change-history content: section has no entries", "## 変更履歴")
            }
        }

        function append(value) {
            entry = entry sprintf("%c", 28) value
        }

        function fence_length(value, marker, count) {
            marker = substr(value, 1, 1)
            if (marker != "`" && marker != "~") return 0
            count = 0
            while (substr(value, count + 1, 1) == marker) count++
            return count >= 3 ? count : 0
        }

        function fence_probe(value) {
            if (substr(value, 1, 3) == "   ") return substr(value, 4)
            if (substr(value, 1, 2) == "  ") return substr(value, 3)
            if (substr(value, 1, 1) == " ") return substr(value, 2)
            return value
        }

        function comment_start(value, i, run, ticks, in_code) {
            i = 1
            while (i <= length(value)) {
                if (substr(value, i, 1) == "`") {
                    run = 1
                    while (substr(value, i + run, 1) == "`") run++
                    if (!in_code) { in_code = 1; ticks = run }
                    else if (run == ticks) { in_code = 0; ticks = 0 }
                    i += run
                    continue
                }
                if (!in_code && substr(value, i, 4) == "<!--") return i
                i++
            }
            return 0
        }

        {
            raw = $0
            sub(/\r$/, "", raw)

            if (in_fence) {
                if (fence_entry) append(raw)
                probe = fence_probe(raw)
                run = fence_length(probe)
                remainder = substr(probe, run + 1)
                if (substr(probe, 1, 1) == fence_marker && run >= opening_run && remainder ~ /^[ \t]*$/) {
                    in_fence = 0
                    fence_entry = 0
                }
                next
            }

            if (in_comment) {
                if (comment_entry) append(raw)
                if (index(raw, "-->") > 0) {
                    in_comment = 0
                    comment_entry = 0
                }
                next
            }

            parse = raw
            comment_at = comment_start(parse)
            if (comment_at > 0) {
                parse = substr(parse, 1, comment_at - 1)
                in_comment = index(substr(raw, comment_at + 4), "-->") == 0
                if (in_comment && in_history && entry != "" && raw ~ /^[ \t]+/) comment_entry = 1
                if (parse ~ /^## 変更履歴[ \t]*$/) {
                    defect(NR, "change-history heading uses an HTML comment boundary")
                    next
                }
                if (in_history && entry != "" && raw ~ /^[ \t]+/ && parse ~ /^[ \t]*$/) {
                    append(raw)
                    next
                }
            }

            probe = fence_probe(parse)
            run = fence_length(probe)
            if (run >= 3) {
                fence_entry = in_history && entry != "" && parse ~ /^[ \t]+/
                if (fence_entry) append(raw)
                in_fence = 1
                fence_marker = substr(probe, 1, 1)
                opening_run = run
                next
            }

            if (parse ~ /^## 変更履歴[ \t]*$/) {
                finish_section()
                history_sections++
                if (history_sections > 1) defect(NR, "duplicate ## 変更履歴 section")
                in_history = 1
                section_line = NR
                section_entries = 0
                next
            }

            if (parse ~ /^#+[ \t]*変更履歴/) {
                finish_section()
                defect(NR, "malformed change-history heading; use ## 変更履歴")
                in_history = 0
                next
            }

            if (parse ~ /^##[ \t]+/) {
                finish_section()
                in_history = 0
                next
            }

            if (!in_history) next

            if (parse ~ /^- /) {
                flush()
                entry = raw
                entry_line = NR
                section_entries++
                if (in_comment) comment_entry = 1
                next
            }

            if (parse ~ /^[ \t]*$/) {
                if (entry != "") pending_blank = 1
                next
            }

            if (parse ~ /^[ \t]+-/) {
                if (entry != "") {
                    if (pending_blank) append("")
                    append(raw)
                    pending_blank = 0
                } else {
                    defect(NR, "malformed change-history entry; use a top-level dash entry")
                }
                next
            }

            if (entry != "" && parse ~ /^[ \t]+/) {
                if (pending_blank) append("")
                append(raw)
                pending_blank = 0
                next
            }

            pending_blank = 0

            if (parse ~ /^-/) {
                defect(NR, "malformed change-history entry; use a top-level dash entry")
            } else {
                defect(NR, "malformed change-history content; expected a top-level dash entry")
            }
        }

        END { finish_section() }
    ' "$source" > "$destination"
}

list_current_paths() {
    destination=$1
    : > "$destination"

    if [ -n "$head_commit" ]; then
        tree_paths=$tmp_dir/tree-paths
        git -C "$repo_root" ls-tree -r --name-only "$head_commit" -- gtp/decisions > "$tree_paths" || \
            usage_error "cannot list Decision Records at head ref $head_ref"
        while IFS= read -r path; do
            case $path in
                gtp/decisions/*.md)
                    name=${path#gtp/decisions/}
                    case $name in */*) ;; *) printf '%s\n' "$path" >> "$destination" ;; esac
                    ;;
            esac
        done < "$tree_paths"
    else
        for file in "$repo_root"/gtp/decisions/*.md; do
            [ -f "$file" ] || continue
            printf 'gtp/decisions/%s\n' "${file##*/}" >> "$destination"
        done
    fi
}

find_changed_occurrences() {
    base_occurrences=$1
    current_occurrences=$2
    changed_occurrences=$3

    awk '
        FILENAME == ARGV[1] { base[$0]++; next }
        {
            tab = index($0, "\t")
            if (!tab) next
            entry = substr($0, tab + 1)
            if (base[entry] > 0) { base[entry]--; next }
            print
        }
    ' "$base_occurrences" "$current_occurrences" > "$changed_occurrences"
}

report_changed_issues() {
    issues=$1
    path=$2

    awk -v path="$path" '
        BEGIN { separator = sprintf("%c", 29) }
        {
            tab = index($0, "\t")
            line_number = substr($0, 1, tab - 1)
            issue = substr($0, tab + 1)
            boundary = index(issue, separator)
            message = boundary ? substr(issue, 1, boundary - 1) : issue
            printf "%s:%s: %s\n", path, line_number, message > "/dev/stderr"
        }
    ' "$issues"
}

validate_changed_entries() {
    entries=$1
    path=$2

    awk -v target="$change_reference" -v path="$path" '
        function escaped(value, at, count) {
            count = 0
            at--
            while (at > 0 && substr(value, at, 1) == "\\") { count++; at-- }
            return count % 2
        }

        function fence_length(value, marker, count) {
            marker = substr(value, 1, 1)
            if (marker != "`" && marker != "~") return 0
            count = 0
            while (substr(value, count + 1, 1) == marker) count++
            return count >= 3 ? count : 0
        }

        function indent_columns(value, i, character, columns) {
            for (i = 1; i <= length(value); i++) {
                character = substr(value, i, 1)
                if (character == " ") columns++
                else if (character == "\t") columns += 4 - (columns % 4)
                else break
            }
            return columns
        }

        function unsupported(value, i, c, run, ticks, in_code, first, tail, boundary, line, probe, line_end, previous_blank) {
            first = 1
            i = 1
            while (i <= length(value)) {
                tail = substr(value, i)
                boundary = index(tail, line_separator)
                line = boundary ? substr(tail, 1, boundary - 1) : tail
                if (!first && previous_blank && indent_columns(line) >= 6) return "indented code block"
                if (!first && line ~ /^[ \t]+-/) return "nested dash list item"
                probe = line
                if (first) {
                    sub(/^- /, "", probe)
                    if (probe ~ /^[ \t]*$/) return "empty top-level entry"
                }
                sub(/^[ \t]+/, "", probe)
                if (!in_code && fence_length(probe) >= 3) return "fenced code block"

                line_end = boundary ? i + boundary - 2 : length(value)
                while (i <= line_end) {
                    c = substr(value, i, 1)
                    if (c == "`" && !escaped(value, i)) {
                        run = 1
                        while (substr(value, i + run, 1) == "`") run++
                        if (!in_code) { in_code = 1; ticks = run }
                        else if (run == ticks) { in_code = 0; ticks = 0 }
                        i += run
                        continue
                    }
                    if (!in_code && substr(value, i, 4) == "<!--") return "HTML comment"
                    if (!in_code && substr(value, i, 3) == "-->") return "HTML comment"
                    if (!in_code && c == "<" && substr(value, i + 1, 1) ~ /[A-Za-z\/!?]/) return "raw HTML"
                    i++
                }
                previous_blank = line ~ /^[ \t]*$/
                first = 0
                if (!boundary) break
                i = line_end + 2
            }
            return ""
        }

        function literal_link(value, wanted, i, c, run, ticks, in_code, close_at, label, after, link_end) {
            i = 1
            while (i <= length(value)) {
                c = substr(value, i, 1)
                if (c == "`" && !escaped(value, i)) {
                    run = 1
                    while (substr(value, i + run, 1) == "`") run++
                    if (!in_code) { in_code = 1; ticks = run }
                    else if (run == ticks) { in_code = 0; ticks = 0 }
                    i += run
                    continue
                }
                if (!in_code && c == "[" && !escaped(value, i)) {
                    close_at = index(substr(value, i + 1), "]")
                    if (close_at > 1) {
                        close_at += i
                        if (escaped(value, close_at)) { i = close_at + 1; continue }
                        label = substr(value, i + 1, close_at - i - 1)
                        if (label !~ /[\[\]`<>]/ &&
                            !(i > 1 && substr(value, i - 1, 1) == "!") &&
                            substr(value, close_at + 1, 1) == "(") {
                            after = close_at + 2
                            if (substr(value, after, length(wanted)) == wanted &&
                                substr(value, after + length(wanted), 1) == ")") return 1
                        }
                        link_end = index(substr(value, close_at + 2), ")")
                        if (link_end) { i = close_at + link_end + 2; continue }
                    }
                }
                i++
            }
            return 0
        }

        BEGIN { line_separator = sprintf("%c", 28) }

        {
            tab = index($0, "\t")
            line_number = substr($0, 1, tab - 1)
            entry = substr($0, tab + 1)
            context = unsupported(entry)
            if (context != "") {
                printf "%s:%s: new or modified change-history entry contains unsupported %s\n", \
                    path, line_number, context > "/dev/stderr"
                defects++
            } else if (target != "" && !literal_link(entry, target)) {
                printf "%s:%s: new or modified change-history entry must link to %s\n", \
                    path, line_number, target > "/dev/stderr"
                defects++
            }
        }

        END { if (defects) exit 1 }
    ' "$entries"
}

current_paths=$tmp_dir/current-paths
list_current_paths "$current_paths"
index=0

while IFS= read -r path; do
    [ -n "$path" ] || continue
    index=$((index + 1))
    current_source=$tmp_dir/current-source-$index
    base_source=$tmp_dir/base-source-$index
    current_entries=$tmp_dir/current-entries-$index
    base_entries=$tmp_dir/base-entries-$index
    changed_entries=$tmp_dir/changed-entries-$index
    current_issues=$tmp_dir/current-issues-$index
    base_issues=$tmp_dir/base-issues-$index
    changed_issues=$tmp_dir/changed-issues-$index

    if [ -n "$head_commit" ]; then
        git -C "$repo_root" show "${head_commit}:${path}" > "$current_source" || \
            usage_error "cannot read $path from head ref $head_ref"
    else
        current_source=$repo_root/$path
        [ -r "$current_source" ] || usage_error "Decision Record is not readable: $path"
    fi

    extract_history_entries "$current_source" "$current_entries" 1 "$current_issues" || \
        usage_error "cannot inspect change history in $path"

    : > "$base_entries"
    : > "$base_issues"
    if git -C "$repo_root" cat-file -e "${base_commit}:${path}" 2>/dev/null; then
        git -C "$repo_root" show "${base_commit}:${path}" > "$base_source" || \
            usage_error "cannot read $path from base ref $base_ref"
        extract_history_entries "$base_source" "$base_entries" 0 "$base_issues" || \
            usage_error "cannot inspect $path from base ref $base_ref"
    fi

    find_changed_occurrences "$base_entries" "$current_entries" "$changed_entries" || \
        usage_error "cannot compare change history in $path"
    find_changed_occurrences "$base_issues" "$current_issues" "$changed_issues" || \
        usage_error "cannot compare change-history profile issues in $path"

    if [ -s "$changed_issues" ]; then
        report_changed_issues "$changed_issues" "$path" || \
            usage_error "cannot report change-history profile issues in $path"
        errors=1
    fi

    if validate_changed_entries "$changed_entries" "$path"; then
        :
    else
        status=$?
        [ "$status" -eq 1 ] || usage_error "cannot inspect changed history entries in $path"
        errors=1
    fi
done < "$current_paths"

if [ "$errors" -ne 0 ]; then
    printf '%s\n' 'GTP conformance: NONCONFORMING' >&2
    exit 1
fi

printf '%s\n' 'GTP conformance: OK'
