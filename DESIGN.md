# GTP implementation design

この文書は、GTP reader、presentation、setup／adapter、配布、外部Operation接続のcurrent architectureを所有する。公開protocolの意味は[`GTP.md`](GTP.md)、materialな判断理由は[`adr/`](adr/)が所有する。

pull requestのsource headにある文書は正準候補である。そのheadがmainへnative mergeされ、main上のpathを再取得できた後にrepositoryのcurrent canonical sourceとなる。

## 正準の所有範囲

| 正準 | 所有するFact | 所有しないFact |
|---|---|---|
| `GTP.md` | version別Record、state、transition、Evidence、native merge、Acquisition Error | implementation内部構成、個別Operationの手順 |
| `DESIGN.md` | reader、presentation、setup、配布、外部Operation境界のcurrent architecture | 公開protocolの新しい意味、過去判断の理由 |
| `adr/` | materialな判断、理由、trade-off、supersession | current architecture全体、task進行 |
| task Issue | 実行Contract、scope、進行、Evidenceへのreference | merge後の設計正本 |

衝突時は、公開protocolについて`GTP.md`、current implementationについて`DESIGN.md`、判断理由について未supersedeのADRを優先する。IssueとREADMEはprojectionであり、独立した意味を作らない。

## Source candidate status

このsource candidateは次を一つのreader／CLIへ接続する。

- protocol 1.0の既存4 Recordと、protocol 1.1の5 Record
- 1.0 baseから1.1へ明示的に移行するmixed history
- add-only amendment chainから導出するeffective Contract revision
- `previous_done_ref` chainから導出するcurrent Doneとre-Done
- current Done、exact source head、Evidence、native mergeから導出する6 state
- 1.0-only machine projectionの互換性と、1.1 projectionのversioned extension
- setup時の既存instructions非干渉、public Record disclosure、source／外部Operation分離

package `1.0.4`はこのsourceを識別するPython distribution versionであり、protocol `1.1`とは別である。mainへのmerge、tag、GitHub Release、PyPI uploadはこのsource candidateの実装factではない。

## Architecture

```text
GitHub Issue comments
        |
        v
 Exact Carrier parser -----> closed versioned schema
        |                         |
        `----------+--------------'
                   v
        Server Order reducer
        - Logical Record / safe retry
        - protocol transition
        - effective revision
        - current Done
                   |
                   v
       GET-only live binding reader
       Issue / branch / PR / head / files
       Check Run / artifact / native merge
                   |
          +--------+---------+
          v                  v
 machine projection    human presentation
```

parser、schema、reducerはGitHub mutationを行わない。live readerはGitHub resourceをGET-onlyで取得し、取得前後のsnapshotを比較する。取得不完全やsnapshot変化を`halt`へ推測せずAcquisition Errorとして分離する。

## Versioned Record model

Exact Markerはprotocol 1.0と1.1で共通の`<!-- gtp-record:v1 -->`である。versionはCarrier内の`gtp`が所有する。unknown versionはrecognized invalid Recordとしてfail closedにし、通常commentへ降格しない。

- 1.0: `contract`、`start`、`done`、`stop`
- 1.1: `contract`、`start`、`amendment`、`done`、`stop`

1.1の`contract`、`start`、`stop`は、`gtp`以外のfield集合を1.0から変えない。`amendment`と1.1 `done`だけを新しいclosed schemaとする。Recordごとのfield集合は`GTP.md` §5が正本であり、model、schema、fixture、presentationへ同じ集合をprojectionする。

1.0 Contract／Startから最初の1.1 amendmentまたはDoneへ移行できる。一度1.1へ移行した後の1.0 Recordは`invalid_transition`である。1.0-only pathは新しいfieldやchainを要求せず、既存のstate、halt reason、machine key、exit codeを維持する。

## Logical Recordとchain

同じID・同じJSONのsafe retry aliasは、最初のCarrier位置にある1 Logical Recordへ畳む。後方aliasでrevision tip、Done tip、terminal cutoffを動かさない。同じID・異なるJSONは`invalid_record`である。

### Effective Contract revision

original Contractをbaseとし、`predecessor_ref`が直前tipを指すamendmentだけを順に適用する。各amendmentは新規Done Conditionを1件以上加える。既存ID、`text`、`evidence_kind`を上書きせず、goal、scope、branch、PR、authorityを持たない。

fork、cycle、親飛ばし、self／forward／cross-Issue／cross-repository refを拒否する。schemaが保証するのは構造上のadd-onlyまでであり、新しい自然言語が既存条件を意味上弱めないことはhuman reviewへ残す。

### Current Done

最初のDoneは`previous_done_ref: null`、re-Doneは直前Logical Doneを指す。1本のchainのunique tipをcurrent Doneとする。re-Doneは同じIssue、Start branch、Bound PRで、current effective revisionとcurrent source headへ全Evidenceを束縛する。

head-only変更はamendmentを必要としない。古いDoneはhistorical Recordとして残し、new headへre-Doneする。後続Carrier、revision、Doneがinvalidなら診断を返し、過去のvalid Doneへfallbackしない。

## State evaluation

reducerがRecord historyを評価した後、live readerがbindingとEvidenceを加える。1.1の`state: done`は次の積であり、一つでも欠ければ導出しない。

```text
valid current Done
× current effective revision
× exact Bound PR source head
× complete successful Evidence bound to that head
× native merge of that head
× no later diagnostic or terminal violation
```

Done RecordはEvidence付きDone Claimである。`state: done`はsource PR lifecycleを再構成した結果であり、Done Recordの別名ではない。

Checkが既知のpending statusかつ`conclusion: null`ならDone Recordをinvalidにせず`in_progress`とする。merge後も同じCheck URLを再取得し、successになれば新Recordなしで`done`へ進む。

1.1ではnative mergeまたはStopをRecord受付のcutoffとする。Check pendingで`in_progress`でも、新しいrecognized Carrierはschema適合性より先に`terminal_violation`へ写像する。safe retry aliasだけは新Recordではない。merge前のstale headは同じPRへのre-Doneで修復できるが、staleなままmergeした後は修復できない。

通常commentとIssue open／closeはRecord chainとGTP stateを変更しない。publication、deploymentその他の外部Operationもstate evaluatorへ入力しない。

## Machine projection

1.0-only historyはtop-levelとcurrent Record群の既存key集合、値の意味、exit codeを維持する。mixed／1.1 historyはtop-level `gtp: "1.1"`を返し、`StatusResult.current`とCLIのRecord projection群へ`amendment`を加える。1.1 Doneの`revision_ref`と`previous_done_ref`を保持し、effective revisionとcurrent DoneをURLから再構成可能にする。

全versionで6 state、7 halt reason、`authority: none`を維持する。human presentationはmachine projectionと観測済みdiagnosticを説明するだけで、stateやauthorityを再判定しない。

## 既存instructionsとsetup

repository、organization、ユーザーが所有するinstructions、rules、authority boundaryは、その既存resourceがcanonical ownerである。GTPは内容、優先順位、正当性、十分性、実効性、遵守を定義または判定しない。

setup preflightはtarget file、branch、Issue、PRを変更する前に、既存instructionsと必要なdependencyをread-onlyで取得する。既存内容を保持してGTP adapterだけを追加できる場合に続行する。取得不能、外部dependency未接続、明白な意味／authority衝突では、自動統合や上書きをせずownerへ判断を戻す。

GTP adapterはGTP Recordの読み方だけを伝えるProjectionであり、既存instructions全体のProjectionや第二の規則体系ではない。Issue／PR／通常taskの入口にかかわらず、valid Contractがあれば既存historyを再構成し、なければCarrierを自動投稿しない。GTP stateから既存instructionsの適用状態を推測しない。

## Public Record disclosure

GitHubに永続化するRecord、通常comment、PR body、acceptance artifactには、公開先へ開示してよい派生情報だけを残す。goal、scope、Done Conditions、判断理由、Evidence、限界、unknown、`next_action`は、それぞれを所有する既存artifactへ置けるが、汎用fieldとしてRecordへ追加しない。

元の指示文、authorization本文、credential、credential path、private prompt、private command、private diagnostic、raw exception、synthetic canary本文を転載しない。外部Operationのauthorizationはその実行直前に外部authority境界で確認し、GTP Recordから推測しない。

synthetic canary acceptanceはhash、検査対象、match count、結果、限界だけを保存する。scanは検査対象と実行時点に限定され、あらゆる経路にprivate情報がないことまでは証明しない。

## 問題説明projection

`state: halt`、Acquisition Error、`gtp check`不適合、setup／外部Operation blockerでは、観測済み事実から次の8項目をhuman presentationへ出す。

1. 何が問題か
2. どこが問題か
3. なぜそう判断したか
4. どこを直すか
5. 何を直さないか
6. 次の安全な一手
7. 最初に確認するURL
8. 解決したと判断する条件

diagnostic tokenは最初に確認する層を示すが、根本原因や修正責任を単独で証明しない。原因URLがなければ既存`primary_url`を使い、どちらもなければ未確認と表示する。修正責任を確定できるのは、production outputから独立したexpected／observed比較とowner Evidenceが揃った場合だけである。

問題説明はread-onlyかつephemeral-by-defaultである。対象Issue、comment、label、branch、PR、working treeを自動変更せず、診断専用Record、repair Record、第二のworkflowを追加しない。詳細な判断理由は[ADR-035](adr/0035-human-actionable-problem-explanations.md)が所有する。

## Distribution boundary

pull requestでは`github.event.pull_request.head.sha`、main pushでは`github.sha`を唯一の`SOURCE_SHA`とする。checkout、commit timestamp、manifest、build、artifact identityをこのSHAへ束縛し、PR merge refをsource identityやDone Evidenceへ使わない。

producerはPython 3.11でexact sourceから2回buildし、sdist／wheelのbytes一致、sdist-to-wheel、SHA-256、Twineを検査する。同じuploaded artifactをPython 3.11、3.12、3.13 consumerが検査する。runtime dependencyは0を維持する。

PR artifactは`v1.0.4-pr-verification-<SOURCE_SHA>`、main artifactは`v1.0.4-main-candidate-<SOURCE_SHA>`とする。workflowの権限は`contents: read`だけであり、tag、GitHub Release、PyPIを変更しない。再現可能buildの詳細と限界は[ADR-036](adr/0036-reproducible-release-artifacts.md)が所有する。

READMEと配布metadataは、「現在公開済み」というmoving claimをsourceへ固定しない。利用時はGitHub latest stable ReleaseとPyPIの両方で解決したversionを選ぶ。したがってsource merge後・publication前とpublication後で文言修正用PRを必要としない。

native merge後のpublicationはGTP source taskと別のOperationである。source SHA、artifact、hash、tag、Release、PyPI、再download結果は通常のGitHub記録へ残せるが、GTP Record、Done Condition、stateへ取り込まない。

## Compatibility and limits

| Input history | CLI 1.0.3 | package 1.0.4 CLI |
|---|---|---|
| 1.0 only | 現行どおり | 同じ意味・同じ結果 |
| 1.0 base + 1.1 | unknown versionとしてfail closed | effective revision／current Doneを再構成 |
| 1.1 native | unknown versionとしてfail closed | closed schemaとして検査 |

fail closedはnonzero exitと同義ではない。旧CLIの実測ではstate、halt reason、exit codeを別々に記録する。

GTPはDone Conditionの自然言語上の充足、Evidence内容の真実性や十分性、actor本人性、review、approval、authorizationを証明しない。native mergeはGitHub factであり、それらの代用品ではない。

## 変更規則

- 公開protocol semanticsは`GTP.md`を同じlaneで更新し、versionと互換性を判断する。
- current architectureは`DESIGN.md`を更新する。
- materialな判断変更は新ADRでsupersessionを記録し、既存ADR本文を遡及編集しない。
- task Issueは実行ContractとEvidenceを所有し、merge後の正本や外部Operationの意味を再定義しない。
