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

- PR #42で、再実行から保存済み結果の返却へ変更。
```

相互参照できる環境ではpull request、commit、Issueなどへのlinkを付ける。参照できない環境では、何から何へ変わったかを短い文章で残す。過去の手段を現在の手段として本文へ併記しない。

判断の対象が廃止されるなど、Decision Recordが現在は適用されなくなった場合もfileを削除しない。`採用した手段`を「現在は適用しない」と分かる内容へ更新し、`変更履歴`へ理由を短く追記する。専用のstatus fieldは追加しない。

## 成果物から参照する

成果物の変更から、関連するDecision Recordへ一方向にたどれるようにする。

pull requestを使う場合は、本文へ判断の概要と相対pathを記載する。

```markdown
## 関連する判断

- 完了済みrequest IDは再実行せず、保存済み結果を返す
  - `gtp/decisions/request-id-retry.md`
```

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

## Issueとpull request

Issueやpull requestへDecision Recordを表示する場合、それらはprojectionであり正本ではない。linkだけにせず、非エンジニアが作業を理解できる説明を残す。

pull requestでは少なくとも次を平易に説明する。

- 目的
- 何が変わるか
- 変更内容
- 関連する判断の概要とDecision Recordへの参照

## 境界

GTP 2.0は、記録方法と参照方法だけを定める。次は扱わない。

- 作業の開始、停止、完了状態
- workflowの制御
- Agentへの権限付与
- 人間による承認の必須化
- GitHubだけからの作業復元
- 完了Evidenceの集約
- checker、CI、gateによる強制

すべての判断が記録されたこと、内容が正しいこと、採用手段が妥当であること、参照が切れていないこと、Agentが従うことは保証しない。必要な検査や強制は、利用者がGTPとは別の運用として追加する。
