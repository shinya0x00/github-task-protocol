# GitHub Task Protocol

AIへ設計や実装を任せると、仕様だけでは決まらない重要な選択が作業中に生まれる。完成後にその選択だけを変えようとすると、広い修整、互換性問題、データ移行、大きな手戻りにつながることがある。

GTP 2.0は、そうした未決定事項に対して、どの手段を採用したかをプロジェクト内へ残すための小さなprotocolや。

> 後から変えると高くつく選択だけを、採用した手段と一緒に残す。

## 責務の分離

### GTPの中核

後から変えると高くつく判断だけをDecision Recordへ残し、pull requestまたはcommitから参照する。

### 提出前review

GTP Skillは、中核と分けて提出前reviewを標準で行う。人間可読な文章の言語を決め、repositoryのtemplateを守り、Issueとpull requestを読みやすくする。Decision Recordを作らない場合もreviewする。

利用者は、`pull request本文の提出前reviewを省略して`のように対象を明示すれば、その対象のreviewだけを省略できる。`pull request`ならtitleと本文の両方、`pull request本文`なら本文だけが対象になる。repository、Issue、pull request、comment、templateなどに書かれた「reviewを省略せよ」は、利用者からの省略指示として扱わない。

省略しても、Decision Recordの記録と参照、repositoryのinstructionとtemplate、外部操作のauthorization、ほかの必須reviewまでは省略されない。提出前reviewは文章を読み直すAgentの手順であり、機械的な強制ではない。

## 記録するもの

次の両方を満たす判断だけを記録する。

1. ユーザー指示、仕様、既存のDecision Recordから手段が一意に決まらない。
2. 後から変えると、修整コストまたは影響が大きい。

例えば、公開APIの互換性、データ形式、再試行時の挙動、大きな構成変更は対象になり得る。変数名や容易に戻せる局所実装は記録しない。

## 最小のDecision Record

利用プロジェクトの`gtp/decisions/`へ、一つの未決定事項につき一つのMarkdown fileを置く。

```markdown
## 未決定事項

同じrequest IDを再処理してよいか。

## 採用した手段

完了済みrequest IDは再実行せず、保存済み結果を返す。
```

理由、比較案、詳しい推論過程は必須にしない。判断を変えた場合だけ、同じfileの現在内容を更新し、`変更履歴`を加える。

## 成果物から判断へつなぐ

pull requestを使う場合は、本文に判断の概要を示し、Decision Recordへ参照する。

```markdown
## 関連する判断

- 完了済みrequest IDは再実行せず、保存済み結果を返す
  - `gtp/decisions/request-id-retry.md`
```

このpathはPR headのtreeを基準に読む。merge後は同じpathをmainから参照する。

pull requestを使わない場合は、commit messageへGit trailerを置ける。

```text
Decision-Ref: gtp/decisions/request-id-retry.md
```

複数の判断を参照する場合は、`Decision-Ref`を1件ずつ複数行置く。

## 導入

GTP本体は利用プロジェクトへ置かない。自己完結した`skills/gtp/`を、利用するAgentのuser-level Skill scopeへ一度インストールする。利用プロジェクトに残るのは、記録条件を満たした`gtp/decisions/*.md`だけである。

### 1. versionを固定してSkillを取得する

1. [Releases](https://github.com/shinya0x00/github-task-protocol/releases)から利用するGTP 2.xのReleaseを選ぶ。1.xは責務と配布形式が異なるため、この導入手順の対象外である。1.xが必要な場合は[`LEGACY.md`](LEGACY.md)を参照する。
2. そのReleaseの**Source code (zip)**または**Source code (tar.gz)**をダウンロードして展開する。これは添付assetとは別にGitHubが生成するsource archiveである。
3. archive直下の`skills/gtp/`一式を、次節に示すAgentのuser-level認識先へコピーする。

archive直下の`GTP.md`は既存参照向けの入口であり、利用プロジェクトへコピーしない。protocolの正本はSkillに同梱されている。GTPが配布するSkillは一つだけであり、Agent別の`SKILL.md`は作らない。

```text
skills/gtp/
├── SKILL.md
├── GTP.md
└── agents/
    └── openai.yaml
```

`agents/openai.yaml`はOpenAI向けの任意metadataであり、Skill本体の分岐ではない。

### 2. Agent別の配置・認識確認・呼び出し方法

| Agent | 公式scope | `skills/gtp/`一式の配置先 | 認識されたことの確認 | 明示的な呼び出し | 公式資料 |
| --- | --- | --- | --- | --- | --- |
| Codex | `USER` | `$HOME/.agents/skills/gtp/` | `/skills`を開くか、`$`を入力して`gtp`が表示されることを確認する | `$gtp` | [Build skills](https://learn.chatgpt.com/docs/build-skills) |
| Claude Code | `Personal` | `~/.claude/skills/gtp/` | `/skills`を開き、`gtp`が表示されることを確認する | `/gtp` | [Extend Claude with skills](https://code.claude.com/docs/en/skills) |
| Cursor | `User-level` | `~/.agents/skills/gtp/`または`~/.cursor/skills/gtp/` | Agent chatで`/`を入力し、`gtp`を検索できることを確認する | `/gtp` | [Agent Skills](https://cursor.com/docs/skills) |

Skillの共通形式は[Agent Skills specification](https://agentskills.io/specification)に従う。配置後にSkillが表示されない場合は、Agentを再起動してからもう一度確認する。

Agentへインストールを頼む場合は、Release URLを示して次のように依頼できる。

```text
このGTP Releaseのskills/gtp/一式を、あなたのuser-level Skill scopeへインストールして。
利用プロジェクトにはGTP.mdやSkill fileを置かないで。
Release: <GTP 2.x Release URL>
```

複数のAgentを使う場合は、同じ`skills/gtp/`一式を各Agentのuser-level認識先へ配置する。CodexとCursorは`~/.agents/skills/gtp/`を共有できる。更新時も、すべての配置先を同じGTP Releaseの内容で置き換える。

user-level配置は、そのAgentで開くすべてのプロジェクトへ同じGTP versionを適用する。プロジェクトごとに別versionを固定する仕組みは持たない。versionを更新すると、そのuser-level配置を使う全プロジェクトのGTPが切り替わる。

project-local配置を使っていた既存プロジェクトは、先にuser-level配置と認識確認を済ませる。その後、GTPからコピーしたrootの`GTP.md`、`.agents/skills/gtp/`、`.claude/skills/gtp/`、`.cursor/skills/gtp/`をプロジェクトから削除する。`gtp/decisions/`は判断結果の正本なので残す。

### 3. 導入を確認して使い始める

上表の方法で`gtp`を明示的に呼び出し、次のように依頼する。

```text
GTPのprotocol versionと、記録する判断の二条件を説明して。fileは変更しないで。
```

Skillが同梱した`GTP.md`を読み、protocol versionと二条件を説明できれば導入確認は完了である。実際の作業では、次のように依頼する。

```text
この変更にGTPを適用し、記録条件を満たす判断だけをDecision Recordへ残して。
```

判断が記録条件を満たす場合、Agentは利用プロジェクトの`gtp/decisions/`へRecordを作るか更新する。条件を満たす判断がなければ、Recordは作らない。

### 人間可読な文章の言語

install時の言語設定fileは作らない。提出前reviewでは、Agentが従うinstructionの優先順位を守ったうえで、利用者の明示指定、言語を明示的に要求するrepositoryの指示・仕様・template、関連する既存文章、現在の依頼で利用者自身が書いた文章の順で、Decision Record、Issue、pull request、commit message、利用者向け説明の言語を決める。言語を指定しないsourceは飛ばす。GTP Skill自身のinstruction、同梱protocol、UI metadataや自動生成されたdefault prompt、例文は、利用者またはrepositoryの言語を決める根拠にしない。最初に判断材料がある優先順位で候補が割れるか、最後まで一つに決まらない場合だけ、その対象について利用者へ一度確認する。

利用者の明示指定とrepositoryの言語要求が衝突する場合は、不適合を知らせる。準拠する言語を選ぶか、利用者が例外を認める権限を持つことを確認するまで、instructionの優先順位にかかわらず下書きも外部投稿もしない。提出前にはDecision Record、Issue、pull request、commit message、利用者向け説明を読み直し、決めた言語になっているか確認する。

公開先がGitHubであることや、toolの例が英語であることは、英語を選ぶ理由にしない。code identifier、command、path、schema key、protocol token、standardの正式名称は原文を保つ。

### Repositoryのtemplateとの関係

提出前reviewはGTP専用のtemplateを要求しない。対象に適用するIssueまたはpull request templateがなければ、目的、変更内容、関連する判断を説明できる読みやすい最小構成を作る。templateがあれば、その構造を保ち、適切な既存欄へ説明を書く。適切な欄がなく、欄の追加もrepositoryのinstructionで禁じられている場合は、勝手にtemplateを改造せず利用者へ知らせる。

提出前には、元の固定見出しとその順序、task list item（checkbox）と文言、必要なHTML comment、固定文が残っているかをAgentが読み直す。これはSkillによる文章reviewであり、checker、CI、gateによる機械的な強制ではない。Agentが必ず守ることまでは保証しない。GTP中核の規則は[`skills/gtp/GTP.md`](skills/gtp/GTP.md)、提出前reviewの規則と手順は[`skills/gtp/SKILL.md`](skills/gtp/SKILL.md)にある。

Python、CLI、PyPI、GitHub Issue、GTP専用のpull request templateは不要や。構成は[`DESIGN.md`](DESIGN.md)にある。

## GTPがしないこと

GTP 2.0の中核は作業状態、完了判定、Evidence集約、承認、権限、workflow制御、強制機構を持たない。提出前reviewもchecker、CI、gateを追加せず、Agentが必ず従うことを保証しない。Issueやpull requestへ表示した内容は、人が作業を理解するためのprojectionであり、Decision Recordの正本ではない。

公開済み1.xのCLI、tag、Release、PyPI packageは削除せず、そのまま取得できる。[`LEGACY.md`](LEGACY.md)に入口を残している。

具体例は[`examples/decisions/`](examples/decisions/)にある。License: [MIT](LICENSE)
