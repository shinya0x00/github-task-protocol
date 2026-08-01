## 未決定事項

GTP 2.0をPython packageとしてPyPIから配布するか、protocol文書とAgent Skillをversion固定して配布するか。

## 採用した手段

protocol正本を同梱した単一の`skills/gtp/`を、tagとGitHub Releaseでversion固定して配布する。利用者は同じSkillを、利用するAgentが公式に定めるuser-level認識先へ配置する。rootの`GTP.md`は既存参照向けのprojectionとし、導入時のcopy対象に含めない。Agent別の`SKILL.md`は作らず、`agents/openai.yaml`はOpenAI向けの任意metadataとして扱う。PythonとPyPIを標準配布経路にしない。

## 変更履歴

- [PR #155](https://github.com/shinya0x00/github-task-protocol/pull/155)で、projectごとに`GTP.md`とSkillを置く配布から、protocolを同梱した自己完結Skillだけをuser-level scopeへ置く配布へ変更。
