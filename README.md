# GitHub Task Protocol

AIに作業を任せたあと、「何を約束したのか」「どこまで終わったのか」「何を根拠にそう言えるのか」が会話の外でも分かるようにする小さなprotocolです。

> 作業はAIに任せる。判断は手放さない。

GTPは、GitHub Issueに残したRecordと、実際のbranch、PR、commit、Check Runを結び付けます。前の会話や実行環境を知らない人やAgentでも、GitHubから現在地を再構成できます。

GTPは仕事の進め方を決めません。repository、organization、ユーザーが既に持つinstructionsやrulesの内容を定義、検証、上書きせず、`AGENTS.md`なども勝手に書き換えません。運用を決めるのはユーザーで、GTPが行うのは残されたRecordの読み取りと接続です。

## 何ができるか

- 作業前の目的、変更範囲、完了条件をContractへ固定する
- 作業中に条件が増えた履歴を、古い条件を消さずに追記する
- PRのsource headが変わったら、古いDoneを残したまま新headへDoneを再提示する
- 最新の不正なDoneを無視して、都合よく古いDoneへ戻らない
- Evidenceが足りない、古い、矛盾している、取得できない状態を成功扱いしない

RecordがないIssueでは、詳しい作業履歴を推測せず`unmanaged`とします。valid Contractがあれば、mode選択を求めず、そのIssueのGTP lifecycleを再構成します。これは既存instructionsやrulesの適用状態を変えるものではありません。

## Recordとstate

protocol 1.0には4 Record、1.1には`amendment`を加えた5 Recordがあります。

| Record | 平易な意味 |
|---|---|
| `contract` | 目的、変更してよい範囲、完了条件を固定する |
| `start` | Contractと唯一の作業branchを結び付ける |
| `amendment` | Start後に新しい完了条件だけを追記する（1.1） |
| `done` | 特定のContract revisionとPR source headへ、条件ごとのEvidenceを提示する |
| `stop` | 完了を主張せず中止し、必要なら後継Issueを示す |

公開stateは次の6つです。

| state | 平易な意味 |
|---|---|
| `unmanaged` | recognized GTP Carrierがない |
| `ready` | ContractはあるがStart前 |
| `in_progress` | 作業中、merge待ち、またはCheck完了待ち |
| `halt` | 記録やGitHub factの不適合により一意に進めない |
| `done` | Done chainのcurrent Doneがexact source headとEvidenceへ結び付き、そのheadのPRがnative mergeされた |
| `stopped` | Stopにより、このIssueでの作業を終了した |

Done Recordは完成候補を示す自主検査記録であり、それだけでtask完了にはなりません。`state: done`は、Done chainのcurrent Done、現在のContract revision、exact source head、全Evidence、native mergeを確認して初めて導出されます。これは独立した検査員の承認、actor本人性、review、approval、authorityを意味しません。

CheckがpendingのままPRがmergeされた場合は`in_progress`です。同じCheckがsuccessになれば新Recordなしで`done`へ進みますが、merge後にamendmentやre-Doneは追加できません。

`done`が示すのはsource PR lifecycleの完了です。tag作成、GitHub Release、PyPI公開、deploymentなど、merge後の外部Operationの完了は示しません。その結果は通常のGitHub記録へ残せますが、GTP stateは変わりません。

## amendmentとre-Done

1.1の`amendment`は、既存のDone Conditionを変更・削除せず、新しい条件だけを追加します。goal、scope、branch、PRを変える汎用patchではありません。そこまで変える場合はStopと後継Issueを使います。

amendment後のDoneは、追加後の最新Contract revisionを指す必要があります。新しい条件が古い条件を意味上弱めていないかは人が読みます。GTPが自動確認するのは構造上のadd-onlyまでです。

re-Doneは同じIssue、branch、PRで、直前のDoneと現在のContract revisionを指し、新しいsource headへEvidenceを出し直します。古いDoneは当時の記録として残ります。後続Doneがinvalidなら`halt`となり、過去のvalid Doneへfallbackしません。

## GTPが証明しないこと

GTPは、存在するRecordを決められた規則で解釈し、GitHub factへ結び付けます。次のことまでは証明しません。

- Done Conditionが自然言語上、本当に満たされたこと
- Evidenceの内容が真実、十分、高品質であること
- 本当は存在したすべての判断やunknownが記録されたこと
- actor本人性、credential安全性、authority、review、approval
- コードや作業結果そのものの正しさ

記録の細かさは利用者の運用次第です。GTPは足りない事実を推測で埋めず、分からないことを分かったふりをしません。

## 導入

bare repository URLだけではsetup依頼にも変更authorizationにもなりません。導入先repositoryを操作中のAgentへ、対象とDraft setup PR作成を明示してください。

```text
このrepositoryへGTPを導入するDraft setup PRを作ってください。
GTP repository: https://github.com/shinya0x00/github-task-protocol
```

setup Agentは、fileやbranchを変える前に既存instructions、必要なauthority、外部dependencyをread-onlyで確認します。既存内容を保持してadapterを追加できる場合だけ、次へ進みます。取得不能や明白な衝突があれば自動統合せず、その内容を所有する人へ判断を戻します。

1. GitHubのlatest stable Releaseが`draft: false`、`prerelease: false`であることを確認し、tagをexact commit SHAへ固定する。
2. target fileを変える前にdefault branch headからsetup branchを作り、switchを確認する。
3. 固定commitの`GTP.md`だけをrootへ置く。異なる既存`GTP.md`を上書きしない。
4. 既存instructionを変更・削除せず、[`GTP.md`](GTP.md) §16のadapter文だけを非破壊で追加する。
5. setup branchだけをcommit、pushし、release tag、exact SHA、変更file、保持したinstructionsを示すDraft PRを作る。
6. 人がsetup PRをmergeしてから、taskごとにIssueを1件作る。

共通adapter文:

> このrepositoryはrootの`GTP.md`をtask protocolの唯一の正本とする。GitHub Issue URLを受け取ったら、Issue commentをServer Orderで読み、protocol versionに対応するRecord、6 state、7 halt reasonに従って既存branch・PR・次のprotocol actionを再構成する。Recordを推測、編集、独自拡張せず、矛盾時は原因URLを示して止まり、取得不能はhaltと混同しない。GTPの表示やRecordは変更・完了・mergeの権限を与えない。

## CLIは任意の検証器

人間がGTPを使うためにCLIをinstallする必要はありません。`gtp status`はGitHubへGETだけを行い、`gtp check`は投稿前Carrierをoffline検査します。CLI、exit code、緑のCheckは変更やmergeの許可ではありません。

利用するpackage versionは、GitHubのlatest stable ReleaseとPyPIのversion pageの両方で同じ値が解決できることを確認して固定します。

```console
VERSION=<確認したversion>
uvx --from "github-task-protocol==$VERSION" gtp status <issue-url>
uvx --from "github-task-protocol==$VERSION" gtp check <comment.md>
```

このsource treeのPython distribution versionは`1.0.4`、新しいRecord protocolは`1.1`です。この値はpublicationのEvidenceでも、exact source commitのidentityでもありません。source metadataのpackage versionは配布候補の識別子です。package versionはPython packagingのversion identifierであり、Semantic Versioningのpatch互換性を主張しません。Record／reader互換性はprotocol versionで示します。理由は[ADR-038](adr/0038-protocol-1-1-revisions-and-package-versioning.md)にあります。

公開仕様の唯一の正本は400行以内の[`GTP.md`](GTP.md)、current architectureは[`DESIGN.md`](DESIGN.md)、materialな判断理由は[`adr/`](adr/)です。

License: [MIT](LICENSE)
