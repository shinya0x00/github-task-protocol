# GitHub Task Protocol 1.0.2

## 何を修正したか

PyPIへそのままuploadできるよう、source distribution（sdist）のfilenameをPython packaging標準に従う`github_task_protocol-1.0.2.tar.gz`へ修正しました。

あわせて、1.0.1公開前の計画と公開後のEvidenceの関係、およびCLIを任意validatorとして公開する方針をrepository内の記録から追えるようにしました。

## 利用方法

GTPを使うためにCLIのinstallは必須ではありません。任意の参照validatorとして使う場合は、次のようにversionを固定できます。

```text
uvx --from github-task-protocol==1.0.2 gtp status <issue-url>
uvx --from github-task-protocol==1.0.2 gtp check <comment.md>
```

## 互換性

- Record内の`"gtp": "1.0"`は維持します。
- `GTP.md`の意味、Record、state、halt選択、terminal成立時刻は変更しません。
- `done`／`stopped`の表示は変更しません。
- sdist内部のroot directoryは`github-task-protocol-1.0.2`のままです。

## 公開前後の確認

公開candidateでは、Python 3.11〜3.13のtest、sdist／wheel build、Twine check、clean installを確認します。公開後は同じartifactを再downloadしてhashを照合し、public PyPIからのclean installとCLI smokeを別のEvidence recordに残します。

## GTPが証明しないこと

GTPはactor本人性、credential安全性、コード品質そのもの、Evidence内容の真実性を証明しません。サンドボックス、最小権限、不可逆操作前の確認、reviewと組み合わせてください。
