## 未決定事項

GTP 2.0をPython packageとしてPyPIから配布するか、protocol文書とAgent Skillをversion固定して配布するか。

## 採用した手段

`GTP.md`と単一の`skills/gtp/`をtagとGitHub Releaseでversion固定して配布する。利用者は同じ配布物を、利用するAgentが公式に定める認識先へ配置する。Agent別の`SKILL.md`は作らず、`agents/openai.yaml`はOpenAI向けの任意metadataとして扱う。PythonとPyPIを標準配布経路にしない。
