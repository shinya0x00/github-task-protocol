# GitHub Task Protocol

AIへ設計や実装を任せると、仕様だけでは決まらない重要な選択が作業中に生まれる。完成後にその選択だけを変えようとすると、広い修整、互換性問題、データ移行、大きな手戻りにつながることがある。

GTP 2.0は、そうした未決定事項に対して、どの手段を採用したかをプロジェクト内へ残すための小さなprotocolや。

> 後から変えると高くつく選択だけを、採用した手段と一緒に残す。

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

### 1. versionを固定して配布物を取得する

1. [Releases](https://github.com/shinya0x00/github-task-protocol/releases)から利用するversionを選ぶ。
2. そのReleaseの**Source code (zip)**または**Source code (tar.gz)**をダウンロードして展開する。これは添付assetとは別にGitHubが生成するsource archiveである。
3. archive直下の`GTP.md`を、利用プロジェクトのrootへコピーする。
4. archive直下の`skills/gtp/`一式を、次節に示すAgentの認識先へコピーする。

`GTP.md`と`skills/gtp/`は、必ず同じtagまたはReleaseから取得する。GTPが配布するSkillは一つだけであり、Agent別の`SKILL.md`は作らない。

```text
skills/gtp/
├── SKILL.md
└── agents/
    └── openai.yaml
```

`agents/openai.yaml`はOpenAI向けの任意metadataであり、Skill本体の分岐ではない。

### 2. Agent別の配置・認識確認・呼び出し方法

pathはすべて利用プロジェクトのrootを基準にする。

| Agent | `skills/gtp/`一式の配置先 | 認識されたことの確認 | 明示的な呼び出し | 公式資料 |
| --- | --- | --- | --- | --- |
| Codex | `.agents/skills/gtp/` | `/skills`を開くか、`$`を入力して`gtp`が表示されることを確認する | `$gtp` | [Build skills](https://developers.openai.com/codex/build-skills) |
| Claude Code | `.claude/skills/gtp/` | `/skills`を開き、`gtp`が表示されることを確認する | `/gtp` | [Extend Claude with skills](https://code.claude.com/docs/en/skills) |
| Cursor | `.agents/skills/gtp/`または`.cursor/skills/gtp/` | Agent chatで`/`を入力し、`gtp`を検索できることを確認する | `/gtp` | [Agent Skills](https://cursor.com/docs/skills) |

Skillの共通形式は[Agent Skills specification](https://agentskills.io/specification)に従う。配置後にSkillが表示されない場合は、Agentを再起動してからもう一度確認する。

複数のAgentを同じプロジェクトで使う場合も、同じ`skills/gtp/`一式を必要な認識先へ配置する。CodexとCursorは`.agents/skills/gtp/`を共有できる。更新時も、すべての配置先を同じGTP Releaseの内容で置き換える。

### 3. 導入を確認して使い始める

上表の方法で`gtp`を明示的に呼び出し、次のように依頼する。

```text
このrepositoryのGTP.mdを読み、GTPが記録する判断と記録しない判断を一つずつ説明して。fileは変更しないで。
```

Skillが`GTP.md`を読み、記録対象と対象外を説明できれば導入確認は完了である。実際の作業では、次のように依頼する。

```text
この変更にGTPを適用し、記録条件を満たす判断だけをDecision Recordへ残して。
```

判断が記録条件を満たす場合、Agentは利用プロジェクトの`gtp/decisions/`へRecordを作るか更新する。条件を満たす判断がなければ、Recordは作らない。

Python、CLI、PyPI、GitHub Issue、特定のpull request templateは不要や。正式な規則は[`GTP.md`](GTP.md)、構成は[`DESIGN.md`](DESIGN.md)、提出前reviewを含むAgentの手順は[`skills/gtp/SKILL.md`](skills/gtp/SKILL.md)にある。

## GTPがしないこと

GTP 2.0は作業状態、完了判定、Evidence集約、承認、権限、workflow制御、強制機構を持たない。Issueやpull requestへ表示した内容は、人が作業を理解するためのprojectionであり、Decision Recordの正本ではない。

公開済み1.xのCLI、tag、Release、PyPI packageは削除せず、そのまま取得できる。[`LEGACY.md`](LEGACY.md)に入口を残している。

具体例は[`examples/decisions/`](examples/decisions/)にある。License: [MIT](LICENSE)
