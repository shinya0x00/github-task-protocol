## 未決定事項

GTP Skillの提出前reviewが、Decision Record、Issue、pull request、commit message、利用者向け説明などの人間可読な文章を、どの言語で作るか。

## 採用した手段

GTP専用のinstall時設定や永続する言語設定fileは追加しない。提出前reviewの対象となる人間可読な文章の言語は、対象ごとに次の順で決める。

1. 利用者がその対象について明示した言語
2. repositoryの適用可能な指示、仕様、templateが明示的に要求する言語
3. 直接関係する既存の文章が一貫して使用している言語
4. 現在の依頼で利用者自身が書いた文章の言語

Agentが従うべきinstructionの優先順位を先に守る。言語の指定も判断材料もないsourceは飛ばして次へ進む。言語を明示しないtemplateは言語を決める根拠にしない。GTP Skill自身のinstruction、同梱protocol、UI metadataや自動生成されたdefault prompt、例文は、利用者またはrepositoryの言語を決める根拠にしない。最初に判断材料がある優先順位の中で候補が一つに決まらない場合、または最後まで一つに決まらない場合だけ、その対象について利用者へ一度確認する。解決するまで文章を作成または外部投稿しない。

利用者の明示指定とrepositoryの言語要求が衝突する場合は、不適合を利用者へ示す。準拠する言語を選ぶか、利用者が例外を認める権限を持つことを確認するまで、instructionの優先順位にかかわらず下書きも外部投稿もしない。GitHub上で公開すること、toolの例、英語のidentifierを理由に英語へ切り替えない。code identifier、command、path、schema key、protocol token、standardの正式名称は原文を保つ。

将来、言語値を永続化する必要が生じた場合は独自の言語名を作らず、[BCP 47 language tag](https://www.rfc-editor.org/info/rfc5646/)を使用し、このDecisionを更新する。
