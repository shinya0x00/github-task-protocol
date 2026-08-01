# ADR-036: exact sourceから一意な配布artifactを生成・検証する

- Status: Accepted; release branchとcandidate artifact identityはADR-037でsupersede
- Date: 2026-07-25
- Supersedes: None
- Superseded by: ADR-037（release branchとcandidate artifact identityのみ）

## 背景

配布物を公開する際は、「どのsourceから作ったか」と「どのbytesを検査したか」が後から一意に分かる必要がある。従来CIはPython versionごとにworking checkoutからsdistとwheelをbuildしたため、pull requestのmerge ref、localの未追跡file、archive metadata、またはbuildを行ったPythonの違いをartifact identityから切り離せなかった。

Python配布の既存形式であるsdistとwheel、再現可能buildで広く使われる`SOURCE_DATE_EPOCH`、およびSHA-256 checksumをそのまま使う。独自の配布形式、Record、state、halt reasonは追加しない。

## 決定

現行のCI構成と配布境界は[`DESIGN.md`](../DESIGN.md)が所有する。本ADRは、その構成を選んだ理由とtrade-offを所有する。

### source identity

- `pull_request`では`github.event.pull_request.head.sha`、`main` pushでは`github.sha`を唯一の`SOURCE_SHA`とする。checkout、commit timestamp取得、`git ls-tree`、`git archive`、build、artifact名をすべてこの値へ束縛する。
- `SOURCE_DATE_EPOCH`は`SOURCE_SHA`のcommit timestampから導出する。明示manifestはそのcommit treeの許可file集合と照合し、未宣言file、cache、symlink、非regular fileを収録しない。
- workflowが実行するGitHub Actionのidentityとrelease surface fixtureの対応値は、同じfull 40文字のlowercase commit SHAだけで表す。tagやversion labelを併記して第二のidentityにしない。

### buildと再現性検査

- producerはPython 3.11でのみ実行する。`SOURCE_SHA`から2つのclean source exportを作り、同じ`SOURCE_DATE_EPOCH`でsdistとwheelをそれぞれbuildし、filenameとbytesの一致を検査する。
- archive memberの順序、timestamp、owner、mode、ZIP metadataをbuild backendで正規化する。fresh virtual environmentでsdistから`pip wheel --no-index --no-deps`を実行し、直接buildしたwheelと同じbytesになることを検査する。
- `twine check`とSHA-256検査を行う。配布fileと同じartifactに`SHA256SUMS`と`BUILD-INFO`を入れ、`SOURCE_SHA`、`SOURCE_DATE_EPOCH`、`GITHUB_RUN_ID`、`GITHUB_RUN_ATTEMPT`、Python 3.11、zlib、filename、size、SHA-256を記録する。

### producerとconsumerの境界

- PR artifactは検証専用とし、`v1.0.3-pr-verification-<SOURCE_SHA>`と命名する。main artifactだけを公開候補とし、`v1.0.3-main-candidate-<SOURCE_SHA>`と命名する。どちらも保持期間は90日とする。
- consumerのPython 3.11、Python 3.12、Python 3.13はproducerが1回uploadした同じartifactをdownloadし、`SHA256SUMS`、clean install、installed CLI、unit testを検査する。matrixごとに新しい配布物をbuildしない。
- pull requestではsource-head build jobが`SOURCE_SHA`のtree、integration jobがsynthetic mergeの`HEAD`（merge tree）を同じmanifest oracleへ渡す。integration jobはmerge treeのmanifest parityとfull unit test／budgetを検査するが、clean export、公開候補sdist／wheel、Twine、sidecar、Actions artifact uploadから成るproducer処理は実行しない。unit testがtemporary directoryでbackendを検査するために作るarchiveは公開候補ではない。merge refは現在のmainとの統合結果だけを所有し、artifact identityまたはDone Evidenceには使用しない。`release-ready` Checkはbuild、3-version consumer matrix、PR時のintegrationの成功を集約する。
- workflowの権限は`contents: read`だけとする。tag作成、GitHub Release、PyPI uploadは行わない。main artifactが生成された後のartifact ID、run URL、expiry、checksum、再検査手順は公開operationのownerに引き継ぐ。

## 不採用案

- pull requestの`github.sha`を使う案は、GitHubが作るmerge refでありsource headと一致しない場合があるため採用しない。
- working checkoutから1回だけbuildする案は、未追跡fileの混入を拒否できず、同じ入力から同じbytesを再生成できることも観測できないため採用しない。
- Python matrixごとにbuildする案は、検査したartifact identityが複数に分かれ、どのbytesを公開候補とするか一意にならないため採用しない。
- 新しいrelease Recordまたは独自checksum schemaを作る案は、GTPの公開surfaceを広げ、既存のSHA-256 sidecarで満たせる要件へ別の用語を持ち込むため採用しない。

## 結果と限界

- `SOURCE_SHA`とsidecarから、検査した配布bytesとbuild条件を追跡できる。PRとmainのartifact identityが名前で区別できる。
- 同じsource、epoch、記録したPythonとzlib条件でのbyte一致を検査する。あらゆるOS、Python実装、zlib versionで同じbytesになることまでは証明しない。
- Checkとartifactはpublication、コード品質、credential安全性、merge authorityを与えない。GTP Record、state、halt reason、machine JSON key、protocol version、runtime dependency 0は変更しない。
