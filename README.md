# GitHub Task Protocol

GTPは、GitHub Issue上のRecordとGitHubの観測事実から、AI coding taskの現在地を再構成するprotocolです。GTP自身は変更・完了宣言・mergeの権限を与えません。

## Development command

```console
python3 -m venv .venv
.venv/bin/python -m pip install --no-build-isolation --no-deps .
.venv/bin/gtp check tests/fixtures/carriers/contract-valid.md

PYTHONPATH=src python3 -m gtp check tests/fixtures/carriers/contract-valid.md
PYTHONPATH=src python3 -m unittest discover -s tests
```

package buildにもruntimeにも外部dependencyはない。repository同梱のPEP 517 backendは標準ライブラリだけでpure-Python wheelと`gtp` entry pointを生成する。

`gtp check`は投稿予定のMarkdown comment全文をoffline検査します。`gtp status`はGitHub Issueをread-onlyで観測してstateを導出します。

`gtp status`は`GITHUB_TOKEN`、次に`GH_TOKEN`を使用し、未設定ならpublic repositoryを匿名でreadします。stateを導出できた場合は`halt`を含めexit 0、state-criticalな取得が不完全な場合は`state: null`とexit 2を返します。production commandはGitHubへwriteしません。

実GitHub acceptanceの手順とEvidenceの限界は[acceptance/README.md](acceptance/README.md)に分離しています。
