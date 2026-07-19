# GitHub Task Protocol

GTPは、GitHub Issue上の記録からAI coding taskの現在地を再構成するためのprotocolである。操作権限や作業品質を与えず、task境界、lifecycle、evidence参照を決定的に説明する。

## Language

**Record**:
GTPが定義する構造化されたtask fact。`contract`、`start`、`done`、`stop`の4種類だけがある。

**Carrier**:
1件のRecordを運ぶGitHub Issue comment全文。通常commentとはExact Markerで区別される。

**Edited Carrier**:
現在もExact Markerを持ち、GitHub metadataから投稿後の編集を観測できるCarrier。

**Exact Marker**:
Carrierを名乗る固定token。完全一致だけを認識し、曖昧な一致は行わない。

**Logical Record**:
同じidentityと構造的に同じ内容を持つretry Carrier群を、1つへ畳んだRecord。

**Contract**:
taskのgoal、scope、done conditionsを表すRecord。操作権限は与えない。

**Start**:
Bound Contractとbranchを結び、Started Onceを成立させるRecord。操作開始の権限は与えない。

**Done**:
特定source commitについてDone ClaimとEvidence参照を提示するRecord。Task Completionそのものではない。

**Stop**:
Task Completionを主張せずIssue lifecycleを閉じるRecord。先行Terminal Resultがない限り、すべてのpre-terminal Haltから利用できる。

**Bound Contract**:
Start投稿時点のcomment履歴に存在する、唯一のactiveなLogical Contract。

**Contract Freeze**:
最初のvalid Start以後、同じIssueでContractを変更しないlifecycle invariant。

**Started Once**:
過去にvalid Startが存在したという単調なhistorical fact。後の訂正やcollisionでは消えない。

**Server Order**:
GitHubがIssue Commentへ与えたascending comment IDによる順序。Record内の自己申告時刻ではない。

**Scope**:
Contractが示すrepository-relativeなtask境界。変更権限やPR差分の遵守は証明しない。

**Done Condition**:
Doneを主張するためにevidence参照が必要な、Contract内の条件。

**Done Claim**:
Doneが特定のsource commitについて表明する完了主張。Task Completionそのものではない。

**Evidence**:
Done Conditionへ提示された、特定commitに束縛されたCheck Runまたはrepository fileへの参照。条件内容の真実性そのものは証明しない。

**Evidence Binding**:
Evidence参照と、その種類、repository、状態、対象source commitとの対応。

**Intrinsic Validity**:
単一Carrierだけから決まる、Carrier、JSON、Record schema、scalar、URL入力形への適合。

**Historical Contextual Validity**:
完全なcomment snapshotとServer Order上のprefixから決まる、Recordの履歴文脈への適合。

**Live Conformance**:
Recordと、現在観測されたbranch、PR、Evidence、Successor Issueなどのexternal resourceとの対応。

**Acquisition Error**:
state決定に必要なObservationを取得できず、適合とも不適合とも判定できないこと。protocol stateではない。

**Task Completion**:
Done Claimが対象とするsource headをBound PRがnative mergeしたという最終事実。

**Repair Group**:
通常のsupersessionでは回復できないinvalid Carrier集合。readerが一時的に導出し、完全置換だけを許す。

**Observation**:
GitHubから取得したcomment、branch、PR、checkなどのfact。Recordとは別にreaderが導出する。

**Live Branch Binding**:
Startが宣言したbranch名と、Issue repositoryで観測されたbranchとの対応。mutableなObservationであり、Startのhistorical factとは区別される。

**PR Candidate**:
Startのbranch名とIssue repositoryから一時的に導出されたsame-repository PR。Doneによる明示binding前のtentativeなObservationである。

**Bound PR**:
Doneの`pr_ref`が明示する特定のPR identity。後のbranch名再利用では変更されない。

**Stale Done**:
Recordとしてはvalidだが、宣言したsource head SHAがBound PRの現在またはmerge対象のsource head SHAと一致しなくなったDone。

**Successor Issue**:
Superseded Stopが参照する、同じrepository内でsource Issueより後、Stop以前に作成された別Issue。

**Halt**:
GitHub履歴とObservationsから特定のprotocol transitionを一意に導出できず、そのtransitionを進めない状態。agent全体の停止命令や操作権限の否定ではない。

**Terminal Result**:
prefix-valid Stopまたは、Done Claimが対象とするsource headのnative mergeによって確定した、taskの中止または完了という結果。

**Terminal Dependency**:
Terminal Resultを現在のsnapshotから証明するために必要なCarrier、Bound PR、Evidence、またはSuccessor Issue。永久に失われてもterminal後のRecordで差し替えない。

**Late Done**:
PR merge後に投稿され、その投稿時点のprefixでEvidence付きDone ClaimとTerminal Resultを成立させるDone。

**Done Terminal At**:
Done comment、Bound PR merge、参照するCheck Run完了のすべてが成立した最も遅いserver-owned時刻。

**Projection**:
protocol semanticsから導出したfactの人向けまたはmachine向け表現。表示shape自体はprotocol stateやRecordではない。

**Core Transition Token**:
readerのstateまたは許可されるrepair transitionを変えるclosed vocabularyの識別子。
