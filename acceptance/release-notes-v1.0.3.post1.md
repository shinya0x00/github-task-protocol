# GitHub Task Protocol 1.0.3.post1 release notes

この文書は、GTP 1.xの公開metadataだけを訂正する最終release `1.0.3.post1`の境界を記録する。基点はtag `v1.0.3`のexact commit `70fab3aacf8637bc1255459afb5efec7a5cf48ee`である。

## 変更するもの

- packageとruntimeのversion identityをPEP 440 post-release `1.0.3.post1`へ合わせる。
- PyPIに表示されるREADMEをlegacy landing pageへ変え、GTP 2.xと1.xの導線を分ける。
- current DESIGNとADR-037、このrelease note、explicit source manifest、release-surface test、CIのartifact名とlegacy branch triggerを新releaseへ合わせる。

`gtp --version`のversion表示を除き、`GTP.md`、Record、state、halt reason、`status`／`check`の意味と出力、GitHubへのread-only access、exit codeを含むprotocol／runtime behaviorは変更しない。`src/gtp/__init__.py`のversion文字列を除き、`src/gtp/`は`v1.0.3`と同一である。既存の`acceptance/release-notes-v1.0.3.md`と公開済み1.x artifactも変更しない。

## この文書とartifactが保証しないこと

このsourceとCI artifactは、tag作成、GitHub Release公開、PyPI upload、公開先からの再download、hash一致、PyPI archiveの完了をClaimしない。security、correctness、Evidence内容の真実性、GTP 2.xとの互換性も保証しない。公開後の検証は別の公開記録で示す。

## 公開時の境界

`v1.0.3.post1`のGitHub Releaseは1.x metadata訂正版として扱い、GitHubの`latest`は2.xのまま維持する。CI workflowはGitHub Releaseの作成や`latest`変更を行わない。PyPIへ同一artifactを公開して再downloadとhashを確認した後、projectをarchiveする予定である。archive前後とも既存1.x fileを削除、上書き、yankしない。
