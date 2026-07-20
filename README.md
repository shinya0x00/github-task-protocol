# GitHub Task Protocol

GTPは、AIへ実装を任せても、人間が目的・変更範囲・現在地・根拠を理解し、停止・再開・やり直し・mergeの判断を手放さないための小さなprotocolです。

> 作業はAIに任せる。判断は手放さない。

AIの説明だけを信じるのではなく、GitHub Issue上のRecordと、実際のbranch・PR・commit・Check Runからtask stateを再構成します。GTP自身は変更、完了、mergeの権限を与えません。

task固有の未確認事項は、通常のIssue本文やcommentへ人が読める形で残します。開始前から完了判断に必要な不明点はDone Conditionにし、開始後にContract変更が必要になった場合はStopと後継Issueへ移ります。GTP Recordは自由文の意味を自動評価しないため、`status`はDone提示前にIssueを確認するURLを表示します。

## 推奨: 明示的にsetupを依頼

bare GTP repository URLだけではsetup依頼にもrepository変更のauthorizationにもなりません。URLだけを受け取ったagentは、説明または目的確認に留まり、現在のrepositoryを変更しません。

導入先repositoryを操作中のclean agentへ、変更対象とDraft setup PR作成を明示して依頼します。

```text
このrepositoryへGTPを導入するDraft setup PRを作ってください。
GTP repository: https://github.com/shinya0x00/github-task-protocol
```

この明示依頼を受けたagentは、次の順序でsetupします。

この手順はdefault branchへの誤操作を低減しますが、pushを物理的には阻止しません。repository ownerはGitHub branch protectionまたはrulesetでdefault branchへの直接pushを拒否し、pull request経由の変更を必須にします。setup agentは保護設定を変更せず、未設定なら人間へ報告します。

1. GitHubのlatest stable Releaseを取得し、`draft: false`かつ`prerelease: false`を確認する。未公開candidateやmoving `main`は選ばない。
2. Releaseのtagをcommit SHAまでdereferenceし、選択したtagとexact commit SHAを記録する。
3. target fileを変更する前にrepositoryのdefault branch名とhead SHAを記録し、そのheadから`gtp/setup-<tag>-<short-sha>` branchを作ってswitchする。現在branchがdefault branchではなくsetup branchであることを確認できなければ停止する。
4. そのcommitの`GTP.md`だけを`https://raw.githubusercontent.com/shinya0x00/github-task-protocol/<commit-sha>/GTP.md`から取得し、導入先rootへvendorする。既存`GTP.md`とSHA-256が同一なら保持する。内容が異なるfile、別のGTP authority、または既存instructionとの衝突があれば、上書きせず停止して人間へ報告する。
5. root `AGENTS.md`がなければ作成する。存在する場合は本文を変更・削除せず、下のexact adapterがなければ`## GitHub Task Protocol adapter` heading付きで追記する。既に同じadapterがあれば重複追加しない。
6. commitとpushはsetup branchだけに行い、default branchへ直接pushしない。push後にdefault branch headを再取得し、setup開始前に記録したSHAから予期せず変化していたら停止して報告する。Draft setup PRのbodyにはrelease tag、exact commit SHA、immutable `GTP.md` URL、変更file、保持した既存instruction、次に必要な人間判断を書く。
7. 人間がsetup PRをmergeするまで導入完了としません。merge後、taskごとにGitHub Issueを1件作り、agentへそのIssue URLだけを渡します。

共通adapter文:

> このrepositoryはrootの`GTP.md`をtask protocolの唯一の正本とする。GitHub Issue URLを受け取ったら、Issue commentをServer Orderで読み、4 Record、6 state、7 halt reasonに従って既存branch・PR・次のprotocol actionを再構成する。Recordを推測、編集、独自拡張せず、矛盾時は原因URLを示して止まり、取得不能はhaltと混同しない。GTPの表示やRecordは変更・完了・mergeの権限を与えない。

配置例は次のとおりです。runtimeごとに異なる指示を作る必要はありません。

- Codex: `AGENTS.md`
- Claude Code: `CLAUDE.md`または`AGENTS.md`
- Cursor: `AGENTS.md`または`.cursor/rules/gtp.md`

## 手動導入

自動setupを使わない場合は、次の3手順で導入できます。

1. latest stable Releaseをexact commitへ固定し、file変更前にdefault branchからsetup用branchを作ってswitchする。
2. setup branch上で`GTP.md`をrootへコピーし、共通adapter文を既存instructionへ非破壊で追加する。
3. commitとpushをsetup branchだけに行ってDraft PRを作り、人間が内容を確認してmergeする。

## 4つのRecord

| Record | 平易な意味 |
|---|---|
| `contract` | 目的、変更してよい範囲、完了条件を固定する |
| `start` | Contractと唯一の作業branchを結び付ける |
| `done` | PRのsource headと、条件ごとのEvidenceを提示する |
| `stop` | 完了を主張せず中止し、必要なら後継Issueを示す |

RecordはIssue commentへ人向け要約を先に、機械用JSONを折りたたんで記録します。1 Issue = 1 branch = 1 PRです。
Start branchへrepositoryのdefault branchは指定できません。
Startより前から存在するPRは、そのtaskのcandidateやDoneとして引き継げません。誤ったStartをStopする場合は、古いPRを対象外として安全に閉じます。

## 6つのstate

| state | 平易な意味 |
|---|---|
| `unmanaged` | 有効なContractがない |
| `ready` | ContractはあるがStart前 |
| `in_progress` | 作業中、またはDone提示後のmerge待ち |
| `halt` | 特定transitionを矛盾や不適合のため進められない |
| `done` | Doneのsource headへEvidence resourceが結び付き、そのPRがnative mergeされた。条件内容の十分性は人がEvidenceを読んで判断する |
| `stopped` | Stopにより、このIssueでの作業を終了した |

GitHub情報を完全に取得できない場合はstateを推測しません。404だけではresource不在と権限不足を区別できないため、これは`halt`ではなくAcquisition Errorです。

## CLIは任意の検証器

人間がGTPを使うためにCLIをinstallする必要はありません。`gtp`はagentや自動検査がRecordと現在stateを確認するための、runtime dependency 0の任意toolです。

CLIはPyPI公開後、固定versionを指定して実行できます。現在のsource candidateは`1.0.2`であり、公開確認前です。公開済み`1.0.1`はこのcandidateと挙動が異なるため、下記commandは`1.0.2`の公開Evidence取得後に使用します。GTPを使うだけならCLIのinstallは不要です。

```console
uvx --from github-task-protocol==1.0.2 gtp status <issue-url>
uvx --from github-task-protocol==1.0.2 gtp check <comment.md>
```

- `status`はGitHubへGETだけを行い、日本語6項目の後にmachine JSONを出します。Evidenceの存在・種類・状態・source headとの結び付きを検査しますが、完了条件の自然言語上の充足までは自動判定しません。
- `check`は投稿前のMarkdown comment全文をoffline検査します。Issue上でもvalidだとは主張しません。
- exit code、緑色のCheck Run、Evidence URLは、変更やmergeの許可ではありません。

## 仕様と判断記録

protocolの唯一の正本は400行以内の[`GTP.md`](GTP.md)です。Record作成やstate判断に、他の文書は必要ありません。

[`DECISIONS.md`](DECISIONS.md)は、設計変更の理由と履歴です。`GTP.md`と意味が衝突する場合は`GTP.md`を優先します。

実GitHubで観測した引き継ぎ結果は[`acceptance/level0/`](acceptance/level0/)にあります。これは仕様の代わりではありません。

## GTPが証明しないこと

GTPは、actor本人性、credential安全性、コード品質そのもの、Evidence内容の真実性を証明しません。filesystem削除や本番database操作を物理的に防ぐものでもありません。

サンドボックス、最小権限、不可逆操作前の確認、reviewと組み合わせてください。最終的な受理は、人間がPRとEvidenceを読み、GitHubのnative mergeで判断します。

License: [MIT](LICENSE)
