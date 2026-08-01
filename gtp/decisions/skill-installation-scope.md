## 未決定事項

GTP本体を利用プロジェクトごとに置くか、Agentのuser-level Skill scopeへ置き、利用プロジェクトには判断結果だけを残すか。

## 採用した手段

protocolを同梱した`skills/gtp/`一式を、利用するAgentが公式に定めるuser-level Skill scopeへ置く。利用プロジェクトには`GTP.md`もAgent Skillも置かず、記録条件を満たした`gtp/decisions/*.md`だけを残す。同じuser-level配置を使う全プロジェクトへ同じGTP versionを適用し、project別のversion固定、GTP独自のinstaller、project-localからuser-levelへ昇格する仕組み、install stateは追加しない。
