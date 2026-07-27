# GitHub Task Protocol

AIに作業を任せたあと、「何を頼んだか」「いまどこまで進んだか」「何を根拠に完成候補といえるか」をGitHub上の記録から確認するための小さなprotocolです。

> 作業はAIに任せる。判断は手放さない。

GTPは、GitHub Issueに残したRecordと、実際のbranch、PR、commit、Check Runを結び付けます。前の会話や実行環境を知らない人やAgentでも、GitHubだけを読んで現在地を確かめられます。

GTPは仕事の進め方を決めません。既存のinstructionsやrulesを定義、検証、上書きせず、`AGENTS.md`なども勝手に書き換えません。merge、公開、やり直しを決めるのは人間です。

## 何ができるか

- 作業前の目的、変更してよい範囲、完了条件を残す
- 作業中に確認項目が増えた履歴を、古い記録を消さずに追加する
- PRを直したあと、新しい内容について確認資料を出し直す
- 記録や確認資料が古い、足りない、矛盾しているときに成功扱いしない
- 最初に確認するURLと、直す場所・直さない場所を人向けに示す

RecordがないIssueでは、詳しい作業履歴を推測せずGTP上の管理対象外とします。この正式なstate名が`unmanaged`です。Recordがある場合だけ、そのIssueのGTP上の現在地を再構成します。どちらの場合も、既存のinstructionsやrulesの効力は変えません。

## protocol 1.1でできるようになったこと

package `1.0.4`は配布するCLIのversion、protocol `1.1`はIssueへ残すRecordの規則のversionです。CLIの更新番号と、記録形式の互換性を示す番号は別物です。

- `amendment`: 作業途中で確認項目を追加します。ただし、目的や変更範囲、branch、PRは変えません。
- re-Done: PRを直したら、新しいPR内容について、現在の全完了条件の確認資料を出し直します。

例えば、作業開始後に「別の環境でも確認する」という条件が必要になったら`amendment`で追加します。その後PRを直したら、追加前後を含むすべての完了条件について確認資料をそろえ、Doneを出し直します。過去のRecordは編集しません。

目的、変更範囲、branch、PRまで変える必要がある場合は`amendment`を使いません。元のIssueをStopで閉じ、人間が後継Issueを作るか判断します。参照関係やterminal ruleの正式な定義は[`GTP.md`](GTP.md)にあります。

## GTPの表示を読む

`gtp status`の人向け表示は、通常は次の6項目です。

### 通常は6項目

1. `状態`: GTPが再構成した現在地
2. `停止要否`: GTP上の次のtransitionへ進めるか
3. `次の行動`: 記録上、次に確認または提示するもの
4. `理由`: その状態になった理由
5. `最初のURL`: 人が最初に開くGitHub URL
6. `非許可表示`: この出力が変更・完了・mergeを許可しないこと

### `halt`時は8項目を追加

`halt`では、通常の6項目に加えて「問題の整理」を次の8項目で表示します。

GitHub情報を最後まで取得できずstateを決められない場合も、取得経路を確認できるよう同じ8項目を表示します。

1. `何が問題か`: 観測した不一致や不足
2. `どこが問題か`: 最初に確認するRecordやGitHub resource
3. `なぜそう判断したか`: 表示の根拠になった観測事実
4. `どこを直すか`: 修正候補
5. `何を直さないか`: 推測で変更してはいけないもの
6. `次の安全な一手`: まずread-onlyで行う確認
7. `最初に確認するURL`: 原因を確認できる場所
8. `解決したと判断する条件`: 再確認で見る結果

`halt`は「GTPの記録だけでは、そのtransitionを正しく確認できない」という状態です。それ自体は作業、merge、公開の禁止命令でも許可でもありません。最初のURLと8項目を読み、実際にどうするかは人間が判断します。

machine JSONの`authority: none`も同じ境界を表します。CLI、Record、緑のCheck、`state: done`は、人間の代わりにmergeや公開を許可しません。

## 人が判断すること

GTPはRecordとGitHub上の事実の対応を確認しますが、次は人が読み、判断します。

- 完了条件の文章が本当に満たされているか
- Check Runやartifactの内容が十分か
- Issue本文や通常commentに未解決事項がないか
- review、merge、公開を実行してよいか

表示に問題があれば、まず`最初のURL`を開きます。正式なRecord形式とstate規則は[`GTP.md`](GTP.md)、現在の実装構成は[`DESIGN.md`](DESIGN.md)、判断理由は[`adr/`](adr/)で確認できます。

## 正式なRecordとstate

protocol 1.0には4 Record、1.1には`amendment`を加えた5 Recordがあります。

| Record | 平易な意味 |
|---|---|
| `contract` | 目的、変更してよい範囲、完了条件を固定する |
| `start` | Contractと唯一の作業branchを結び付ける |
| `amendment` | Start後に新しい完了条件だけを追加する（1.1） |
| `done` | 特定のContract revisionとPR source headへ、条件ごとのEvidenceを提示する |
| `stop` | 完了を主張せず中止し、必要なら後継Issueを示す |

公開stateは次の6つです。

| state | 平易な意味 |
|---|---|
| `unmanaged` | recognized GTP Carrierがない |
| `ready` | ContractはあるがStart前 |
| `in_progress` | 作業中、merge待ち、またはCheck完了待ち |
| `halt` | 記録やGitHub factの不適合により、GTP上の次のtransitionを一意に決められない |
| `done` | current Doneがexact source headとEvidenceへ結び付き、そのheadのPRがnative mergeされた |
| `stopped` | Stopにより、このIssueでの作業を終了した |

`done`が示すのはsource PR lifecycleの完了です。tag作成、GitHub Release、PyPI公開、deploymentなど、merge後の外部Operationの完了は示しません。その結果は通常のGitHub記録へ残せますが、GTP stateは変わりません。

CheckがpendingのままPRがmergeされた場合は`in_progress`です。同じCheckがsuccessになれば新Recordなしで`done`へ進みます。merge後に`amendment`やre-Doneは追加できません。

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

人間がGTPを使うためにCLIをinstallする必要はありません。`gtp status`はGitHubへGETだけを行い、`gtp check`は投稿前Carrierをoffline検査します。

利用するpackage versionは、GitHubのlatest stable ReleaseとPyPIのversion pageの両方で同じ値が解決できることを確認して固定します。

```console
VERSION=<確認したversion>
uvx --from "github-task-protocol==$VERSION" gtp status <issue-url>
uvx --from "github-task-protocol==$VERSION" gtp check <comment.md>
```

このsource treeのPython distribution versionは`1.0.4`、新しいRecord protocolは`1.1`です。この値はpublicationのEvidenceでも、exact source commitのidentityでもありません。source metadataのpackage versionは配布候補の識別子です。

公開仕様の唯一の正本は[`GTP.md`](GTP.md)です。READMEの入口を守る行数上限の理由は[ADR-041](adr/0041-readme-human-entry-budget.md)にあります。License: [MIT](LICENSE)
