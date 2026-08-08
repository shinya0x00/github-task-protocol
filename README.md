# GitHub Task Protocol

AIへ設計や実装を任せると、仕様だけでは決まらない重要な選択が作業中に生まれる。完成後にその選択だけを変えようとすると、広い修整、互換性問題、データ移行、大きな手戻りにつながることがある。

GTP 2.0は、そうした未決定事項に対して、どの手段を採用したかをプロジェクト内へ残すための小さなprotocolや。

> 後から変えると高くつく選択だけを、採用した手段と一緒に残す。

## Releaseに含むSkill

同じGitHub Releaseのsource archiveに、二つの独立したAgent Skillを収録する。

### GitHub Task Protocol

`skills/gtp/`はGTP中核を適用する。後から変えると高くつく判断だけをDecision Recordへ残し、pull requestまたはcommitから参照する。一般的な文章reviewは行わない。

### Pre-submission Review

`skills/pre-submission-review/`は、Issue、pull request、commit message、Release notes、Decision Record、利用者向けの提出文章を、handoffまたは外部投稿の前にreviewする。言語を決め、repositoryのtemplateを守り、目的と変更を読みやすくする。GTPを使わないtaskにも適用できる。

二つのSkillは実行時には互いを必要としない。標準インストールでは、二つのSkillを同じinstall runでuser-level scopeへ入れる。インストール後に片方が不要なら、そのSkill directoryだけを削除する。同じReleaseに収録して一緒にインストールすることは、同じ発火条件や責務を持たせることを意味しない。

## GTPが記録するもの

次の両方を満たす判断だけを記録する。

1. ユーザー指示、仕様、既存のDecision Recordから手段が一意に決まらない。
2. 後から変えると、修整コストまたは影響が大きい。

例えば、公開APIの互換性、データ形式、再試行時の挙動、大きな構成変更は対象になり得る。変数名や容易に戻せる局所実装は記録しない。

### 最小のDecision Record

利用プロジェクトの`gtp/decisions/`へ、一つの未決定事項につき一つのMarkdown fileを置く。

```markdown
## 未決定事項

同じrequest IDを再処理してよいか。

## 採用した手段

完了済みrequest IDは再実行せず、保存済み結果を返す。
```

理由、比較案、詳しい推論過程は必須にしない。判断を変えた場合だけ、同じfileの現在内容を更新し、`変更履歴`を加える。

### 成果物から判断へつなぐ

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

二つのSkillは、利用するAgentのuser-level Skill scopeへ置く。利用プロジェクトへGTP本体やPre-submission Review本体をcopyしない。GTPを使う利用プロジェクトに残るのは、記録条件を満たした`gtp/decisions/*.md`だけである。

### 1. 固定版`skills`で二つを同時に入れる

[Releases](https://github.com/shinya0x00/github-task-protocol/releases)から利用するGTP 2.xのReleaseを選ぶ。1.xは責務と配布形式が異なるため、この導入手順の対象外である。1.xが必要な場合は[`LEGACY.md`](LEGACY.md)を参照する。

v2.0.9では、Release assetとinstallerを検証してから二つのSkillを入れる。可変な`latest`指定やtag名だけに依存せず、source archiveのSHA-256と、外部CLI `skills` v1.5.21のSHA-512を確認する。次の共通準備を一回だけ実行する。

```sh
RELEASE_DIR="$(mktemp -d)"
cd "$RELEASE_DIR"
curl -fsSLO https://github.com/shinya0x00/github-task-protocol/releases/download/v2.0.9/github-task-protocol-v2.0.9.tar.gz
curl -fsSLO https://github.com/shinya0x00/github-task-protocol/releases/download/v2.0.9/SHA256SUMS
grep ' github-task-protocol-v2.0.9.tar.gz$' SHA256SUMS | shasum -a 256 -c -
tar -xzf github-task-protocol-v2.0.9.tar.gz
test "$(tar -tzf github-task-protocol-v2.0.9.tar.gz | grep -Ec '^github-task-protocol-v2.0.9/skills/(gtp|pre-submission-review)/SKILL.md$')" -eq 2
export SKILLS_TARBALL="$(npm pack --ignore-scripts --silent skills@1.5.21)"
export SKILLS_SHA512="089e30c7af765244005be0cba63260ff0c3a7490688eae44f2c4013aa3fadfd1aeb4eef6bf8105895fdfab57ad5b6afd36133f9b0688abc628a8a149f5757b9e"
printf '%s  %s\n' "$SKILLS_SHA512" "$SKILLS_TARBALL" | shasum -a 512 -c -
export SOURCE_DIR="$RELEASE_DIR/github-task-protocol-v2.0.9/skills"
```

検証が成功したあと、使うAgentを選んで実行する。最後の`--yes`は付けず、CLIが表示するSkill一覧を確認してから続行する。

Codex:

```sh
npm exec --ignore-scripts --yes --package="./${SKILLS_TARBALL}" -- skills add \
  "$SOURCE_DIR" \
  --skill gtp --skill pre-submission-review \
  --global --agent codex --copy
```

Claude CodeではAgent名だけを変える。

```sh
npm exec --ignore-scripts --yes --package="./${SKILLS_TARBALL}" -- skills add \
  "$SOURCE_DIR" \
  --skill gtp --skill pre-submission-review \
  --global --agent claude-code --copy
```

同じ端末でCodexとClaude Codeの両方を使う場合は、一回の実行へ二つのAgentも指定できる。

```sh
npm exec --ignore-scripts --yes --package="./${SKILLS_TARBALL}" -- skills add \
  "$SOURCE_DIR" \
  --skill gtp --skill pre-submission-review \
  --global --agent codex --agent claude-code --copy
```

`SOURCE_DIR`はSHA-256検証済みRelease archiveからだけ作る。二つの`--skill`が標準install setを固定し、`--global`がproject-local配置を避ける。`--copy`は各Skillを独立したdirectoryとして配置する。インストール後に片方が不要なら、そのSkill directoryだけを削除できる。

| Agent | `skills`のAgent名 | user-level認識先 | 明示的な呼び出し | 公式資料 |
| --- | --- | --- | --- | --- |
| Codex | `codex` | `$HOME/.agents/skills/` | `$gtp` / `$pre-submission-review` | [Build skills](https://learn.chatgpt.com/docs/build-skills) |
| Claude Code | `claude-code` | `~/.claude/skills/` | `/gtp` / `/pre-submission-review` | [Extend Claude with skills](https://code.claude.com/docs/en/skills) |

`skills`はGTP専用のinstallerではない。Agent Skills repositoryを探索して複数のSkillを導入する外部CLIである。利用するCLI版はv1.5.21へ固定し、上記のSHA-512検証が通ったtarballだけを実行する。GTPとPre-submission ReviewはCLIのlockやprovenance情報をruntimeで読まない。CLIの引数と挙動は[`vercel-labs/skills`](https://github.com/vercel-labs/skills)で確認できる。

### 2. 手動で入れる代替手順

Node.jsまたは`npx`を使わない場合も、Release asset `github-task-protocol-v2.0.9.tar.gz`のSHA-256を同じReleaseの`SHA256SUMS`で先に検証する。検証に成功したarchiveだけを展開し、次の二directoryを同じ作業でAgentのuser-level認識先へcopyする。片方だけを標準install setとして選ばない。GitHubが自動生成する未検証のzipや、tag名だけを根拠にしたarchiveは使わない。

```text
skills/
├── gtp/
│   ├── SKILL.md
│   ├── GTP.md
│   └── agents/
│       └── openai.yaml
└── pre-submission-review/
    ├── SKILL.md
    └── agents/
        └── openai.yaml
```

archive直下の`GTP.md`は既存参照向けの入口であり、利用プロジェクトへcopyしない。protocolの正本は`skills/gtp/GTP.md`である。各`agents/openai.yaml`はOpenAI向けの任意metadataであり、Skill本体の分岐ではない。

Skillの共通形式は[Agent Skills specification](https://agentskills.io/specification)に従う。配置後に`/skills`を開くなど、Agentが二つのSkillを認識したことを確認する。表示されない場合はAgentを再起動してからもう一度確認する。

### 3. 2.0.7以前から更新する

共通準備でv2.0.9のRelease archiveと固定版CLIを検証してから、利用するAgent向けの標準コマンドを実行する。`--copy`による再導入は、同名のSkill directoryを新しいRelease内容へ置き換える。導入先を直接変更していた場合、その変更は失われるため、必要なら実行前にuser-level認識先の外へ退避する。

v2.0.6またはv2.0.7で`gtp`だけが入った状態でも、不足分だけを別手順で足さない。v2.0.9の標準コマンドを一回実行し、`gtp`と`pre-submission-review`を同じReleaseから入れ直す。

2.0.5以前のGTP Skillに含まれていた提出前reviewは、新しいGTP Skillには含まれない。v2.0.9の標準コマンドで、GTP中核と独立したPre-submission Reviewを同時に入れる。片方が不要なら、二つの認識確認が終わってから不要なSkill directoryだけを削除する。

project-local配置を使っていた既存プロジェクトは、先にuser-level配置と認識確認を済ませる。その後、GTPからcopyしたrootの`GTP.md`とproject-localのSkill copyをプロジェクトから削除する。`gtp/decisions/`は判断結果の正本なので残す。

### 4. 認識を確認する

GTPは次のように明示的に呼び出す。

```text
$gtp
GTPのprotocol versionと、記録する判断の二条件を説明して。fileは変更しないで。
```

Skillが同梱した`GTP.md`を読み、protocol version `2.0`と二条件を説明できればGTPの導入確認は完了である。

Pre-submission Reviewは、GTPを使わない依頼で確認する。

```text
$pre-submission-review
この完成済みpull request本文にpre-submission reviewを行って。外部投稿はしないで。
```

言語、適用するrepository template、目的、変更、参照の可読性を確認できれば導入確認は完了である。

## Pre-submission Reviewの言語

install時の言語設定fileは作らない。対象ごとに、利用者の明示指定、言語を明示的に要求するrepositoryの指示・仕様・template、関連する既存文章、現在の依頼で利用者自身が書いた文章の順で決める。言語を指定しないsourceは飛ばす。Skill自身のinstruction、UI metadata、自動生成されたdefault prompt、例文は、利用者またはrepositoryの言語を決める根拠にしない。

最初に判断材料がある優先順位で候補が割れるか、最後まで一つに決まらない場合だけ、その対象について利用者へ一度確認する。利用者の明示指定とrepositoryの言語要求が衝突する場合は、準拠する言語を選ぶか、利用者が例外を認める権限を持つことを確認するまで下書きも外部投稿もしない。

公開先がGitHubであることやtoolの例が英語であることは、英語を選ぶ理由にしない。code identifier、command、path、schema key、protocol token、standardの正式名称は原文を保つ。

## Repository templateとの関係

Pre-submission Reviewは専用templateを要求しない。対象に適用するtemplateがなければ、目的、変更内容、検証、関連する参照を説明できる最小構成を使う。templateがあれば、その構造を保ち、適切な既存欄へ説明を書く。

提出前には、固定見出しとその順序、task list itemと文言、必要なHTML comment、固定文が残っているかを読み直す。これは文章reviewであり、checker、CI、gateによる機械的な強制ではない。Agentが必ず守ることまでは保証しない。

Claude Codeで、外部投稿前にreviewする時点をモデルの判断だけに任せたくない場合は、[Claude Code hooks](https://code.claude.com/docs/en/hooks)による任意の補助を検討できる。hooksはPre-submission Reviewの導入要件、通常利用の要件、またはAgent complianceの保証ではない。このrepositoryはhook、hook用state、Agent別の設定を配布しない。

GTP中核の規則は[`skills/gtp/GTP.md`](skills/gtp/GTP.md)、Agentによる適用手順は[`skills/gtp/SKILL.md`](skills/gtp/SKILL.md)、文章reviewの手順は[`skills/pre-submission-review/SKILL.md`](skills/pre-submission-review/SKILL.md)にある。構成は[`DESIGN.md`](DESIGN.md)にある。

## しないこと

GTP 2.0は作業状態、完了判定、Evidence集約、承認、権限、workflow制御、文章review、強制機構を持たない。Issueやpull requestへ表示した内容は、人が作業を理解するためのprojectionであり、Decision Recordの正本ではない。

Pre-submission Reviewは外部操作のauthorization、承認、正しさの証明、checker、CI、gate、workflow制御を追加しない。

公開済み1.xのCLI、tag、Release、PyPI packageは削除せず、そのまま取得できる。[`LEGACY.md`](LEGACY.md)に入口を残している。

具体例は[`examples/decisions/`](examples/decisions/)にある。License: [MIT](LICENSE)
