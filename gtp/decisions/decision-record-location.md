## 未決定事項

Decision Recordの正本をどこへ置き、何をidentityとして参照するか。

## 採用した手段

利用プロジェクトの`gtp/decisions/`を設定不能な正本pathとし、repository-relative pathをDecision Recordのidentityとする。連番や独自IDは追加しない。Issueとpull requestは、人間可読な説明と正本への参照を持つprojectionとして扱う。

## 変更履歴

- PR #147で、固定pathに加えてrepository-relative pathをidentityとする判断を追加。
