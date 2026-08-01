## 未決定事項

GTP 2.0が、taskの開始・停止・完了状態まで扱うか、後から変更する影響が大きい未決定事項と採用手段だけを扱うか。

## 採用した手段

後から変更する影響が大きい未決定事項、採用した手段、その参照方法、およびこれらに対する狭いGTP Markdown形式検査だけを扱う。同じversionのSkillには、pull requestの判断概要とDecision Record pathの対応、および新規・更新された変更履歴linkを提出前に判定するvalidatorを含める。coreの変更は、具体的なfailureまたは既存contractとの互換性に対して、正しさ、portable性、診断、securityのいずれかに直接必要なものへ限り、将来の便利さ、一般性、対称性、完全性、拡張余地だけでは追加しない。形式不適合は判定するが、task state、Done、Evidence集約、authority、approval、repository workflowの状態遷移、review開始またはmergeの許可・拒否、CIまたはmerge gateによる強制、general-purpose Markdown parser、repository checker、policy engineへの拡張は扱わない。

## 変更履歴

- [Issue #149](https://github.com/shinya0x00/github-task-protocol/issues/149)で、強制機構を一律に扱わない手段から、観測されたGTP形式の欠落だけを提出前に不適合とし、taskやrepository workflowの状態遷移は引き続き扱わない手段へ変更。
