# ADR-037: 最終1.x公開候補をlegacy branchへ束縛する

- Status: Accepted
- Date: 2026-08-01
- Supersedes: ADR-036のmain push、candidate artifact identity、publication handoff
- Superseded by: None

## 背景

公開済み`v1.0.3`のsourceと配布artifactはGTP 1.xである。repositoryの`main`はGTP 2.xへ移行し、1.xのPython runtime、package、test、acceptance、CIを持たない。PR #152は、既存1.x artifactを変更せず、最終PEP 440 post-release `1.0.3.post1`で誤導する公開metadataを訂正し、そのsourceと公開後Evidenceを`legacy/1.x`へ残す方針を採用した。

ADR-036は1.0.3公開時点の構成として、squash merge後の`main` push artifactだけを公開候補にした。この再現build、checksum、producer／consumer分離は引き続き必要だが、1.xを`main`へ戻さず最終post-releaseを作るには、公開候補のbranchとartifact identityだけを変更する必要がある。

## 決定

- GTP 1.x legacy sourceのcurrent canonical branchを`legacy/1.x`とする。
- pull requestでは`github.event.pull_request.head.sha`、`legacy/1.x` pushでは`github.sha`を唯一の`SOURCE_SHA`とする。
- PR artifactは検証専用の`v1.0.3.post1-pr-verification-<SOURCE_SHA>`とする。
- `legacy/1.x`へのsquash merge後に生成される`v1.0.3.post1-legacy-candidate-<SOURCE_SHA>`だけを公開候補とする。
- ADR-036のclean export、`SOURCE_DATE_EPOCH`、byte一致、`SHA256SUMS`、`BUILD-INFO`、Python 3.11 producer、Python 3.11／3.12／3.13 consumer、Twine check、90日保持を変更しない。
- workflowは`contents: read`だけを使い、tag、GitHub Release、PyPI uploadを行わない。公開操作はcandidate artifactを再検査した後に手動で行い、GitHubのlatest Releaseを2.xのまま維持する。
- 公開後Evidenceは`legacy/1.x`へversion管理し、PyPI archiveとEvidence記録の完了後にbranchを凍結する。

## 不採用案

- 1.x sourceを`main`へ戻して従来のmain candidateを作る案は、2.xと1.xのsource境界を再び混在させるため採用しない。
- PR artifactをそのまま公開する案は、human mergeで受理されたsource commitではなくPR headへ束縛されるため採用しない。
- `legacy/1.x` pushへ移しても`v1.0.3-main-candidate-<SOURCE_SHA>`という名前を残す案は、実際のbranchとartifact identityが食い違うため採用しない。
- GitHub ReleaseまたはPyPI uploadをworkflowへ追加する案は、CI成功と公開authorityを混同するため採用しない。

## 結果と限界

- clean readerはcurrent design、workflow、artifact名から、最終1.x公開候補を一意の`legacy/1.x` push commitへ結び付けられる。
- `main`のGTP 2.x sourceとGitHub latest Releaseを変更せず、1.xの最終metadata訂正を別branchで保持できる。
- PR artifact、Check Run、candidate artifactはpublication、credential安全性、merge authority、コード品質全体を証明しない。
- merge後のrun、artifact ID、hash、GitHub Release、PyPI upload、再download、archiveは、実際に観測するまで完了をClaimしない。
