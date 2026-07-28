# GTP 1.x legacy

GTP 1.xは、GitHub Issue上のContract、Start、Done、Stop、Evidenceなどからtask stateを再構成するPython CLI中心のprotocolだった。

2.0では責務をDecision Recordへ変更したため、1.xの通常開発とpackage releaseは終了した。公開済みのtag、GitHub Release、PyPI packageは削除、移動、上書き、yankせずlegacyとして残す。

## 1.xの正本

- 最後の公開tag: [`v1.0.3`](https://github.com/shinya0x00/github-task-protocol/tree/v1.0.3)
- 最後のGitHub Release: [`v1.0.3`](https://github.com/shinya0x00/github-task-protocol/releases/tag/v1.0.3)
- PyPIの公開履歴: [`github-task-protocol`](https://pypi.org/project/github-task-protocol/)
- すべてのtag: [GitHub tags](https://github.com/shinya0x00/github-task-protocol/tags)

source treeで準備されていたpackage `1.0.4`は公開Releaseにせず、release laneを終了した。1.xの仕様、実装、test、acceptance artifactが必要な場合は、対応する公開tagを参照する。mainへ1.x sourceの複製は置かない。

securityまたはcorrectness上の重大な問題が見つかった場合、既存公開物を黙って置き換えず、影響範囲と対応を別の公開記録で示す。
