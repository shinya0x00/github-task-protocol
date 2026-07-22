# GTP implementation design

この文書は、GTP reader、presentation、setup／adapter、外部Operation接続、通常のIssue→PR workflowのcurrent implementation architectureを所有する。

公開protocolの意味は[`GTP.md`](GTP.md)だけが所有する。この文書やADRだけで、4 Record、6 state、7 halt reason、transition、Evidence、native merge、Acquisition Error、CLI machine contractの意味を変更しない。protocol変更が必要な場合は、同じ変更laneで`GTP.md`を更新する。

## 正準の所有範囲

| 正準 | 所有するFact | 所有しないFact |
|---|---|---|
| `GTP.md` | 公開Record、state、transition、Evidence、native merge、Acquisition Error、CLI machine contract | implementation内部の構成、個別Operationのpolicy |
| `DESIGN.md` | reader、presentation、setup／adapter、外部Operation接続、非干渉境界を含むcurrent architecture | 公開protocol vocabularyの追加・変更、過去判断の理由 |
| `adr/` | materialな判断、理由、trade-off、supersession | current architecture全体、taskの進行状態 |
| 親Issue #97 | 正準へのlink、受け入れ条件の要約、子Issueの進行状態 | 設計、実装仕様、GTP task state |
| 子Issue | 1 PR分の実行contract、scope、完了条件 | merge後の設計正本 |

正準が衝突する場合、公開protocolについては`GTP.md`、current implementationについては`DESIGN.md`、materialな判断理由については未supersedeのADRを優先する。親Issueと子Issueはこれらを参照するprojectionであり、新しい意味を作らない。

## Architecture

```text
GitHub Issue comments + live GitHub resources
                    |
                    v
             read-only reader
                    |
                    +--> machine projection
                    |    (既存schema・token・authority: none)
                    |
                    `--> human presentation
                         (normal summary / blocker時だけ問題の整理)

explicit setup request + target repository observations
                    |
                    v
          setup／adapter preflight
                    |
       proceed または ephemeral blocker report

external Operation observations
                    |
                    v
       Operation ownerを参照するephemeral report
```

- readerはGitHubの観測事実をGET-onlyで取得し、`GTP.md`に従ってstate、diagnostic、Acquisition Errorを導出する。
- machine projectionは既存のdiagnostic、acquisition error、`primary_url`、`authority: none`を保持する。
- human presentationはmachine projectionと既存診断事実を説明する。stateやauthorityを再判定しない。
- setup／adapter preflightはtarget fileまたはbranchを変更する前に既存instruction、authority、外部dependencyを読む。
- 外部Operationの内部rule、provider、activationはそのOperationのownerが所有し、GTPは推測または複製しない。

## 通常workflow

blockerがなければ、次のworkflowと既存の通常表示を変更しない。

```text
Issue -> Contract -> Start -> branch -> PR -> Done -> Human native merge
```

問題説明は通常のIssue本文やPR本文へ常設しない。問題説明を見て人間が修正を選んだ場合も、診断専用workflowへ移らず、通常の別IssueでContractから開始する。

## 問題説明projection

問題説明は、既存の診断事実から人間向けに導出するread-onlyかつephemeral-by-defaultなpresentation projectionである。対象は次に限定する。

- `state: halt`の7 halt reason
- `state: null / acquisition: incomplete`
- `gtp check`のCarrier未認識、形式／JSON／schema不適合、input error
- setup先の既存instruction、authority、外部dependencyによるblocker
- 外部Operationの未接続またはactivation blocker

### 表示する8項目

| 順序 | 項目 | 表示する内容 | 推測しない内容 |
|---:|---|---|---|
| 1 | 何が問題か | 観測済みdiagnosticまたはblockerの平易な要約 | 未観測の原因、成功／完了claim |
| 2 | どこが問題か | Record履歴、binding、Evidence、取得経路、入力Carrier、setup先、外部Operationのいずれか | 一意に決められない所有層 |
| 3 | なぜそう判断したか | diagnostic token、error code、観測値、参照URL | private diagnostic、raw exceptionからの憶測 |
| 4 | どこを直すか | 観測事実が所有する最小の修正対象 | 関係のないrepository、protocol vocabulary |
| 5 | 何を直さないか | 守る正準、Record、state、対象外resource | 将来必要かもしれない変更 |
| 6 | 次の安全な一手 | read-only確認、再取得、人間判断、通常の後継Issueのいずれか | 自動修復、自動mutation |
| 7 | 最初に確認するURL | diagnosticの先頭URL。なければ既存`primary_url` | 存在未確認のURL、private URL |
| 8 | 解決したと判断する条件 | 同じ入力を再検査したときに観測すべき具体的結果 | Evidenceが保証しない内容の十分性 |

「どこを直すか」と「何を直さないか」は必ず同時に表示する。修正対象だけでは、非エンジニアがGTP coreや正常なresourceまで変更する指示を出す危険があるためである。

### 所有層mapping

| 入力 | 問題の所有層 | 修正候補 | 変更しない対象 |
|---|---|---|---|
| `invalid_record`、`conflicting_records`、`invalid_transition` | 対象IssueのRecord履歴 | 原因commentの確認と、必要なら人間判断後のStop／後継Issue | Carrierの編集・削除、Record grammar |
| `invalid_binding` | Issue、branch、PR、scopeのbinding | 原因URLで参照関係と変更fileを確認 | 4 Record、6 state、7 halt reason |
| `invalid_evidence`、`stale_evidence` | Done Claim、Evidence resource、source head | resource状態とSHAの一致を確認し、継続不能なら通常の後継Issue | Contract、state vocabulary |
| `terminal_violation` | terminal履歴と後続Record／merge | 先に成立したterminal resultを保持し、必要作業を別Issueへ送る | 元Issueの履歴修復、新Record追加 |
| Acquisition Error | GitHub取得、認証、rate limit、snapshot経路 | 同じresourceのread-only再取得またはアクセス経路の修正 | protocol不適合への分類、Record |
| `gtp check`不適合 | 投稿予定Markdown Carrier | error codeとJSON pathが示す入力箇所 | 未観測のIssue、branch、PR |
| setup blocker | setup先instruction／authority／dependency | 確認済みownerまたはtarget instruction | target file、branch、Issue、PR |
| 外部Operation blocker | Operation provider／activation owner | 確認済みowner repository、Issue、host integration | GTP core、test providerによる代用 |

所有層または修正先を一意に決められない場合は「所有層未確定」または「修正先Issue未確認」と表示し、人間へ戻す。存在を確認していないIssueやownerを作らない。

## 非干渉境界

問題説明の生成は、対象taskまたはsetup先の次のstateを自動変更しない。

- Issue本文、comment、label、Issue state
- branch、commit、default branch head
- pull request、review、merge state
- working tree、repository file

診断専用Record、repair Record、第二のworkflow、永続診断台帳を追加しない。問題説明をIssue comment、label、PR body、acceptance artifactへ自動保存しない。受け入れやreleaseで永続Evidenceが必要な場合は、その専用Issueの明示scopeで作成する。

## Authorityとprivacy

- 問題説明、exit code、Check Run、Record、Evidenceは変更、完了、mergeのauthorityを与えない。
- private provider identity、private rule／version、credential、credential path、local absolute path、stack trace、raw exception、private diagnosticを人向け表示へ出さない。
- 公開可能なGitHub URLは、取得と公開可否を確認できた場合だけ表示する。
- Evidenceが示すのは観測resourceとのbindingまでであり、自然言語上の十分性やactor本人性を証明しない。

## 変更規則

- 公開protocol semanticsを変える変更は`GTP.md`を同じlaneで更新し、versionと互換性を判断する。
- current architectureの変更は`DESIGN.md`を更新する。
- materialな判断変更は新しいADRでsupersessionを記録する。既存ADRを遡及編集しない。
- 親Issue #97はGTP taskとして実行せず、子Issueのnative mergeを観測した後に進行状態だけを更新する。
