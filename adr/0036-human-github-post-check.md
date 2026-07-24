# ADR-036: 人向けGitHub投稿を明示targetのoffline checkへ追加する

- Status: Accepted
- Date: 2026-07-24
- Supersedes: ADR-006のCarrier-only target制限、ADR-007の日本語判定を設けない判断のうち人向けtargetの先頭日本語count
- Superseded by: None

## 背景

`gtp check <comment.md>`は、GTP Recordを入れたIssue commentのExact Marker、Markdown構造、strict JSON、closed schema、UUID、SHA、scope、URLなどを投稿前にoffline検査していた。一方、Issue本文、PR本文、通常commentは対象ではなく、人間が読む投稿に必要な結論と判断材料が欠けていても検査されなかった。

PR #117の本文は、英語と内部用語から始まり、結論と技術的な検証情報を同じ本文へ混在させた。従来の`gtp check`にこの本文を検査するtargetがなかったため、投稿前検査を一度も通っていない。これはvalidatorが受理した結果ではなく、Carrierだけを対象にした設計境界の漏れである。

完全な理解度、記述内容の真実性、必要な判断が本当に十分かは機械だけでは証明できない。しかし、今回のように必要な見出しがない、説明よりSHAやcommandが先にある、第一の説明が英語中心である、未説明の内部用語がある、結論と技術情報が混在する入力は、決定的な構造・文字検査で投稿前に拒否できる。

## 決定

### commandとtarget

公開commandは引き続き`check`と`status`の2つだけとする。新しいcommandやGitHubへのwrite pathは追加しない。

`check`の公開構文を`gtp check --target record|issue|pr|comment <file>`とする。`--target`省略は`--target record`と同じであり、従来のCarrier classifierとRecord schema validatorをそのまま使う。`issue`、`pr`、`comment`だけを人向けGitHub投稿targetとする。

targetを入力内容から自動推測しない。これにより、marker typoを人向け投稿と誤認して通す経路を作らず、live `status` readerとRecord検査は同じclassifier／schemaを使い続ける。

### 人向け投稿の構造

人向けtargetは、最初の非空行から次の4つのH2 headingをexactに、この順序で、各1回だけ持つ。各section本文は空であってはならない。追加H2 headingは許すが、この4つの代用にもtechnical signalの配置許可にもならない。

HTML commentおよびCommonMark raw HTML block内の文字列は可視Markdown構造・proseとして数えず、backtick／tilde fence内のliteral H2はheadingとして数えない。fence openerはCommonMarkのindent・info string・container境界に従う。これらを除外した可視Markdownをsection非空、先頭言語、内部用語検査へ使う。

1. `## 何が起きたか`
2. `## 何が変わるか`
3. `## 何は変わらないか`
4. `## 人間が次に判断すること`

最初のsection本文では、日本語文字を`[\u3040-\u30ff\u3400-\u9fff々〆ヵヶ]`、Latin letterを`[A-Za-z]`として数える。日本語文字は1文字以上かつLatin letter数以上でなければならない。これは先頭説明が日本語中心であることの下限であり、本文全体の言語、自然さ、理解度を判定するものではない。

最初のsection本文で説明なしに現れる内部用語を固定辞書で拒否する。辞書はcase-sensitiveな`GTP Record`、`Carrier`、`Exact Marker`、`strict JSON`、`closed schema`、`Done Condition`、`Done Claim`、`Contract`、`Start`、`Done`、`Stop`、`Evidence`、`Record`、`Records`、`scope`、`binding`、`head_sha`、`schema_valid`、`halt`、`halt_reason`、`terminal_violation`、`invalid_record`、`invalid_binding`、`stale_evidence`、`Acquisition Error`とする。最長一致で走査し、section内で各termの最初の出現直後、またはinline codeのtermを閉じる1個のbacktick直後に、spaceを挟まず全角括弧内へ1文字以上の日本語説明を置く。同じtermの2回目以降は説明を繰り返さなくてよい。辞書をruntimeやrepository内容から増減しない。

最初のsectionの先頭prose lineは、Markdownのquote／list prefixと、その直後のoptionalなGFM task marker `[ ]`／`[x]`／`[X]`を除いた後、`$ `または`% `のshell prompt、optional backtick付きの既知command、7〜40桁hex SHAから始まってはならない。既知commandはcase-sensitiveな`git`、`gh`、`gtp`、`python`、`python3`、`pytest`、`unittest`、`uv`、`uvx`、`pip`、`npm`、`pnpm`、`yarn`、`node`、`cargo`、`go`、`make`、`curl`、`wget`、`docker`、`kubectl`に固定する。

### 技術情報の分離

4つの必須sectionの後にだけ、optionalなexact H2 `## 技術的な検証情報`を1回置ける。backtick／tilde code fence、lowercase／uppercaseを問わないfull 40桁hex SHA、`$ `／`% ` promptまたは既知commandから始まるline、case-insensitiveな`stdout`、`stderr`、`exit code`、`検証結果`、`実行結果`の直後にspaceを任意数置いた`:`／`：` label、`https://github.com/OWNER/REPO/runs/N`、`https://github.com/OWNER/REPO/blob/<40桁hex>/PATH` permalinkはtechnical signalである。technical signalはこのoptional section内だけに置ける。

### machine outputとexit code

人向けtargetのmachine JSONは`gtp: "1.0"`、`command: "check"`、明示target、`valid`、`errors`、`authority: "none"`、`contextual_checks: "not_run"`を返す。`valid`は読取成功時にboolean、input error時に`null`とする。validならexit `0`、不適合なら`1`、fileをUTF-8 Markdownとして読めない等のinput errorなら`2`とする。

この検査はlocal fileだけを読むoffline lintである。GitHubへ接続せず、投稿、Issue／PR state、URLの存在、説明の事実性、人間の理解、判断の妥当性を検査しない。`valid`とexit codeは投稿、変更、完了、review、mergeのauthorityを与えない。

人向けtargetを採用するproducerは投稿直前に該当targetを実行し、exit `0`の場合だけ投稿する。checker自身はGitHub writeを実行またはinterceptせず、直接clientによる未検査投稿を検出しないため、このgateは各producerの責任で接続する。

### 互換性境界

- `--target record`とtarget省略時のCarrier認識、strict JSON、closed Record schema、machine projectionを変更しない。
- `status`のlive reader、GitHub取得、contextual validation、4 Record、6 state、7 halt reason、Evidence、native merge、Acquisition Errorを変更しない。
- Record Carrierの人向け要約が日本語か、平易かは引き続きmachine検査しない。ADR-002とADR-007のRecord scalar境界を維持する。
- runtime dependencyは0、production Pythonは2500行以内を維持する。

## 理由

明示targetにすれば、同じMarkdownを内容から推測してRecordまたは通常commentへ振り分ける必要がない。Recordのmarker typoを通常commentとして受理する抜け道を作らず、投稿者が何を投稿するかを検査時に固定できる。

4つのsectionは「事実」「変更」「非変更」「次の人間判断」を分離する最小構造である。第一sectionの文字count、固定辞書の初出説明、先頭proseとtechnical signalの配置は、意味推論なしで再現できる。完全な日本語品質や理解をclaimせず、機械が確実に拒否できる下限だけを公開契約にする。

offlineと`contextual_checks: "not_run"`を維持すれば、credential、network、GitHub snapshotなしで投稿前に決定的に実行できる。GitHub上の状態判定は引き続き`status`が所有する。

## 検討した代替案

### 内容からtargetを自動判定する

不採用。Exact Markerのtypoを人向けcommentとして通す可能性があり、Record classifierと人向けvalidatorのauthority boundaryが曖昧になる。

### 人間向け投稿をLLM reviewだけにする

不採用。結果が非決定的で、offline conformanceとして同じinputから同じ判定を再現できない。理解度の最終判断には人間を残し、構造と言語の下限だけをmachine lintにする。

### 技術情報を各必須sectionへ許可する

不採用。何が起きたかという人向け結論と、SHA、command、実行結果のどちらを先に読めばよいかを再び混在させる。

### Recordの人向け要約にも日本語countを適用する

不採用。Issue #118の対象はIssue本文、PR本文、通常commentであり、Carrier compatibilityとlive readerの認識結果を変える必要がない。

## migrationとEvidence境界

この規則はvalidator導入後に、targetを明示して検査した投稿へ適用する。既存のIssue／PR本文を遡及的に「検査済み」とみなさない。

特にIssue #118本文は、このcheckerと4-section migrationより前に作成された入力である。その本文自体は問題と目的を記録するhistorical inputであり、validatorが受理したEvidenceではない。受け入れは、fixed source headでpositive／negative fixture、production CLI、machine JSON、exit codeを独立に実行し、期待結果との一致を記録して初めて確認する。

## 結果

- Issue本文、PR本文、通常commentも投稿前に決定的な最低要件を検査できる。
- 人が最初に読む結論と、任意の技術的な検証情報を構造上分離できる。
- Record default compatibility、live state reader、protocol vocabulary、offline/no-network境界を維持する。
- validator成功は構造と言語の下限だけを示し、事実性、理解、GitHub上の適合、投稿やmergeの許可を証明しない。
- pull requestのsource headにあるこのADRは正準候補であり、repository canonical sourceへの昇格はnative merge後にmain上のpathを再取得して確認する。
- 後続のmaterialな変更は新ADRからこのADRを`Supersedes`で参照する。判断本文は遡及編集しないが、supersession relationを解決可能にする`Status`と`Superseded by`の参照metadataは更新できる。
