# Real GitHub acceptance run

このdirectoryは、walking skeletonを実GitHubで1回だけ通した受け入れ記録を置く。GTP coreの正準仕様ではない。

## Scenario

実リポジトリで実行する受け入れシナリオはIssue #1の1件だけとする。

```text
Contract A
→ 競合するContract B
→ Contract Cによるsupersession回復
→ Start
→ branch・commit・PR
→ GitHubだけを入力としたfresh process再開
→ immutable artifact Evidence付きDone
→ native merge
→ done
```

alias、複数leaf、malformed、edited、collision、terminal resource消失、Done／Stop orderingなどの破壊的variantは、GitHub API境界のfixtureと実reducer/statusを用いて検証する。実Issueへ追加の破壊的Recordは投稿しない。

## Observed result

- Issue: https://github.com/shinya0x00/github-task-protocol/issues/1
- PR: https://github.com/shinya0x00/github-task-protocol/pull/2
- PR source head: `618aa6f26e08c1e496ff1ac790f8a2e46288fc99`
- native merge commit: `537601111c5559dedf7cbd75fad9cd10fcc10ee6`
- final observation: `state: done`、diagnosticなし、acquisition complete

production CLIは、Bound Contract、Start、Done、Bound PR、PR source head、immutable artifactをGitHubから再取得して上記結果を導出した。Issue #1はterminal済みであり、今後の検証はread-onlyで行う。

## Verification

```console
GITHUB_TOKEN=<token> PYTHONPATH=src python3 -m gtp status \
  https://github.com/shinya0x00/github-task-protocol/issues/1
```

release candidateのlocal/CI検証結果は`acceptance/v1.0.0.json`へ記録する。

## Evidence limits

- artifact bindingが証明するのは、指定source SHAにfileが存在することまでである。file内容の真実性は証明しない。
- Check Runが証明するのは、指定SHAに対してGitHubがsuccessを返したことまでである。Done Conditionの自然言語全体を証明しない。
- clean-process再開はlocal checkpointなしの再構成を実演するが、GitHub accountの本人性やmutation authorityをGTPが証明したことにはならない。
- GitHubが返さない削除済みCarrierやmarker除去編集を、v1 readerが検出できるとは主張しない。
