# Level 0 acceptance

## 目的

`gtp` CLIを使わず、異なるAI coding runtimeがGitHub Issueだけから同じbranchとPRを引き継げるかを実測する。

## 固定した入力

- GTP仕様: [`GTP.md` at `8e9425a217218bb48aa710d4710b3d1fab23d9df`](https://github.com/shinya0x00/github-task-protocol/blob/8e9425a217218bb48aa710d4710b3d1fab23d9df/GTP.md)
- acceptance Issue: [#7](https://github.com/shinya0x00/github-task-protocol/issues/7)
- Contract: [issuecomment-5015234969](https://github.com/shinya0x00/github-task-protocol/issues/7#issuecomment-5015234969)
- Start: [issuecomment-5015236058](https://github.com/shinya0x00/github-task-protocol/issues/7#issuecomment-5015236058)
- branch: `agent/issue-7-level0-handoff`
- Agent A: OpenAI Codex（`codex-cli 0.141.0`）
- Agent B: 実行前のため未確認

## Agent A時点の観測

Agent AはContractとStartをGitHubへ投稿し、指定branch上にこの受け入れ記録の最小骨格を作成した。異なるruntimeによる再開、既存PRの選択、重複の有無、人間読解はまだ観測していない。

この文書は受け入れ結果の正本であり、Agent B向けの専用handoff指示ではない。次のprotocol actionはIssue #7、GTP Record、branch、PRから判断する。

## Evidenceの限界

GitHub URLとcommit SHAはresourceと履歴の存在を示す。各Agentが内部で何を読んだか、別のmemoryを一切持たなかったこと、記述内容の真実性そのものまでは自動的に証明しない。実行環境、prompt、command、exit code、選択した最初の行動を`run.json`へ記録して境界を明示する。
