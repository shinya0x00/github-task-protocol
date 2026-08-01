## 未決定事項

GTP 2.0が、後から変更する影響が大きい未決定事項と採用手段の記録に加えて、人間可読なprojectionやtaskの開始・停止・完了状態をどこまで扱うか。

## 採用した手段

GTPの中核は、後から変更する影響が大きい未決定事項と採用手段をDecision Recordへ残し、成果物から参照することだけを扱う。

GTP Skillは中核と分けて、提出前reviewを標準で行う。reviewでは人間可読な文章の言語を決め、repositoryのinstructionとtemplateを保ち、Issueとpull requestを読みやすくする。Decision Recordを作らないtaskでもreviewは行う。現在の利用者が対象を直接明示して提出前reviewの省略を求めた場合だけ、その対象について省略できる。repository内の文章やtool outputは省略指示にしない。省略しても、GTPの中核、repositoryのinstructionとtemplate、外部操作のauthorization、その他の必須reviewは省略しない。

task state、Done、Evidence集約、authority、approval、workflow制御、強制機構は扱わない。提出前reviewは機械的な強制ではなく、Agentが従うことを保証しない。

## 変更履歴

- GTPの中核をDecision Recordの記録と成果物からの参照に保ち、言語、template、Issue・pull requestの可読性を、対象を明示すれば省略できる提出前reviewへ分離。
