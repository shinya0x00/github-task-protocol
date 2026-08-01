# GitHub Task Protocol 2.0

Protocol version: `2.0`

GitHub Task Protocol（GTP）は、後から変更するコストまたは影響が大きい未決定事項について、採用した手段をプロジェクト内へ残すためのprotocolである。

## 記録する判断

次の両方を満たす判断だけを記録する。

1. ユーザー指示、仕様、既存のDecision Recordなどから、採用する手段が一意に決まらない。
2. 後から変更すると、広い修整、互換性への影響、データ移行、利用者から見える挙動の変更、または大きな手戻りが生じる。

設計、実装計画、実装シミュレーション、実装中のどの段階で見つかった判断でもよい。変数名、関数分割、容易に戻せる局所実装などは記録しない。

## Decision Record

一つの未決定事項につき、一つのMarkdown fileを作る。正準見出しは`## 未決定事項`と`## 採用した手段`である。判断を変更した場合だけ`## 変更履歴`を追加する。

最低限の形式は次のとおりである。

```markdown
## 未決定事項

同じrequest IDを再処理してよいか。

## 採用した手段

同じrequest IDの完了済み処理は再実行せず、保存済み結果を返す。
```

理由、比較案、詳細な推論過程、status、承認者は必須項目にしない。既存仕様やADRがすでに手段を一意に決めている場合は、新しいDecision Recordを作らず、その正本に従う。

Decision Recordには、そのrepositoryへ保存してよい派生情報だけを書く。credential、token、private prompt、authorization本文などを転載しない。

## 正本

Decision Recordの正本は、利用プロジェクトがversion管理する`gtp/decisions/`に固定し、別pathへ設定可能にしない。

```text
利用プロジェクト/
└── gtp/
    └── decisions/
        └── request-id-retry.md
```

Decision Recordのidentityはrepository-relative pathである。file名は、判断対象を説明するlowercaseのhyphen区切りとする。連番、status、独自IDは要求しない。特定Agentのmemory、chat、一時file、Issue、pull requestは正本にしない。GitHubの利用も必須にしない。

## 判断を変更する

採用した手段が変わった場合は、同じfileの`採用した手段`を現在の内容へ更新し、`変更履歴`を追記する。

```markdown
## 変更履歴

- [PR #42](https://github.com/example/project/pull/42)で、再実行から保存済み結果の返却へ変更。
```

変更履歴entryは`- `で始まるtop-levelのdash list itemとし、続きは字下げしたplain textとして同じitemへ置ける。相互参照できる環境では、新規または更新した各entryへ、その変更を参照できるpull request、commit、Issueなどの`[label](target)`形式のinline Markdown linkを付ける。括弧内は指定されたtargetだけとし、angle bracket、title、その他のsuffixは加えない。code spanやimageに同じ文字列を置いてもlinkとはみなさない。新規または更新したentryにHTML comment、raw HTML、fenced code blockがある場合は、曖昧なMarkdownを実linkと誤認しないため不適合とする。参照できない環境では、何から何へ変わったかを短い文章で残す。過去の手段を現在の手段として本文へ併記しない。

判断の対象が廃止されるなど、Decision Recordが現在は適用されなくなった場合もfileを削除しない。`採用した手段`を「現在は適用しない」と分かる内容へ更新し、`変更履歴`へ理由を短く追記する。専用のstatus fieldは追加しない。

## 成果物から参照する

成果物の変更から、関連するDecision Recordへ一方向にたどれるようにする。

pull requestを使う場合は、本文へ判断の概要と相対pathを記載する。

```markdown
## 関連する判断

- 完了済みrequest IDは再実行せず、保存済み結果を返す
  - `gtp/decisions/request-id-retry.md`
```

各判断の概要を`- `で始まる一行のtop-level dash list itemとし、その直下へASCII space 2文字から4文字で字下げしたdash list itemを置く。そのitemには、対応するDecision Recordの相対pathをcode spanとして一つだけ置く。複数の判断は、この組を判断ごとに繰り返す。概要を伴わないpathだけの参照、一つの概要に複数pathを対応させた参照、概要とpathの対応が読み取れない参照は不適合である。fenced code blockやHTML comment内の見かけ上の組は対応とはみなさない。

pull request本文のrepository-relative pathはPR headのtreeを基準に解決する。merge後は同じpathをmainのtreeから参照する。

pull requestを使わない場合は、Git trailerとしてcommit message末尾へ記載できる。

```text
Decision-Ref: gtp/decisions/request-id-retry.md
```

`Decision-Ref`はGTPが定めるtrailer tokenである。値は、そのcommitのtree上で解決できるDecision Recordへのrepository-relative pathとする。Decision Recordがそのcommitのdiffに含まれる必要はない。

複数の判断を参照する場合は、1件につき1行の`Decision-Ref`を置く。

```text
Decision-Ref: gtp/decisions/request-id-retry.md
Decision-Ref: gtp/decisions/user-identifier.md
```

Decision Recordから成果物への逆参照や、成果物fileへの参照埋め込みは要求しない。

## 提出前の形式検査

同じversionのSkillに含まれる`scripts/validate.sh`は、pull request本文と変更履歴について、上記の形式へ適合するかを提出前に判定する。

```text
sh <Skillの配置先>/scripts/validate.sh \
  --repo-root . \
  --base-ref <比較元commit> \
  --head-ref <PR head commit> \
  --pr-body <pull request本文を保存したfile> \
  --change-reference <参照可能なpull request、commit、Issueのlink先>
```

pull request本文を検査する場合、`--base-ref`と`--head-ref`には検査対象のexact commitを渡し、`--change-reference`も必須とする。validatorはrefを開始時にcommitへ一度だけ解決して固定し、pull request本文のpathと現在の変更履歴をhead commitのtreeから読む。worktreeはpull request本文の検査に使わない。

pull requestを使わない場合は`--pr-body`を省略できる。この場合、`--head-ref`を指定すればそのcommit、指定しなければ現在のworktreeにある変更履歴を比較する。worktreeの検査結果を将来のcommitやpull requestの適合として扱ってはならない。相互参照できるcommitやIssueも存在しない場合だけ`--change-reference`を省略できる。参照先が存在するのに、link検査を避ける目的で省略してはならない。

validatorは、次だけを検査する。

- pull request本文の各Decision Record pathが、`関連する判断`で一つの概要と一対一に対応していること
- 対応した相対pathが指定したPR headのtreeに存在すること
- 比較元commitから指定したheadまたはworktreeまでに新規または更新された変更履歴entryが、`--change-reference`で渡した参照先へのinline Markdown linkを含むこと

関連する判断がないpull request本文と、比較元から変わっていない過去の変更履歴は不適合にしない。終了code `0`は適合、`1`は入力したGTP Markdownの形式上の不適合、`2`は引数または実行環境の誤りを表す。終了codeはreview、提出、mergeなどのrepository workflowの状態遷移を許可または禁止する判定ではない。validatorはCI checkを登録せず、merge gateとして動作せず、link先の到達可能性も判定しない。

## Issueとpull request

Issueやpull requestへDecision Recordを表示する場合、それらはprojectionであり正本ではない。linkだけにせず、非エンジニアが作業を理解できる説明を残す。

pull requestでは少なくとも次を平易に説明する。

- 目的
- 何が変わるか
- 変更内容
- 関連する判断の概要とDecision Recordへの参照

## 境界

GTP 2.0は、記録方法、参照方法、およびその狭い形式検査だけを定める。次は扱わない。

将来の便利さ、一般性、対称性、完全性、拡張余地だけを理由にcoreを増やさない。coreの変更は、具体的なfailureまたは既存contractとの互換性に対して、正しさ、portable性、診断、securityのいずれかに直接必要なものへ限る。

- 作業の開始、停止、進行、完了、retry、修復、成果物生成
- repository workflowの状態遷移
- Agentへの権限付与
- 人間による承認の必須化
- GitHubだけからの作業復元
- 完了Evidenceの集約
- review開始またはmergeの許可・拒否
- CI、merge gateによる強制
- general-purpose Markdown parser、repository checker、policy engineへの拡張

付属validatorは、上記で明示したGTP Markdown profileだけを判定し、Markdown一般の同値性を解釈しない。与えられた比較元、pull request本文、参照先だけを使い、link先の到達可能性、権限、内容、同一性、将来の存続は検査しない。すべての判断が記録されたこと、内容が正しいこと、採用手段が妥当であること、作業が完了したこと、Agentが従うことは保証しない。それらの検査や強制は、利用者がGTPとは別のtool、workflow、policy、または運用として追加する。
