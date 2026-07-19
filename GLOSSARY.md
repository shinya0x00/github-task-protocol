# GTP glossary

## 権限（authority）

変更、完了宣言、mergeなどを実行してよい根拠。ユーザーの指示、repository policy、GitHub permissionなどGTPの外部から与えられる。GTPは権限を付与せず、その存在も証明しない。

## 観測（observation）

GitHub上のIssue、comment、branch、PR、checkなどを読み取ること。対象を正しく観測できたことは、その対象を変更してよいことを意味しない。

## record

GTPの規約に従ってGitHub Issue commentへ記録された構造化データ。タスクの契約、開始、完了主張、中止を表すが、操作権限は与えない。

## contract

タスクの目標、範囲、完了条件を表すrecord。許可証ではなく、タスク境界の主張である。

## start

特定のcontractに基づく作業開始を表すrecord。開始事実の主張であり、操作権限の付与ではない。

## carrier

1件のGTP recordを運ぶIssue comment全文。平易な要約、exact marker、JSON fenceを含む。JSONだけを指す言葉ではない。

## exact marker

GTP carrierを通常のcommentから区別する固定token `<!-- gtp-record:v1 -->`。文字列が完全に一致するときだけmarkerとして認識する。

## carrier classifier

raw Markdown commentがGTP carrierか、通常のcommentか、壊れたGTP carrierかを判定する処理。`gtp status`と`gtp check`で同じ実装を使う。

## raw comment

GitHub APIから取得する、render前のMarkdown comment本文。carrier classifierは画面上のHTMLではなく、この原文を検査する。

## supersession

後続recordが、同じIssue上の過去commentを`supersedes`配列で明示的に置換すること。複数の有効な葉を1件のrecordへjoinできる。通常は同じ`type`だけを置換する。

## server order

GitHubが保持するcommentの投稿順序。supersessionの過去・未来判定には、record内の自己申告時刻ではなくserver orderを使う。

## 有効な葉（active leaf）

後続recordからsupersedeされていない論理record。同じ`type`の有効な葉が複数あれば`conflicting_records`になる。

## 壊れたcarrier

exact markerはあるが、carrier形式またはJSONが不正で有効recordとして解釈できないcomment。後続の有効recordからcomment URLを指定してsupersedeできる。

## 論理record

同じ`id`と構造的に同じparsed JSONを持つretry comment群を、1つへ畳んだGTP record。状態導出とsupersessionは論理record単位で行う。

## 構造的一致（structural equality）

検証済みJSON値同士の一致。objectのキー順と空白は無視するが、配列順、文字列、大小文字、JSON型、値の差は保持する。duplicate keyを含むJSONは比較対象にならない。

## alias

1つの論理recordを運ぶcomment URL群。永続的な台帳には保存せず、観測したcomment一覧から毎回導出する。

## identity collision

同じ`id`に、構造的に異なるparsed JSONが結び付いている状態。retryとはみなさず`invalid_record`にする。後続の新しい`id`から、collisionに属する全comment URLを指定して修復できる。

## read-side convergence

投稿側へidempotency機構を追加せず、readerがGitHub comment集合をgroupingして同一retryを1つの論理recordへ収束させること。

## observation

GitHubから取得し、machine出力へ付加する導出情報。`comment_url`、`comment_id`、`github_login`、`created_at`などを含むが、GTP commentのrecord fieldではない。

## github_login

comment投稿に使われたGitHub accountのlogin名。人間の本人性、agent runtime、操作権限を証明する値ではない。

## schema_valid

GitHub Issue文脈を使わずに検査できる、carrierとrecord schemaの適合結果。参照先の存在、順序、Issue同一性などのcontextual checksが成功したことは意味しない。

## contextual check

Issue上の他commentやGitHub native factを取得しないと判定できない検査。別Issue参照、未来参照、参照先`type`、comment URLの存在などが該当する。

## recognized

入力commentがexact markerを持ち、GTP carrierを名乗っているかを表すCLI検査結果。`recognized: true`はschemaが正しいことを意味しない。protocol stateではない。

## offline validator

networkやGitHub metadataを使わず、単一commentのcarrier形式、JSON、schemaを検査する唯一のvalidator。`gtp check`と`gtp status`が同じ実装を使用する。

## closed schema

許可fieldと必須fieldを完全列挙し、未知fieldを拒否するschema。GTP v1 coreが所有するすべてのobject階層へ適用する。

## unknown_field

closed schemaに列挙されていないfieldを検出したときのoffline validator診断code。protocol stateやhalt reasonではない。

## protocol version

recordの`gtp` fieldが示すschemaと意味規則のversion。v1の値は正確に`"1.0"`であり、未知versionはschema不適合になる。既存versionへfieldを黙って追加しない。

## 通常comment

GTPのexact markerを持たないGitHub Issue comment。質問、議論、実装上の相談などに使う。GTP recordではなく、reducerは内容を解釈しない。

## done condition

`contract`で定義する、完了を主張するために充足と証拠が必要な条件。成否を確認できないconditionが1つでもあれば、`done`を投稿しない。

## scope

`contract`に含めるrepository-relative pathの配列。task境界をagentと人間へ提示するが、変更権限やPR差分の遵守を証明しない。

## repository-relative path

repository rootを基準にしたpath。directoryは末尾`/`、fileは正確なpath、`.`はrepository全体を表す。glob、絶対path、`..`は使用できない。

## condition ID

done conditionを一意に識別し、`done_conditions`と`done.evidence`を対応付けるobject key。lower snake caseの固定形式に従い、object内の記述順には意味を持たない。

## evidence map

condition IDからevidence参照へのmap。key集合はactive contractの`done_conditions`と完全一致する必要がある。evidence kindは繰り返さず、contract側のcondition定義が所有する。

## evidence kind

done conditionが要求するevidence参照の種類。v1では`check`と`artifact`だけ。condition定義が所有し、`done`側では重複して指定しない。

## check evidence

`done.head_sha`に束縛されたGitHub Check Runへの参照。completedかつsuccessであることを検査する。check内容がdone conditionの意味を十分に検査したことまでは証明しない。

## artifact evidence

`done.head_sha`をfull SHAとして含むrepository fileのimmutable blob permalink。指定commitにfileが存在することを検査するが、file内容の真実性は証明しない。

## 検査不能

network、認証、rate limitなどによりGitHub resourceを取得できず、適合・不適合を判定できないこと。record不正とは区別し、取得失敗のためのprotocol stateは追加しない。

## repair group

通常のsame-type supersessionでは修復できないinvalid comment集合。schema-invalid carrierのsingleton group、またはschema-valid recordだけで構成されるidentity collision groupとしてreaderが一時的に導出する。recordへ保存しない。

## repair supersession

repair recordより過去のrepair group memberを完全列挙し、freshな`id`で置換するsupersession。group内のtype不一致だけを許容し、schemaやlifecycle条件は緩和しない。

## prefix-valid

あるcommentが投稿された時点までのserver-ordered comment prefixだけを使って、schema、参照、lifecycle規則を満たしていたこと。後のcommentによるcollisionやsupersessionで、過去のprefix-valid factは消えない。

## started_once

過去にprefix-validな`start`が1件でも存在したことを表す、履歴から導出する単調な事実。record fieldやprotocol stateではない。trueになった後はfalseへ戻らない。

## contract freeze

最初のprefix-validな`start`以後、同じIssueで新しいcontractを受理しないlifecycle規則。contract変更が必要なら、旧Issueを`stop`してsuccessor Issueで新しいcontractを作る。

## bound contract

`start`投稿時点のcomment prefixに存在する、唯一のactiveな論理contract。`start` recordへURLを保存せず、readerが導出する。

## canonical alias URL

論理recordのalias群のうち、server order上で最初のcomment URL。machine outputの代表URLとして使うが、record identityそのものではない。

## PR candidate

`done`前にStartのbranch名から検索されたsame-repositoryのtentativeなPR observation。Bound PRではなく、branch名の再利用により変化し得る。

## Bound PR

valid `done.pr_ref`で明示された特定のPR identity。binding後に同名branchが再利用されても変更しない。

## stale done

schemaおよび投稿時の文脈ではvalidになり得るが、`done.head_sha`がBound PRの現在またはmerge対象のsource head SHAと一致しなくなったDone。record自体を`invalid_record`にはせず、live binding mismatchとして`halt`を導出する。

## Done Claim

Doneが特定のsource commitについて表明する完了主張。Evidence Bindingが適合していても、Bound PRのnative mergeまではTask Completionではない。

## Evidence Binding

Evidence参照について、期待する種類、repository、resource状態、`done.head_sha`との対応が一致すること。Done Conditionの内容自体の真実性は証明しない。

## Task Completion

Done Claimが対象とするsource headをBound PRがnative mergeしたという最終事実。

## successor Issue

`reason: "superseded"`のStopが`successor_ref`で参照する後継Issue。同じrepositoryにあり、source Issueより後、Stop comment以前に作成された別Issueである。

## Halt

GitHub履歴とlive observationsから特定のprotocol transitionを一意に導出できず、そのtransitionを進めないstate。agent全体の停止命令ではなく、操作権限の有無も表さない。

## Edited Carrier

現在もExact Markerを持ち、GitHub metadataから投稿後の編集を観測できるCarrier。unresolvedな場合はsingleton Repair Groupとなる。

## Terminal Result

prefix-valid Stopまたは、Done Claimが対象とするsource headのnative mergeによって確定したtaskの中止または完了。append-onlyな後続commentでは覆らない。

## Terminal Dependency

Terminal Resultを現在のsnapshotから証明するために必要なCarrier、Bound PR、Evidence、またはSuccessor Issue。永久に失われてもterminal後のRecordで差し替えない。

## Server Order

GitHub Issue Commentのascending comment IDによる順序。Record内の自己申告時刻や`updated_at`では並べ替えない。

## Late Done

PR merge後に投稿され、その投稿prefixでEvidence付きDone ClaimとTerminal Resultを成立させるDone。merge時点へ遡及しない。

## Intrinsic Validity

単一Carrierだけから決まる、Carrier、JSON、Record schema、scalar、URL入力形への適合。

## Historical Contextual Validity

完全なcomment snapshotとServer Order上のprefixから決まる、Recordの履歴文脈への適合。

## Live Conformance

Recordと、現在観測されたbranch、PR、Evidence、Successor Issueなどのexternal resourceとの対応。

## Acquisition Error

state決定に必要なObservationを取得できず、適合とも不適合とも判定できないこと。protocol stateではない。

## Done Terminal At

Done comment、Bound PR merge、参照するCheck Run完了のすべてが成立した最も遅いserver-owned時刻。

## Projection

protocol semanticsから導出したfactの人向けまたはmachine向け表現。表示shape自体はprotocol stateやRecordではない。

## Stop

Task Completionを主張せずIssue lifecycleを閉じるRecord。先行Terminal Resultがない限り、すべてのpre-terminal Haltから利用できる。

## Core Transition Token

readerのstateまたは許可されるrepair transitionを変えるclosed vocabularyの識別子。
