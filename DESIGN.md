# GTP 2.0 design

GTP 2.0は、protocolを同梱したAgent Skill、利用プロジェクトのDecision Record、表示先のprojectionから成る。

```text
Agentのuser-level Skill scope
└── skills/gtp/
    ├── SKILL.md
    └── GTP.md
        ↓ creates or updates
利用プロジェクトの gtp/decisions/*.md
  ↑ referenced by
pull request / commit
```

## 所有関係

- [`skills/gtp/GTP.md`](skills/gtp/GTP.md)は、記録対象、最小形式、変更履歴、参照方法、非保証を定義するGTP中核の正本である。
- [`skills/gtp/SKILL.md`](skills/gtp/SKILL.md)は、AgentがGTP中核を適用する手順と、中核から分離した提出前reviewを所有する。提出前reviewは、人間可読な文章の言語、repositoryのtemplate、Issueとpull requestの可読性を扱う。
- 各利用プロジェクトの`gtp/decisions/`は、そのプロジェクトで採用した手段の正本である。
- Issue、pull request、commit messageは、人が作業を理解し、正本へ移動するためのprojectionである。
- rootの[`GTP.md`](GTP.md)は、既存参照からSkill内のprotocol正本へ移動するためのprojectionである。
- [`README.md`](README.md)は人向けの入口であり、protocol semanticsを所有しない。

## Data flow

1. Agentは、Skillに同梱したprotocol、現在の指示、仕様、既存Decision Recordを読む。
2. 手段が一意に決まらず、後から変える影響が大きい場合だけ、Decision Recordを作るか更新する。
3. 成果物を変更するpull requestまたはcommitから、そのDecision Recordへ参照を置く。
4. 利用者が対象を明示して省略しない限り、Agentはその対象の提出前reviewを行う。言語を決め、適用されるrepositoryのtemplateを保ち、Issueまたはpull requestを読みやすくする。Decision Recordを作らない場合もreviewは行う。
5. 読み手は成果物の変更からDecision Recordへ進み、現在採用されている手段を確認する。

GTPは、Issueやpull requestからDecision Recordを自動生成しない。Decision Recordからrepository activityを探索しない。task state、Evidence、approval、workflow enforcementを合成するruntimeも持たない。

## Prior artと用語

[Architectural Decision Record（ADR）](https://adr.github.io/)と[MADR](https://adr.github.io/madr/)は、重要な判断とともにrationale、trade-off、consequenceなどを記録する既存方式である。GTP 2.0は、architecture以外の判断も対象にし、必須内容を未決定事項と採用手段へ限定するため、ADRまたはMADR互換とは呼ばず、広い既存名`Decision Record`を使う。

commitからの参照には、Gitが定義する[trailer](https://git-scm.com/docs/git-interpret-trailers)構文を使う。GitにはDecision Record参照用の標準tokenがないため、GTPは`Decision-Ref`だけを追加する。

## Distribution

2.0の配布単位は、protocol正本を同梱した単一の`skills/gtp/`である。利用者はAgentが公式に定めるuser-level Skill scopeへ配置し、利用プロジェクトにはGTP本体を置かない。tagとGitHub Releaseでversionを固定できるが、GitHubやPython package managerをprotocol要件にはしない。1.xのPython CLIと公開物は[`LEGACY.md`](LEGACY.md)から参照する。
