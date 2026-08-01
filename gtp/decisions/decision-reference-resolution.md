## 未決定事項

pull request本文とcommit trailerからDecision Recordを参照するとき、どのtreeを基準にpathを解決し、複数の判断をどう表すか。

## 採用した手段

pull request本文では、各判断の概要を一行のtop-level dash list itemとし、対応するrepository-relative pathをASCII space 2文字から4文字で字下げしたdash list itemへ一つだけ置く。概要を伴わないpathだけの参照と、一つの概要に複数pathを置く参照は不適合とする。pathはPR headのtreeを基準とし、merge後は同じpathをmainのtreeから参照する。Skill付属validatorはpull request本文の検査時にexact head commitを入力として受け、開始時にcommitへ一度だけ解決して固定し、この一対一対応とhead treeでの存在を検査する。pull request本文の検査にはworktreeを使わない。`Decision-Ref`はcommitのtree上で解決できるpathを1件につき1行置き、参照先が同じcommitのdiffに含まれることは要求しない。

## 変更履歴

- [Issue #149](https://github.com/shinya0x00/github-task-protocol/issues/149)で、[Exit Criteria PR #10のreview](https://github.com/agent-operated/exit-criteria/pull/10#pullrequestreview-4832893665)を受け、pathの解決基準だけを定める手段から、pull request本文の概要と相対pathを一対一で対応させ、exact head treeに対して提出前に検査する手段へ変更。
