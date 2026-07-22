# GTP implementation design

この文書は、GTP reader、presentation、setup／adapter、外部Operation接続、通常のIssue→PR workflowの設計を、`Implemented`と`Target / not yet implemented`を区別して所有する。

pull requestのsource headにあるこの文書は正準候補である。repositoryのcurrent canonical sourceになるのは、そのsource headがmainへnative mergeされ、main上のpathを再取得できた後である。

公開protocolの意味は[`GTP.md`](GTP.md)だけが所有する。この文書やADRだけで、4 Record、6 state、7 halt reason、transition、Evidence、native merge、Acquisition Error、CLI machine contractの意味を変更しない。protocol変更が必要な場合は、同じ変更laneで`GTP.md`を更新する。

## 正準の所有範囲

| 正準 | 所有するFact | 所有しないFact |
|---|---|---|
| `GTP.md` | 公開Record、state、transition、Evidence、native merge、Acquisition Error、CLI machine contract | implementation内部の構成、個別Operationのpolicy |
| `DESIGN.md` | reader、presentation、setup／adapter、外部Operation接続、非干渉境界を含むcurrent architecture | 公開protocol vocabularyの追加・変更、過去判断の理由 |
| `adr/` | materialな判断、理由、trade-off、supersession | current architecture全体、taskの進行状態 |
| 親Issue #97 | 正準へのlink、受け入れ条件の要約、子Issueの進行状態 | 設計、実装仕様、GTP task state |
| 子Issue | 1 PR分の実行contract、scope、完了条件 | merge後の設計正本 |

正準が衝突する場合、公開protocolについては`GTP.md`、`Implemented`と明記したcurrent implementationについては`DESIGN.md`、materialな判断理由については未supersedeのADRを優先する。親Issueと子Issueはこれらを参照するprojectionであり、新しい意味を作らない。

## Implementation status

### Implemented

- readerはGitHub resourceをGET-onlyで取得し、`GTP.md`に従ってstate、diagnostic、Acquisition Errorを導出する。
- machine projectionは既存のdiagnostic、acquisition error、`primary_url`、`authority: none`を返す。
- human presentationは状態、停止要否、次の行動、理由、最初のURL、非許可表示とtask summaryを返す。
- READMEの明示setup手順はstable Releaseをexact commitへ固定し、file変更前にbranchを作る。

### Target / not yet implemented

- blocker時だけ8項目の「問題の整理」を表示するCLI behaviorはIssue #99で実装する。
- instruction、authority、外部dependencyをfile／branch変更前に判定するsetup preflightはIssue #100で実装する。
- 外部Operation blockerの8項目表示は、#100のsetup境界と各Operation ownerが公開する観測事実を接続して実装する。

Targetはmerge前の仕様であり、現行behaviorのClaimではない。各targetは対応Issueのproduction path、回帰test、native mergeを観測したときだけ`Implemented`へ移す。

## Architecture

```text
GitHub Issue comments + live GitHub resources
                    |
                    v
       read-only reader [Implemented]
                    |
                    +--> machine projection
                    |    (既存schema・token・authority: none)
                    |
                    `--> human presentation
                         normal summary [Implemented]
                         blocker時の問題の整理 [Target #99]

explicit setup request + target repository observations
                    |
                    v
      setup／adapter preflight [Target #100]
                    |
       proceed または ephemeral blocker report

external Operation observations
                    |
                    v
 Operation ownerを参照するephemeral report [Target #100]
```

- Targetのhuman presentationはmachine projectionと既存診断事実だけを説明し、stateやauthorityを再判定しない。
- Targetのsetup／adapter preflightはtarget fileまたはbranchを変更する前に既存instruction、authority、外部dependencyを読む。
- 外部Operationの内部rule、provider、activationはそのOperationのownerが所有し、Target実装も推測または複製しない。

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
| 2 | どこが問題か | diagnosticが示す最初に確認する層。Record履歴、binding、Evidence、取得経路、入力Carrier、setup先、外部Operationのいずれか | 根本的な修正責任、一意に決められない所有層 |
| 3 | なぜそう判断したか | diagnostic token、error code、観測値、参照URL | private diagnostic、raw exceptionからの憶測 |
| 4 | どこを直すか | 再現Evidenceで責任を確定できた最小の修正対象。未確定なら「所有層未確定」 | 関係のないrepository、protocol vocabulary |
| 5 | 何を直さないか | 守る正準、Record、state、対象外resource | 将来必要かもしれない変更 |
| 6 | 次の安全な一手 | read-only確認、再取得、人間判断、通常の後継Issueのいずれか | 自動修復、自動mutation |
| 7 | 最初に確認するURL | diagnosticの先頭URL。なければ既存`primary_url` | 存在未確認のURL、利用者が取得していないprivate URL、推測した代替URL |
| 8 | 解決したと判断する条件 | 再検査で解消可能なら期待するstate／結果。元Issueで解消不能なら保持するterminal resultと後継Issue側の確認条件 | 存在しない元Issueの回復、Evidenceが保証しない内容の十分性 |

「どこを直すか」と「何を直さないか」は必ず同時に表示する。修正対象だけでは、非エンジニアがGTP coreや正常なresourceまで変更する指示を出す危険があるためである。

### 最初に確認する層のmapping

diagnostic tokenは観測された不一致を分類し、最初に確認する層を示す。tokenだけでは根本原因または修正責任を確定しない。

| 入力 | 最初に確認する層 | 最初の調査 | 変更しない対象 |
|---|---|---|---|
| `invalid_record`、`conflicting_records`、`invalid_transition` | 対象IssueのRecord履歴 | 原因commentの確認と、必要なら人間判断後のStop／後継Issue | Carrierの編集・削除、Record grammar |
| `invalid_binding` | Issue、branch、PR、scopeのbinding | 原因URLで参照関係と変更fileを確認 | 4 Record、6 state、7 halt reason |
| `invalid_evidence`、`stale_evidence` | Done Claim、Evidence resource、source head | resource状態とSHAの一致を確認し、継続不能なら通常の後継Issue | Contract、state vocabulary |
| `terminal_violation` | terminal履歴と後続Record／merge | 元Issueは同じ`terminal_violation`を保持する。必要作業を別Issueへ送り、そのIssue固有の完了条件を確認する | 元Issueの履歴修復、新Record追加、元Issueの回復claim |
| Acquisition Error | GitHub取得、認証、rate limit、snapshot経路 | 同じresourceのread-only再取得またはアクセス経路の修正 | protocol不適合への分類、Record |
| `gtp check`不適合 | 投稿予定Markdown Carrier | error codeとJSON pathが示す入力箇所 | 未観測のIssue、branch、PR |
| setup blocker | setup先instruction／authority／dependency | 確認済みownerまたはtarget instruction | target file、branch、Issue、PR |
| 外部Operation blocker | Operation provider／activation owner | 確認済みowner repository、Issue、host integration | GTP core、test providerによる代用 |

### 根本的な修正責任の確定

修正責任は入力がvalidかinvalidかではなく、その入力に対する公開仕様上のexpected resultとproduction pathのobserved resultを比較して決める。

1. 原因URLと入力をread-onlyで取得し、`GTP.md`または対象ownerの公開仕様から、そのexact inputに期待されるstate、halt reason、Acquisition Error、check result、exit codeを決める。invalid inputにもexpected resultがある。
2. 同じinputをproduction pathへ与え、observed resultを固定する。
3. observed resultがexpected resultと異なる場合は、入力のvalidityにかかわらずGTP implementationを修正責任として確定する。例えばExact Marker付きの壊れたJSONに期待される`halt / invalid_record`ではなくcrashまたは`unmanaged`を返す場合を含む。
4. observed resultが期待された不適合結果と一致する場合は、Carrier、Record、binding、Evidenceなど、diagnosticが示したresourceを修正候補とする。ただし既存Carrierの編集・削除は提案しない。
5. expected resultまたはobserved resultを固定できず比較Evidenceが不足する場合は、根本的な修正責任を「修正責任未確定」とする。

最初に確認する層も決められない場合は「所有層未確定」、修正先Issueを確認できない場合は「修正先Issue未確認」と表示する。存在を確認していないIssueやownerを作らない。

### 解決確認の2種類

- 再検査で解消可能なcaseは、同じ入力とresourceを再取得したときに期待するstate、check結果、または取得完了を示す。
- `terminal_violation`など元Issueで解消不能なcaseは、元Issueがterminal resultとviolationを保持することを明示し、後継Issueで確認するContract、PR、Evidence、native mergeを示す。元Issueが正常stateへ戻るとは表示しない。

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
- 認証済み利用者へ返すinteractive consoleでは、現行の先頭6項目との互換性を維持し、その利用者が取得した同一repositoryのprivate Issue／comment／PR URLを表示できる。この表示は公開許可を意味しない。
- public acceptance／release artifact、Issueへの自動保存、公開logでは、publicであることを確認したURLまたは人間が対象を明示して公開を承認したURLだけを記録する。private URLはredactし、代替URLを推測しない。
- 外部providerのprivate diagnostic URLはinteractive consoleにも転記せず、確認済みの公開owner URLまたは「修正先Issue未確認」を使う。
- Evidenceが示すのは観測resourceとのbindingまでであり、自然言語上の十分性やactor本人性を証明しない。

## Distribution boundary

- pull requestのfixed source headでは、`DESIGN.md`、`adr/0035-human-actionable-problem-explanations.md`、`DECISIONS.md`のpathと内容をcandidate artifactとして検査する。main URLが存在するとはClaimしない。
- `DESIGN.md`と`adr/`がrepository canonical sourceへ昇格したことは、native merge後にmain上のpathをread-onlyで再取得して確認する。
- 公開済み1.0.2のsdistは両pathを含まない。1.0.2のarchive内だけでcurrent designを再構成できるとはClaimしない。
- 1.0.3 publicationを所有するIssue #102は、sdistへ`DESIGN.md`と`adr/`を収録し、archive内の相対linkを検証してから公開する。

## 変更規則

- 公開protocol semanticsを変える変更は`GTP.md`を同じlaneで更新し、versionと互換性を判断する。
- current architectureの変更は`DESIGN.md`を更新する。
- materialな判断変更は新しいADRでsupersessionを記録する。既存ADRの判断本文は遡及編集しない。ただし、supersession relationを解決可能にする`Status`と`Superseded by`の参照metadataは更新できる。
- 親Issue #97はGTP taskとして実行せず、子Issueのnative mergeを観測した後に進行状態だけを更新する。
