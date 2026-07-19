# Level 1 acceptance

Issue #13のrelease gateとして、固定したinstalled CLIを実GitHubへ接続し、
矛盾停止、安全なStop、native merge後の完了再構成、7 halt reason coverage、
人間読解を一つの受け入れ記録へまとめる。

## 現在状態

機械的なprobeは完了したが、repository owner本人のhuman probeは受け入れ失敗となった。
taskの目的、Done ConditionとEvidence、未証明事項を判断できず、
「全体的にわかりにくい。負荷が高い」と評価された。

repair Issue #34をmainへmergeし、新candidateでrunとhuman probeを最初から
実行するまでIssue #13のDone、ready化、mergeを行わない。

## 固定candidate

- commit: `f0ad9f38f14a222771c6eb4ce86ab3c9a2c79deb`
- wheel SHA-256: `5eca7722e645243e08aba6806cadd56b8736fc77a05207081d0644a5c05d7cb3`
- Python: `3.12.12`
- installed `gtp --version`: `1.0.0`
- GTP.md: https://github.com/shinya0x00/github-task-protocol/blob/f0ad9f38f14a222771c6eb4ce86ab3c9a2c79deb/GTP.md

## 観測結果

| 経路 | GitHub | 結果 |
|---|---|---|
| live矛盾 | Issue #31 / PR #32 | Evidence key不足が`halt / invalid_evidence`、原因Done URL、exit 0になった |
| safe abandonment | Issue #31 | final Stop後は`stopped`。PRはunmerged close、branch削除後も再構成できた |
| 完了 | Issue #12 / PR #24 | branch削除後もDone source head `67b9d786…`とnative mergeから`done`を再構成した |
| 7 reasons | 2 production-path truth tables | 7件すべてで期待state、reason、first cause URLを検査した |
| human probe | PR #33 response | task contextが不明で理解負荷が高く、受け入れ失敗 |

merge commitではなくDoneが指したsource headを比較対象とする。

詳細なmachine-readable recordは`run.json`、観測stdoutは`stdout/`、
本人回答は`human-probe.md`が所有する。

## 途中で見つかったblocker

- Issue #25: installed `gtp --version`がなかった。PR #26で修復。
- Issue #29: production-path coverageが原因URLをassertしていなかった。PR #30で修復。

修復でcandidateが変わったため、旧Issue #27のprobeを最終Evidenceへ継ぎ足さず、
Issue #31でrunを最初から実行した。

## Evidenceの限界

- artifactは指定commitにfileが存在することまでを証明する。
- Check Runは指定SHAでGitHubがsuccessを返したことまでを証明する。
- native mergeは最終受理の事実だが、actor本人性やcredential安全性を証明しない。
- clean installの記録は、GitHub外情報を参照しなかったことを暗号学的に証明しない。
- statusのexit 0は取得成功であり、変更・完了・merge権限ではない。
