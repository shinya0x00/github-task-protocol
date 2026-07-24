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

agentが手順を理解できることと、実行中ずっと意図の境界内に留まり続けることは別の能力です。この手順はbranch-first順序で境界逸脱のriskを下げます。GTP単独の強制力はこの手順の受入対象にしません。repository ownerは補完策としてGitHub branch protectionまたはrulesetでdefault branchへの直接pushを拒否し、pull request経由の変更を必須にできます。setup agentは保護設定を変更せず、未設定なら人間へ報告します。

### file・branch変更前のpreflight

target fileの編集、branch作成、Issue／comment／label操作、PR作成より前に、read-onlyで既存instruction、task protocol authority、必要な外部provider／runtime／Operationとその接続状態を確認します。結果は次の4つだけです。

1. `instructionなし`: 通常setupを続行する。
2. `両立可能`: 既存instructionを保持し、adapterを非破壊で追加する通常setupを続行する。
3. `未接続dependency`: test／mock providerでproduction dependencyを代用せず、変更せずに外部Operation接続のblockerを報告する。
4. `別authority／意味衝突`: 自動統合や上書きをせず、人間のauthority判断へ戻す。

blockerでは、chatまたはconsoleへ「何が問題か」「どこが問題か」「なぜそう判断したか」「どこを直すか」「何を直さないか」「次の安全な一手」「最初に確認するURL」「解決したと判断する条件」の8項目を返します。外部Operationのowner URLはread-only取得で確認できた場合だけ表示し、不明なら`修正先Issue未確認`と表示します。

preflightとblocker報告はephemeralです。working tree、branch、commit、push、Issue、comment、label、PRを変更せず、repair Issueも自動作成しません。blocker解消後は同じ入力でpreflightを再実行します。`instructionなし`または`両立可能`の場合だけ、次の既存branch-first手順へ進みます。

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

CLI `1.0.2`は[PyPI](https://pypi.org/project/github-task-protocol/1.0.2/)と[GitHub Release](https://github.com/shinya0x00/github-task-protocol/releases/tag/v1.0.2)へ公開済みです。再downloadとhash・clean install・live statusの検証結果は[`acceptance/public-release-v1.0.2.json`](acceptance/public-release-v1.0.2.json)にあります。GTPを使うだけならCLIのinstallは不要です。

現在のsource candidateは`1.0.3`（公開前）です。tag、GitHub Release、PyPIにはまだ公開していないため、利用commandは検証済みの`1.0.2`に固定します。

```console
uvx --from github-task-protocol==1.0.2 gtp status <issue-url>
uvx --from github-task-protocol==1.0.2 gtp check <comment.md>
```

source candidate `1.0.3`で人向けGitHub投稿を行うOperationは、投稿直前に次の明示targetを実行し、exit `0`の場合だけ投稿します。これは未公開candidateの例であり、公開済み`1.0.2`に`--target`があるという案内ではありません。

```console
PYTHONPATH=src python3 -m gtp check <record-comment.md>
PYTHONPATH=src python3 -m gtp check --target issue <issue-body.md>
PYTHONPATH=src python3 -m gtp check --target pr <pr-body.md>
PYTHONPATH=src python3 -m gtp check --target comment <normal-comment.md>
```

target省略は`--target record`と同じです。人向けtargetは「何が起きたか」「何が変わるか」「何は変わらないか」「人間が次に判断すること」を、この順のH2として必須にし、任意の技術情報を最後の「技術的な検証情報」へ分離します。

`check`自身はGitHubへの投稿を実行または横取りしません。直接clientの未検査投稿は検出できないため、投稿するOperationが上記gateを接続します。

- 公開済み`1.0.2`の`status`はGitHubへGETだけを行い、日本語6項目の後にmachine JSONを出します。Evidenceの存在・種類・状態・source headとの結び付きを検査しますが、完了条件の自然言語上の充足までは自動判定しません。
- source candidate `1.0.3`は、blocker時だけ先頭6項目の直後に8項目の「問題の整理」を表示します。normal state、machine JSON、exit code、`authority: none`は変更しません。
- 公開済み`1.0.2`の`check`はGTP Record入りcommentをoffline検査します。source candidateだけが明示targetでIssue本文、PR本文、通常commentも検査します。
- human targetの`valid`は構造・先頭言語・技術情報配置の最低条件だけを示し、内容の真実性、人間の理解、GitHub上の状態を検査しません。
- Issue #118本文はcheckerと4-section migrationより前に作成されており、validatorが受理したEvidenceではありません。
- exit code、緑色のCheck Run、Evidence URLは、変更やmergeの許可ではありません。

## 仕様と判断記録

protocolの唯一の正本は400行以内の[`GTP.md`](GTP.md)です。Record作成やstate判断に、他の文書は必要ありません。

[`DECISIONS.md`](DECISIONS.md)は、設計変更の理由と履歴です。`GTP.md`と意味が衝突する場合は`GTP.md`を優先します。

実GitHubで観測した引き継ぎ結果は[`acceptance/level0/`](acceptance/level0/)にあります。これは仕様の代わりではありません。

## GTPが証明しないこと

GTPは、actor本人性、credential安全性、コード品質そのもの、Evidence内容の真実性を証明しません。filesystem削除や本番database操作を物理的に防ぐものでもありません。

サンドボックス、最小権限、不可逆操作前の確認、reviewと組み合わせてください。最終的な受理は、人間がPRとEvidenceを読み、GitHubのnative mergeで判断します。

License: [MIT](LICENSE)

GTPを試して、分かりにくかった所・詰まった所があれば、一言だけでも教えてもらえると助かります。IssueでもXでも。
