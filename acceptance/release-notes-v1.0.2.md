# GitHub Task Protocol 1.0.2 candidate

状態: source candidate。PyPI、GitHub tag、GitHub Releaseは未作成であり、公開済みとはClaimしない。

このcandidateは、同じGitHub記録を後から安全に再構成する境界を修復する。

- Stop後のfresh Recordを`halt / terminal_violation`として表示する。
- Stop後に作られた同名branchのPRを、過去のstopped taskへ結び付けない。
- GitHub 404、取得中のsnapshot変化、不完全なPR file一覧をAcquisition Errorとして分離する。
- PR file取得前後でbase/head SHAと`changed_files`を固定し、repositoryの`default_branch`も再読する。
- Start前から存在するPRをcandidateとDoneでは拒否し、Stopでは対象外として安全に閉じる。
- PR作成またはmergeとStopが同一instantならstateを断定しない。
- native merge前のDoneでbranch SHA、PR head SHA、Done head SHAを一致させる。
- repositoryのdefault branchをStart branchとして受理しない。
- Done提示前に、task固有の未確認事項を読むIssue URLを表示する。
- clean-installed wheelからproduction status pathを実行するCI E2Eを追加する。

Record grammarと`"gtp": "1.0"`は変更しない。package versionだけを`1.0.2`へ進める。
旧release laneのIssue #64 / PR #67と修復predecessor Issue #73 / PR #74は未mergeでsupersedeされ、Issue #75 / PR #76をcanonical candidate laneとする。

## Evidenceの限界

- local testとclean installは、GitHub Actionsのexact-head Check Runを代替しない。
- fixtureは外部GitHub HTTP境界を置き換え、実GitHubの権限構成や同時更新を証明しない。
- package公開、tag、Release、mergeには、それぞれ別の明示的なauthorityが必要である。
- 公開後のinstallとlive status再検証が終わるまで、READMEの1.0.2 commandを利用可能とはClaimしない。
