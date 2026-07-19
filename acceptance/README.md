# Real GitHub acceptance run

このdirectoryは、walking skeletonを実GitHubで1回だけ通す受け入れ記録を置く。GTP coreの正準仕様ではない。

## Preconditions

- `main`に`CONTEXT.md`、`DECISIONS.md`、`GLOSSARY.md`を含む初期commitがあり、exact SHAを記録できる。
- 実装はそのSHAから作った`codex/` branchにあり、default branchへ直接pushしない。
- Issue comment作成、branch push、PR作成、native mergeのauthorityを各mutation前にGTP外部で確認する。
- `gtp`は実装branchのsourceから実行できる。

## Phase A: seed and fire

1. `shinya0x00/github-task-protocol`に専用Issueを1件作る。
2. Contract Aを投稿し、`gtp status`が`ready`を返すことを記録する。
3. fresh IDのContract Bを投稿する。`halt`、`conflicting_records`、A/B両comment URLを記録する。
4. fresh IDのContract CからA/B両URLを`supersedes`し、`ready`への回復を記録する。
5. Contract CへbindingするStartを投稿する。
6. 実装branchをpushしてPRを作り、`status`がbranchとPR CandidateをGitHubから導出して`in_progress`を返すことを記録する。
7. test command、結果、Issue/Record/PR URL、実装branchのsource head SHAを`acceptance/run.json`へ記録して最後のcommitに含める。Done投稿後はheadを変更しない。

## Phase B: clean-agent resume

fresh agentへtask stateとして渡すのはIssue URLだけとする。CLI sourceとGitHub credentialはtask stateではなく実行環境として与えてよい。

1. `gtp status <issue-url>`からBound Contract、Start branch、PR Candidateを再構成する。
2. PR source head SHAと、同SHAを含む`acceptance/run.json`のimmutable blob permalinkを取得する。
3. Contract Cのcondition IDへartifact URLを対応付けたDoneを投稿する。
4. merge前のstateが`in_progress`であることを記録する。
5. live authorityを再確認してPRをnative mergeする。
6. 同じIssue URLから`done`を観測し、比較対象がmerge commitではなくPR source head SHAであることを記録する。

## Evidence limits

- artifact bindingが証明するのは、指定source SHAにfileが存在することまでである。file内容の真実性は証明しない。
- clean-agent手順はlocal checkpointなしの再構成を実演するが、GitHub accountの本人性や操作権限をGTPが証明したことにはならない。
- API取得不能時の`state: null`はprotocol stateではない。
