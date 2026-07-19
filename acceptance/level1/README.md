# Level 1 acceptance

Issue #13のrelease gateとして、固定したinstalled CLIを実GitHubへ接続し、
矛盾停止、安全なStop、native merge後の完了再構成、7 halt reason coverage、
人間読解を一つの受け入れ記録へまとめる。

## 現在状態

repair Issue #38をmainへmergeし、第三candidateでmachine probeを最初から再実行した。
live矛盾、final Stop、branch削除後のstopped、既存native mergeのdone、全98 testは成功した。

平易な要約に対するrepository owner本人の第三human probeだけが未確認である。
回答を実装者が代筆するまでIssue #13のDone、ready化、mergeを行わない。

## 固定candidate

- commit: `0b70b4f46ac090a59cfa02f00b67548bf5441d1e`
- wheel SHA-256: `b3d0b27dea4f769a847a5e427a065bb47d9c2d15b883f3ff7f8698f3e2b18a76`
- Python: `3.12.12`
- installed `gtp --version`: `1.0.0`
- GTP.md: https://github.com/shinya0x00/github-task-protocol/blob/0b70b4f46ac090a59cfa02f00b67548bf5441d1e/GTP.md

## 観測結果

| 経路 | GitHub | 結果 |
|---|---|---|
| live矛盾 | Issue #40 / PR #41 | 確認資料不足が`halt / invalid_evidence`、原因Done URL、exit 0になり、平易な要約も同時表示された |
| safe abandonment | Issue #40 | final Stop後は`stopped`。PRはunmerged close、branch削除後も再構成できた |
| 完了 | Issue #12 / PR #24 | branch削除後もDone source head `67b9d786…`とnative mergeから`done`を再構成した |
| 7 reasons | 2 production-path truth tables | 7件すべてで期待state、reason、first cause URLを検査した |
| human probe | 第三回答待ち | Issue #38の平易な要約に対するrepository owner本人の回答はまだない |

merge commitではなくDoneが指したsource headを比較対象とする。

詳細なmachine-readable recordは`run.json`、観測stdoutは`stdout/`、
本人回答は`human-probe.md`が所有する。

## 途中で見つかったblocker

- Issue #25: installed `gtp --version`がなかった。PR #26で修復。
- Issue #29: production-path coverageが原因URLをassertしていなかった。PR #30で修復。

修復でcandidateが変わったため、旧Issue #27、Issue #31、Issue #36のprobeを
最終Evidenceへ継ぎ足さず、Issue #40でrunを最初から実行した。

- Issue #34: taskの目的、変更範囲、作業先、Condition別Evidence、未証明事項を
  一つのstatus出力へ表示する修復。PR #35でmainへmergeした。
- Issue #38: 二回目のhuman probeで残った用語負荷を下げ、「確認できたもの」と
  「確認できないもの」を非エンジニア向けに説明する修復。

## Evidenceの限界

- artifactは指定commitにfileが存在することまでを証明する。
- Check Runは指定SHAでGitHubがsuccessを返したことまでを証明する。
- native mergeは最終受理の事実だが、actor本人性やcredential安全性を証明しない。
- clean installの記録は、GitHub外情報を参照しなかったことを暗号学的に証明しない。
- statusのexit 0は取得成功であり、変更・完了・merge権限ではない。
