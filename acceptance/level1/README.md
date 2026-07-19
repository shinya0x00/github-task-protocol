# Level 1 acceptance

Issue #13のrelease gateとして、固定したinstalled CLIを実GitHubへ接続し、
矛盾停止、安全なStop、native merge後の完了再構成、7 halt reason coverage、
人間読解を一つの受け入れ記録へまとめる。

## 現在状態

repair Issue #34をmainへmergeし、新candidateでmachine probeを最初から再実行した。
live矛盾、final Stop、branch削除後のstopped、既存native mergeのdone、全98 testは成功した。

残るgateはrepository owner本人のhuman probe再回答だけである。回答を実装者が
代筆するまでIssue #13のDone、ready化、mergeを行わない。

## 固定candidate

- commit: `c859172c97a1804642d77248673470f51af73a79`
- wheel SHA-256: `b610a77a0cd19ed7018b5983477816197584d36eb3d56376814cbad79bae18cb`
- Python: `3.12.12`
- installed `gtp --version`: `1.0.0`
- GTP.md: https://github.com/shinya0x00/github-task-protocol/blob/c859172c97a1804642d77248673470f51af73a79/GTP.md

## 観測結果

| 経路 | GitHub | 結果 |
|---|---|---|
| live矛盾 | Issue #36 / PR #37 | Evidence key不足が`halt / invalid_evidence`、原因Done URL、exit 0になり、task contextも同時表示された |
| safe abandonment | Issue #36 | final Stop後は`stopped`。PRはunmerged close、branch削除後も再構成できた |
| 完了 | Issue #12 / PR #24 | branch削除後もDone source head `67b9d786…`とnative mergeから`done`を再構成した |
| 7 reasons | 2 production-path truth tables | 7件すべてで期待state、reason、first cause URLを検査した |
| human probe | 再回答待ち | Issue #34の修正後stdoutに対するrepository owner本人の回答はまだない |

merge commitではなくDoneが指したsource headを比較対象とする。

詳細なmachine-readable recordは`run.json`、観測stdoutは`stdout/`、
本人回答は`human-probe.md`が所有する。

## 途中で見つかったblocker

- Issue #25: installed `gtp --version`がなかった。PR #26で修復。
- Issue #29: production-path coverageが原因URLをassertしていなかった。PR #30で修復。

修復でcandidateが変わったため、旧Issue #27とIssue #31のprobeを最終Evidenceへ
継ぎ足さず、Issue #36でrunを最初から実行した。

- Issue #34: taskの目的、変更範囲、作業先、Condition別Evidence、未証明事項を
  一つのstatus出力へ表示する修復。PR #35でmainへmergeした。

## Evidenceの限界

- artifactは指定commitにfileが存在することまでを証明する。
- Check Runは指定SHAでGitHubがsuccessを返したことまでを証明する。
- native mergeは最終受理の事実だが、actor本人性やcredential安全性を証明しない。
- clean installの記録は、GitHub外情報を参照しなかったことを暗号学的に証明しない。
- statusのexit 0は取得成功であり、変更・完了・merge権限ではない。
