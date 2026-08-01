# GTP 1.x legacy

GTP 1.xは、GitHub Issue上のContract、Start、Done、Stop、Evidenceなどからtask stateを再構成するPython CLI中心のprotocolだった。

2.0では責務をDecision Recordへ変更したため、1.xの通常開発とruntimeを変更するpackage releaseは終了した。公開済みのtag target、GitHub Release asset、PyPI fileは削除、移動、上書き、yankせずlegacyとして残す。

PyPIの`1.0.3` pageに表示されるREADMEは1.x公開当時の内容である。そこにある「GitHubのlatest stable Release」を取得する手順は、現在は2.xを選ぶため使わない。2.xの`GTP.md`と1.xのadapterを組み合わせず、2.xは[`README.md`の導入手順](README.md#導入)から導入する。

## 1.xの正本

- 最後のruntime versionのtag: [`v1.0.3`](https://github.com/shinya0x00/github-task-protocol/tree/v1.0.3)
- 最後のruntime versionのGitHub Release: [`v1.0.3`](https://github.com/shinya0x00/github-task-protocol/releases/tag/v1.0.3)
- PyPIの1.x公開履歴: [`github-task-protocol`](https://pypi.org/project/github-task-protocol/)
- すべてのtag: [GitHub tags](https://github.com/shinya0x00/github-task-protocol/tags)

source treeで準備されていたpackage `1.0.4`は公開Releaseにせず、protocol semanticsとversion identity以外のCLI behaviorを変更するrelease laneを終了した。誤導する公開metadataを訂正するため、package version、人向け説明、release検証だけを変える最終post-release `1.0.3.post1`を公開し、公開検証後にPyPI projectをarchiveする。1.xの仕様、実装、test、acceptance artifactが必要な場合は、対応する公開tagを参照する。mainへ1.x sourceの複製は置かない。

securityまたはcorrectness上の重大な問題が見つかった場合、既存公開物を黙って置き換えず、影響範囲と対応を別の公開記録で示す。
