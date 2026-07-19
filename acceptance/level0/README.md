# Level 0 acceptance

## まず、これだけ読めば分かる現在地

- **目標**: 最初のAI（Codex）が途中で止まっても、別のAI（Claude Code）がIssue #7だけを読んで同じ作業を続けられるか確かめる。
- **変更してよいファイル**: この`README.md`と、同じdirectoryの`run.json`だけ。
- **現在地**: Claude Codeは正しい既存branchとPR #16を見つけ、重複を作らず記録を追加した。自動testも成功した。ただし、最初の人間読解確認では内容が伝わらず、受け入れはまだ未完了。
- **次に行うこと**: repository ownerがこの4行を読み、目標・変更範囲・現在地・次の行動を自分の言葉で説明できるか、もう一度確認する。伝われば記録を確定してPR #16をreview・mergeする。

## 目的

`gtp` CLIを使わず、異なるAI coding runtimeがGitHub Issueだけから同じbranchとPRを引き継げるかを実測する。

## 固定した入力

- GTP仕様: [`GTP.md` at `8e9425a217218bb48aa710d4710b3d1fab23d9df`](https://github.com/shinya0x00/github-task-protocol/blob/8e9425a217218bb48aa710d4710b3d1fab23d9df/GTP.md)
- acceptance Issue: [#7](https://github.com/shinya0x00/github-task-protocol/issues/7)
- Contract: [issuecomment-5015234969](https://github.com/shinya0x00/github-task-protocol/issues/7#issuecomment-5015234969)
- Start: [issuecomment-5015236058](https://github.com/shinya0x00/github-task-protocol/issues/7#issuecomment-5015236058)
- branch: `agent/issue-7-level0-handoff`
- Agent A: OpenAI Codex（`codex-cli 0.141.0`）
- Agent B: Claude Code（Sonnet 5）

## Agent A時点の観測

Agent AはContractとStartをGitHubへ投稿し、指定branch上にこの受け入れ記録の最小骨格を作成した。異なるruntimeによる再開、既存PRの選択、重複の有無、人間読解はまだ観測していない。

この文書は受け入れ結果の正本であり、Agent B向けの専用handoff指示ではない。次のprotocol actionはIssue #7、GTP Record、branch、PRから判断する。

## Agent B時点の観測

Agent B（Claude Code, Sonnet 5）へ渡された入力は、Issue [#7](https://github.com/shinya0x00/github-task-protocol/issues/7)のURLのみであり、chat履歴、local checkpoint、専用handoff文書は一切参照していない。

Agent Bはroot `GTP.md`をtask protocolの唯一の正本として読み、Issue commentをServer Orderで読んだ。有効なRecordはContract（[issuecomment-5015234969](https://github.com/shinya0x00/github-task-protocol/issues/7#issuecomment-5015234969)）とStart（[issuecomment-5015236058](https://github.com/shinya0x00/github-task-protocol/issues/7#issuecomment-5015236058)）の2件のみであり、GTP markerのない3件目のcommentは通常commentとして扱った。これによりstateを`in_progress`と再構成し、既存branch `agent/issue-7-level0-handoff`と既存draft PR [#16](https://github.com/shinya0x00/github-task-protocol/pull/16)を、新規branchや新規PRを作らずそのまま継続した。詳細は`run.json`を参照する。

## 人間読解probe

1回目の確認でrepository ownerは、目標、変更範囲、現在地、次の行動について「何もわからない」と回答した。この時点では人間読解条件を満たしていない。原因を人間側の知識不足とは扱わず、READMEの要点が先に示されていなかった表示上の失敗として、この文書の冒頭へ平易な4回答を追加した。

2回目の確認結果は未実施である。実際の回答が得られるまで受け入れ完了とは書かない。

## Evidenceの限界

GitHub URLとcommit SHAはresourceと履歴の存在を示す。各Agentが内部で何を読んだか、別のmemoryを一切持たなかったこと、記述内容の真実性そのものまでは自動的に証明しない。実行環境、prompt、command、exit code、選択した最初の行動を`run.json`へ記録して境界を明示する。

Agent Bのsystem環境には`GTP.md`掲載の共通adapter文が設定されていた。この試験が示すのは「GTP.mdと詳細なadapterを導入した環境」で引き継げたことまでであり、Issue URLだけからGTP.mdを自力で発見できることまでは示さない。
