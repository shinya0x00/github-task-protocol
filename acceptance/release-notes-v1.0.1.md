# GitHub Task Protocol 1.0.1

> これはGitHub Releaseへ転記するための原稿です。tag、GitHub Release、PyPIの公開確認が終わるまでは、公開済みとは扱いません。

## 何を公開するか

AIへ作業を任せながら、人間が目的、変更範囲、現在地、根拠、未確認事項をGitHub上で確認できるGitHub Task Protocolの仕様、任意CLI、受け入れ資料を同じcandidateから公開します。

## 導入は3手順

1. repository rootへ`GTP.md`をコピーします。
2. READMEの共通adapter文をagentが必ず読む文書へ追加します。
3. taskごとにGitHub Issueを1件作り、そのURLをagentへ渡します。

CLIを使う場合は、`uvx --from github-task-protocol==1.0.1 gtp status <issue-url>`で現在地を確認できます。

## 現行実装から削った複雑性

- RecordはContract、Start、Done、Stopの4種類だけです。
- stateは6種類、halt reasonは7種類に固定しています。
- runtime dependencyは0です。
- GitHub取得はread-onlyで、GTP自身には変更、完了、mergeの権限がありません。
- 仕様の正本は400行以内の`GTP.md`だけです。

## 実際に通した受け入れ

- [Level 0: 別agentへのIssue URLだけの引き継ぎ](https://github.com/shinya0x00/github-task-protocol/tree/8045948fe25fc6e94fa5cf839abd6c3d10de188e/acceptance/level0)
- [Level 1: clean installしたCLIによるlive GitHub検証](https://github.com/shinya0x00/github-task-protocol/tree/8045948fe25fc6e94fa5cf839abd6c3d10de188e/acceptance/level1)
- [仕様正本 GTP.md](https://github.com/shinya0x00/github-task-protocol/blob/8045948fe25fc6e94fa5cf839abd6c3d10de188e/GTP.md)

公開candidateのCI、artifact hash、PyPIからの再検証結果は、公開確認後にIssue #14のrelease evidenceとして示します。

## 互換性上の注意

package versionは`1.0.1`です。Record内の`"gtp": "1.0"`はprotocol versionであり、package versionとは別です。既存のannotated tag `v1.0.0`は履歴として保持し、移動・再利用しません。

## GTPが証明しないこと

GTPはactor本人性、credential安全性、コード品質そのもの、Evidence内容の真実性を証明しません。サンドボックス、最小権限、不可逆操作前の確認、reviewと組み合わせてください。
