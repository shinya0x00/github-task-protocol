# GTP 2.0 design

一つのGitHub Release source archiveに、二つの独立したAgent Skillを収録する。

```text
GitHub Release source archive
└── skills/
    ├── gtp/
    │   ├── SKILL.md
    │   └── GTP.md
    │       ↓ creates or updates
    │   利用プロジェクトの gtp/decisions/*.md
    │       ↑ referenced by
    │   pull request / commit
    └── pre-submission-review/
        └── SKILL.md
            ↓ reviews before handoff or external write
        Issue / pull request / commit message / Release notes / Decision Record
```

## 所有関係

- [`skills/gtp/GTP.md`](skills/gtp/GTP.md)は、記録対象、最小形式、変更履歴、参照方法、非保証を定義するGTP中核の正本である。
- [`skills/gtp/SKILL.md`](skills/gtp/SKILL.md)は、AgentがGTP中核を適用する手順を所有する。一般的な文章reviewは所有しない。
- [`skills/pre-submission-review/SKILL.md`](skills/pre-submission-review/SKILL.md)は、人間可読な提出文章の言語、repository template、可読性をreviewする手順を所有する。GTPを必要としない。
- 各利用プロジェクトの`gtp/decisions/`は、そのプロジェクトで採用した手段の正本である。
- Issue、pull request、commit messageは、人が成果物を理解し、Decision Recordへ移動するためのprojectionになり得る。
- rootの[`GTP.md`](GTP.md)は、既存参照からSkill内のprotocol正本へ移動するためのprojectionである。
- [`README.md`](README.md)は人向けの入口であり、protocol semanticsもreview semanticsも所有しない。

## GTP data flow

1. Agentは、GTP Skillに同梱したprotocol、現在の指示、仕様、既存Decision Recordを読む。
2. 手段が一意に決まらず、後から変える影響が大きい場合だけ、Decision Recordを作るか更新する。
3. 成果物を変更するpull requestまたはcommitから、そのDecision Recordへ参照を置く。
4. 読み手は成果物の変更からDecision Recordへ進み、現在採用されている手段を確認する。

GTPは、Issueやpull requestからDecision Recordを自動生成しない。Decision Recordからrepository activityを探索しない。task state、Evidence、approval、文章review、workflow enforcementを合成するruntimeも持たない。

## Pre-submission Review data flow

1. Agentは、利用者とrepositoryのinstruction、適用するtemplate、関連する既存文章を読む。
2. 完成稿の言語を決め、目的、変更、検証、参照を読める形にする。
3. handoffまたは外部投稿の前に完成稿を読み直し、templateと観測事実へ照合する。

Pre-submission ReviewはGTPの起動、Decision Recordの作成、またはGTPによるauthorizationを前提にしない。review完了は、外部操作のauthorization、承認、正しさ、Agent complianceを保証しない。

## Prior artと用語

[Architectural Decision Record（ADR）](https://adr.github.io/)と[MADR](https://adr.github.io/madr/)は、重要な判断とともにrationale、trade-off、consequenceなどを記録する既存方式である。GTP 2.0はarchitecture以外の判断も対象にし、必須内容を未決定事項と採用手段へ限定するため、ADRまたはMADR互換とは呼ばず、広い既存名`Decision Record`を使う。

commitからの参照には、Gitが定義する[trailer](https://git-scm.com/docs/git-interpret-trailers)構文を使う。GitにはDecision Record参照用の標準tokenがないため、GTPは`Decision-Ref`だけを追加する。

`Pre-submission Review`は、外部投稿やhandoff前に完成稿を読み直す処理をそのまま表す説明的な名前である。独自のreview形式、status、verdictは追加しない。

## Distribution

tag時点のrepositoryを含むGitHub Release source archiveを配布単位とする。archive内の`skills/gtp/`と`skills/pre-submission-review/`は、Agent Skills形式に従う独立したSkill directoryである。標準インストールでは、二つを同じinstall runで、Agentが公式に定めるuser-level Skill scopeへ配置する。インストール後に片方が不要なら、そのSkill directoryだけを削除する。

二つは実行時には互いを必要としない。標準install setを二つに固定することは、発火条件、手順、成果物の所有者を統合することを意味しない。

独自package、複数Skill用manifest、installer、install stateは追加しない。利用プロジェクトにはSkill本体を置かない。tagとGitHub Releaseでsourceを固定できるが、GitHubやPython package managerをprotocol要件にはしない。1.xのPython CLIと公開物は[`LEGACY.md`](LEGACY.md)から参照する。
