# GitHub Task Protocol

GTPは、AIへ実装を任せても、人間が目的・変更範囲・現在地・根拠・未確認事項を理解し、停止・再開・やり直し・mergeの判断を手放さないための小さなprotocolです。

> 作業はAIに任せる。判断は手放さない。

AIの説明だけを信じるのではなく、GitHub Issue上のRecordと、実際のbranch・PR・commit・Check Runからtask stateを再構成します。GTP自身は変更、完了、mergeの権限を与えません。

## 導入は3手順

1. [`GTP.md`](GTP.md)を導入先repositoryのrootへコピーする。
2. 下の共通adapter文を、agentが必ず読む文書へ1段落追加する。
3. taskごとにGitHub Issueを1件作り、agentへそのIssue URLを渡す。

共通adapter文:

> このrepositoryはrootの`GTP.md`をtask protocolの唯一の正本とする。GitHub Issue URLを受け取ったら、Issue commentをServer Orderで読み、4 Record、6 state、7 halt reasonに従って既存branch・PR・次のprotocol actionを再構成する。Recordを推測、編集、独自拡張せず、矛盾時は原因URLを示して止まり、取得不能はhaltと混同しない。GTPの表示やRecordは変更・完了・mergeの権限を与えない。

配置例は次のとおりです。runtimeごとに異なる指示を作る必要はありません。

- Codex: `AGENTS.md`
- Claude Code: `CLAUDE.md`または`AGENTS.md`
- Cursor: `AGENTS.md`または`.cursor/rules/gtp.md`

## 4つのRecord

| Record | 平易な意味 |
|---|---|
| `contract` | 目的、変更してよい範囲、完了条件を固定する |
| `start` | Contractと唯一の作業branchを結び付ける |
| `done` | PRのsource headと、条件ごとのEvidenceを提示する |
| `stop` | 完了を主張せず中止し、必要なら後継Issueを示す |

RecordはIssue commentへ人向け要約を先に、機械用JSONを折りたたんで記録します。1 Issue = 1 branch = 1 PRです。

## 6つのstate

| state | 平易な意味 |
|---|---|
| `unmanaged` | 有効なContractがない |
| `ready` | ContractはあるがStart前 |
| `in_progress` | 作業中、またはDone提示後のmerge待ち |
| `halt` | 特定transitionを矛盾や不適合のため進められない |
| `done` | Doneのsource headとEvidenceを持つPRがnative mergeされた |
| `stopped` | Stopにより、このIssueでの作業を終了した |

GitHub情報を完全に取得できない場合はstateを推測しません。これは`halt`ではなくAcquisition Errorです。

## CLIは任意の検証器

人間がGTPを使うためにCLIをinstallする必要はありません。`gtp`はagentや自動検査がRecordと現在stateを確認するための、runtime dependency 0の任意toolです。

CLI 1.0.2のPyPI公開後は、固定versionを指定して実行できます。GTPを使うだけならCLIのinstallは不要です。

```console
uvx --from github-task-protocol==1.0.2 gtp status <issue-url>
uvx --from github-task-protocol==1.0.2 gtp check <comment.md>
```

- `status`はGitHubへGETだけを行い、日本語6項目の後にmachine JSONを出します。
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
