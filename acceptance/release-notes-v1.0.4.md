# GitHub Task Protocol 1.0.4 release notes

この文書は、このsourceからbuildするPython package version `1.0.4`と、そこに実装するprotocol version `1.1`の変更を説明する。`1.0.4`はPython packagingのversion identifierであり、Semantic Versioningのpatch互換性をClaimしない。tagやGitHub Releaseを含むpublicationをClaimせず、PyPI publication、deploymentをClaimせず、公開前後のどちらでもこの意味は変わらない。

## 変更内容

- protocol `1.1`は、既存Contractへ完了条件だけを追加する`amendment` Recordを追加する。goal、scope、branch、PR、authorityの置換や、既存条件の変更・削除には使えない。
- protocol `1.1`のDone Recordは、評価したContract revision、Bound PR、正確なsource head、条件ごとのEvidenceへ結び付く。PR headがmerge前に変わった場合は、同じIssue・branch・PRでre-Doneできる。
- 評価対象は最新のLogical Doneである。認識した新しいCarrier、revision、Doneがinvalidなら、過去のvalid Doneへfallbackしない。retry aliasはLogical Recordの順序を変えない。
- native mergeまたはStopの後は、新しいamendmentとre-Doneを拒否する。merge時点でCheckがpendingでも、このcutoffは変わらない。
- `state: done`はContractへ結び付いたsource PR lifecycleの完了だけを表す。tag、GitHub Release、PyPI、deploymentその他の外部OperationはGTP stateを変更せず、公開可能な結果は通常のGitHub commentへ残す。
- repository、organization、userが既に所有するinstructionは、そのownerに残る。GTPは内容を定義、検証、上書きせず、valid ContractがないIssueの詳細なlifecycleを推測しない。
- public Recordと公開Evidenceには、再構成に必要な公開可能情報だけを残す。credential、private prompt、非公開のauthorization、内部診断の原文は転記しない。
- protocol `1.0`だけの履歴は従来の意味を保持する。protocol `1.1`へ移行した履歴を理解できない旧CLIは、推測で成功扱いせずfail closedする。

## packageとprotocolの境界

- package `1.0.4`とprotocol `1.1`は別のversion軸であり、一方から他方の互換性を推測しない。
- `pyproject.toml`、wheel／sdist metadata、`gtp --version`はpackage version `1.0.4`を示す。
- `GTP.md`とRecordの`gtp` fieldがprotocol versionを所有する。protocol `1.0`のRecordを`1.1`の意味で再解釈しない。
- READMEのinstall手順は、GitHubのlatest stable ReleaseとPyPIの公開versionが一致したことを確認してから、そのversionをcommandへ入れる。source内のversion文字列だけをpublication Evidenceにしない。

## 検証surface

- [`v1.0.4/walking-skeleton.json`](v1.0.4/walking-skeleton.json)は、追加したRecordが実際のreader経路へ接続される最初の縦切りを記録する。
- [`v1.0.4/live-paths.json`](v1.0.4/live-paths.json)は、merge前に観測できるrevision移行、re-Done、旧CLI fail-closedをproduction pathで検査する。native merge cutoffはunit／HTTP acceptanceで固定し、実GitHubのpost-merge観測はmergeが別途許可されるまでpendingとする。
- [`v1.0.4/public-record-disclosure.json`](v1.0.4/public-record-disclosure.json)は、公開Record／Evidenceへ秘密情報を転載しない境界を検査する。
- [`v1.0.4/release-candidate.json`](v1.0.4/release-candidate.json)は、source候補、line budget、build、install、test、Twine、artifact metadataを検査する。final source SHAはPR head確定後のEvidenceが所有し、この文書へ先書きしない。
- production Python budgetは`src/gtp/*.py`のphysical nonblank lines 2500以下とし、blank-line formattingはRuff 0.12.3の`E301`、`E302`、`E305`で独立して検査する。total linesとblank linesは観測値として残すが合否には使わない。

## 配布artifactの境界

- PR artifactは検証専用で、`v1.0.4-pr-verification-<SOURCE_SHA>`と命名する。
- native merge後にmainからbuildされるartifactだけを公開候補とし、`v1.0.4-main-candidate-<SOURCE_SHA>`と命名する。CIにpublish jobは置かない。
- Python 3.11 producerが同じsourceを2回buildしてbytesを比較し、Python 3.11、3.12、3.13のconsumerが同じartifactをclean installして検査する。`SOURCE_SHA`、`SOURCE_DATE_EPOCH`、`BUILD-INFO`、`SHA256SUMS`で候補物を束縛する。
- producerはbuilt sdistに収録されたsuiteも実行し、全testの成功、tracked件数との一致、skipがrepository-only 2件と`.git`なしのrelease-lock 2件だけであることを検査する。
- source完了後のtag、GitHub Release、PyPI upload、redownload確認は別の外部Operationであり、2本目のsource PRを必要条件にしない。

## Evidenceの限界

- valid Doneは、Done Claim、Contract revision、source head、Evidence resource、GitHub factの構造とbindingを検査した結果であり、Done Conditionが自然言語上・意味上、本当に充足されたことを証明しない。
- native mergeはGitHub上のsource受入事実であり、actor本人性、人間のreview、approval、authorizationを証明しない。
- test、Twine、checksum、clean install、再現buildは、publication、deployment、安全性全体、または将来環境での完全互換性を証明しない。
