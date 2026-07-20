# GitHub Task Protocol 1.0.1

## 何を公開したか

AIへ実装を任せながら、人間が目的、変更範囲、現在地、根拠、未確認事項をGitHub上で確認できるGitHub Task Protocolの仕様、任意CLI、受け入れ資料を公開します。

## 導入は3手順

1. repository rootへ`GTP.md`をコピーします。
2. READMEの共通adapter文をagentが必ず読む文書へ追加します。
3. taskごとにGitHub Issueを1件作り、そのURLをagentへ渡します。

CLIは必須ではありません。使う場合は`uvx --from github-task-protocol==1.0.1 gtp status <issue-url>`で現在地を確認できます。

## 現行実装から削った複雑性

- RecordはContract、Start、Done、Stopの4種類だけです。
- stateは6種類、halt reasonは7種類です。
- runtime dependencyは0です。
- GitHub取得はread-onlyで、GTP自身に変更、完了、mergeの権限はありません。
- 仕様の正本は400行以内の`GTP.md`だけです。

## 実際に通した受け入れ

- Level 0: Issue URLだけを渡した異なるagent間の引き継ぎ
- Level 1: clean installしたCLIによるlive `done`、`halt`、`stopped`の再構成と人間読解probe
- Python 3.11〜3.13のtest、build、clean wheel install、CLI smoke

公開candidateのcommit、Check Run、artifact hash、Level 0／Level 1 permalink、PyPI URLは、公開後のEvidence recordに示します。

## 互換性上の注意

package versionは`1.0.1`です。Record内の`"gtp": "1.0"`はprotocol versionであり、package versionとは別です。既存tag `v1.0.0`は移動・再利用していません。

## GTPが証明しないこと

GTPはactor本人性、credential安全性、コード品質そのもの、Evidence内容の真実性を証明しません。サンドボックス、最小権限、不可逆操作前の確認、reviewと組み合わせてください。
