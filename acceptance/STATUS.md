# Walking skeleton acceptance status

更新日: 2026-07-19

この文書は実装進行のhandoffであり、GTP core specificationやDone Recordではない。

## 観測済み

| 要件 | 状態 | Evidence | Evidenceの限界 |
|---|---|---|---|
| Exact Carrier認識 | local verified | `tests/test_carrier.py`、valid/normal/marker typo/malformed/duplicate key fixtures | GitHubがMarkdown bodyを返す全variantを網羅しない |
| 4 Record type closed schema | local verified | `tests/fixtures/carriers/`、`tests/test_schema.py` | v1全repair routeの実装完了を意味しない |
| Server Order prefix fold | local verified | `tests/test_reducer.py` | 実Issue上の複数page履歴では未発火 |
| 6 state | local verified | reducer/status testsで`unmanaged`、`ready`、`in_progress`、`halt`、`done`、`stopped`を観測 | `done`と`stopped`はfake GitHub observationsによる |
| 2-leaf Contract conflictと回復 | local verified | `conflicting_records`の両URLと2 URL supersessionのtest | 実comment URLでは未発火 |
| branch / PR / Evidence / merge境界 | local verified | artifact、Check Run pending/failure、PR source head、merge前後のstatus tests | 実branch・PR・Check Runでは未発火 |
| dependency-free package | isolated verified | PEP 517 wheel build、clean venv install、生成された`gtp check`実行成功 | release artifactの公開は未実施 |
| production GitHub read wiring | live read verified | `cli/cli#13826`で`unmanaged`、`cli/cli#13919`で通常commentを無視、Issue形式のPR resourceを拒否 | GTP Carrierを含む実Issueでは未発火 |
| 実repository E2E | ready to start | 初期`main` SHA `af29a98be8b6666afe5fabfecdaac2a5a6f3ae13`をlocal treeとGitHub APIの両方で照合 | Issue、Record、実装PR、native mergeは未作成 |

## 現在の検証command

```console
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests

python3 -m venv /tmp/gtp-verify
/tmp/gtp-verify/bin/python -m pip install --no-build-isolation --no-deps .
/tmp/gtp-verify/bin/gtp check tests/fixtures/carriers/contract-valid.md
```

直近の観測結果は36 tests成功。実GitHub readでは、取得完了時に`unmanaged`とexit 0、存在しないIssueでは`state: null`とexit 2を観測した。

## Resolved bootstrap

`bootstrap_main_missing`は2026-07-19に解消した。

- Operatorの明示指示に基づき、3正準文書だけを含む初期`main` commitを作成した。
- local SHAとGitHub `refs/heads/main`はともに`af29a98be8b6666afe5fabfecdaac2a5a6f3ae13`である。
- 実装branchはこのSHAから`codex/gtp-walking-skeleton`として作成した。

このbootstrapはGTP Recordが付与したauthorityによるものではない。

## Exact resume point

1. 現在のuntracked実装を`codex/gtp-walking-skeleton`へcommitする。
2. [README.md](README.md)のPhase Aを実Issueで実行し、`halt`と両原因comment URL、superseding Contractによる`ready`回復を記録する。
3. 実装branch/commit/PRを接続し、fresh agentへIssue URLだけを引き渡す。
4. `acceptance/run.json`をsource headへ固定し、artifact Evidence付きDone、merge前`in_progress`、native merge後`done`を観測する。
