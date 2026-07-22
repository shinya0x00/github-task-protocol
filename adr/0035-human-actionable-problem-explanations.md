# ADR-035: 人間が修正指示を出せる問題説明をpresentation projectionとして定義する

- Status: Accepted
- Date: 2026-07-23
- Supersedes: None
- Superseded by: None

## 背景

既存CLIは`halt_reason`、diagnostic URL、Acquisition Error、Carrier errorをmachine JSONへ返し、人向けにも状態、停止要否、次の行動、理由、最初のURLを表示する。しかし、非エンジニアが「問題はどの層にあり、どこを直し、何を直してはいけないか」を具体的な修正指示へ変換するには情報が不足する。

一方、問題説明のために新しいRecord、state、repair workflow、Issue commentを追加すると、公開protocolの意味と通常の1 Issue = 1 branch = 1 PRへ第二の作業系を持ち込む。表示が自動修復やmutationを行うと、診断対象そのものを変化させ、観測入力と説明結果を結び付けられなくなる。

## 決定

問題説明を、既存の診断事実とmachine projectionから導出するhuman presentation projectionとして設計する。これはprotocol stateではなく、read-onlyかつephemeral-by-defaultである。CLI behaviorはIssue #99、setup preflightと外部Operation blocker接続はIssue #100で実装され、各production pathのnative mergeまでは`Target / not yet implemented`である。

### 入力

- `state: halt`と7 halt reason
- `state: null / acquisition: incomplete`とacquisition error
- `gtp check`の認識結果、schema判定、error code、JSON path、input error
- setup前にread-onlyで観測したinstruction、authority、外部dependency
- 外部Operationが公開した接続／activation blockerと確認済みowner URL

入力に存在しないcause、owner、Issue、permission、修正方法を推測しない。

### 出力

blocker時だけ、次の8項目をこの順で表示する。

1. 何が問題か
2. どこが問題か
3. なぜそう判断したか
4. どこを直すか
5. 何を直さないか
6. 次の安全な一手
7. 最初に確認するURL
8. 解決したと判断する条件

各項目の表示内容と推測禁止事項は[`DESIGN.md`](../DESIGN.md)を参照する。diagnostic URLがある場合は先頭URLを使い、ない場合だけ既存`primary_url`へfallbackする。投稿前の`gtp check`にGitHub URLがなければ、その事実を「URLなし（投稿前入力）」と表示する。

解決確認は2種類に分ける。再検査で解消可能なcaseは期待するstateまたは結果を示す。`terminal_violation`のように元Issueで解消不能なcaseは、元Issueのterminal resultとviolationを保持し、後継Issue側のContract、PR、Evidence、native mergeを確認条件として示す。元Issueが正常stateへ戻るとは表示しない。

### 所有層

観測事実を次の所有層へ写像する。

- Record履歴
- GitHub binding
- Evidence
- Acquisition経路
- 投稿前Carrier
- setup先instruction／authority／dependency
- 外部Operation

`invalid_record`等をRecord履歴、`invalid_binding`をGitHub binding、`invalid_evidence`／`stale_evidence`をEvidence、Acquisition Errorを取得経路へ写像する。ただし、これは最初に確認する層であり、根本的な修正責任ではない。setup blockerと外部Operation blockerはtokenだけからGTP coreへ写像しない。

原因入力を公開仕様へ照合し、そのexact inputに期待されるstate、halt reason、Acquisition Error、check result、exit codeを決めてproduction implementationのobserved resultと比較する。invalid inputにもexpected resultがある。

- observed resultがexpected resultと異なる場合は、入力のvalidityにかかわらず、observed resultを返したproduction pathのowner implementationを修正責任とする。GTP reader／CLIまたは`gtp check`ならGTP implementation、setup／adapter preflightならそのsetup workflow owner、外部Operation／providerならそのOperation／provider ownerとする。Exact Marker付きの壊れたJSONをGTP reader／CLIが期待される`halt / invalid_record`ではなくcrashまたは`unmanaged`として返す場合は、GTP implementationが修正責任を持つ。
- observed resultがexpected invalid resultと一致する場合はCarrier、Record、binding、Evidence等のresourceを修正候補とする。
- expected result、observed result、またはobserved resultを返したproduction pathのownerを固定できず、比較Evidenceまたはowner Evidenceが不足する場合は「修正責任未確定」とする。

所有層を一意に決められない場合は「所有層未確定」とし、修正先Issueを確認できない場合は「修正先Issue未確認」とする。推測したownerやIssueを表示または起票しない。

### read-only／ephemeral境界

問題説明の導出では、対象Issue、comment、label、Issue state、branch、commit、PR、working treeを変更しない。診断結果をGTP Record、Issue comment、label、PR body、永続ledgerへ自動保存しない。

人間が修正を選んだ後は、特別なrepair workflowではなく通常の別IssueでContract、Start、branch、PR、Done、Human mergeへ戻る。元のCarrierを編集・削除して履歴を修復しない。

### authority boundary

問題説明は変更、完了、review、merge、publicationのauthorityを与えない。既存の`authority: none`、machine JSON、exit code、4 Record、6 state、7 halt reason、2 command、Evidence、native merge、Acquisition Errorの意味を変更しない。

private provider identity、private rule／version、credential、credential path、local absolute path、stack trace、raw exception、private diagnosticは人向け表示へ出さない。

認証済み利用者へのinteractive consoleでは、既存表示との互換性のため、その利用者が取得した同一repositoryのprivate Issue／comment／PR URLを表示できる。public acceptance／release artifactまたは公開logへは、public確認済みまたは人間が明示的に公開承認したURLだけを記録する。外部providerのprivate diagnostic URLはconsoleにも転記しない。

## 理由

「どこを直すか」だけでは、問題と無関係なGTP core、Record grammar、正常なresourceまで変更する指示につながり得る。そのため「何を直さないか」を同時に必須とする。

既存diagnosticからのprojectionに限定すれば、readerのprotocol判定とpresentationの説明責任を分離できる。read-onlyかつephemeralにすれば、説明生成前後のsnapshotを比較でき、通常workflowへ診断用stateを混入させずに済む。

## 検討した代替案

### 診断専用Recordを追加する

不採用。4 Recordのclosed vocabularyと同一Issue lifecycleを変更し、表示改善だけのためにprotocol migrationが必要になる。

### repair Recordまたは第二のworkflowを追加する

不採用。通常の1 Issue = 1 branch = 1 PRと競合し、どちらがtask stateを所有するか曖昧になる。

### 問題説明を自動commentまたはlabelとして保存する

不採用。診断実行が対象Issueを変更し、read-only observationではなくなる。必要なEvidenceは別の明示contractで記録できる。

### 修正対象だけを表示する

不採用。非対象が不明なため、scope拡大やprotocol coreの誤修正を防げない。

## 結果

- blocker時にだけ、人間が所有層、修正対象、非対象、次の一手、解決条件を追える。
- normal stateの表示とIssue→PR workflowは変わらない。
- CLI、setup、外部Operationは同じ8項目を共有するが、各内部ruleの正準はそれぞれのownerに残る。
- 問題説明だけでは、原因の真実性、人間の理解、修正の成功、merge authorityを証明しない。
- pull requestのsource headにあるこのADRと設計文書は正準候補であり、main canonical sourceへの昇格はnative merge後のpath再取得で確認する。
- 後続のmaterialな変更は新ADRからこのADRを`Supersedes`で参照する。判断本文は遡及編集しないが、supersession relationを解決可能にする`Status`と`Superseded by`の参照metadataは更新できる。
