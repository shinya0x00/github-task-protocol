#!/bin/sh

set -eu

test_dir=$(CDPATH= cd "$(dirname "$0")" && pwd)
repo_root=$(CDPATH= cd "$test_dir/.." && pwd)
validator=$repo_root/skills/gtp/scripts/validate.sh
change_url=https://example.test/pull/10
tab=$(printf '\t')
tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/gtp-validator-test.XXXXXX")
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM

passed=0

write_file() {
    destination=$1
    shift
    printf '%s\n' "$@" > "$destination"
}

write_crlf_file() {
    destination=$1
    shift
    printf '%s\r\n' "$@" > "$destination"
}

write_record() {
    destination=$1
    shift
    write_file "$destination" \
        '## 未決定事項' \
        '' \
        '同じrequest IDを再処理してよいか。' \
        '' \
        '## 採用した手段' \
        '' \
        '完了済みrequest IDは再実行しない。' \
        "$@"
}

make_repo() {
    name=$1
    repo=$tmp_dir/$name
    mkdir -p "$repo/gtp/decisions"
    git -C "$repo" init -q
    git -C "$repo" config user.name validator-test
    git -C "$repo" config user.email validator-test@example.test
    write_record "$repo/gtp/decisions/request-id-retry.md"
    git -C "$repo" add .
    git -C "$repo" commit -qm base
}

commit_repo() {
    git -C "$repo" add .
    git -C "$repo" commit -qm "$1"
}

validate() {
    "$validator" "$@"
}

validate_in_repo() {
    (CDPATH= cd "$repo" && "$validator" "$@")
}

expect() {
    name=$1
    wanted_status=$2
    wanted_text=$3
    shift 3
    output=$tmp_dir/$name.output

    set +e
    "$@" > "$output" 2>&1
    status=$?
    set -e

    if [ "$status" -ne "$wanted_status" ]; then
        printf 'not ok - %s (expected exit %s, got %s)\n' "$name" "$wanted_status" "$status" >&2
        sed -n '1,120p' "$output" >&2
        exit 1
    fi
    if ! grep -Fq -e "$wanted_text" "$output"; then
        printf 'not ok - %s (missing diagnostic: %s)\n' "$name" "$wanted_text" >&2
        sed -n '1,120p' "$output" >&2
        exit 1
    fi

    passed=$((passed + 1))
    printf 'ok - %s\n' "$name"
}

expect help_exit_status 0 'Exit status:' validate --help
expect base_ref_required 2 '--base-ref is required' validate

make_repo pr_contract
write_record "$repo/gtp/decisions/cache-policy.md"
write_record "$repo/gtp/decisions/other.md"
commit_repo decision-records

write_file "$repo/pr-body.md" \
    '## 関連する判断' \
    '' \
    '- 完了済みrequest IDは再実行しない' \
    '  - `gtp/decisions/request-id-retry.md`'
expect pr_head_required 2 '--head-ref is required when --pr-body is used' \
    validate --repo-root "$repo" --base-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"
expect pr_reference_required 2 '--change-reference is required when --pr-body is used' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md"

mkdir "$repo/not-a-body"
expect pr_body_must_be_regular 2 'PR body is not a regular file' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/not-a-body" --change-reference "$change_url"

write_file "$repo/pr-body.md" \
    '## 関連する判断' \
    '' \
    '- 完了済みrequest IDは再実行しない' \
    '' \
    '  - `gtp/decisions/request-id-retry.md`' \
    '- cacheは24時間保持する' \
    '   - `gtp/decisions/cache-policy.md`' \
    '- 別の判断' \
    '    - `gtp/decisions/other.md`'
expect canonical_pr_mappings 0 'GTP conformance: OK' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_file "$repo/pr-body.md" \
    '## 変更内容' \
    '' \
    '`gtp/decisions/` directoryへRecordを置く。' \
    '' \
    '## 関連する判断' \
    '' \
    '- 完了済みrequest IDは再実行しない' \
    '  - `gtp/decisions/request-id-retry.md`'
expect directory_mention_is_not_record_path 0 'GTP conformance: OK' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_file "$repo/pr-body.md" \
    '## 変更内容' \
    '' \
    '外部資料は https://example.test/gtp/decisions/a.md にある。' \
    '' \
    '## 関連する判断' \
    '' \
    '- 完了済みrequest IDは再実行しない' \
    '  - `gtp/decisions/request-id-retry.md`'
expect external_url_is_not_record_path 0 'GTP conformance: OK' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_file "$repo/pr-body.md" \
    '## 関連する判断' \
    '' \
    '- comment marker `<!--` is literal code' \
    '  - `gtp/decisions/request-id-retry.md`'
expect inline_code_comment_marker_in_summary 0 'GTP conformance: OK' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_file "$repo/pr-body.md" \
    '## 変更内容' \
    '' \
    'Decision Recordを変更しない。'
expect no_related_decisions 0 'GTP conformance: OK' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_file "$repo/pr-body.md" \
    '## 関連する判断' \
    '' \
    '- `gtp/decisions/request-id-retry.md`'
expect path_only_mapping 1 'path-only Decision Record reference' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_file "$repo/body=ignored.md" \
    '## 関連する判断' \
    '' \
    '- `gtp/decisions/request-id-retry.md`'
expect awk_assignment_pr_body_name 1 'body=ignored.md:3: path-only Decision Record reference' \
    validate_in_repo --repo-root . --base-ref HEAD --head-ref HEAD --pr-body 'body=ignored.md' --change-reference "$change_url"

write_file "$repo/pr-body.md" \
    '## 関連する判断' \
    '' \
    '- 二つのpathを対応させる' \
    '  - `gtp/decisions/request-id-retry.md`' \
    '  - `gtp/decisions/cache-policy.md`'
expect one_summary_two_paths 1 'Decision Record path has no summary' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_file "$repo/pr-body.md" \
    '## 関連する判断' \
    '' \
    '- 最初の概要' \
    '  - `gtp/decisions/request-id-retry.md`' \
    '- 重複した概要' \
    '  - `gtp/decisions/request-id-retry.md`'
expect duplicate_mapping 1 'duplicate Decision Record mapping' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_file "$repo/pr-body.md" \
    '## 変更内容' \
    '' \
    '- 概要' \
    '  - `gtp/decisions/request-id-retry.md`'
expect mapping_outside_section 1 'outside ## 関連する判断' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_file "$repo/pr-body.md" \
    '## 関連する判断' \
    '' \
    '- 五文字の字下げ' \
    '     - `gtp/decisions/request-id-retry.md`'
expect mapping_indentation 1 'must be one nested repository-relative code span' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_file "$repo/pr-body.md" \
    '## 関連する判断' \
    '' \
    '```markdown' \
    '- fence内の概要' \
    '  - `gtp/decisions/request-id-retry.md`' \
    '```'
expect fenced_mapping 1 'inside a fenced code block' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_file "$repo/pr-body.md" \
    '<!--' \
    '## 関連する判断' \
    '- comment内の概要' \
    '  - `gtp/decisions/request-id-retry.md`' \
    '-->'
expect commented_mapping 1 'inside an HTML comment' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_file "$repo/pr-body.md" \
    '## 関連する判断' \
    '' \
    '- comment境界で分断する' \
    '  <!-- note -->- `gtp/decisions/request-id-retry.md`'
expect fragmented_mapping 1 'uses an HTML comment boundary' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_file "$repo/pr-body.md" \
    '## 関連する判断' \
    '' \
    '  - `gtp/dec<!-- -->isions/request-id-retry.md`'
expect fragmented_path_only_mapping 1 'decision summary may contain only one nested Decision Record path' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_record "$repo/gtp/decisions/untracked-record.md"
write_file "$repo/pr-body.md" \
    '## 関連する判断' \
    '' \
    '- worktreeだけにある判断' \
    '  - `gtp/decisions/untracked-record.md`'
expect mapping_uses_exact_head_tree 1 'does not exist at head ref' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

write_crlf_file "$repo/pr-body.md" \
    '## 関連する判断' \
    '' \
    '- CRLFでも同じmapping' \
    '  - `gtp/decisions/request-id-retry.md`'
expect crlf_pr_body 0 'GTP conformance: OK' \
    validate --repo-root "$repo" --base-ref HEAD --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

make_repo history_profile

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- PR #10で再実行をやめた。'
expect missing_history_link 1 'new or modified change-history entry must link to' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

write_crlf_file "$repo/gtp/decisions/request-id-retry.md" \
    '## 未決定事項' \
    '' \
    '同じrequest IDを再処理してよいか。' \
    '' \
    '## 採用した手段' \
    '' \
    '完了済みrequest IDは再実行しない。' \
    '' '## 変更履歴' '' \
    '- 再実行をやめた。' \
    "  詳細は [PR #10]($change_url) を参照。"
expect continuation_link 0 'GTP conformance: OK' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    "- [PR #10]($change_url \"title\")で変更。"
expect link_target_must_be_exact 1 'new or modified change-history entry must link to' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- [label\](https://example.test/pull/10) はlinkではない。'
expect escaped_closing_bracket_is_not_link 1 'new or modified change-history entry must link to' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- `[PR #10](https://example.test/pull/10)` はcode span。'
expect code_span_is_not_link 1 'new or modified change-history entry must link to' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    "- ![PR #10]($change_url) はimage。"
expect image_is_not_link 1 'new or modified change-history entry must link to' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    "- 変更。 <!-- [PR #10]($change_url) -->"
expect comment_is_profile_violation 1 'unsupported HTML comment' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    "- <span>変更</span> [PR #10]($change_url)"
expect raw_html_is_profile_violation 1 'unsupported raw HTML' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 変更。' \
    '  ```markdown' \
    "  [PR #10]($change_url)" \
    '  ```'
expect fence_is_profile_violation 1 'unsupported fenced code block' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- indented codeへlinkを置く。' \
    '' \
    "      [PR #10]($change_url)"
expect indented_code_block_is_profile_violation 1 'unsupported indented code block' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- tab-indented codeへlinkを置く。' \
    '' \
    "${tab}  [PR #10]($change_url)"
expect tab_indented_code_block_is_profile_violation 1 'unsupported indented code block' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 参照先がない環境でplain textを残す。'
expect plain_history_without_reference 0 'GTP conformance: OK' \
    validate --repo-root "$repo" --base-ref HEAD

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 参照先がない環境で変更。' \
    '  <!-- 曖昧なcontinuation -->'
expect violation_without_reference 1 'unsupported HTML comment' \
    validate --repo-root "$repo" --base-ref HEAD

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- dangling comment close -->'
expect dangling_comment_without_reference 1 'unsupported HTML comment' \
    validate --repo-root "$repo" --base-ref HEAD

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- four-space fence。' \
    '    ```markdown' \
    '    ambiguous text' \
    '    ```'
expect indented_fence_without_reference 1 'unsupported fenced code block' \
    validate --repo-root "$repo" --base-ref HEAD

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴<!-- -->' '' \
    '- commentで分断した見出し。'
expect fragmented_history_heading 1 'heading uses an HTML comment boundary' \
    validate --repo-root "$repo" --base-ref HEAD

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴:' '' \
    '- malformed heading。'
expect literal_history_heading 1 'malformed change-history heading' \
    validate --repo-root "$repo" --base-ref HEAD

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- top-level entry。' \
    '  - nested item。'
expect top_level_history_entry 1 'unsupported nested dash list item' \
    validate --repo-root "$repo" --base-ref HEAD

make_repo updated_indented_code
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 過去のindented code。' \
    '' \
    '      first code line' \
    '      old second code line'
commit_repo indented-code-legacy
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 過去のindented code。' \
    '' \
    '      first code line' \
    "      [PR #10]($change_url)"
expect updated_indented_code_is_profile_violation 1 'unsupported indented code block' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

make_repo updated_nested_history
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 過去のlinkなしentry。' \
    '  - 過去からあるnested item。'
commit_repo nested-legacy
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    "- 更新して [PR #10]($change_url) を追加。" \
    '  - 過去からあるnested item。'
expect updated_entry_with_nested_item_is_profile_violation 1 'unsupported nested dash list item' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

make_repo updated_empty_history_entry
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- ' \
    '  old continuation'
commit_repo empty-entry-legacy
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- ' \
    "  [PR #10]($change_url)"
expect updated_empty_entry_is_profile_violation 1 'unsupported empty top-level entry' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

make_repo updated_comment_payload
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 過去のcomment。' \
    '  <!--' \
    '  old payload' \
    '  -->'
commit_repo comment-payload-legacy
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 過去のcomment。' \
    '  <!--' \
    "  [PR #10]($change_url)" \
    '  -->'
expect updated_comment_payload_is_profile_violation 1 'unsupported HTML comment' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

make_repo unchanged_malformed_history
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 過去のlinkなしentry。' \
    '  - 過去からあるmalformed nested item。'
commit_repo malformed-legacy
expect unchanged_malformed_history_is_exempt 0 'GTP conformance: OK' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

make_repo inline_code_comment
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 過去のentryでは `<!--` をliteral codeとして説明。'
commit_repo inline-code-legacy
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 過去のentryでは `<!--` をliteral codeとして説明。' \
    '- 新しいlinkなしentry。'
expect inline_code_comment_does_not_hide_entry 1 'new or modified change-history entry must link to' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

make_repo occurrence_comparison
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 過去のlinkなしentry。'
commit_repo legacy-entry
expect unchanged_legacy_entry 0 'GTP conformance: OK' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 更新したlinkなしentry。'
expect modified_entry_is_detected 1 'new or modified change-history entry must link to' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 過去のlinkなしentry。' \
    '- 過去のlinkなしentry。'
expect duplicate_occurrence_is_detected 1 'new or modified change-history entry must link to' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

make_repo hidden_base_entry
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '<!--' \
    '- 見えないentry。' \
    '-->'
commit_repo hidden-entry
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 見えるようにしたentry。'
expect hidden_base_text_is_not_occurrence 1 'new or modified change-history entry must link to' \
    validate --repo-root "$repo" --base-ref HEAD --change-reference "$change_url"

make_repo exact_head_history
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    "- [PR #10]($change_url)で再実行をやめた。"
commit_repo linked-head
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- dirty worktreeのlinkなしentry。'
expect exact_head_ignores_worktree 0 'GTP conformance: OK' \
    validate --repo-root "$repo" --base-ref HEAD^ --head-ref HEAD --change-reference "$change_url"
expect worktree_mode_reads_worktree 1 'new or modified change-history entry must link to' \
    validate --repo-root "$repo" --base-ref HEAD^ --change-reference "$change_url"

make_repo subdirectory_root
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    "- [PR #10]($change_url)で変更。"
mkdir -p "$repo/nested/work"
expect repository_top_level_normalization 0 'GTP conformance: OK' \
    validate --repo-root "$repo/nested/work" --base-ref HEAD --change-reference "$change_url"

make_repo integrated_positive
write_record "$repo/gtp/decisions/request-id-retry.md" \
    '' '## 変更履歴' '' \
    '- 再実行をやめた。' \
    "  [Issue #149]($change_url)を参照。"
write_record "$repo/gtp/decisions/cache-policy.md"
commit_repo integrated-head
write_file "$repo/pr-body.md" \
    '## 変更内容' \
    '' \
    '判断を二件参照する。' \
    '' \
    '## 関連する判断' \
    '' \
    '- 完了済みrequest IDは再実行しない' \
    '  - `gtp/decisions/request-id-retry.md`' \
    '- cacheは24時間保持する' \
    '    - `gtp/decisions/cache-policy.md`'
expect integrated_exact_head 0 'GTP conformance: OK' \
    validate --repo-root "$repo" --base-ref HEAD^ --head-ref HEAD --pr-body "$repo/pr-body.md" --change-reference "$change_url"

printf '%s tests passed\n' "$passed"
