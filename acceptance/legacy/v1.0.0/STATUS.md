# Legacy GTP v1.0.0 release candidate status

更新日: 2026-07-19

この文書はrelease handoffであり、GTP core specificationやDone Recordではない。

## 観測済み

| 項目 | 結果 | Evidence | 限界 |
|---|---|---|---|
| 4 Record type / Exact Carrier / closed schema | verified | carrier、schema、CLI tests | GitHubが将来追加するMarkdown variantまでは保証しない |
| alias / supersession / Repair Group | verified | v1 conformance fixture suite | destructive variantはfake GitHub boundaryであり実Issueへは投稿していない |
| 6 state / terminal timeline | verified | Done／Stop、Late Done、pending Check、terminal dependency tests | fixture timestampより細かい外部resource順序は復元しない |
| ADR-001〜ADR-026 coverage | verified | `tests/fixtures/adr-conformance.json`とcoverage test | 対応表は自然言語条件の真実性を自動証明しない |
| Python 3.11〜3.13 / wheel / installed CLI | verified | GitHub Actions CI | OS matrixはUbuntuのみ |
| 実repository E2E | verified | Issue #1、PR #2、[`../issue-1/run.json`](../issue-1/run.json) | actor identityとauthorityはGTPの対象外 |
| 完成作業dogfooding | in progress | Issue #3、`codex/gtp-v1-complete` | native mergeとtagはrelease candidate検証後に実施する |

## Release transition

1. release candidate commitでlocal tests、wheel install、Issue #1／#3のlive readを再実行する。
2. completion PRの全Check Run成功を確認する。
3. Issue #3へCheck Runと当時のimmutable acceptance artifactをEvidenceとするDoneを投稿する。
4. fresh processでmerge前`in_progress`を確認する。
5. completion PRをnative mergeする。
6. mainからIssue #3の`done`とIssue #1の`done`を確認する。
7. 検証したmain merge commitへannotated tag `v1.0.0`を作成してpushする。

## Unknown

release candidate時点では、completion PRの最終Check Run URL、native merge commit SHA、tag push結果は未観測である。これらを先取りして完了claimしない。
