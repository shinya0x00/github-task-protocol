# ADR-038: protocol 1.1のrevisionとpackage versionを分離する

- Status: Accepted
- Date: 2026-07-26
- Supersedes: None
- Superseded by: None

## 背景

protocol 1.0のContractはStart後に凍結され、DoneもIssueごとに1件だった。そのため、作業中に完了条件を追加する場合や、Done後に同じPRのsource headが変わる場合は、古い判断を残したまま同じIssueで続けられなかった。

一方、公開済みの1.0 historyは既存readerが解釈している。新しいfieldやRecordを`gtp: "1.0"`へ黙って追加すると、過去の意味とunknown versionのfail-closed境界を壊す。

配布packageとRecord protocolには別の変更頻度と互換性がある。Python distributionのversion `1.0.4`を、protocolの互換性やSemantic Versioningのpatch保証と同一視できない。

## 決定

### Protocol version

新しいRecord grammarをprotocol `1.1`として定義する。Exact Markerは`<!-- gtp-record:v1 -->`を維持し、Carrier内の`gtp`で1.0と1.1を区別する。

- protocol 1.0は`contract`、`start`、`done`、`stop`の4 Recordを維持する。
- protocol 1.1は`amendment`を加えた5 Recordを持つ。
- 1.1 `amendment`はDone Conditionsだけをadd-onlyで追記し、linearなeffective Contract revisionを作る。
- 1.1 `done`は`revision_ref`と`previous_done_ref`を持ち、current revisionとlinearなDone chainへ束縛する。
- latest Doneがinvalidなら、過去のvalid Doneへfallbackしない。
- 1.0 baseから最初の1.1 amendmentまたはDoneで明示的に移行できる。1.1後の1.0 downgradeは`invalid_transition`とする。

1.0-only historyのstate、halt reason、binding、machine projection、exit codeを変更しない。旧CLI 1.0.3は同じExact Marker内の1.1をunknown versionとして認識し、通常commentとして読み飛ばさずfail closedにする。fail closedとnonzero exitは同義とせず、実測したstate、halt reason、exit codeを別々に記録する。

### Package version

このsourceをbuildするPython distributionのversionは`1.0.4`とする。この値は[Python packaging version scheme](https://packaging.python.org/en/latest/specifications/version-specifiers/)に従うpublic version identifierである。

package `1.0.4`は次を意味しない。

- [Semantic Versioning](https://semver.org/)におけるpatch互換性の保証
- protocol versionまたはRecord grammarの識別
- exact source commitのidentity
- GitHub ReleaseやPyPI publicationが完了したというEvidence

Record／reader互換性はprotocol versionとcompatibility matrixで示す。exact source identityはfull commit SHA、配布bytesはfilenameとSHA-256で示す。利用可能な公開versionは、GitHub latest stable ReleaseとPyPIの両方で同じversionが解決することを確認して選ぶ。

| Input history | CLI 1.0.3 | package 1.0.4 CLI |
|---|---|---|
| 1.0 only | 現行どおり | 同じ意味・同じ結果 |
| 1.0 base + 1.1 | unknown versionとしてfail closed | effective revision／current Doneを再構成 |
| 1.1 native | unknown versionとしてfail closed | closed schemaとして検査 |

## 理由

protocol versionを上げれば、旧readerは未知のmeaningを成功扱いせず、新readerはclosed grammarを明示的に選べる。package versionと分ければ、実装releaseの順序とRecord compatibilityを一つの数字へ過剰に背負わせない。

既存のExact Markerを維持することで、旧CLIも1.1 Carrierをrecognized inputとして検査できる。markerを変えて通常commentへ見せる方式よりfail-closed境界が強い。

## 検討した代替案

### `gtp: "1.0"`へ新fieldを追加する

不採用。closed schemaと公開済み1.0 historyの意味を遡及変更する。

### Exact Markerをv2へ変える

不採用。旧readerが1.1を通常commentとして無視し、古いDoneへfallbackできる。

### package `1.0.4`をSemVer patchとして説明する

不採用。このprojectはSemVerのpublic API compatibility contractをpackage versionへ割り当てていない。実際の互換性境界はversioned Record grammarにある。

### source commit、package version、protocol versionを一つにする

不採用。commit、distribution、Record grammarはidentityとlifecycleが異なり、一つの値では正確に束縛できない。

## 結果と限界

- 1.0 historyをそのまま保ち、1.1でamendmentとre-Doneを導入できる。
- package metadataだけからpublicationやexact sourceをClaimできない。
- compatibility matrixは定義したreader behaviorを示すが、Done Conditionの意味上の充足や任意の将来versionとの互換性を保証しない。
