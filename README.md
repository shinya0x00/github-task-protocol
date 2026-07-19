# GitHub Task Protocol

GTPは、GitHub Issue上のRecordと現在のGitHub observationから、AI coding taskの状態を決定的に再構成するprotocolです。GTP自身は変更、完了宣言、mergeの権限を与えません。

GTP v1.0.0は、4 Record type、Exact Carrier、closed schema、6 state、Server Orderによるprefix fold、alias、supersession、Repair Group、Done／Stop terminal orderingを実装しています。外部runtime dependencyはありません。

## Commands

```console
gtp check <comment.md>
gtp status <github-issue-url>
```

`gtp check`は投稿予定のMarkdown comment全文をofflineで検査します。通常comment、schema-valid Carrier、壊れたCarrierを区別し、GitHub文脈の検査を実施済みとは表示しません。

`gtp status`はIssue commentを全page取得してcomment ID順にfoldし、次の6 stateのいずれかを返します。

```text
unmanaged | ready | in_progress | halt | done | stopped
```

state-criticalな取得が不完全な場合はprotocol stateを推測せず、`state: null`、`acquisition.complete: false`、exit 2を返します。`halt`を含め、stateを導出できた場合のexit codeは0です。

logical Recordのmachine projectionは、server order上の最初のcommentを`url`、観測した全retry commentを`aliases`として返します。diagnosticにはclosed core tokenと原因comment/resource URLが含まれます。

## Authentication

`gtp status`は`GITHUB_TOKEN`、次に`GH_TOKEN`を使用します。どちらも未設定なら匿名readを試みます。production commandはGitHubへwriteしません。

## Development

```console
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests

python3 -m pip wheel --no-build-isolation --no-deps --wheel-dir dist .
python3 -m venv /tmp/gtp-verify
/tmp/gtp-verify/bin/python -m pip install --no-index --find-links dist github-task-protocol
/tmp/gtp-verify/bin/gtp check tests/fixtures/carriers/contract-valid.md
```

CIはPython 3.11、3.12、3.13でconformance tests、wheel build/install、installed CLI smokeを実行します。ADR-001〜ADR-026とconformance testの対応は`tests/fixtures/adr-conformance.json`で機械検査します。

実GitHub acceptanceの手順、観測結果、Evidenceの限界は[acceptance/README.md](acceptance/README.md)に分離しています。
