# ADR-037: privateな入力とpublic Recordを分離する

- Status: Accepted
- Date: 2026-07-26
- Supersedes: None
- Superseded by: None

## 背景

GTPのRecordはGitHub Issueに残り、clean sessionが作業の現在地を再構成するために使う。一方、作業のきっかけになった元の指示、authorization、credential、private prompt、内部diagnosticは、同じ公開範囲へ複製してよいとは限らない。

再構成可能性を「元の入力を全文保存すること」と同一視すると、秘密情報を永続化し、公開時にRecordを書き換える必要が生じる。反対に、安全を理由としてgoal、scope、判断理由、Evidenceの限界まで残さなければ、人やAgentは記録の意味を追えない。

## 決定

GitHubへ永続化するGTP Recordと関連artifactには、公開先の閲覧者へ開示してよい派生情報だけを記録する。

### 記録できる情報

- goal、scope、Done Conditions
- 判断理由、検討した代替案、trade-off
- Evidence、Evidenceが保証しない範囲
- unknown、`next_action`
- source head、resource URL、hash、検査結果

各情報は、それを所有するContract、通常comment、PR、ADR、acceptance artifactへ置く。これらを汎用fieldとしてGTP Recordへ追加しない。

### 複製しない情報

- 元の指示文またはauthorization本文の引用・要約転載
- credential、credential path、token、private key
- private prompt、private command、private diagnostic、raw exception
- synthetic canary本文

外部Operationがauthorizationを必要とする場合は、そのOperationの直前に外部authority境界で確認する。確認内容をpublic Recordへ複製せず、GTP Record、native merge、comment author、CLI出力からauthorizationを推測しない。

synthetic canaryによる検査は、canaryのSHA-256、検査対象、match count、結果、限界だけを保存する。canary本文はsource tree、配布物、Issue、PR、logへ残さない。

### 表示と保存の境界

認証済み利用者がinteractiveに取得した同一repositoryのprivate resource URLを、その利用者のconsoleへ表示できることと、public artifactへ保存できることを分ける。public artifactにはpublic確認済み、または対象を明示して公開承認されたURLだけを残す。

Recordや通常commentは投稿後に公開用へ意味を書き換えない。訂正が必要なら、既存履歴を編集せず後続の許可された記録から参照する。

## 理由

再構成に必要なのは、作業の目的、境界、Evidence、限界を理解できる派生情報であり、元の秘密入力そのものではない。保存対象をこの差へ合わせれば、Recordを公開可能な品質で最初から作り、privacyとtraceabilityを両立できる。

GTPのclosed schemaを維持すれば、private入力の格納場所に転用される汎用fieldも増えない。authorizationを外部Operationへ残すことで、記録と実行権限も混同しない。

## 検討した代替案

### 元の指示とauthorizationを全文保存する

不採用。再構成に不要なsecretを永続化し、閲覧範囲と実行権限を混同する。

### 公開時にRecordをredactまたは書き換える

不採用。投稿時と公開時でRecordの意味とidentityが変わり、append-only historyを再構成できない。

### 判断理由やunknownも一切保存しない

不採用。秘密情報は減るが、人がEvidenceの限界や次の行動を判断できない。公開可能な派生情報まで捨てる必要はない。

### private情報用の新Recordまたは汎用fieldを加える

不採用。GTPのclosed vocabularyを広げ、別のaccess control問題をRecord grammarへ持ち込む。

## 結果と限界

- public RecordだけからGTP stateとsource lifecycleを再構成できる。
- privileged authorizationはGTP外で確認し、public Recordから取得または推測しない。
- scanとcanaryは、検査した対象と時点で一致を検出しなかったことまでを示す。未検査経路を含む秘密情報の不存在は証明しない。
- 公開可能性の判断そのもの、GitHub access control、credential管理はGTPが検証または強制しない。
