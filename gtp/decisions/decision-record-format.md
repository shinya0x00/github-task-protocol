## 未決定事項

Decision Recordの必須見出しを例示に留めるか、protocolの正準形式として固定するか。

## 採用した手段

`## 未決定事項`と`## 採用した手段`を正準見出しとする。判断を変更した場合だけ`## 変更履歴`を追加する。変更履歴entryはtop-levelのdash list itemとし、続きは字下げしたplain textとする。相互参照できるpull request、commit、Issueがある場合、新規または更新した各entryへ、その参照先の`[label](target)`形式のinline Markdown linkを含める。括弧内は指定targetだけとし、angle bracket、title、suffixは加えない。code spanやimageに同じ文字列を置いてもlinkとはみなさず、新規または更新したentryのHTML comment、raw HTML、fenced code blockは不適合とする。Skill付属validatorは、指定された比較元commitと現在のsourceを比較し、新規または更新されたentryに指定した参照先linkがなければ提出前に不適合とする。現在のsourceはPR head commit、明示したhead commit、またはpull request本文を検査しない場合のworktreeである。この形式は`GTP.md`が所有し、Skillは参照する。

## 変更履歴

- [Issue #149](https://github.com/shinya0x00/github-task-protocol/issues/149)で、[Exit Criteria PR #10のreview](https://github.com/agent-operated/exit-criteria/pull/10#pullrequestreview-4832893665)を受け、変更履歴の有無だけを定める手段から、参照先が存在する場合の実際のMarkdown linkまで提出前に検査する手段へ変更。
