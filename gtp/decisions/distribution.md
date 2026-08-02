## 未決定事項

GTP 2.0をPython packageとしてPyPIから配布するか、protocol文書とAgent Skillをversion固定して配布するか。

## 採用した手段

tag時点のrepositoryを含むGitHub Release source archiveへ、protocol正本を同梱した`skills/gtp/`と、独立した`skills/pre-submission-review/`を収録する。二つはAgent Skills形式に従う自己完結したSkill directoryとし、利用者は片方または両方を、利用するAgentが公式に定めるuser-level認識先へ配置できる。

rootの`GTP.md`は既存参照向けのprojectionとし、導入時のcopy対象に含めない。Agent別の`SKILL.md`、独自package、複数Skill用manifest、installer、install stateは作らない。各`agents/openai.yaml`はOpenAI向けの任意metadataとして扱う。PythonとPyPIを標準配布経路にしない。

## 変更履歴

- [PR #155](https://github.com/shinya0x00/github-task-protocol/pull/155)で、projectごとに`GTP.md`とSkillを置く配布から、protocolを同梱した自己完結Skillだけをuser-level scopeへ置く配布へ変更。
- [PR #159](https://github.com/shinya0x00/github-task-protocol/pull/159)で、単一のGTP Skillだけを収録する配布から、GTPとPre-submission Reviewを独立したSkillとして同じGitHub Release source archiveへ収録する配布へ変更。
