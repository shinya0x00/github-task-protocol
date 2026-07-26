# GitHub Task Protocol (GTP) v1

GTPは、GitHubに残されたRecordとIssue、branch、PR、commit、Evidenceを結び付け、作業の現在地と完成候補の根拠を後から再構成するための最小protocolである。このファイルだけを公開仕様の正本とする。

GTPは仕事の進め方を決めず、repository、organization、ユーザーが既に所有するinstructionsやrulesを定義、検証、上書きしない。Record、CLI、native mergeは、作業、review、approval、完了、公開の権限を与えない。

## 1. 導入と開始条件

1. repository rootへこの`GTP.md`をコピーする。
2. `AGENTS.md`など、agentが読む既存文書を保持したまま、§16のadapter文を追加する。
3. taskごとに1 Issueを使い、下記CarrierをIssue commentとして投稿する。

CLIは任意である。Issue、comment、branch、commit、PRだけでも実行できる。

valid Contractが通常のGTP lifecycleを開始する。選択用のmodeやprofileはない。recognized CarrierがないIssueは`unmanaged`であり、GTPはContractを推測または自動投稿しない。invalid Carrier、invalid history、Stopを既に観測した場合は、valid Contractがないことを理由に無視せず、定義された`halt`、`stopped`またはAcquisition Errorを返す。

GTPの導入、Contractの有無、`unmanaged`を含むstateは、既存instructionsやrulesを有効化、無効化、変更しない。既存内容を保持してadapterを追加できない場合、GTPは自動統合せず、その内容を所有する人へ判断を戻す。この確認は既存規則の妥当性検証ではない。

## 2. 固定語彙

protocol 1.0のRecord typeは4種類、protocol 1.1は`amendment`を加えた5種類である。

```text
1.0: contract | start | done | stop
1.1: contract | start | amendment | done | stop
```

公開stateは6種類だけである。

```text
unmanaged | ready | in_progress | halt | done | stopped
```

`halt_reason`は7種類だけである。細かな原因は`details`で説明する。

```text
invalid_record | conflicting_records | invalid_transition | invalid_binding
invalid_evidence | stale_evidence | terminal_violation
```

## 3. Exact Carrier

1件のRecordは、1件のGitHub Issue comment全文であるCarrierに入れる。

````markdown
<!-- gtp-record:v1 -->
契約を確定した

<details><summary>記録(JSON)</summary>

```json
{ ... }
```

</details>
````

Carrierは次をすべて満たす。

- Exact Marker `<!-- gtp-record:v1 -->`が最初の非空行に完全一致する。
- markerの次の非空行は、空でない1行の人向け要約である。
- 要約後は上記と完全に同じ`<details>`、`summary`、`json` fenceを使う。
- JSON fenceは1個だけで、strict JSONのRecord object 1個だけを持つ。duplicate key、`NaN`、`Infinity`を拒否する。
- `</details>`後にproseを置かず、指定箇所の空行だけを許す。

markerのないcommentとmarker typoは通常commentとして無視する。Exact MarkerがあるのにCarrier、JSON、schemaが壊れていれば`halt / invalid_record`である。`updated_at != created_at`のCarrierも同じであり、編集や削除で修復しない。

## 4. 共通scalarとresource

- `gtp`は文字列`"1.0"`または`"1.1"`だけを許す。
- `id`はlowercase canonical UUID v4とする。
- SHAはlowercase 40桁hexのfull commit SHAとする。
- condition IDは`^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$`とする。
- textは空でなく、前後whitespaceとcontrol characterを持たない文字列とする。
- `scope` pathはrepository-relativeなfileまたは末尾`/`付きdirectoryとする。`.`だけはrepository全体を表す。絶対path、glob、空segment、`.` segment、`..` segmentを拒否する。
- branchはshort nameとする。URL、`refs/heads/`、空文字を拒否する。
- GitHub URLは`https://github.com`のcanonical URLだけを許し、query、独自port、credentialを拒否する。

Resource URLは次の形だけを使う。`N`は先頭0のない正整数、`SHA`はfull commit SHAである。

```text
Issue:         https://github.com/OWNER/REPO/issues/N
Issue comment: https://github.com/OWNER/REPO/issues/N#issuecomment-N
PR:            https://github.com/OWNER/REPO/pull/N
Check Run:     https://github.com/OWNER/REPO/runs/N
Artifact:      https://github.com/OWNER/REPO/blob/SHA/PATH
```

## 5. Closed schema

すべてのobjectはclosed schemaである。以下にないfield、未知type、未知versionを拒否する。投稿者、comment ID、時刻、URLはGitHub metadataをObservationとして使い、Recordへ追加しない。

`done_conditions`は1件以上のcondition mapである。各keyはcondition ID、各valueは`text`と`evidence_kind`だけを持つ。`evidence_kind`は`check`または`artifact`である。

### 5.1 `contract`

taskの目標、変更範囲、完了条件を確定する。1.0と1.1でfieldは同じである。

| field | type | 規則 |
|---|---|---|
| `gtp` | string | `"1.0"`または`"1.1"` |
| `type` | string | `"contract"` |
| `id` | string | UUID v4 |
| `goal` | string | text |
| `scope` | array of string | 1件以上、重複なし |
| `done_conditions` | object | condition map |

### 5.2 `start`

有効なContractと唯一の作業branchを束縛する。1.0と1.1でfieldは同じである。

| field | type | 規則 |
|---|---|---|
| `gtp` | string | Contractと同じversion |
| `type` | string | `"start"` |
| `id` | string | UUID v4 |
| `contract_ref` | string | 同じIssue内の先行Contract comment URL |
| `branch` | string | Issue repository内のbranch short name |

default branchを拒否する。Startとbranchは作業権限を与えない。

### 5.3 `amendment`

1.1だけのRecordであり、Start後にDone Conditionsを追記する。

| field | type | 規則 |
|---|---|---|
| `gtp` | string | `"1.1"` |
| `type` | string | `"amendment"` |
| `id` | string | UUID v4 |
| `predecessor_ref` | string | 最初はoriginal Contract、以後は直前amendmentのcomment URL |
| `done_conditions` | object | 1件以上の新規condition map |

既存condition ID、`text`、`evidence_kind`の再定義、変更、削除を認めない。goal、scope、branch、PR、authorityのfieldや任意JSON patchを認めない。それらを変える場合はStopと後継Issueを使う。

### 5.4 `done`

Done Recordは、何を、どの根拠で、どのsource headまで完成候補とclaimしたかを再構成するためのRecordである。運用上は自主検査記録に相当するが、Task Completionそのものでも、独立した検査員の承認でもない。

1.0のfieldは次だけである。

| field | type | 規則 |
|---|---|---|
| `gtp` | string | `"1.0"` |
| `type` | string | `"done"` |
| `id` | string | UUID v4 |
| `pr_ref` | string | Bound PR URL |
| `head_sha` | string | PR source headのfull SHA |
| `evidence` | object | condition IDからEvidence URLへのmap |

1.1のfieldは次だけである。

| field | type | 規則 |
|---|---|---|
| `gtp` | string | `"1.1"` |
| `type` | string | `"done"` |
| `id` | string | UUID v4 |
| `revision_ref` | string | original Contractまたはcurrent amendment tipのcomment URL |
| `previous_done_ref` | string or null | 最初のDoneは`null`、re-Doneは直前Logical Doneのcomment URL |
| `pr_ref` | string | Bound PR URL |
| `head_sha` | string | PR source headのfull SHA |
| `evidence` | object | condition IDからEvidence URLへのmap |

`evidence`のkey集合は、参照するrevisionの全condition IDと完全一致し、各URL kindは`evidence_kind`と一致する。

### 5.5 `stop`

完了を主張せずIssueを放棄する。1.0と1.1でfieldは同じである。

| field | type | 規則 |
|---|---|---|
| `gtp` | string | 現在のprotocol version |
| `type` | string | `"stop"` |
| `id` | string | UUID v4 |
| `reason` | string | `"abandoned"`または`"superseded"` |
| `successor_ref` | string or null | `superseded`は後継Issue URL、`abandoned`は`null` |

## 6. 最小記入例

値は実際のresourceへ置き換える。各objectを§3のCarrierへ1件ずつ入れる。

```json
{"gtp":"1.1","type":"contract","id":"123e4567-e89b-42d3-a456-426614174000","goal":"仕様を更新する","scope":["GTP.md"],"done_conditions":{"spec":{"text":"仕様が存在する","evidence_kind":"artifact"}}}
{"gtp":"1.1","type":"start","id":"223e4567-e89b-42d3-a456-426614174001","contract_ref":"https://github.com/example/project/issues/6#issuecomment-1001","branch":"issue-6-spec"}
{"gtp":"1.1","type":"amendment","id":"323e4567-e89b-42d3-a456-426614174002","predecessor_ref":"https://github.com/example/project/issues/6#issuecomment-1001","done_conditions":{"tests":{"text":"検査が成功する","evidence_kind":"check"}}}
{"gtp":"1.1","type":"done","id":"423e4567-e89b-42d3-a456-426614174003","revision_ref":"https://github.com/example/project/issues/6#issuecomment-1003","previous_done_ref":null,"pr_ref":"https://github.com/example/project/pull/20","head_sha":"0123456789abcdef0123456789abcdef01234567","evidence":{"spec":"https://github.com/example/project/blob/0123456789abcdef0123456789abcdef01234567/GTP.md","tests":"https://github.com/example/project/runs/3001"}}
```

## 7. Server Order、version、safe retry

Issue commentはGitHub comment IDの昇順で読む。Record内の自己申告時刻は使わない。

同じ`id`かつ構造的に同じJSONの再投稿だけをsafe retry aliasとして1 Logical Recordへ畳む。object key順、JSON whitespace、人向け要約は同一性へ含めず、配列順と値は含める。aliasは元Logical RecordのServer Order位置を維持し、後方aliasでrevisionやDoneのtipを移動しない。同じ`id`で異なるJSONは`halt / invalid_record`である。

1.0だけのhistoryは1.0の意味を維持する。1.0 Contract／Startから最初の1.1 amendmentまたはDoneで明示的に1.1へ移行できる。最初の1.1 Record後の1.0 Recordは`invalid_transition`である。1.1／mixed historyのmachine projectionはtop-level `gtp: "1.1"`とし、current Record群に`amendment` projectionを加え、effective revisionとcurrent Doneを解決可能にする。1.0-only projectionのkey集合と意味は変えない。

## 8. Effective Contract revision

original ContractとamendmentをServer Orderで読み、唯一のlinearなeffective revisionを作る。amendmentはStart後、1.1 historyのnative mergeまたはStopより前だけ受理する。

fork、cycle、親飛ばし、forward／self ref、逆順、別Issue／別repository参照を拒否する。valid amendment後は以前のDoneをcurrent completionへ再利用せず、new effective revisionを指す新しいDoneを要求する。

schemaが保証するのは、既存condition mapを構造上変更・削除しないことまでである。追加された自然言語が既存条件を意味上否定、緩和、無効化しないことは人間がreviewし、readerは証明しない。

## 9. Current Doneとre-Done

1.1のDoneは`previous_done_ref`で1本のlinear chainを作る。current Doneはchainのunique tipである。最初のDoneは`null`、後続のre-Doneはversionを問わず直前のLogical Doneを指す。

re-Doneはcurrent effective revision、同じIssue、Start branch、Bound PRのcurrent source head、全Evidenceへ束縛する。head変更だけならamendmentは不要であり、同じIssue、branch、PRで新headへ再提示する。古いDoneは当時のRecordとして残す。

fork、欠落predecessor、直前以外への参照、branching、invalidな後続Doneを拒否する。後続のrecognized Carrier、revision、Doneがinvalidなら`halt`とし、過去のvalid Doneへfallbackしない。Done後・merge前のPR head変更は`stale_evidence`であり、re-Doneで修復できる。

## 10. lifecycleとstate

- `unmanaged`: recognized Carrierがない。
- `ready`: valid Contractがあり、Startがない。
- `in_progress`: valid Start後の作業中、Done後のmerge待ち、またはEvidence Checkの完了待ち。
- `done`: §11の全条件を満たす。
- `stopped`: 証明済み`done`より前の最後のLogical Recordがvalid Stopで、その後に対象PR mergeがない。
- `halt`: Observationを完全取得できたが、Record、履歴、binding、Evidence、terminal規則が不適合である。

pending CheckはDone Recordをinvalidにせず、PRがmerge済みでも`in_progress`とする。同じURLをread-onlyで再取得し、successになれば新Recordなしで`done`へ進む。

## 11. `state: done`

1.0では従来どおり唯一のvalid Done、1.1ではcurrent Doneを評価対象とする。次をすべて満たす場合だけ`done`である。

1. DoneがRecord、transition、chain、binding上validである。
2. 1.1 Doneの`revision_ref`がcurrent effective revisionを指す。
3. `head_sha`が同じBound PRのsource headである。
4. 全Evidenceがsuccessで、同じrepositoryと`head_sha`へ束縛されている。
5. Bound PRがそのsource headをGitHub上でnative mergeしている。
6. 後続のinvalid Carrier、diagnostic、terminal violationがない。

Done RecordはEvidence付きDone Claimであり、`state: done`はsource PR lifecycleを後から再構成した結果である。native mergeはGitHub上の観測factであり、actor本人性、人間による確認、review、approval、authorizationを証明しない。

`done`はmerge後のpublication、deploymentその他の外部Operationの完了を表さない。その結果は通常のGitHub記録へ残せるが、GTP Recordではなく、GTP stateを変更しない。Issueのopen／closeもstateを変更しない。

## 12. transitionとterminal cutoff

- ContractはStartより前に1件だけ置く。StartはそのContractと非default branchを指す。
- StartなしのDone／amendment、Start後のContract、順序違反は`invalid_transition`である。
- 1.0では異なるStart、Done、Stopを複数置かない。1.1ではStartとStopを複数置かず、amendment／Doneは各linear chainだけを許す。
- 1 Issue = 1 branch = 1 PRとする。分割、統合、別branch／PRへの移動はStopと後継Issueを使う。
- Startと同時刻以前の`created_at`を持つPRをcandidateまたはDone対象にせず`invalid_binding`とする。
- PR file一覧の`filename`とrename時の`previous_filename`はすべてContract scope内でなければならない。
- Doneの`head_sha`、Bound PR、branch、Evidenceを同じrepositoryとsource headへ束縛する。

1.1ではnative mergeまたはStopの観測時点をRecord受付のcutoffとする。stateがCheck待ちの`in_progress`でも、その後のrecognized Carrierはschema上valid／invalidを問わず`terminal_violation`であり、amendmentやre-Doneで修復しない。safe retry aliasだけは新Recordではない。1.0-only historyのterminal規則は変更しない。

## 13. Evidenceと非保証

Evidence kindは`check`と`artifact`だけである。

- `check`は同じrepositoryのGitHub Check Runで、`status: completed`、`conclusion: success`、`head_sha == done.head_sha`を満たす。
- `artifact`は同じrepositoryの`done.head_sha`に存在するfileのimmutable blob permalinkである。

`queued`、`in_progress`、`requested`、`waiting`、`pending`かつ`conclusion: null`のCheckはpendingである。SHA不一致、未知status、非終端statusと非null conclusion、completedの非successは`stale_evidence`または`invalid_evidence`である。

GTPが確認するのは、Done Claim、effective revision、current Done、source head、Evidence resource、GitHub factの構造とbindingである。次は証明しない。

- Done Conditionが自然言語上・意味上、本当に充足されたこと
- Evidence内容の真実性、十分性、testやartifactの品質
- すべての判断やunknownが記録されたこと、一定の記録密度
- actor本人性、credential安全性、authority、review、approval
- 作業結果そのものの正しさ、不可逆操作の物理的防止

GitHubへ残すRecordと通常commentには、公開先へ開示してよい派生情報だけを書く。goal、scope、判断理由、Evidence、限界、unknown、`next_action`は各内容のownerへ残せるが、元の指示文、authorization本文、credential、private prompt／command／diagnosticを転載しない。外部Operationのauthorizationは実行直前にその境界で確認し、GTP Recordから推測しない。

## 14. halt reasonとStop

| reason | 意味 |
|---|---|
| `invalid_record` | Carrier、JSON、closed schema、scalar、編集、identity collisionが不適合 |
| `conflicting_records` | 同じ単一役割の異なるLogical Recordが複数存在 |
| `invalid_transition` | Record順、version、chain lifecycleが不適合 |
| `invalid_binding` | Contract、revision、branch、PR、repositoryの参照が不適合 |
| `invalid_evidence` | Evidence key、kind、resource、success条件が不適合 |
| `stale_evidence` | Done後にPR source headまたはEvidence SHAが古くなった |
| `terminal_violation` | terminal cutoff後に新しいrecognized Carrierまたは対象外mergeを観測 |

不適合結果には最初に確認すべきcommentまたはresource URLを含める。

Stopは完了をclaimせずIssueを放棄する非常口である。`superseded`は後継Issueへ、`abandoned`は`null`へ束縛する。Stop後は元Issueへ新Recordを投稿しない。証明済みDoneは後のStopで上書きせず、Stop後の対象PR mergeも`done`にせず、先のterminal resultをdetailsへ残して`terminal_violation`とする。

## 15. Acquisition Errorと受け入れ

state決定に必要なIssue comments、branch、PR、Check Run、artifact、merge factを完全取得できない場合、stateを出さない。これは`halt`ではなくAcquisition Errorである。network、authentication、rate limit、pagination失敗、404をprotocol不適合と推測しない。取得前後でrepository、Issue、branch、PR snapshotが変化した場合もstateを出さない。

Level 0はCLIなしで、clean sessionへIssue URLだけを渡し、同じbranchとPRで重複なく再開できることを実GitHubで確認する。Level 1はrelease candidate CLIを実GitHubへ接続し、原因URL付き`halt`、amendment、re-Done、Evidence付きDone、native merge後の`done`、人が日本語表示から判断できることを確認する。unit testは代わりにならない。

## 16. 共通adapter文

次の1段落を`AGENTS.md`などへコピーする。これはGTP Recordの読み方だけを伝え、既存instructions全体を所有または代替しない。

> このrepositoryはrootの`GTP.md`をtask protocolの唯一の正本とする。GitHub Issue URLを受け取ったら、Issue commentをServer Orderで読み、protocol versionに対応するRecord、6 state、7 halt reasonに従って既存branch・PR・次のprotocol actionを再構成する。Recordを推測、編集、独自拡張せず、矛盾時は原因URLを示して止まり、取得不能はhaltと混同しない。GTPの表示やRecordは変更・完了・mergeの権限を与えない。

## 17. 公開v1に含めないもの

判断理由用Record、generic patch、Record置換、任意数leafのjoin、PR専用lifecycle、publication／deployment Record、runtime別adapter、bot、自動投稿、自動merge、mutation command、plan管理、dashboard、database、cacheは定義しない。

複数repository、fork PR、GitHub Enterprise Serverも対象外である。
