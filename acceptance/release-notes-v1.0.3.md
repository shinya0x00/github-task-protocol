# GitHub Task Protocol 1.0.3 release notes

この文書は、package version `1.0.3`のsourceに含まれる変更を説明する。tag、GitHub Release、PyPIでのpublicationをClaimしない。公開状況はrepository内のversion文字列ではなく、各公開先と公開後Evidenceで確認する。

## 変更内容

- `state: halt`のとき、既存の診断事実から非エンジニアも修正境界を判断できる8項目の「問題の整理」を表示する。machine JSONのkey集合、exit code規則、`authority: none`は変更しない。
- 既知の非終端Check Run statusは、responseに`conclusion` keyが存在し、値が明示的な`null`の場合だけpendingとする。key自体が欠落したresponseは既存の`invalid_evidence`とする。
- sdistとwheelはexplicit manifestに宣言したregular fileだけを収録する。archive memberの順序とmetadataを正規化する。CIはcommit timestampを`SOURCE_DATE_EPOCH`として渡し、未指定のbuildは固定値`0`を使う。
- sdistは`DESIGN.md`、`DECISIONS.md`、`adr/`を収録し、current designとADR-035・ADR-036をarchive内で解決できるようにする。
- CIはpull requestのsource headまたはmain push commitを`SOURCE_SHA`に固定する。Python 3.11 producerが2つのclean source exportから再buildしてbytesを比較し、`SHA256SUMS`と`BUILD-INFO`を添付する。
- pull requestではsource-head build jobが`SOURCE_SHA`のtree、integration jobがsynthetic mergeの`HEAD`（merge tree）を同じmanifest oracleへ渡す。integration jobはmerge treeのmanifest parityとfull unit test／budgetを検査するが、clean export、公開候補sdist／wheel、Twine、sidecar、Actions artifact uploadから成るproducer処理は実行しない。unit testがtemporary directoryで作るarchiveは公開候補ではない。merge refを公開候補のsourceにはしない。最後の`release-ready` Checkはbuild、3-version consumer matrix、integrationの結果を集約する。
- Python 3.11、3.12、3.13のconsumerは同じbuild artifactをdownloadし、checksum、clean install、installed CLI、unit testを検査する。
- READMEはsource versionとpublicationを分離し、特定versionの公開前後で意味が変わらないinstall案内にする。

Record grammar、`"gtp": "1.0"`、6 state、7 halt reason、machine JSON key、`next_action`、runtime dependency 0は変更しない。

## 含めないもの

generic Contract amendment semantics、human-post checker／gate、line-budgetの置き換えまたはstatus split、tag・GitHub Release・PyPI uploadなどのpublication operationは、1.0.3のartifact修復に含めない。

## 配布artifactの境界

- PR artifactは検証専用であり、`v1.0.3-pr-verification-<SOURCE_SHA>`と命名する。
- squash merge後のmain artifactだけを公開候補とし、`v1.0.3-main-candidate-<SOURCE_SHA>`と命名する。CI自体は公開しない。
- artifactの保持期間は90日である。公開前にsource SHA、`GITHUB_RUN_ID`、`GITHUB_RUN_ATTEMPT`、artifact IDとexpiry、filename、size、SHA-256、Pythonとzlib条件、再検査手順を公開operationの記録へ引き継ぐ。

## Evidenceの限界

- 2回のbyte一致は、同じ`SOURCE_SHA`、`SOURCE_DATE_EPOCH`、記録したPythonとzlib条件での再現性を示す。未記録の実行環境まで同一bytesになることは保証しない。
- `twine check`、checksum、clean install、unit testは公開、merge、安全性全体、または自然言語のDone Conditionの十分性を証明しない。
- tag作成、GitHub Release、PyPI upload、公開後のredownloadとlive status検査には、それぞれ別のauthorityとEvidenceが必要である。
