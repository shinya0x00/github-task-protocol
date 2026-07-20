# GTP decisions

> 現在のprotocolの唯一の正本は[`GTP.md`](GTP.md)である。この文書は採否理由と設計履歴を所有し、Record作成やstate判断の追加仕様ではない。意味が衝突する場合は`GTP.md`を優先する。

## 現在の判断を読む順序

1. ADR-027: `GTP.md`を唯一の公開正本とし、4 Record・6 state・7 halt reasonへ限定した理由。
2. ADR-028: Exact Carrier、closed schema、pure reducerを中間不整合なく切り替えた理由。
3. ADR-029: GitHub live bindingをGET-onlyとし、Acquisition Errorをhaltから分離した理由。

ADR-001〜ADR-026は設計履歴として残す。現行`GTP.md`と矛盾する旧語彙や修復機構を、現在の公開仕様として使用しない。

## ADR-001: GTPを権限の根拠にしない

- Status: Accepted
- Date: 2026-07-19

### 背景

GTPはGitHub上のrecordと観測事実から、タスクの現在地を説明する。一方、v1.0はactorの本人性、credential、組織上の権限を検証しない。そのため、recordの投稿だけで変更やmergeの権限が生まれると定義しても、その権限の正当性をGTP自身では証明できない。

### 決定

GTPのrecord、tool出力、GitHub上の観測事実は、変更、完了宣言、mergeの権限を一切与えない。

GTPは、外部から既に与えられた権限下の作業を制約し、現在地を説明するだけである。`contract`と`start`も許可証ではなく、タスク境界と開始事実の主張として扱う。

### 結果

- GTPはactor識別やcredential管理を実装しない。
- toolの状態、exit code、next actionを操作権限として解釈しない。
- 実行主体は、変更前にGTPの外部で権限が与えられていることを確認する。
- GTPは外部権限の存在や妥当性を証明したとは主張しない。

## ADR-002: exact markerでcarrierを識別する

- Status: Accepted
- Date: 2026-07-19

### 背景

Issue commentには説明用のJSON、引用、通常の会話が混在する。JSON fenceだけを手掛かりにすると、GTP recordではないcommentを誤認する可能性がある。一方、曖昧一致を導入するとclassifierの判定規則が増え、引用や入力ミスをrecordとして拾う危険が残る。

### 決定

GTP carrierは、次をすべて満たすIssue commentとする。

1. 最初の非空行は、前後whitespaceのない、空でない1行の人向け要約である。
2. 次の非空行は、列0から正確に `<!-- gtp-record:v1 -->` である。
3. markerの後に、opening lineが列0から正確に ```` ```json ````、closing lineが列0から正確に ```` ``` ````であるJSON fenceが1個だけある。
4. JSON fenceの内容は単一のGTP record objectである。
5. 要約、marker、fenceの間とcomment末尾には空白行だけを許可し、それ以外のproseやwrapperを許可しない。

大文字`JSON`、tilde fence、4個以上のbacktick、追加info string、fence lineの行末空白、`<details>` wrapperは拒否する。要約が日本語か、平易かはmachine検査しない。要約はLogical Record identityへ含めない。

markerがないcomment内のJSONは、通常のcommentとして無視する。exact markerがあるのにcarrierまたはJSONが壊れている場合は、`invalid_record`として当該comment URLを示して停止する。

`gtp status`と`gtp check`は、同じcarrier classifierを使用する。

```text
gtp status <issue-url>   # GitHub APIから取得したraw commentを検査
gtp check <comment.md>   # 投稿予定のcomment全文を検査
```

`gtp check`はJSON断片ではなく、実際に投稿するMarkdown comment全文を入力とする。

### 最低限の受け入れケース

| 入力 | 結果 |
|---|---|
| exact marker + valid JSON | recordとして受理 |
| markerなしのJSON | 通常のcommentとして無視 |
| marker typo | 投稿前の`gtp check`で拒否 |
| exact marker + malformed JSON | `invalid_record`としてcomment URLを表示 |

### 結果

- 普通のcommentとGTP recordを、raw Markdownから決定的に区別できる。
- 新しいstate、record type、commandは増えない。
- Level 0でtoolを使わずmarkerを打ち間違えたcommentは、live readerから認識されない。
- live readerはmarker typoを推測で補正しない。この見落としは、通常commentの誤認を防ぐための明示的なtrade-offである。

### 参考

- [GitHub Flavored Markdown: HTML comment](https://github.github.com/gfm/#html-comment)
- [GitHub REST API: Issue comments](https://docs.github.com/en/rest/issues/comments)

## ADR-003: `supersedes`を常時配列にする

- Status: Accepted
- Date: 2026-07-19

### 背景

同じ`type`の有効な葉が複数あると、状態は`conflicting_records`になる。`supersedes`が単一URLの場合、新しいrecordが一方を置換しても、置換されなかった葉と新しいrecordが残る。そのため、一般的な競合を1本の有効な葉へ戻せない。

exact marker付きで壊れ、`type`を判定できないcarrierも考慮する必要がある。このcarrierを後続recordから置換できない場合、`invalid_record`が永久に修復不能になる。

### 決定

`supersedes`の正準形は、常にcomment URLの配列とする。新規recordは空配列を使用する。

```json
"supersedes": []
```

有効な参照は、次をすべて満たす。

- 参照元と同じIssueにある。
- 参照元commentより前にGitHubへ投稿されている。
- 参照先が有効recordなら、参照元と同じ`type`である。
- 配列内のURLは重複しない。
- 1件のrecordから複数の過去commentを参照できる。

自己参照、未来参照、別Issue参照、重複URL、有効recordへのcross-type参照は`invalid_record`とする。

順序判定にはrecord内の`created_at`などの自己申告値を使わない。GitHub commentのserver orderを使用する。

exact marker付きだが壊れており、`type`を判定できないcarrierには回復用例外を設ける。後続の有効recordは、その壊れたcarrierのcomment URLを`supersedes`へ指定できる。置換された壊れたcarrierは、以後の`invalid_record`原因から外れる。

### 競合のjoin

有効な同型record AとBが競合している場合、後続のCは両方を列挙して競合を解消できる。

```json
"supersedes": [
  "https://github.com/.../issuecomment-A",
  "https://github.com/.../issuecomment-B"
]
```

### 結果

- `conflicting_records`と、type不明の壊れたcarrierから回復できる。
- 参照先を過去commentだけに限定するため、cycleは構造的に作れない。
- cycle専用のstate、reason code、検査機構は追加しない。
- record内の自己申告時刻は、順序やsupersessionの正当性を決めない。

## ADR-004: read-side convergenceで安全なretryを扱う

- Status: Accepted
- Date: 2026-07-19

### 背景

Issue comment投稿の応答が途切れると、producerは投稿が成功したか判断できず、同じrecordを再投稿する可能性がある。GitHub Issue Comment作成APIには、公開仕様上、commentの`body`とは別のidempotency keyがない。同じ意味のretryを別recordとして扱うと、安全な再送が`conflicting_records`を発生させる。

一方、同じ`id`で異なる内容が投稿された場合はretryとみなせない。さらに、そのcollisionに異なる`type`が含まれると、通常のcross-type supersession禁止だけでは回復不能になる。

### 決定

同じ`id`かつ同じparsed JSONを持つcomment群は、1つの論理recordへ畳む。comment URL群は、その論理recordのaliasとしてcomment一覧から毎回導出する。alias台帳や保存フィールドは追加しない。

#### parsed JSON一致

一致は、JSON文字列ではなく、検証済みJSON値の構造的一致で判定する。

- objectのキー順、空白、carrier外側の平易な要約は無視する。
- 配列順、文字列、大小文字、JSON型、値の差は保持する。
- duplicate keyを含むJSONは、比較前に`invalid_record`とする。

#### aliasとsupersession

- aliasの1つがsupersedeされたら、論理record全体をsupersedeされた扱いにする。
- 論理recordがsupersedeされた後に同一内容のretry commentが現れても、その論理recordは復活しない。
- aliasは観測したcomment集合から決定的に再導出する。

#### identity collision

同じ`id`でparsed JSONが異なる場合は、identity collisionとして`invalid_record`にする。

回復のため、次の狭い例外を設ける。

> 新しい`id`のrecordは、検出済みsame-id collisionを修復する場合に限り、そのcollisionに属する全comment URLを`type`にかかわらずsupersedeできる。

この例外は、collisionに属する全comment URLを列挙した場合だけ成立する。一部だけの置換、collisionではない通常recordへのcross-type参照、同じ`id`を再利用した修復は認めない。

### 結果

- 同一内容のretryは競合を発生させない。
- 異内容のsame-id collisionはfail-closedで検出され、後続の新しい`id`から回復できる。
- 新しいstate、record type、永続的なalias台帳は追加しない。
- groupingとsupersessionは、毎回取得したGitHub comment集合から再計算できる。

### 参考

- [GitHub REST API: Create an issue comment](https://docs.github.com/en/rest/issues/comments?apiVersion=2022-11-28#create-an-issue-comment)

## ADR-005: core recordとGitHub observationを分離する

- Status: Accepted
- Date: 2026-07-19

### 背景

Draftのcore envelopeには、自己申告の`author`と`created_at`が含まれていた。しかし、GTPはactorの本人性を証明せず、recordの順序にはGitHub commentのserver orderを使う。GitHub metadataと同じ情報をrecordへ重複して持つと、不一致規則が必要になり、retry時に時刻だけが変化してidentity collisionになる危険もある。

### 決定

core envelopeを次へ限定する。

```json
{
  "gtp": "1.0",
  "type": "contract | start | done | stop",
  "id": "<UUID小文字>",
  "supersedes": []
}
```

`author`と`created_at`はcore recordから削除する。type固有payloadは、この共通envelopeへ追加する。

GitHubから取得したmetadataは、commentへ書き込むrecord fieldではなく、machine出力へ付加する導出情報として扱う。

```json
{
  "record": {
    "gtp": "1.0",
    "type": "contract",
    "id": "01234567-89ab-cdef-0123-456789abcdef",
    "supersedes": []
  },
  "observation": {
    "comment_url": "...",
    "comment_id": 123,
    "github_login": "...",
    "created_at": "..."
  }
}
```

GitHub metadataを観測情報の唯一のownerとし、論理recordの同一性比較には含めない。`github_login`は投稿に使われたGitHub accountを表すだけで、人間の本人性、runtime、実行権限を証明しない。

### `gtp check`の検査境界

GitHub metadataなしで検査できるのは、次に限定する。

- JSON構文とduplicate key
- core envelope schema
- UUIDの表記
- record typeごとの必須field
- `supersedes`がURL配列であること

別Issue参照、未来参照、server order、参照先`type`、comment URLの存在などはIssue文脈が必要であり、offlineでは判定できない。offline結果を「完全にvalid」と表示せず、`schema_valid`とcontextual checks未実施を区別する。この区別はCLIの検査結果であり、GTPのstateではない。

### 結果

- record本体は純粋なプロトコル情報だけを持つ。
- 自己申告値とGitHub metadataの不一致規則を作らない。
- retry時にmetadata差分でidentity collisionが発生しない。
- actor本人性と権限判定は、引き続きGTPの対象外である。

## ADR-006: `gtp check`をoffline schema検査に限定する

- Status: Accepted
- Date: 2026-07-19

### 背景

単一commentの形式検査と、GitHub Issue全体の文脈検査では必要な入力と失敗理由が異なる。両方を`gtp check`へ入れると、network、認証、Issue指定が必要になり、offlineで決定的に実行できる利点が失われる。一方、offline結果を「完全にvalid」と表示すると、参照先やserver orderまで確認済みだと誤解される。

### 決定

`gtp check <comment.md>`は、単一commentのoffline schema検査だけを行う。将来の`--issue` optionはv1.0へ追加しない。

検査対象は次に限定する。

- GTP carrierの認識と構造
- JSONの厳密なparse
- duplicate keyの拒否
- core envelopeのschemaと必須field
- `gtp`、`type`、UUID、`supersedes`の形式
- type固有payloadの形式

次は検査しない。

- 参照先commentの存在
- 参照元と参照先が同一Issueか
- 過去参照か
- type間のsupersession可否
- alias、競合、有効な葉
- GitHub author、comment URL、server order

通常comment、認識した有効carrier、認識した壊れたcarrierを、protocol stateとは別のCLI結果で区別する。

通常comment:

```json
{
  "recognized": false,
  "schema_valid": null,
  "contextual_checks": "not_run"
}
```

認識した有効carrier:

```json
{
  "recognized": true,
  "schema_valid": true,
  "contextual_checks": "not_run"
}
```

認識した壊れたcarrier:

```json
{
  "recognized": true,
  "schema_valid": false,
  "contextual_checks": "not_run",
  "errors": ["..."]
}
```

`gtp status`は別のschema validatorを実装しない。最初に`gtp check`と同じoffline validatorを使用し、その後だけGitHub Issue文脈の検査と状態導出を追加する。

### 結果

- schema規則の実装ownerは1つになる。
- `gtp check`はnetworkと認証に依存せず、決定的に実行できる。
- 未検査項目を成功扱いしない。
- `recognized`、`schema_valid`、`contextual_checks`はCLI検査結果であり、新しいprotocol stateではない。
- contextual preflightはv1へ含めない。

## ADR-007: GTP v1 core schemaを閉じる

- Status: Accepted
- Date: 2026-07-19

### 背景

未知fieldを保持して無視すると、field名のtypoを見逃す。さらに、未知fieldがlogical recordの構造比較へ入り込むと、安全なretryとidentity collisionの境界が不明確になる。GTP v1は外部JSON Schema libraryを使わず、依存ゼロで実装する制約もある。

### 決定

GTP v1 core schemaを閉じる。

- `gtp: "1.0"`の各`type`について、許可fieldと必須fieldを完全列挙する。
- GTPが所有するすべてのobject階層で未知fieldを拒否する。
- 未知の`gtp` versionと未知の`type`もschema不適合とする。
- schema検証を通過したrecordだけを、grouping、supersession、reducerへ渡す。
- `gtp check`と`gtp status`は同じoffline validatorを使用する。
- GitHub observationとCLI出力はcore recordではないため、core schemaの閉鎖範囲に含めない。
- GTP v1は外部運用向けの拡張field、専用marker、adapterを定義しない。
- 新fieldが必要になっても`gtp: "1.0"`を黙って拡張せず、version変更と互換性を判断する。

未知fieldは、例えば次のvalidator診断を返す。

```json
{
  "recognized": true,
  "schema_valid": false,
  "contextual_checks": "not_run",
  "errors": [
    {
      "code": "unknown_field",
      "path": "$.suprsedes"
    }
  ]
}
```

`unknown_field`はoffline validatorの診断codeであり、Issue全体のprotocol stateやhalt reasonではない。

### validator方針

外部JSON Schema libraryは追加しない。共有validatorが、各`type`の許可field集合、必須field集合、値の型と形式を直接照合する。

共有validatorは`gtp check`と`gtp status`の両方が使用する。schema-invalid recordをgrouping、supersession、reducerへ渡さない。schema拡張用の予約fieldや仮設物は定義しない。

### scalarとURLの正準形

- `id`は次のcanonical lowercase UUID v4とする。

  ```regex
  ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$
  ```

- `head_sha`は省略なしのlowercase 40桁hexとする。
- `goal`とDone Conditionの`text`は空でない文字列とし、前後whitespaceとcontrol characterを禁止する。
- Unicode normalization、日本語判定、protocol独自の文字数上限は設けない。
- v1のGitHub resource URLは`https://github.com`だけを受理し、GitHub Enterprise Serverは対象外とする。
- query、userinfo、独自portを全resourceで禁止する。
- fragmentは原則禁止する。Issue Comment URLだけ、正確な`#issuecomment-<decimal-id>`を必須とする。
- Issue、PR、Issue Comment、Check Run、blobごとにpath profileを固定する。
- liveな同一repository判定はURL文字列ではなく、GitHubから取得したrepository identityで行う。

ownerとrepositoryのsegmentは、空でないliteral segmentとする。`%`、`/`、`\\`、NULを禁止し、`.`と`..`も拒否する。GitHub固有の完全な名前文法は再実装しない。

resourceごとのpath profileは次とする。decimal IDは`[1-9][0-9]*`である。

```text
Issue:
https://github.com/{owner}/{repo}/issues/{issue-id}

PR:
https://github.com/{owner}/{repo}/pull/{pr-id}

Issue Comment:
https://github.com/{owner}/{repo}/issues/{issue-id}#issuecomment-{comment-id}

Check Run:
https://github.com/{owner}/{repo}/runs/{check-run-id}

Artifact:
https://github.com/{owner}/{repo}/blob/{lowercase-40-hex-sha}/{nonempty-path}
```

Artifact pathだけはpercent encodingを許可する。ただし、malformedな`%XX`、UTF-8として不正なdecoded bytes、encodedまたはliteralの`/`によるsegment変形、`\\`、NUL、decode後の`.`または`..` segmentを拒否する。pathは空でなく、queryとfragmentを持たない。

### 結果

- typoと未知versionをfail-closedで検出できる。
- idempotencyの構造比較へ、未定義fieldが入り込まない。
- 外部運用向けの拡張契約はv1 coreへ含めない。
- 各typeのpayloadを完全列挙するまで、schema実装は開始できない。

### 参考

- [JSON Schema: Objects](https://json-schema.org/understanding-json-schema/reference/object)

## ADR-008: unknownをprotocol modelへ入れない

- Status: Accepted
- Date: 2026-07-19

### 背景

自由文のunknownをrecordへ保存しても、reducerはその意味や重要性を決定的に判定できない。unknownがstateへ影響しないならfieldは冗長であり、影響させるなら`paused`などの新stateと解釈規則が必要になる。また、完了条件と無関係な将来的疑問は、GTPの完了判定対象ではない。

### 決定

- `contract.unknowns`と`done.unknowns`を削除する。
- `none_observed`を導入しない。
- unknown専用のrecord、field、stateを作らない。
- 契約確定前の質問は通常commentへ書き、解決するまで`contract`を投稿しない。
- 契約を変えない実装上の質問は通常commentへ書き、stateは`in_progress`のままにする。
- 完了条件の充足を確認できない場合は`done`を投稿しない。
- `paused` stateを追加しない。
- reducerは自由文と外部運用情報を解釈しない。

完了時の未確認事項とは、done conditionの成否に関係するものだけを指す。完了条件と無関係な将来的疑問はGTPの判定対象外である。

GTPは、外部運用向けのcompanion artifact、専用marker、adapterを定義しない。

### 結果

- GTPにはunknownを表す構造や待機stateが存在しない。
- 質問と議論はGitHubの通常commentへ残る。
- done conditionを確認できない作業は、完了として扱われない。
- 外部の開発管理機構なしでも、GTP仕様とGitHub commentだけで利用できる。

## ADR-009: scopeは狭い形式のtask境界とする

- Status: Accepted
- Date: 2026-07-19

### 背景

`contract.scope`をPR差分へ機械的に強制するには、glob、rename、submodule、生成物などの判定規則が必要になる。v1で不完全なscope checkerを提供すると、検証していない差分へ「範囲内」という誤った保証を与える危険がある。一方、agentの引き継ぎと人間の理解には、対象pathを狭い形式で示す価値がある。

### 決定

`scope`はrequiredの配列とし、1件以上のrepository-relative pathを含む。

```json
"scope": [
  "src/",
  "README.md"
]
```

形式規則は次とする。

- 配列は空にしない。
- 同じpathを重複させない。
- directoryは末尾`/`で表す。
- fileはrepository rootからの正確なpathで表す。
- `.`だけはrepository全体を表す。
- glob、絶対path、空文字、`..` path segmentを禁止する。
- `.`以外の`.` path segmentと、空のpath segmentを禁止する。

`scope`はtask境界の主張であり、変更権限を与えない。`gtp status`はPR diffがscope内であることを検査せず、遵守済みとも表示しない。

### 結果

- agentと人間は、contractから対象領域を読み取れる。
- scope grammarは小さく決定的になる。
- PR差分のscope遵守証明はv1の非目標となる。
- scope遵守の機械検査はv1へ含めない。

## ADR-010: done conditionsとevidenceをmapで対応付ける

- Status: Accepted
- Date: 2026-07-19

### 背景

配列形式ではcondition IDの一意性と`done.evidence`との対応付けを別規則で管理する必要がある。condition IDをobject keyにすれば、IDがcanonical ownerとなり、対応付け専用fieldと配列順への依存を除去できる。

### 決定

`contract.done_conditions`を、condition IDからcondition定義へのmapとする。

```json
"done_conditions": {
  "tests_pass": {
    "text": "すべてのテストが成功する",
    "evidence_kind": "check"
  }
}
```

`done.evidence`は、同じcondition IDからevidence URLへのmapとする。

```json
"evidence": {
  "tests_pass": "https://github.com/..."
}
```

condition IDは次の正規表現へ一致させる。

```regex
^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$
```

先頭・末尾の`_`、連続する`__`、大文字は認めない。

`done_conditions`の規則:

- requiredかつ空でないobjectである。
- 各conditionは`text`と`evidence_kind`だけを持つ。
- `text`は空でない文字列である。
- `evidence_kind`は許可されたkindの1つである。
- duplicate condition IDはduplicate JSON keyとして拒否する。

`done.evidence`の規則:

- requiredかつ空でないobjectである。
- keyはcondition IDと同じ形式に従う。
- 値はevidence参照の基本schemaに従う。
- `kind`を繰り返さない。kindのownerはcontract側だけである。

### 検査境界

offline validatorは、両mapの存在、空でないこと、key形式、duplicate key、nested field、値の基本schemaを検査する。

`gtp status`のcontextual validatorは、active contractの`done_conditions`と`done.evidence`のkey集合が完全一致することと、各参照がcontract側の`evidence_kind`へ適合することを検査する。不足、余分、key不一致はcontextualな`invalid_record`とする。

objectの記述順に意味を持たせない。人向け表示とmachine出力を生成するときだけ、condition IDをlexicographic順に並べる。

### 限界

key集合が一致し、URL形式とevidence kindが適合しても、done conditionの自然言語上の内容が本当に充足されたことまでは自動的に証明しない。GTPが主張できるのは、要求された種類のevidence参照が各conditionへ提示され、検証可能なGitHub factと整合している範囲までである。

### 結果

- condition IDの一意性と対応関係が構造で表現される。
- `evidence_kind`のownerがcontract側へ一本化される。
- 配列順と対応付け専用fieldが不要になる。
- 条件内容の意味評価をGTPが行ったという過剰な主張を避ける。

## ADR-011: evidence kindを`check`と`artifact`へ限定する

- Status: Accepted
- Date: 2026-07-19

### 背景

`human` evidenceが参照するcommentは、GitHub accountによる投稿が存在することしか証明しない。本人性、権限、判断能力、記述内容の真実性は証明できない。`approval`や`attestation`へ改名しても、この境界は変わらない。また、複数種類のGitHub check resourceを同じkindへ含めると、URL profileとAPI validatorが増える。

### 決定

GTP v1のevidence kindを、次の2種類だけに限定する。

```text
check | artifact
```

`human`、`approval`、`attestation`は定義しない。人間の権限判断と最終判断はGitHub nativeのreview・mergeへ残す。

#### `check`

`check`が参照できるresourceはGitHub Check Runだけとする。validatorは次を確認する。

- Check Runがbound PRと同じrepositoryに属する。
- `status == completed`である。
- `conclusion == success`である。
- `head_sha == done.head_sha`である。

GitHub Actions Workflow Runはv1の`check` profileへ含めない。

#### `artifact`

`artifact`は、bound PRと同じrepositoryにあるfileのimmutable blob permalinkとする。validatorは次を確認する。

- URLが`/blob/<full-sha>/<path>`形式である。
- URLのfull SHAが`done.head_sha`と一致する。
- fileがそのcommitに存在する。
- branch名、tag、`main`などを使った可変URLではない。

手動probeの結果をevidenceにする場合は、結果をrepository内のfileへ記録し、full-SHA permalinkを`artifact`として参照できる。

### evidenceが証明する範囲

`check`が証明するのは、指定SHAに対してGitHub Check Runが`success`を返したことまでである。check内容がdone conditionの自然言語上の意味を十分に検査したことまでは証明しない。

`artifact`が証明するのは、指定SHAに参照先fileが存在することまでである。fileの内容、記録されたprobeの実施方法、記述の真実性までは証明しない。

GTPが検証するのは、evidence参照の存在、固定性、repository、resource状態、SHA bindingである。

### 取得失敗との分離

- resourceを取得でき、repository、SHA、status、conclusion、URL profileが一致しなければevidence不適合とする。
- network、認証、rate limitなどでresourceを取得できなければ検査不能とする。record不正とは断定しない。
- 検査不能時は`done`を確認済みと表示せず、CLIの取得エラーとして報告する。
- 取得失敗のための新しいprotocol stateは追加しない。

### 結果

- evidence validatorは2種類の固定profileだけを持つ。
- commentを人間性や権限の証明として扱わない。
- evidenceの存在とdone conditionの真実性を混同しない。
- GitHubデータ取得不能とprotocol不適合を分離する。

## ADR-012: repair supersessionをinvalid groupの完全置換へ統合する

- Status: Accepted
- Date: 2026-07-19

### 背景

recognizedだがJSONまたはschemaが壊れたcarrierと、same-ID identity collisionは、どちらも通常のsame-type supersessionだけでは回復できない。個別の例外を増やす代わりに、readerが一時的なrepair groupを導出し、invalidな過去comment集合の完全置換として共通判定できる。

### repair groupの導出

readerは次の優先順位でgroupを導出する。

1. Edited Carrierはsingleton groupとする。
2. Intrinsic-validなsame-ID identity collisionは、collisionに属するcomment全体で1 groupとする。
3. Intrinsic-invalidなrecognized Carrierはsingleton groupとする。
4. Historical Contextual-invalidのうち、規定されたclosed reason-code setに属するcommentはsingleton groupとする。

1つのcommentを複数groupへ所属させない。Edited Carrierはidentity groupingへ入れず、collision memberはcontextual-invalid singletonへも入れない。repair group membershipをreaderの自由な「repairable」判断から導出してはならず、closed reason-code setだけをownerとする。

Historical Contextual-invalid singletonを作るclosed reason-code setは次の8個だけとする。

```text
invalid_supersession
incomplete_repair_group
start_contract_binding_failed
done_before_start
done_condition_keys_mismatch
done_evidence_kind_mismatch
stop_without_contract
successor_order_invalid
```

`successor_order_invalid`はself-reference、source Issue以前、Stopより後に作成された場合だけを含む。Successor Issueの後日の削除、移管、取得不能はLive ConformanceまたはAcquisition Errorであり、このcodeへ含めない。

post-start Contract、Started Once後のfresh-ID Start、Contract Freeze違反、terminal後の新Logical Record、terminal violationはrepair groupへ入れない。これらはhistoricalで単調なlifecycle factであり、後続supersessionによって消せない。

Live Conformance不適合もrepair groupへ入れない。terminal前のvalid DoneまたはStopがlive resourceと不適合になった場合は、通常のsame-type supersessionで新しいRecordへ置換できる。

repair groupはrecordへ保存するfieldやprotocol stateではなく、観測したcomment集合からreaderが一時的に導出する検査単位である。

### supersession判定

`supersedes`の各URLを次の順で判定する。

```text
URLがrepair groupに属する
  → repair recordよりserver order上で過去のgroup memberを完全列挙しているか
  → repair recordがfresh idを持つか
  → group内に限りtype不一致を許容

URLがrepair groupに属さない
  → 通常の過去・同一Issue・同一type規則
```

URLがrepair groupに属する場合、通常規則へfallbackできない。必ずrepair規則を満たす。これにより、schema-validかつ同型に見えるidentity collision memberだけを部分的にsupersedeすることを防ぐ。

完全列挙の対象は、repair recordよりserver order上で過去に存在するgroup memberとする。repair後に遅延retry commentが現れても、過去のrepairを遡ってinvalidにしない。同一内容の遅延retryは、既存のalias規則により、supersede済みの論理recordへ畳まれる。

複数groupを1件のrecordで修復する場合は、各groupについて独立に完全列挙する。

### 緩和する範囲

repair規則が緩和するのは、完全列挙したgroup内部の`type`一致条件だけである。repair record自体は、通常のschema、freshな`id`、過去参照、同一Issue、lifecycle、type固有payloadのすべてを満たす必要がある。repair supersessionを使って不正なstate transitionを正当化できない。

### 結果

- 壊れたCarrier、Edited Carrier、identity collision、closed setに属するHistorical Contextual-invalidを同じ判定で修復できる。
- repair groupの部分置換を禁止できる。
- 遅延retryにより過去のrepairが遡及的に無効にならない。
- repair専用field、record type、state、reason codeは追加しない。

## ADR-013: 最初のvalid startでcontractをfreezeする

- Status: Accepted
- Date: 2026-07-19

### 背景

作業開始後に同じIssue内でgoal、scope、done conditionsを変更できると、どのcontractに対して作業とevidenceを評価すべきかが曖昧になる。変更の大小をreducerが判断する規則も必要になる。Issueを分ける手間と引き換えに、開始時のcontractが途中で変わらない不変条件を採用する。

### 歴史的なfreeze判定

server orderでcommentを先頭から評価し、各comment投稿時点までのprefixに対してvalidだった`start`が1件でも存在すれば、`started_once`をtrueとする。

```text
started_once = 過去にprefix-validなstartが1件でも存在した
```

`started_once`はcomment履歴から導出する単調な事実であり、record fieldや永続stateではない。後から該当`start`がsupersedeされても、same-ID collisionへ巻き込まれても、falseへ戻らない。

### contract freeze

- `started_once == false`の間は、contractを通常のsupersessionで訂正できる。
- 最初のprefix-validな`start`以後、新しい`id`のcontractは、内容が同じでもfreeze違反になる。
- 同じ`id`かつ同じparsed JSONの再投稿だけは、API retry aliasとして扱う。
- 同じ`id`かつ異なるparsed JSONはidentity collisionである。
- scope縮小、condition追加、文言修正を含め、parsed JSONが変わるcontractは変更の大小を問わない。

post-start contractはactive contractにならず、pre-startに確定したcontractをsupersedeしない。active contractは最後のpre-start contractのまま保持し、Issueは`halt`になる。post-start contractを新しい仕様として解釈しない。後続supersessionでも歴史的なfreeze違反は消えない。

### contract変更が必要な場合

次の順序でsuccessor Issueへ移行する。

```text
successor Issueを先に作成
  → 旧Issueへ stop(reason="superseded", successor_ref="...")
  → successor Issueへ新しいcontract
  → successor Issueへ新しいstart
```

successor Issueを作成できなければ、旧Issueは`in_progress`のまま維持し、`successor_ref`のない`superseded` stopを残さない。

### freeze違反からのstop

contract freeze違反による`halt`中でも、schemaと通常のstop条件を満たす`stop`だけは受理できる。有効な`stop`後は`stopped`をterminal stateとして表示し、freeze違反commentは履歴上のdiagnosticとして残す。

この例外はfreeze違反を正当化せず、旧Issueを閉じてsuccessor chainを残すためだけに使う。

### 結果

- 作業開始時のcontractが途中で変わらない。
- 歴史的なstartを後から消してfreezeを解除できない。
- API retryとcontract改訂を明確に区別できる。
- freeze違反があっても、successor Issueへの正式な移行経路を失わない。

## ADR-014: startから`contract_ref`を削除する

- Status: Accepted
- Date: 2026-07-19

### 背景

contract freezeと、start投稿時点でactiveな論理contractが1件だけという条件があれば、`contract_ref`はreaderが導出できるfactの重複保存になる。明示URLを保存すると、stale URL、typo、別Issue参照、retry aliasのどれを選ぶかという追加規則が必要になる。

### start payload

`start`のtype固有payloadは`branch`だけとする。

```json
{
  "gtp": "1.0",
  "type": "start",
  "id": "01234567-89ab-cdef-0123-456789abcdef",
  "supersedes": [],
  "branch": "feature/example"
}
```

### contract binding

bindingは各`start`について、次の順序で決定する。

1. `start`より前のcommentだけをserver orderで評価する。
2. repair、supersession、alias groupingを適用する。
3. activeな論理`contract`を数える。
4. 正確に1件なら、その論理contractへbindingする。
5. 0件または複数なら、`start`をcontextual invalidとする。
6. bindingに成功した`start`だけがcontract freezeを発生させる。

comment URL数ではなく論理record数を数える。同じcontractに複数のretry aliasがあっても、active contractは1件である。

bindingは常にstart投稿時点のcomment prefixから導出する。後のcommentを使って過去のstartを別contractへrebindしない。post-start contractによってIssueが`halt`しても、元のbindingは変わらない。

bindingに失敗したStartはfreezeを発生させない。修正版Startはfreshな`id`を持ち、`supersedes`へ置換対象のinvalid Start URLを含める。activeなinvalid Startが複数ある場合は全active leafを列挙する。GitHub取得不能はbinding failureと断定しない。

一度prefix-valid Startが成立した後は、同じbranchと内容であってもfresh IDのStartによる改訂を認めない。同じID・同じparsed JSONの遅延retryだけをaliasとして扱う。branchを変更する場合はvalid StopとSuccessor Issueを使用する。

### machine output

binding結果をrecordへ保存せず、machine outputへ次の導出情報を含める。

```json
{
  "bound_contract": {
    "id": "contract-record-id",
    "url": "https://github.com/.../issuecomment-...",
    "aliases": [
      "https://github.com/.../issuecomment-..."
    ]
  }
}
```

`url`はserver order上で最初のaliasをcanonical表示にする。`aliases`は観測した全comment URLをserver orderで含める。

### 結果

- contract bindingのownerはreaderのprefix評価へ一本化される。
- stale URL、別Issue参照、alias選択の規則が不要になる。
- `gtp check`はGitHub文脈なしでstart schemaを検査できる。
- contract commentが削除された場合は内容を復元できないため、`contract_ref`を保存しても回復性は増えない。

## ADR-015: branchはshort nameの宣言とlive bindingに分ける

- Status: Accepted
- Date: 2026-07-19

### 背景

Git ref文法全体をoffline validatorへ再実装すると独自規則が増える。一方、branchは削除可能なmutable GitHub resourceであり、comment履歴から導出する`start`やcontract freezeとは寿命が異なる。

### offline schema

`start.branch`は次を満たす。

- requiredの空でない文字列である。
- 前後にwhitespaceがない。
- control characterを含まない。
- `refs/heads/`で始まらない。
- URL形式ではない。
- `/`を含むshort branch nameを許容する。

repository名らしい文字列かどうかや、Git ref文法全体はofflineで判定しない。

### live binding

`gtp status`はIssueと同じrepositoryでbranch名をexact matchし、次の規則を適用する。

- `in_progress`ではbranchの存在が必要である。
- valid `done`があってもbound PRが未mergeならbranchの存在が必要である。
- bound PRがmerge済みならbranch不在を許容する。
- `stopped`ではbranch不在を許容する。
- merge後のbranch削除で、過去のvalid `done`、prefix-validな`start`、`started_once`を取り消さない。

exact branchの存在を確認できればbinding適合、GitHubから不在を確認できればbinding不適合とする。network、認証、rate limitなどで判定できなければ取得不能とし、record不正とは断定しない。

branch存在はmutableなlive observationであり、`start` recordのschema validityとcontract freezeから分離する。branchが一時的に消えても、過去のvalid startは消えない。

### 結果

- offline validatorは独自のGit ref文法を持たない。
- native merge前のbranch消失を検出できる。
- merge後の自動branch削除を正常に扱える。
- immutableなcomment履歴とmutableなbranch factを混同しない。

## ADR-016: Bound PRは`done.pr_ref`で明示する

- Status: Accepted
- Date: 2026-07-19

### 背景

Contractは同じIssue内のimmutableなcomment prefixから一意に導出できる。一方、PRはbranch名で検索するmutableな外部resourceである。branch名は削除後に再利用できるため、`start.branch`だけからPR identityを永続的に導出すると、後年の同名branchと新しいPRによって過去Issueのbindingが変わり得る。

### 決定

`done.pr_ref`を維持し、特定のPR identityを選ぶdurable bindingとする。

```json
{
  "gtp": "1.0",
  "type": "done",
  "id": "01234567-89ab-cdef-0123-456789abcdef",
  "supersedes": [],
  "pr_ref": "https://github.com/owner/repo/pull/123",
  "head_sha": "...",
  "evidence": {}
}
```

`gtp status`はvalid `done.pr_ref`について次を検査する。

- PRのbase repositoryがIssue repositoryと一致する。
- PRのhead repositoryがIssue repositoryと一致する。
- PRの`head.ref`が`start.branch`と一致する。
- `done.head_sha`がPRの対象head SHAと一致する。
- fork PRではない。

valid `done.pr_ref`でbindingした後は、そのPRをBound PRとする。後から同名branchが再利用され、新しいPRが作られても、過去IssueのBound PRを変更しない。

### done前のPR候補

`done`前は、`start.branch`からPR候補をtentativeなObservationとして導出する。この候補はBound PRではない。

候補は次をすべて満たすPRだけとする。

- base repositoryがIssue repositoryである。
- head repositoryもIssue repositoryである。
- `head.ref == start.branch`である。
- fork PRではない。

検索対象はopen、closed-unmerged、mergedの全履歴とする。候補0件は正常であり、候補が正確に1件ならidentityは一意である。closed-unmergedが1件だけでも、それだけでは`halt`にしない。branchが存在しなければLive Branch Binding mismatchは別に評価する。PR Candidateのmachine表示shapeはprotocol coreに含めない。

```text
done前:
  branch → PR候補（導出・tentative）

done時:
  pr_ref → Bound PR（明示・durable）
```

active Doneがない状態で同じbranchをheadとするsame-repository PR Candidateが複数存在すれば`halt`とする。ただし、halt中にvalid `done.pr_ref`がrepository、branch、head SHAへ適合する1件を明示した場合、そのPRをBound PRとしてambiguityを解消できる。Doneは権限や品質を決めず、PR identityだけを選択する。valid Stopによる終了も許可する。

`merge_without_done`をLate Doneで解消する場合、`pr_ref`は実際にmergeされたPRを指さなければならない。無関係な未merge候補を選んでも、過去のmerge異常は解消しない。

Bound PR確定後は、将来のbranch再利用による候補増加を過去Issueの競合として扱わない。

### 結果

- branch labelの再利用で過去のPR bindingが変わらない。
- PR作成時刻とdone投稿時刻の比較や、branch名の永久再利用禁止が不要になる。
- `pr_ref`は重複情報ではなく、mutableな候補からstableなPR identityを選ぶfieldとなる。
- fork PRはv1の対象外となる。

## ADR-017: PR head変更時はstale doneとしてfail-closedにする

- Status: Accepted
- Date: 2026-07-19

### 背景

`done`は`head_sha`で示した特定のsource commitに対する完了主張である。valid `done`の投稿後、merge前にBound PRへcommitが追加されると、既存evidenceは新しいheadを検証していない。一方、古い`done`はschema-validであり、投稿時点では主張が成立していた可能性があるため、record自体を`invalid_record`へ変更してはならない。

### 決定

active `done`の`head_sha`とBound PRの現在のsource head SHAが異なる場合、record validityではなくLive Conformance mismatchとしてIssueを`halt`にする。正準tokenは`done_head_sha_mismatch`だけとし、`stale_done`、`stale_evidence`、`head_sha_mismatch`を別tokenとして使用しない。新しいprotocol stateは追加しない。

```json
{
  "state": "halt",
  "active_done_head_sha": "old-sha",
  "bound_pr_head_sha": "new-sha"
}
```

この`halt`中は、修正版`done`またはvalid `stop`を受理できる。

修正版`done`は次をすべて満たす。

- freshな`id`を持つ。
- 古いactive `done`を`supersedes`で置換する。
- conflictingなactive `done`が複数ある場合は、すべてのactive leafを列挙する。
- Bound PRの現在のsource head SHAを完全な`head_sha`として持つ。
- active Contractの全Done Conditionについて、新しいSHAへbindingされたevidenceを完全に再提示する。
- 古い`done`のevidenceを暗黙に継承しない。

bindingが再び一致した場合だけ、Issueは完了へ復帰できる。

### merge時のSHA

`done.head_sha`と比較するのは、PRからmerge対象になったsource head SHAである。merge後にbase branchへ作られたmerge commit、squash commit、rebase後のcommitのSHAとは比較しない。

Bound PRがmergeされた後は、そのPRについて記録されたsource head SHAを評価する。将来の同名branch再利用や別PRは、確定済みBound PRと過去の`done`へ影響しない。

### 結果

- evidence取得後に追加されたcodeを未検証のまま完了扱いしない。
- 過去に成立し得た`done`のrecord validityを遡及的に壊さない。
- 回復に新しいstate、record type、evidence継承規則を必要としない。

## ADR-018: Stopのsuccessorは同一repositoryの未来のIssueへ限定する

- Status: Accepted
- Date: 2026-07-19

### 背景

`stop`はtaskを中止するだけでなく、`superseded`の場合には後継Issueを明示する。参照先のrepositoryと作成順を制限しなければ、別repositoryへの不安定な移管や、Issue AからB、BからAというsuccessor cycleを作れる。

### 決定

`stop`のtype固有payloadは`reason`と`successor_ref`だけを持ち、`successor_ref`は常にrequiredとする。

```json
{
  "gtp": "1.0",
  "type": "stop",
  "id": "01234567-89ab-cdef-0123-456789abcdef",
  "supersedes": [],
  "reason": "abandoned",
  "successor_ref": null
}
```

fieldの組合せは次に限定する。

- `reason == "abandoned"`なら`successor_ref`は`null`。
- `reason == "superseded"`なら`successor_ref`はcanonical GitHub Issue URL文字列。
- PR URL、comment URL、fragment付きURL、query付きURLはsuccessorとして拒否する。

`gtp check`はこの型、enum、条件付き組合せ、URL入力形だけをofflineで検査する。

`successor_ref`のURL入力形はIntrinsic Validityで検査する。参照先を取得できた場合、そのstableな作成時刻を使って、source Issue自身ではないこと、source Issueより後かつ`stop` comment以前に作成されたことをHistorical Contextual Validityで検査する。

Successor Issueの現在の存在とrepository identityへの解決はLive Conformanceとする。後の移管や削除によってStop Record自体を遡及的にcontext-invalidへ変えない。open/closed状態、GTP Recordの有無、successor Issueの内容を条件にせず、successor chainも再帰評価しない。

時間関係は次のとおりとする。

```text
source Issue creation
  < successor Issue creation
  <= stop comment creation
```

作成順の不一致を確認できた場合はcontextual invalidとする。現在の存在またはrepository identityの不一致はlive reference mismatchとする。network、認証、rate limitなどで取得できない場合は取得不能として扱い、record不正とは断定しない。

successor Issueが後でclosedになっても、過去のvalid `stop`には影響しない。後からURLを解決できなくなった場合はlive reference mismatchとして表示し、`stop`のschema validityとは分離する。

### 結果

- successor chainはIssue作成順で常に未来へ進む。
- cycle専用のstate、reason、再帰検査を追加せずcycleを排除できる。
- `successor_ref`のnullable条件が`reason`だけで決まる。
- Operation連携、権限、successor Issueの内容評価をGTPへ持ち込まない。

## ADR-019: valid Doneのmerge待ちはin_progressのまま扱う

- Status: Accepted
- Date: 2026-07-19

### 背景

`done` Recordは特定のsource commitについてDone Conditionsを満たしたという主張であり、Evidenceはその主張へ対応する参照である。GTPが機械的に確認できるのはEvidence resourceの存在、状態、repository、種類、SHA bindingまでであり、条件内容の真実性そのものではない。また、taskの最終事実はBound PRのnative mergeである。

validなactive `done`が存在しても、Bound PRが未mergeであることは矛盾でもblockerでもない。この待機を独立stateへすると、既存の`in_progress`で表せる状態を増やすことになる。

### 決定

次をすべて満たし、Bound PRが未mergeの場合、Issue stateは`in_progress`のままとする。

- activeなvalid `done`がある。
- Doneの全Evidence参照がactive ContractのDone Conditionsと対応する。
- 各Evidence resourceのrepository、種類、状態、`done.head_sha`へのbindingが適合する。
- Bound PRのsource head SHAが`done.head_sha`と一致する。
- Bound PRは未mergeである。

`awaiting_merge`などのprotocol stateは追加しない。Done Claim、Evidence Binding、merge待ちをどのfield名で表示するかはCLI projectionであり、protocol coreに含めない。Done Conditionの内容自体をGTPが証明したように表現してはならない。

Bound PRが`done.head_sha`に対応するsource headをnative mergeした時点だけ、Issue stateを`done`へ移す。

人向けには、完了の主張と各条件に対応するEvidence参照があり、それらが対象commitへbindingされているが、PRは未mergeであることを表示する。

### 結果

- Done Claim、Evidence Binding、native mergeを別のfactとして表示できる。
- 通常のmerge待ちを`halt`へ昇格しない。
- 新しいprotocol stateを追加せず、進行状況を正確に説明できる。

## ADR-020: Haltは導出不能なtransitionだけを止める

- Status: Accepted
- Date: 2026-07-19

### 背景

`halt`をagentの全行動を禁止するstateとして解釈すると、矛盾の確認、修正版Recordの投稿、valid `stop`など、回復に必要な行動まで止めてしまう。また、GTPは操作権限を与えたり取り消したりするprotocolではない。

### 決定

`halt`は、GitHub履歴とlive observationsから特定のprotocol transitionを一意かつ安全に導出できないため、そのtransitionを進めない状態とする。

- agent全体への停止命令ではない。
- repository mutationの許可または禁止を表さない。
- 通常の待機や取得不能を自動的にtask全体のblockerへ昇格しない。
- 各halt reasonが明示的に許す修正版Recordやvalid `stop`などの回復操作は妨げない。
- 人向け出力は、止めるtransition、理由、確認対象URL、許可を与える表示ではないことを説明する。

### 結果

- fail-closedの対象を曖昧なtransitionへ限定できる。
- recovery pathまで包括的に禁止する過剰停止を避けられる。
- GTPのstateと外部の操作権限を混同しない。

## ADR-021: Carrier編集を拒否し、削除検出の限界を明示する

- Status: Accepted
- Date: 2026-07-19

### 背景

GTPはappend-onlyなcomment履歴からstateを再構成するが、GitHub Issue Commentは編集・削除できる。v1 readerが過去bodyを完全な台帳として再構成しようとすると、GraphQLの編集差分、権限、欠落履歴を含む別の履歴機構が必要になる。

### 決定

- 現在もExact Markerを持ち、GitHub metadataから編集済みと観測できるCarrierを`edited_carrier`とする。
- unresolvedなEdited Carrierはsingleton Repair Groupとする。
- fresh IDの後続Recordが当該URLを明示的に完全置換した後は、Edited Carrierをactiveなhalt原因に残さない。
- 要約だけの編集も区別せず拒否する。
- markerを除去する編集は、過去bodyやcarrier台帳を再構成しないv1 readerでは通常commentと区別できない場合がある。
- 削除済みで、どの参照にも現れないCarrierも検出できない。
- 参照先の欠落を確認できた場合はlive reference mismatchとして表示する。
- network、認証、rate limitなどにより欠落と取得不能を区別できない場合はrecord不正と断定しない。
- GTPはtamper-proof ledgerや、特権主体による改変への耐性を提供しない。

Terminal根拠となるCarrier自体が編集・削除された場合は、append-onlyな後続commentに対するTerminal Resultの単調性より、この編集・欠落規則を優先する。

### 結果

- accidentによるCarrier編集を明示的に検出・修復できる。
- 過去body再構成用の台帳や新しいprotocol stateを追加しない。
- readerが検出できない改変を検出可能と主張しない。

### 参考

- [GitHub REST API: Issue comments](https://docs.github.com/en/rest/issues/comments?apiVersion=2022-11-28)
- [GitHub GraphQL: IssueComment](https://docs.github.com/en/graphql/reference/issues#issuecomment)

## ADR-022: Terminal Resultはappend-onlyな後続commentに対して単調とする

- Status: Accepted
- Date: 2026-07-19

### 背景

terminal後の誤投稿を常に`halt`へ昇格すると、既に完了または中止したtaskが回復不能になる。一方、Terminal根拠Carrier自体の編集・削除まで無視すると、fresh readerが確認できない履歴を証明したことになる。

### 決定

- valid Stopは、すべてのpre-terminal `halt`から利用できる非完了escapeとする。
- Stop CarrierがIntrinsic-validであること、Stop以前にHistorical Contextual-valid Contractが1件以上存在すること、先行Terminal Resultがないこと、reasonとSuccessor規則が適合すること、Stop自身の`supersedes`が適合することだけを受理条件とする。
- active Contractの一意性、Start、active Done、pre-terminal diagnosticの解消、PR state、branch存在はStopの受理条件にしない。
- valid Contractが存在する`ready`、Start後、active DoneのPR merge前、すべてのpre-terminal `halt`からvalid Stopを受理できる。
- prefix-valid Stop、またはactive valid Doneが対象とするsource headのnative mergeによってTerminal Resultが成立する。
- Terminal Resultはappend-onlyな後続commentによって覆らない。
- 既存Logical Recordと同じID・同じparsed JSONの遅延retryは新しいLogical Recordではないため、terminal violationにならない。
- terminal後の新しいLogical RecordはTerminal Resultを変更せず、`terminal_violation` diagnosticを残す。stateは`done`または`stopped`を維持する。
- Stop後にPRがmergeされても`stopped`を維持し、`merge_after_stop` diagnosticを表示する。
- terminalになる前のinvalid StopまたはDoneは、通常のrepair規則に従って修復できる。
- Terminal根拠Carrier自体の編集・削除にはADR-021を適用し、Terminal Resultの単調性で覆い隠さない。

valid Stop成立後、過去のpre-terminal blockerはdiagnosticとして残るが、stateは`stopped`とする。Stopは完了、権限付与、過去Recordの消去を意味しない。先行Terminal Resultがある場合だけ、fresh Stopを受理しない。

Terminal Result成立後に再検査するlive resourceは、その結果が実際に依存するものだけに限定する。

DoneによるTerminal Resultは次に依存する。

- intactなDone Carrierまたは未編集alias。
- Bound PR。
- merge対象source head SHA。
- Doneが列挙したEvidence resource。

Superseded StopによるTerminal Resultは次に依存する。

- intactなStop Carrierまたは未編集alias。
- Successor Issue identityと作成時間関係。

merge後に削除されたbranch、Bound PR確定後の同名branch、将来の同名branch PR、stopped後のbranch不在はTerminal Resultの依存resourceではない。

依存resourceの適合を確認できれば`done`または`stopped`とする。不一致または欠落を十分なアクセス下で確認した場合は、live reference mismatchとして`halt`にする。network、認証、rate limit、権限不足と区別できない404などではstateを確認済みとして出力せず、acquisition errorとする。resourceが再び確認可能になれば、新Recordなしで再導出する。

Terminal Result成立後は、fresh DoneまたはStopによる依存resourceの差し替えを許可しない。terminal dependencyが永久に失われた場合は同じIssue内で回復不能になり得る。過去cache、永続alias台帳、terminal repair例外は追加しない。

### 結果

- 後続の誤投稿でterminal taskが回復不能な`halt`へ変わらない。
- append-only履歴に対する単調性と、観測できない履歴を証明しない境界を両立する。
- 新しいterminal stateや修復record typeを追加しない。

## ADR-023: DoneなしのmergeはHaltとし、後続Recordのprefixで回復する

- Status: Accepted
- Date: 2026-07-19

### 背景

native mergeはtaskの最終的なGitHub factだが、active valid Doneがなければ、Done Conditionsに対応するEvidence付き完了主張が存在しない。mergeだけを理由に`done`へ進めると、Evidence要件を迂回できる。

### 決定

一意なsame-repository PR Candidateがmerge済みで、active valid Doneがない場合は、`merge_without_done`を理由に`halt`とする。

late Doneはmerge時点へ遡及しない。次の順序で、そのcomment prefixにおいてTerminal Resultを成立させる。

```text
merge発生
  → halt: merge_without_done
  → late Done投稿
  → late DoneのprefixでTerminal Result成立
```

late Doneはfreshな`id`、merged PRの`pr_ref`、merge対象だったsource head SHA、全Done Conditionに対応するEvidenceを持つ。merged PRではbranch存在を要求しない。複数PR Candidateが存在する場合でも、実際にmergeされたPRを明示することでPR identityを決定できる。無関係なPRへのbindingでは`merge_without_done`を解消しない。

valid Stopによる回復も許可する。この場合は`stopped`となり、mergeを取り消したともTask Completionを主張したとも解釈しない。merge済みという外部事実は`merge_before_stop` diagnosticとして残す。

### 結果

- mergeだけでEvidence要件を迂回できない。
- late DoneがいつTerminal Resultを成立させたかをServer Orderで説明できる。
- Evidenceを提示できない場合も、完了を主張せずStopできる。

## ADR-024: ReaderはServer Orderのincremental prefix foldで履歴を評価する

- Status: Accepted
- Date: 2026-07-19

### 背景

same-ID grouping、collision、Repair Groupを最終履歴からglobalに先読みすると、将来のcommentが過去prefixのStart Bindingやhistorical factを書き換える。GitHub Issue Comment APIはIssue単位のcommentをascending IDで返すため、その順序をserver-ownedな評価順として利用できる。

### 決定

readerの正準評価は次の3段階とする。

1. Intrinsic prepass。
2. Server Orderによるincremental prefix fold。
3. state決定に必要なlive resourceとのconformance評価。

次の不変条件を満たす限り、内部関数、cache、API client、pagination処理の構造は実装へ委ねる。

- comment snapshotは完全で、comment IDがstrict ascendingかつ重複なしでなければならない。
- future commentを過去prefixの評価へ使用しない。
- same-ID grouping、collision、Repair Groupもprefix-localに更新する。
- `supersedes`は過去prefixだけで検査する。
- prefix foldはContract Binding、Started Once、Start Binding、valid Done Claim、Stop Terminalを導出する。
- PR mergeとEvidenceなどのlive resourceはcomment fold後に結合する。
- state決定に必要なacquisitionが不完全ならstateを確定しない。
- intactなTerminal Result成立後の新commentは結果を変更しない。
- Terminal根拠Carrier自体の編集はADR-021を優先する。未編集aliasが残れば、そのLogical Recordから証明できる。
- 証明可能なaliasがなければ現在のsnapshotだけから再導出し、過去cacheを正本にしない。

blocking原因、関連URL、terminal前後、unresolvedかrepair済みかはprotocol semanticsに必要である。diagnosticのexact sort、表示上の重複排除、JSON field配置はCLI projectionへ委ねる。

### 結果

- future commentが過去prefixのbindingやhistorical factを書き換えない。
- grouping、repair、lifecycleを同じServer Orderで説明できる。
- 不完全取得をprotocol stateとして誤表示しない。

### 参考

- [GitHub REST API: Issue comments](https://docs.github.com/en/rest/issues/comments?apiVersion=2022-11-28)

## ADR-025: Stateをpriority orderと3つの検査境界から導出する

- Status: Accepted
- Date: 2026-07-19

### 背景

state条件を独立した表として並べると、取得不能、terminal後diagnostic、invalid Carrierが同時に存在する場合の優先順位に穴が生じる。また、単一Carrierの形式不適合、履歴prefixの不適合、mutableなGitHub resourceとの不一致を同じvalidityとして扱うと、過去Recordを不必要に遡及invalid化する。

### 決定

stateは次のpriority orderで導出する。

1. state決定に必要なdependencyの取得が不完全なら、stateを確定しない。CLIでは`state: null`として表現できるが、これはprotocol stateではない。
2. 完全なcomment snapshotにrecognized Carrierが0件なら`unmanaged`。
3. 証明可能なTerminal Resultがあれば`done`または`stopped`。terminal後のcomment異常はdiagnosticだけとし、Terminal根拠自体の編集・欠落は例外とする。
4. terminal前のblocking diagnosticがあれば`halt`。
5. active Contractが正確に1件、Started Onceがfalse、blocking diagnosticがなければ`ready`。
6. Started Onceがtrue、Terminal Resultがなく、blocking diagnosticがなければ`in_progress`。

任意のAPI取得失敗ではなく、現在のstateを決定するために必要なdependencyだけをstep 1の対象にする。Issueのopen/closedはGTP stateへ影響しない。表示するかどうかはCLI projectionへ委ねる。

検査境界は次の3つに分ける。これらは説明上の分類であり、Record fieldやprotocol stateを追加しない。

- **Intrinsic Validity**: 単一Carrierだけで判定する。Carrier正準形、strict JSON、duplicate key、closed schema、UUID、scalar、URL入力形を含む。
- **Historical Contextual Validity**: 完全なcomment snapshotと各prefixで判定する。past・same-Issue supersession、Repair Group完全列挙、alias/collision、Contract Binding、Contract Freeze、Start Binding、Done ConditionとEvidenceのkey集合、lifecycle cardinalityを含む。
- **Live Conformance**: 現在取得した外部resourceとの対応。branch、PR、Check Run、Artifact、Successor Issueの現在の解決、repository identityを含む。

IntrinsicまたはHistorical Contextual不適合のRecordはactive reducer inputへ渡さない。Live不適合はRecord自体をinvalidにせず、依存するtransitionを`halt`する。Acquisition Errorでは適合・不適合を断定せず、必要なstateを確定しない。Edited CarrierはRecord validity以前のCarrier-level問題とする。

typeごとのcardinalityは次とする。

- ContractはStart前にactive Logical Recordが最大1件。複数leafはconflict。valid Start後の新Contractはfreeze violationでactiveにならない。
- 最初のprefix-valid Startだけがhistorical Start Bindingを作る。後続fresh-ID Startはlifecycle violation。invalid Startの修正版は対象URLを明示的にsupersedeする。
- terminal前のactive valid Doneは最大1件。複数のunsuperseded leafはconflictであり、修正版Doneは全active leafをsupersedeする。
- 最初のprefix-valid StopだけがStop Terminalを作る。後続Stopはactive setへ入らずterminal violation diagnosticとなる。invalid Stopはterminalを作らず、明示的なsupersessionで修復できる。
- invalid Start、Done、Stopの対象が複数leafなら、修正版は全leafを列挙する。
- StopはContract、Start、Doneをcross-type supersedeしない。terminal selectionはlifecycleが担当する。

### core transition token

exact tokenを機械が読んでstateまたは許可されるrepair transitionを変える場合だけ、tokenをprotocol coreに含める。v1のclosed vocabularyは次で全部とする。

Repair Group membershipまたはrepair routeを変えるtoken:

```text
invalid_record
edited_carrier
identity_collision
invalid_supersession
incomplete_repair_group
start_contract_binding_failed
done_before_start
done_condition_keys_mismatch
done_evidence_kind_mismatch
stop_without_contract
successor_order_invalid
```

その他のstateまたは許可transitionを変えるtoken:

```text
conflicting_records
multiple_pr_candidates
merge_without_done
contract_freeze_violation
start_redefinition
branch_binding_mismatch
pr_binding_mismatch
done_head_sha_mismatch
evidence_live_mismatch
terminal_violation
terminal_dependency_mismatch
```

`evidence_live_mismatch`は取得できたEvidenceがrepository、SHA、kind、またはcompleted-success条件へ不適合な場合に用いる。Check Runがまだ完了していないだけならDone Terminal未成立の`in_progress`であり、このtokenを付けて`halt`へ進めない。

`terminal_dependency_mismatch`は、十分なアクセス下でTerminal Dependencyの欠落または不一致を確認した場合だけに用いる。一時的な取得不能には使用しない。

pre-terminalにおけるtokenと、通常進行へ戻るために許されるtransitionを次へ固定する。Stopの5条件を満たすvalid Stopは、すべてのpre-terminal行に共通する非完了escapeである。ただし`stop_without_contract`では、先にHistorical Contextual-valid Contractが必要となる。

| token | stateへの作用 | Stop以外の解消経路 |
|---|---|---|
| `invalid_record` | `halt` | singleton Repair Groupの完全置換 |
| `edited_carrier` | `halt` | singleton Repair Groupの完全置換 |
| `identity_collision` | `halt` | collision Repair Groupの完全置換 |
| `invalid_supersession` | `halt` | singleton Repair Groupの完全置換 |
| `incomplete_repair_group` | `halt` | 新しいfresh-ID Recordによる完全置換 |
| `start_contract_binding_failed` | `halt` | Contract側を一意にした後、invalid Startを完全置換 |
| `done_before_start` | `halt` | valid Start成立後、invalid Doneを完全置換 |
| `done_condition_keys_mismatch` | `halt` | fresh-ID Doneで完全置換 |
| `done_evidence_kind_mismatch` | `halt` | fresh-ID Doneで完全置換 |
| `stop_without_contract` | `halt` | valid Contract成立後、invalid Stopを完全置換 |
| `successor_order_invalid` | `halt` | fresh-ID Stopで完全置換 |
| `conflicting_records` | `halt` | fresh-IDの同type Recordで全active leafを通常supersession |
| `multiple_pr_candidates` | `halt` | valid `done.pr_ref`で1件をBound PRにする |
| `merge_without_done` | `halt` | mergeされたPRを指すLate Done |
| `contract_freeze_violation` | `halt` | Record修復なし。valid Stopのみ |
| `start_redefinition` | `halt` | Record修復なし。valid Stopのみ |
| `branch_binding_mismatch` | `halt` | 同じbranch identityのLive Conformance回復 |
| `pr_binding_mismatch` | `halt` | terminal前のfresh-ID Doneによる通常supersession、または同じPRのLive Conformance回復 |
| `done_head_sha_mismatch` | `halt` | 新headと全Evidenceを持つfresh-ID Doneによる通常supersession |
| `evidence_live_mismatch` | `halt` | 全Evidenceを再提示するfresh-ID Doneによる通常supersession |
| `terminal_violation` | terminal stateを変更しない | 新Logical Recordを結果へ反映しない。retry aliasだけ許容 |
| `terminal_dependency_mismatch` | `halt` | Record修復なし。同じTerminal Dependencyの回復だけを再評価 |

intactなTerminal Result成立後に現れたtokenは、`terminal_dependency_mismatch`とTerminal根拠Carrierの編集・欠落を除き、terminal stateを変更しないdiagnosticとなる。

Acquisition Errorはprotocol stateではないが、reader動作を固定するclosed classificationとして`acquisition_incomplete`だけを使用する。state決定に必要なcomment snapshotまたはlive resourceを完全に取得できない場合を含み、stateを確定しない。詳細なnetwork、authentication、rate-limitなどの表示codeはCLI specificationへ委ねる。

上記以外のexact diagnostic tokenをv1 readerがstateまたはrepair判断へ使用してはならない。同じ意味へ複数tokenを割り当てない。説明文、表示順、severity、JSON field配置はprotocol coreに含めない。

### 結果

- 6 stateを増やさず、同時に成立する条件の優先順位を固定できる。
- Record validityとmutableなexternal resourceの不一致を分離できる。
- active setへ入るRecordとhistorical factのownerが明確になる。

## ADR-026: Done Terminal成立時刻とStop時刻を比較する

- Status: Accepted
- Date: 2026-07-19

### 背景

PRの`merged_at`だけでDoneとStopの先後を決めると、merge後にStop、その後にLate Doneが投稿された場合に、Doneが先にterminalになったと誤判定する。また、Done投稿時にはpendingだったCheck Runが後からsuccessになる場合、Evidence Bindingが成立する前にDone Terminalを成立させてしまう。

### 決定

比較対象となるDoneは現在のLive Conformanceを満たさなければならない。Done Terminal Atを次で導出する。

```text
done_terminal_at = max(
  Done comment.created_at,
  Bound PR.merged_at,
  Doneが参照する全Check Runのcompleted_at
)
```

Artifactは`done.head_sha`のcommitに既に存在するfileであるため、追加の成立時刻を持たない。

Done Terminal AtとStop commentのserver-owned `created_at`を比較する。

```text
done_terminal_at <= stop.created_at
  → done

stop.created_at < done_terminal_at
  → stopped
```

同値ではDoneを優先する。異なるGitHub resource間で表示精度より細かい全順序を復元する新機構は追加しない。

Late Doneは自身のcomment時刻がmaxへ入るため、先に成立したStopを遡及的に覆さない。Check RunがStop後にsuccessとなった場合も、先に成立したStopを覆さない。

### 結果

- Done Claim、merge、Check Run successがすべて成立した時点でDone Terminalを評価できる。
- Late Doneが過去へ遡及しない。
- 同秒timestampのための追加stateや外部台帳を必要としない。

### 参考

- [GitHub REST API: Check runs](https://docs.github.com/en/rest/checks/runs)

## 文書境界（GTP protocol外）

今後、規則をprotocol coreへ含めるかは、その規則を削除したとき、適合する2つのreaderがCarrier認識、offline validity、state、repair結果のいずれかで異なるかによって判断する。異ならない表示shape、diagnostic sort、日本語文面、pagination実装、API client構造はCLIまたは開発文書へ置く。

protocol coreは次の4領域へ限定する。

1. CarrierとRecord schema。
2. Offline validation。
3. Prefix reducerとstate。GitHub API取得、Live Conformance、Acquisition Errorは外部入力境界として扱う。
4. Supersession、retry、repair。

この節はGTP利用者のprotocol semanticsやadmission ruleではなく、仕様書を肥大化させないための開発・文書分類である。

## ADR-027: `GTP.md`を唯一の公開正本にし、複雑な同一Issue内修復を外す

- Status: Accepted
- Date: 2026-07-19
- Supersedes: ADR-002〜ADR-026のうち`GTP.md`と矛盾する公開protocol semantics

### 観測事実

- 現行仕様は26件のADR、`CONTEXT.md`、実装、acceptance記録へ分散し、利用者が1ファイルだけをコピーしてRecordを作れる形ではない。
- 現行実装にはRepair Group、任意数leafのjoin、Done Terminal成立時刻、Late Done、24個相当の細分化されたtransition tokenがある。
- Issue #1とPR #2では、GitHub Issue、branch、PR、Evidence、native mergeから状態を再構成するwalking skeletonを実GitHubで観測した。
- 比較対象の`gtp-test` PR #1と`gtp-test2` PR #1では、1ファイルの仕様正本、人向け日本語を先に出すCLI、仕様・pure reducer・GitHub取得・表示の責務分離が提案された。これらを本repositoryの公開candidateで受け入れた事実は、後続のLevel 0／Level 1 acceptanceまで未確認である。

### 推論

- 非エンジニアの個人開発者が導入し、異なるruntime間で引き継ぐ目的には、同一Issue内であらゆる壊れ方を修復する能力より、規則を1ファイルから一意に読めることの方が重要である。
- 複雑な修復を残すと、producerとreaderの双方が理解・実装すべき分岐が増え、実際の事故URLがない機構まで公開契約になる。
- pre-terminalな矛盾を最後のvalid Stopで閉じ、新Issueへ移る単一経路があれば、履歴を消さずに安全な再開先を作れる。

### 決定

- repository rootの`GTP.md`をprotocolの唯一の公開正本とする。意味が衝突する場合、`GTP.md`を優先する。
- `DECISIONS.md`は採否理由と設計履歴を所有し、公開Recordを作るための追加仕様にはしない。
- 公開v1を`contract`、`start`、`done`、`stop`の4 Record、6 state、7 halt reasonへ限定する。
- Repair Group、任意数leafのjoin、同一Issue内のRecord置換、Done active interval、Late Done専用機構、細分化されたtransition token、`human` Evidenceを外す。
- 訂正の正準経路を、最後のvalid Stopと新Issueへの移行へ一本化する。
- ADR-001の「GTPを権限の根拠にしない」は`GTP.md`と整合するため、そのまま維持する。
- ADR-002〜ADR-026は削除せず設計履歴として保持するが、`GTP.md`と矛盾する意味を現行仕様として使用しない。

### 結果

- 利用者は`GTP.md`と共通adapter文だけでprotocolへ参加できる。
- 後続実装は`GTP.md`のclosed schemaと語彙へ適合させる必要があり、現行codeとtestsはこのADRだけでは適合済みにならない。
- 旧acceptanceはwalking skeletonの回帰材料として残るが、新しい最小仕様のLevel 0／Level 1 acceptanceを証明しない。
- 公開仕様から外した複雑な修復が必要になった場合は、実際のfailure URLを持つ新IssueとDecisionで再検討する。

## ADR-028: Carrier、closed schema、pure reducerをatomicに切り替える

- Status: Accepted
- Date: 2026-07-19
- Supersedes: ADR-002〜ADR-026のうちRepair Group、Record supersession、DoneWindow、旧diagnostic tokenに依存する実装判断

### 観測事実

- Issue #8の途中実装ではExact Carrierとclosed schemaのtargeted tests 24件が成功した。
- 同じ候補でfull suite 76件を実行すると、旧reducerとstatusが`supersedes`、Repair Group、DoneWindowを要求するため36 failures、2 errorsになった。
- `GTP.md`はこれらを公開v1へ含めず、4 Record、6 state、7 halt reasonだけを定義している。
- Issue #18ではContract Recordの必須fieldを欠く投稿ミスがあり、そのRecordを編集せずStopしてIssue #20へ移行した。

### 推論

- Carrier/schemaだけを先にmainへ入れると、同じrepository内に互いに矛盾するreaderが共存する。
- legacy compatibility layerを足すと、`GTP.md`から削除した意味をproduction codeへ温存することになる。
- pure reducerを既存CLIから検証するには、GitHub取得全体を再設計せず、status adapterの接続点だけを同じ変更で更新する必要がある。

### 決定

- Issue #8と#9を一つのatomic変更として後継Issue #20とPRで実装する。
- `src/gtp/model.py`と`src/gtp/reducer.py`からRepair Group、Record supersession、DoneWindowを削除する。
- reducerのdiagnostic tokenを`GTP.md`の7 halt reasonだけに限定する。
- `src/gtp/status.py`は新reducerへ接続する最小限のadapter変更を許可し、GitHub取得・live判定の全面整理はIssue #10へ残す。
- safe retryは同一`id`かつ構造的に同じRecordのaliasだけとし、同じIssue内の修復はfinal Stopと新Issueで行う。

### 結果

- Exact Carrier、closed schema、pure reducerを中間不整合なしに同時導入できる。
- reducer truth tableとlegacy vocabulary prune reportをimmutable artifactとしてDone Evidenceに使用できる。
- 旧ADRは設計履歴として残るが、現行動作の根拠は`GTP.md`、ADR-027、ADR-028になる。

## ADR-029: GitHub live bindingをGET-only HTTP境界として固定する

- Status: Accepted
- Date: 2026-07-19

### 観測事実

- Issue #10開始時点の`GitHubClient`はGET、Link pagination、repository／Issue／comment／branch／PR／Check Run／artifact取得の骨格を持っていた。
- 同時点のstatus adapterにはPR changed filesのscope検査、rename旧path検査、Issue snapshot再読、Bound PR head再読、successor時刻検査がなかった。
- Check RunがpendingのときはDone Evidence不適合ではなく`in_progress`を返し、Doneなしmergeは`invalid_transition`へ分類していた。
- 既存status testはin-memory clientを使い、HTTP responseからCLIまでの接続を証明していなかった。

### 推論

- pure reducerへnetwork処理を戻さず、GitHub REST adapterとstatus application serviceの境界でlive Observationを結合すれば、Historical stateとAcquisition Errorを分離できる。
- 内部moduleをmockするだけではrequest method、pagination、host、redirect headerを検証できないため、外部HTTP境界だけを置換するfixtureが必要である。
- branch、PR、Evidenceの個別取得が成功しても、読取中にIssueまたはBound PR headが変われば同一snapshotとはいえない。

### 決定

- production transportはPython standard libraryの`Request`と`HTTPRedirectHandler`を用いるGET-only adapterとする。
- 初期requestと最終response URLを`https://api.github.com`へ限定し、cross-origin redirectでは`Authorization`を除去する。
- Issue metadataをread前後で比較し、Bound PRはEvidenceとchanged files取得後にsource headを再読する。変化時はhaltではなくAcquisition Errorを返す。
- PR changed filesを全page取得し、renameでは`filename`と`previous_filename`の両方をBound Contract scopeへ照合する。
- fork、repository mismatch、branch mismatch、scope外pathを`invalid_binding`、SHA不一致を`stale_evidence`、Evidence resource不適合を`invalid_evidence`へ分類する。
- pendingまたはfailureのCheck RunはDone条件を満たさないため`invalid_evidence`とする。Doneなしmerge、Doneより先のmerge、Stop後mergeは`terminal_violation`とする。
- HTTP fixture suiteはCLI、URL admission、classifier、reducer、binding logicをproduction実装のまま通し、`_open`だけを外部境界として置換する。

### 結果

- 取得不能時にstateを推測せず、`state: null`と`acquisition: incomplete`を返せる。
- GitHubへのwrite path、GraphQL、webhook、cache、database、fork、GHESを追加せず、Issue #10のlive binding規則を検証できる。
- live HTTP matrixとprune reportをimmutable Done Evidenceとして利用できる。

## ADR-030: CLIを任意validatorとしてPyPIへ公開する

- Status: Accepted
- Date: 2026-07-20
- Supersedes: Issue #5完了時のCLI非公開方針

### 観測事実

- [Issue #5の完了コメント](https://github.com/shinya0x00/github-task-protocol/issues/5#issuecomment-5016145451)は、`v1.0.1` tag、GitHub Release、PyPI packageを作成せず、CLI配布方式を未決定とする境界で親Issueを閉じた。
- 利用者の新しい判断を受け、Issue #49で1.0.1公開candidateを準備し、Issue #52でsdistの`PKG-INFO`を修復した。
- Issue #54では固定candidateからannotated tag、GitHub Release、PyPI公開、public PyPIからのclean install、live `done`／`stopped`再読を行った。
- `README.md`は、GTP利用にCLI installは不要であり、使う場合だけ固定versionを指定できると説明している。
- 最終公開結果とEvidenceの限界は`acceptance/public-release-v1.0.1.json`が所有する。一方、`acceptance/release.json`は公開前計画の`prepared_not_published`とplaceholderを保持していた。

### 推論

- CLIをPyPIから取得可能にすると、任意validatorを試す利用者の導入負担を下げられるが、GTPの参加条件へCLIを追加する必要はない。
- packageの公開factは、Level 0のtoolなし引き継ぎ、人間のnative merge判断、GTPが権限を与えない境界を変更しない。
- 公開前計画と最終Evidenceが異なる役割を持つことを明示しなければ、clean readerは`prepared_not_published`を現在状態と誤読できる。
- `acceptance/release.json`をrenameすると過去のIssueとPRからのpath参照を壊すため、同じpathでsupersessionを明示する方が履歴を追いやすい。

### 決定

- CLIはGTP利用の必須条件ではないが、任意の参照validatorとしてPyPIへ公開する。
- 公開によってRecord、state、halt reason、Level 0の価値、人間の受理権限、GTPが証明する範囲を変更しない。
- `acceptance/release.json`は1.0.1公開前計画のhistorical artifactとして残し、statusを`superseded_by_public_release_evidence`とする。
- 同fileの`superseded_by`から`acceptance/public-release-v1.0.1.json`へ解決可能な関係を持たせる。最終公開factはsuccessor Evidenceが所有し、公開前placeholderを遡及的な実績値へ書き換えない。
- npm公開、自動publish workflow、CLI必須化はこのDecisionへ含めない。

### 不採用案

- CLI非公開方針の維持は、新しい利用者判断と実際の1.0.1公開factに一致しないため採用しない。
- `acceptance/release.json`の削除またはrenameは、公開前判断の履歴と既存path参照を弱めるため採用しない。
- 公開後の値でplaceholderを全面更新する案は、計画時点の観測と実行後Evidenceのownerを混同するため採用しない。

### 結果

- clean readerは、公開前計画から最終public Evidenceへ一意に移動できる。
- 配布方針の理由をIssueとPRの全履歴から再構成せず、Decisionとして読める。
- 今後のversion準備、tag、GitHub Release、registry upload、公開後検証は、それぞれのrelease IssueとEvidenceで扱う。
- PyPI公開、CI成功、CLI出力は、actor本人性、credential安全性、package品質全体、変更・完了・merge authorityを証明しない。

## ADR-031: 目的説明とEvidence binding表示を分離する

- Status: Accepted
- Date: 2026-07-20

### 観測事実

- `GTP.md`はCheck Runのtest十分性とArtifact内容の真実性を証明しないと定義している。
- 変更前のCLIは`done`を「このIssueの完了を確認しました」、条件一覧を「確認できた完了条件」と表示し、resource bindingの確認を条件内容の意味評価と読める余地があった。
- core schemaはtask固有のunknown fieldを持たず、通常commentは履歴へ影響しない。
- reducerは同一ID・同一JSONのsafe retryをLogical Recordへ畳むが、live terminal検査はDone aliasだけを除外していたため、terminal後のContractまたはStart retryを新Recordとして扱っていた。
- Level 1のIssue #12はbranch削除後の完了再構成を示す一方、Issue #65はPython 3.11、3.12、3.13の各Done Conditionを個別のexact-head Check Runへ束縛している。

### 推論

- protocol stateの`done`と、人間による条件内容の受理を同じ文面にすると、GTPが証明しないsemantic fulfillmentを過剰claimする。
- task固有のunknownをclosed Record schemaへ追加すると、stateへ影響する意味規則が必要になり、最小protocolの境界を越える。通常のIssue本文・commentで人へ引き継ぎ、Done可否に関係するunknownが残るならDoneを提示しない方が一意である。
- safe retry aliasは新Logical Recordではないため、Record typeにかかわらずterminal後の違反検査から除外しなければ仕様と実装が一致しない。
- current acceptanceは、Done ConditionとEvidenceを一対一に追えるIssue #65を参照した方がclean readerの再検証可能性が高い。

### 決定

- CLIはDone Claim、Evidence binding、native mergeを観測factとして表示し、Done Conditionの自然言語上の充足を自動判定しないことを同じ出力で明示する。
- `task_context.not_proven`と`evidence_limits`へsemantic fulfillmentの限界を投影する。task固有のunknown field、state、Record typeは追加しない。
- terminal後の同一ID・同一JSON retryはContract、Start、Done、Stopの別なくsafe aliasとして扱う。fresh Recordは従来どおり`terminal_violation`とする。
- Level 1のIssue #12を歴史的な完了再構成Evidenceとして保持し、現行のexact-head CI受入はIssue #65を参照する。

### 不採用案

- `done`をsemantic fulfillmentの自動証明として扱う案は、Evidence resourceから内容の十分性を一般に判定できないため採用しない。
- unknownをGTP Recordへ追加する案は、closed schemaと4 Recordの最小境界を変えるため採用しない。
- terminal検査でDone aliasだけを特別扱いする案は、Logical Recordのidentity規則がRecord typeに依存しないため採用しない。
- Issue #12の記録を削除または現在値へ書き換える案は、過去の受入履歴を失うため採用しない。

### 結果

- 人はCLI出力だけで、機械確認できたbindingと、人がEvidenceを読んで判断すべき条件内容を区別できる。
- ContractとStartの遅延retryがterminal resultを壊さず、fresh Recordだけが違反になる。
- task固有の未確認事項はGitHub上の通常proseへ残り、protocol coreのstate判断へ暗黙に混入しない。
- clean readerは歴史的な完了再構成と現行のexact-head CI受入を区別して辿れる。

## ADR-032: terminal identityと取得完全性をfail-closedにする

- Status: Accepted
- Date: 2026-07-20

### 観測事実

- Stop後のfresh Recordを`terminal_violation`として検出しても、live statusは`stopped`と`none_stopped`を表示していた。
- Stop再読時に同名branchの全PR履歴を対象としていたため、Stop後に別taskが同名branchを再利用してmergeすると、過去Issueが`stopped`から`halt`へ変化した。
- GitHub RESTの404はresource不在と権限不足を一意に区別できないが、branch、PR、Check Run、artifact、successor Issueの404をprotocol不適合へ変換していた。
- Issueだけを再読していたため、取得中のbranch、PR candidate、merge factの変化を検出しない経路があった。
- List Pull Request Filesには取得上限があるが、返却fileを完全なPR差分としてscope判定していた。
- Startはrepository default branchも受理し、`continue_work`を提示できた。
- sourceは公開1.0.1後にruntime挙動を変更したが、package versionとREADME commandは1.0.1のままだった。

### 決定

- Stop後のfresh Recordはpublic stateを`halt`、reasonを`terminal_violation`とし、最初のfresh comment URLを原因とする。pre-terminal diagnosticを持つvalid Stopの非常口は維持する。
- Stop後mergeの対象は、Start以後かつStop以前に作成されたsame-repository・same-branch PRへ限定する。Stop後に作成された同名branch PRは過去Issueへ影響させない。
- 汎用404からresource不在を推測せず、十分な取得を証明できない場合はAcquisition Errorとする。
- branch、PR candidate collection、Bound PRを再読し、stateを左右するsnapshotが変化した場合はAcquisition Errorとする。
- PR detailの`changed_files`と取得したfile数を照合し、完全な差分を取得できない場合はscope適合をClaimしない。
- Start branchがrepository default branchと一致する場合は`halt / invalid_binding`とする。valid Stopはこのpre-terminal不適合を安全に閉じられる。
- task固有の自由文はIssue本文・通常commentがcanonical ownerであり、CLIはその意味を自動判定しない。開始前から完了判断に必要な不明点はDone Conditionとし、開始後にContract変更が必要ならStopと後継Issueへ移る。CLIはDone提示前の確認先としてIssue URLを表示する。
- Record grammarは変更しない。runtime修復candidateのpackage versionを1.0.2とし、公開完了前はpublic packageとして案内しない。

### 不採用案

- unknown専用Recordまたは自由文parserの追加は、4 Recordと決定的reducerの境界を広げるため採用しない。
- 404を常にresource不在とする案は、権限不足をprotocol不適合へ変換するため採用しない。
- branch名をrepository全体で永久に再利用禁止とする案は、Stop comment時刻でtask対象PRを限定できるため採用しない。
- 既に公開済みの1.0.1 tagまたはartifactを移動・置換する案は、immutableなrelease identityを壊すため採用しない。

### 結果

- terminal resultはfresh Recordと将来の無関係なbranch再利用を区別できる。
- 取得不能、取得中変化、file一覧打ち切りをprotocol haltと混同しない。
- default branchへの作業継続をGTP statusが案内しない。
- clean readerはIssue URLからtask固有の未確認事項を確認する必要と、CLIが意味評価しない限界を同時に確認できる。
- source candidateと次のpublic package identityを1.0.1から分離できる。

## ADR-033: PR snapshotとtask lifecycleのidentity境界を一致させる

- Status: Accepted; Stopのpre-Start PR判断はADR-034でsupersede
- Date: 2026-07-20

### 観測事実

- PR snapshot比較はhead SHAとmerge時刻を含む一方、base ref・base SHA・`changed_files`を含まず、file一覧取得中のbase更新を検出できなかった。
- 通常のcandidateとDoneはStart前から存在するsame-branch PRを受理したが、Stop後merge検査はStart以後に作成されたPRだけを対象とし、同じPRのtask identityがlifecycle途中で変わった。
- repositoryの`default_branch`はStart拒否を決めるが、最初の取得後に再確認していなかった。
- native merge前のDoneはPR headとDone SHAを照合したが、同時に観測したbranch SHAとの一致を要求していなかった。
- Issue #64 / PR #67とIssue #73 / PR #74が、異なるruntime内容で同じ未公開version 1.0.2をcandidateとして保持していた。

### 決定

- PR snapshotはbase repository・ref・SHA、head repository・ref・SHA、state、merge時刻、取得可能な`changed_files`を含む。scope判定ではdetail PRをfile一覧の前後に取得し、全snapshotが一致した場合だけfile一覧を使用する。
- Startと同時刻以前に作成されたPRはcandidate、Done、Stopの全経路で`invalid_binding`とする。Stop後に作成された同名branch PRは従来どおり元taskの対象外とする。
- issue repositoryをstate評価後に再取得し、identityまたは`default_branch`が変化した場合はAcquisition Errorとする。
- native merge前のDoneでは、安定したbranch SHA、Bound PR head SHA、Done head SHAの三者一致を要求する。merge後にbranchが削除されても、Issue、Done、PR、merge factから再構成できる既存境界は維持する。
- Issue #64とIssue #73をIssue #75へsupersedeし、PR #67とPR #74を未mergeで閉じる。未公開1.0.2のopen delivery laneはIssue #75 / PR #76へ一本化する。

### 不採用案

- PR作成時刻をStop時だけ使う案は、作業中と停止後でtask identityが変わるため採用しない。
- base branch名だけを比較する案は、同じbranch名の先端更新を検出できないため採用しない。
- merge後もbranch取得を必須にする案は、正常なbranch削除後にhistorical Doneを再構成できなくなるため採用しない。
- RecordへPR番号またはbase SHA fieldを追加する案は、GitHub live resourceから取得でき、Record grammarを広げる必要がないため採用しない。

### 結果

- scope判定が使用したfile一覧を、同じbase/head/`changed_files`のdetail PRへ束縛できる。
- PRがtaskへ属するかの規則がcandidate、Done、Stopで一致する。
- default branch変更とnative merge前のbranch/PR反映差からstateを推測しない。
- clean readerはpredecessorから一つのopen 1.0.2 candidate laneへ移動できる。

## ADR-034: Stopではpre-Start PRを対象外とし、同一instantを推測しない

- Status: Accepted
- Date: 2026-07-20

### 観測事実

- ADR-033はStartと同時刻以前のPRをcandidate、Done、Stopの全経路で`invalid_binding`とした。
- この規則では、古いsame-branch PRが原因でhaltしたIssueへvalid Stopを投稿しても`stopped`へ着地できず、pre-terminalな不適合を安全に放棄するStopの役割と衝突した。
- GitHubのPR作成時刻とStop comment時刻が同一instantでも、実装はPRをStop以前の対象として扱い、後日のmergeを`terminal_violation`と断定できた。

### 決定

- candidate探索とDone bindingでは、Startと同時刻以前のPRを従来どおり`invalid_binding`とする。
- Stopでは、Startと同時刻以前のPRを現在taskの対象外として除外し、diagnosticへ加えない。
- PR作成時刻とStop時刻が同一instantなら、merge有無より先にAcquisition Errorとする。merge時刻とStop時刻の同一instantもAcquisition Errorを維持する。
- timestampはtimezone付きdatetimeとしてUTCへ正規化して比較する。Record、state、halt reasonは追加しない。

### 不採用案

- Stopでもpre-Start PRを`invalid_binding`にする案は、valid Stopを非常口として使えなくするため採用しない。
- PR作成とStopの同一instantをStop以前とみなす案は、Stop後に作成された別taskのPRを元Issueへ結び付ける可能性があるため採用しない。
- branch名を永久に再利用禁止とする案は、Stopの時間窓と後継Issueの新branchでtask identityを分離できるため採用しない。

### 結果

- 作業中に古いPRを誤継承せず、壊れたStartはvalid Stopで`stopped`へ閉じられる。
- Stopと同一instantのPR作成から`stopped`または`terminal_violation`を推測しない。
- candidate、Done、Stopは同じPR集合を同じ目的で扱うのではなく、作業bindingと安全な放棄という役割に応じた境界を持つ。
