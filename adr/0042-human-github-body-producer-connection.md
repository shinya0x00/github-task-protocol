# ADR-042: Issue／PR本文checkを明示producerのbody-file経路へ接続する

- Status: Accepted
- Date: 2026-07-27
- Supersedes: None
- Superseded by: None

## 背景

`gtp status`はRecordとGitHub factから人向け表示を返すが、人が最初に読むIssue本文とPR本文は検査対象外だった。Issue #118／PR #119は人向け本文のoffline checkerを試したが、実際に投稿するproducerへ接続されず、PR本文もproblem／fix専用の4見出しへ固定していた。そのため、checkerが存在しても投稿本文の品質を保証できず、目的達成型、追加型、移行型などの一般的なPRへ使いにくかった。

GitHubの[Issue／pull request template](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates)はrepository単位の初期本文を標準化でき、Issue Formsはstructured inputをMarkdownへ変換できる。しかし、どちらもrepository設定であり、既存のinstructions、workflow、template選択をGTPが所有しない境界を満たさない。templateだけではcurrent task、head、unknownから現在地を更新したことも観測できない。

GitHub CLIはIssueとPRのcreate、およびPR editで`--body-file`を提供する。これは本文transportの標準経路であり、新しいGitHub mutation protocolを作る必要がない。

## 決定

公開commandは`check`と`status`の2つを維持し、既存`gtp check`へ明示`--target issue|pr`を追加する。target省略は従来のRecord checkと同じにし、本文からtargetを推測しない。

IssueとPRは異なるrequired H2集合を持つ。Issueは目的、ゴール、観測、境界、決定事項、完了条件、unknown、人間判断を持つ。決定事項は採用方針、非採用／延期案、見直す条件、固定参照の4項目を必須にする。PRはproblem/fix専用にせず、目的、ゴール、変更、利用者影響、現在地、unknown、人間判断を持つ。技術詳細は任意で最後に分離する。

checkerは順序、一意性、非空、決定事項4項目、固定参照、技術詳細配置だけをoffline検査する。決定の正しさ、理由、網羅性、言語、文章の意味、真実性、理解、GitHub state、authorizationを判定せず、GitHubへwriteしない。

Issue本文はcurrent decision、通常の`Decision update` commentはappend-onlyな変更履歴、ADR／DESIGNは複数Issueへ影響する長期判断を所有する。goal、scope、Done Conditionsが変わる場合だけ既存amendmentを使う。新しいRecord、state、command、approval flowは追加しない。

reviewのP1／P2は、Purpose、Scope / constraint、Done Condition、Decision record、Public contract、Compatibility requirement、Correctness / security / privacy invariantのいずれに違反したかを示す。該当しない別案はblocking findingにしない。決定自体への異議は、見直す条件に該当する新事実を示す`Contract challenge`へ分離する。

producer接続は、投稿直前check、body-file相当のcreate／edit、投稿後GET一致を一つのOperationとして観測する。head更新時はPR本文の現在地を置換し、先頭へ履歴logを積まない。producerの使用は明示的かつ任意であり、Issue、Issue Form、PR template、workflow、ruleset、required checkをGTP導入条件にしない。

## 理由

明示targetは既存Record checkの互換性を守り、marker typoや通常本文を別targetへ推測でfallbackしない。body-file transportを再利用すれば、GTP CLIへmutation command、bot、GitHub credential handlingを追加せず、pre-write入力とpost-write結果を比較できる。

構造検査とhuman acceptanceを分けることで、機械検査が理解を証明したという過剰claimを避けつつ、templateより現在のtaskに即した本文をproducerが作れる。IssueとPRを別targetにするが、PR targetはIssue referenceを要求しないため、既存の二層境界を維持する。

## 検討した代替案

### 新しいrender commandと入力schemaを追加する

不採用。新command、別schema、生成state、migrationを増やし、既存producerが持つtask contextと重複する。v1.0.4で必要なのは、汎用本文の最低構造と実投稿接続である。

### Issue Form／PR templateをsetupで追加する

不採用。repository固有設定を変更し、Issue-firstまたは一つのworkflowをGTPが強制する。PR head更新後の現在地置換も保証しない。

### 文書化したproducer手順だけにする

不採用。投稿前入力の構造をdeterministicにrejectできず、producerがcheckを実行したEvidenceも残らない。

## 結果と限界

- Issue／PR本文を、既存Record checkを壊さず明示targetで検査できる。
- 実producer接続はcreate／edit／GETの観測Evidenceを持てる。
- PR-only作業と既存repository運用を維持できる。
- machine check成功は文章の真実性、人間の理解、merge／公開authorizationを証明しない。
- Decision updateとreview規則は人間向け契約であり、checkerが決定やfindingの妥当性を採点しない。
- GitHub以外のproducer transportは、このreleaseでは実接続を観測しない。
