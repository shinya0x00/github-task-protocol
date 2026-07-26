# ADR-040: production source budgetとblank-line formattingを分離する

- Status: Accepted
- Date: 2026-07-27
- Supersedes: None
- Superseded by: None

## 背景

production実装には`src/gtp/*.py`全体で2500 physical lines以下というbudgetがあった。しかしtotal linesをそのまま数えると、functionやclass間のblank linesを削るだけで実装量を減らさずにbudgetを満たせる。実際にmainの2229 nonblank linesから変更後はnonblank linesが増えた一方、blank linesが大幅に削られ、total linesだけは2500以下になっていた。

[PEP 8のBlank Lines](https://peps.python.org/pep-0008/#blank-lines)はtop-levelのfunction／class間に2 blank lines、class内のmethod間に1 blank lineを置く。budgetとこのformatting conventionを同じ数値で評価すると、可読性を保つ変更ほどbudget上不利になる。

## 決定

`src/gtp/*.py`の**physical nonblank lines**をproduction implementation budgetとし、2500以下を必須とする。判定は各physical lineについてwhitespaceを除いた後に1文字以上残るかで行う。commentとdocstringもmaintenance対象なので数える。mainのbaselineは2229 nonblank linesとする。

total linesとblank linesは候補ごとに観測して公開するが、合否判定には使わない。これにより、実装量が増えた事実とblank linesの増減を別々に確認できる。

blank-line qualityは別のgateで判定する。Ruff 0.12.3を固定し、次の検査を`src/gtp/*.py`へ適用する。

```text
ruff check --preview --select E301,E302,E305 src/gtp
```

Ruffの[E301](https://docs.astral.sh/ruff/rules/blank-line-between-methods/)、[E302](https://docs.astral.sh/ruff/rules/blank-lines-top-level/)、[E305](https://docs.astral.sh/ruff/rules/blank-lines-after-function-or-class/)は、PEP 8のmethod、top-level definition、definition後のblank-line conventionを機械的に検査する。budgetを満たすためのblank-line削除は、このgateがrejectする。

最終候補が2500 nonblank linesを超えた場合は完了とせず、実装を縮小するか、別の明示的なDecisionでbudgetを変更するまで停止する。実行時dependencyは追加せず、Ruffは開発・CIの検査toolとしてのみ使用する。

## 理由

physical nonblank linesは「blank linesだけを削って実装budgetを通す」という観測済みの抜け道を閉じる。commentとdocstringを含めるため、独自の意味分類やlanguage parserを追加せず、repository内で同じ値を再計算できる。

formattingは実装量とは異なるqualityである。PEP 8の既存conventionと、それを実装するRuffのruleを独立gateにすれば、可読性を犠牲にせずbudgetを強制できる。Ruffをruntimeへ含めないため、package利用者のdependencyと動作は変わらない。

## 検討した代替案

### blank linesを復元し、total-line capを引き上げる

不採用。capを引き上げても、将来blank linesを削れば実装量を増やせる性質は変わらない。formatting変更とimplementation budgetが引き続き競合する。

### total linesを2500以下に保つため、moduleを大規模に分割する

不採用。fileを分割してもrepository全体のphysical linesは減らない。数値を満たすための圧縮や大規模refactorは、今回必要なbehavior repairと無関係な回帰riskを増やす。

### blank-line ruleを設けず、reviewで可読性を判断する

不採用。今回観測した削除を同じ方法で確実にrejectできず、候補ごとに判断が揺れる。

## 結果と限界

- production implementation budgetは2500 nonblank lines以下として機械的に判定できる。
- total lines、nonblank lines、blank linesを別々に観測し、whitespaceによる見かけ上の削減を確認できる。
- PEP 8 blank-line conventionはRuffの固定versionとrule集合で独立してrejectできる。
- runtime dependencyとpublic protocol semanticsは変更しない。
- physical nonblank linesはcyclomatic complexity、結合度、設計品質を測らない。それらが必要な変更はtest、review、別の設計判断で評価する。
