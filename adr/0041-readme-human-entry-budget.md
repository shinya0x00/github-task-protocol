# ADR-041: READMEのplain-first入口を行数budgetより優先する

- Status: Accepted
- Date: 2026-07-27
- Supersedes: None
- Superseded by: None

## 背景

READMEには150行以下というbudgetがあり、v1.0.4 source merge時点では108行だった。しかし短さを優先した結果、protocol 1.1のformal tokenと例外が目的説明へ近づき、通常表示6項目と`halt`時に追加する問題整理8項目の関係も入口から読めなくなった。

READMEは正式仕様ではなく、非エンジニアが「何を確認でき、何を人が判断するか」を最初に理解する入口である。厳密なRecord、参照、transition、terminal ruleは400行以下の`GTP.md`が所有する。

## 決定

READMEの上限を150行から180行へ変更する。180行は目標行数ではなく上限であり、説明を増やす許可ではない。

READMEでは、目的とできることをformal tokenより先に置く。packageとprotocolの短い区別、通常表示6項目、`halt`等で追加する問題整理8項目、人が判断すること、最小の導入・CLI手順を置いた後に、正式なRecordとstateを示す。protocol 1.1の厳密規則は`GTP.md`と既存ADRへ委ねる。

変更後READMEは138行であり、旧上限では残り12行だった。180行なら42行の余白があり、入口を再び圧縮せずに小さな説明修正を受け入れられる。testは単語の有無ではなく、plain-firstなsection順と「通常6項目に追加8項目」という構造を検査する。

`GTP.md`の400行上限とproduction Pythonの2500 physical nonblank lines上限は変更しない。

## 検討した代替案

### 150行を維持する

不採用。現在の文面は収まるが、必要な入口をすべて置くと余白が小さく、将来の文言修正でformal detailを前へ戻す圧力が再発する。

### READMEのbudgetをなくす

不採用。READMEが正式仕様や設計判断まで重複して持つことを防げない。180行の上限とsection関係のtestを併用する。

### 6項目と8項目をREADMEへ置かない

不採用。CLIを初めて読む人が、通常表示と問題時の追加説明の関係を判断できない。詳細なhalt reasonやterminal ruleはREADMEへ戻さない。

## 結果と限界

- READMEの短さではなく、人が最初に判断できる順序を守る。
- READMEはGTPの正式規則を新設せず、`GTP.md`への入口に留まる。
- 180行以内であることは、実際に読みやすいことを証明しない。独立したhuman probeで確認する。
- GTP state、schema、machine JSON、runtime dependency、package versionは変更しない。
