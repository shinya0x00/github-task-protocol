## 未決定事項

GTP本体を利用プロジェクトごとに置くか、Agentのuser-level Skill scopeへ置き、利用プロジェクトには判断結果だけを残すか。

## 採用した手段

標準インストールでは、`skills.sh`の一回の実行へRelease tag URLと二つのSkill名を明示し、protocolを同梱した`skills/gtp/`一式と、独立した`skills/pre-submission-review/`一式の二つを同時に、利用するAgentが公式に定めるuser-level Skill scopeへcopyする。インストール後に片方が不要なら、そのSkill directoryだけを削除する。

利用プロジェクトには`GTP.md`もAgent Skillも置かず、記録条件を満たした`gtp/decisions/*.md`だけを残す。同じuser-level配置を使う全プロジェクトへ同じGTP versionを適用し、project別のversion固定、GTP独自のinstaller、project-localからuser-levelへ昇格する仕組み、GTP独自のinstall stateは追加しない。`skills.sh`が保持するlockまたはprovenance情報は外部CLIが所有し、GTPとPre-submission Reviewはruntimeで参照しない。

## 変更履歴

- [PR #160](https://github.com/shinya0x00/github-task-protocol/pull/160)で、GTPだけを標準配置する方式から、GTPとPre-submission Reviewを標準インストールで同時に配置し、不要分は導入後に削除する方式へ変更。
- この変更で、二つのpathをAgentへ解釈させる導入から、Release tag URLと二つのSkill名を`skills.sh`へ機械的に渡す導入へ変更し、外部CLIのlockとGTP独自stateの境界を追加。
