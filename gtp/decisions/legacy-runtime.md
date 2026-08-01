## 未決定事項

公開済み1.xとPython runtimeを、2.0のmainへ複製または隔離して残すか、公開tagへ固定してmainから除くか。

## 採用した手段

公開済み1.xの既存tag target、GitHub Release asset、PyPI fileは削除、移動、上書き、yankせず、exact versionから取得できる状態で残す。誤導する説明metadataは、既存artifactのidentityを変えずに訂正できる。

公開済み`1.0.3`のprotocol semanticsとversion identity以外のCLI behaviorを変えず、package version、人向け説明、release検証だけを訂正する最終[PEP 440 post-release](https://packaging.python.org/en/latest/specifications/version-specifiers/#post-releases) `1.0.3.post1`を一度だけ公開する。公開後にartifactの一致、clean install、version表示を検証してから[PyPI projectをarchive](https://blog.pypi.org/posts/2025-01-30-archival/)する。2.0はPyPIから配布せず、GitHubのlatest Releaseは2.xのまま維持する。

`1.0.3.post1`のsourceと公開後Evidenceは`legacy/1.x` branchへversion管理し、PyPI archiveとEvidence記録の完了後はこのbranchを凍結する。作業branchは削除する。

mainには案内だけを置き、2.0から参照されないPython runtime、package、test、acceptance、CIはmainから除く。

## 変更履歴

- [PR #152](https://github.com/shinya0x00/github-task-protocol/pull/152)で、すべての1.x公開物を変更せず残す方針から、既存artifactを保持しつつ誤導するmetadataを最終post-releaseで訂正し、PyPIをarchiveする方針へ変更。
