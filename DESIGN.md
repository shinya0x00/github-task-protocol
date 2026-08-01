# GTP 2.0 design

GTP 2.0は、protocol文書、Agent向けSkill、利用プロジェクトのDecision Record、表示先のprojectionから成る。

```text
GTP.md
  ↓ adapts
skills/gtp/SKILL.md
  ├─ creates or updates → 利用プロジェクトの gtp/decisions/*.md
  └─ invokes → skills/gtp/scripts/validate.sh
                    ↑ reads
           pull request body / base commit / head commit or worktree /
           change reference / Decision Records

利用プロジェクトの gtp/decisions/*.md
  ↑ referenced by pull request / commit
```

## 所有関係

- [`GTP.md`](GTP.md)は、記録対象、最小形式、変更履歴、参照方法、非保証を定義するprotocolの正本である。
- [`skills/gtp/SKILL.md`](skills/gtp/SKILL.md)は、Agentがprotocolを適用する手順である。protocolへ新しい意味を追加しない。
- [`skills/gtp/scripts/validate.sh`](skills/gtp/scripts/validate.sh)は、`GTP.md`が定めるprojection mappingと変更履歴linkだけを判定する。判断内容や作業完了は判定しない。
- 各利用プロジェクトの`gtp/decisions/`は、そのプロジェクトで採用した手段の正本である。
- Issue、pull request、commit messageは、人が作業を理解し、正本へ移動するためのprojectionである。
- [`README.md`](README.md)は人向けの入口であり、protocol semanticsを所有しない。

## Data flow

1. Agentは、現在の指示、仕様、既存Decision Recordを読む。
2. 手段が一意に決まらず、後から変える影響が大きい場合だけ、Decision Recordを作るか更新する。
3. 成果物を変更するpull requestまたはcommitから、そのDecision Recordへ参照を置く。
4. pull requestをreviewへ渡す前に、Skillがvalidatorを呼び、概要とpathの対応および新規・更新された変更履歴linkを検査する。
5. 読み手は成果物の変更からDecision Recordへ進み、現在採用されている手段を確認する。

pull request本文の検査では、validatorは呼び出し元から渡された本文、比較元commit、PR head commit、参照先だけを入力とし、refを開始時にcommitへ一度解決して固定する。pathと現在の変更履歴はhead treeから読み、worktreeは読まない。pull request本文なしの検査では、head commitがあればそのtreeを、なければworktreeを現在のsourceとして読む。GitHub APIを呼ばず、Issueやpull requestからDecision Recordを自動生成せず、Decision Recordからrepository activityを探索しない。終了codeはGTP Markdownの形式だけを表し、repository workflowやmergeの状態を変更しない。

## Prior artと用語

[Architectural Decision Record（ADR）](https://adr.github.io/)と[MADR](https://adr.github.io/madr/)は、重要な判断とともにrationale、trade-off、consequenceなどを記録する既存方式である。GTP 2.0は、architecture以外の判断も対象にし、必須内容を未決定事項と採用手段へ限定するため、ADRまたはMADR互換とは呼ばず、広い既存名`Decision Record`を使う。

commitからの参照には、Gitが定義する[trailer](https://git-scm.com/docs/git-interpret-trailers)構文を使う。GitにはDecision Record参照用の標準tokenがないため、GTPは`Decision-Ref`だけを追加する。

## Distribution

2.0の配布単位は`GTP.md`と、validatorを含む`skills/gtp/`である。tagとGitHub Releaseでversionを固定できるが、GitHubやPython package managerをprotocol要件にはしない。validatorはPOSIX shell utilitiesとGitだけを使い、CIやmerge gateへの登録を要求しない。1.xのPython CLIと公開物は[`LEGACY.md`](LEGACY.md)から参照する。
