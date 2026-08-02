## 未決定事項

GTP 2.0が、後から変更する影響が大きい未決定事項と採用手段の記録に加えて、人間可読なprojectionやtaskの開始・停止・完了状態をどこまで扱うか。

## 採用した手段

GTPの中核は、後から変更する影響が大きい未決定事項と採用手段をDecision Recordへ残し、成果物から参照することだけを扱う。

GTP SkillはGTP中核の適用手順だけを扱い、一般的な文章reviewを行わない。

人間可読な提出文章の言語、repositoryのinstructionとtemplate、Issue、pull request、commit message、Release notes、Decision Record、利用者向け説明の可読性は、独立したPre-submission Review Skillが扱う。このSkillはGTPの起動やDecision Recordの作成を前提にせず、GTP SkillもPre-submission Review Skillを必要としない。

task state、Done、Evidence集約、authority、approval、workflow制御、強制機構はGTP中核で扱わない。Pre-submission Reviewもauthorization、approval、正しさ、Agent complianceを保証しない。

## 変更履歴

- [PR #156](https://github.com/shinya0x00/github-task-protocol/pull/156)で、GTPの中核をDecision Recordの記録と成果物からの参照に保ち、言語、template、Issue・pull requestの可読性を、対象を明示すれば省略できる提出前reviewへ分離。
- この変更で、提出前reviewをGTP Skill内の手順から独立したPre-submission Review Skillへ分離。
