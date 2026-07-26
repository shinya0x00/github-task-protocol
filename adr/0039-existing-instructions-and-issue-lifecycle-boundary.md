# ADR-039: 既存instructionsとGTP lifecycleの境界を分離する

- Status: Accepted
- Date: 2026-07-26
- Supersedes: None
- Superseded by: None

## 背景

repository、organization、ユーザーは、GTPとは独立したinstructions、rules、authority boundaryを既に持ち得る。GTPがそれらを一つの固定語彙へまとめて定義すると、GTP自身が運用内容、優先順位、適用条件を所有または検証するように読める。

また、GTP RecordがないIssueとvalid ContractがあるIssueでは、再構成できる詳細が異なる。この差をユーザー選択のmodeとして表すと、GTPを使う前に独自概念への同意を要求し、GitHub上の実際のRecordより自己申告を優先することになる。

## 決定

### 既存instructionsのowner

repository、organization、ユーザーが所有するinstructions、rules、authority boundaryは、それぞれの既存resourceが所有する。`AGENTS.md`などはAgentへinstructionsを伝える媒体であり、GTPは次を定義または判定しない。

- 内容、優先順位、正当性、十分性、実効性
- どの人やAgentが遵守したか
- GTP導入による有効化、無効化、変更

GTP adapterはGTP Recordの読み方だけを伝えるProjectionである。既存instructions全体を代表せず、第二の運用規則にもならない。

setupはtarget file、branch、Issue、PRを変更する前に既存instructionsをread-onlyで取得する。既存内容を保持してadapterだけを非破壊で追加できる場合に続行する。取得不能、外部dependency未接続、明白な意味／authority衝突を観測した場合は、自動統合または上書きせず、そのresourceのownerへ判断を戻す。この確認は既存規則の妥当性検証ではない。

### GTP lifecycleの開始

valid ContractをGTP lifecycleの開始条件とする。ユーザーへmodeやprofileの選択を求めない。

| entry | valid Contractなし | valid Contractあり |
|---|---|---|
| Issue URL | recognized Carrierがなければ`unmanaged`。詳細を推測しない | RecordとGitHub factから通常lifecycleを再構成する |
| PR／通常task | Carrierを自動投稿せず、GTP lifecycleを捏造しない | 関連Issueの既存lifecycleを同じ規則で再構成する |

recognized invalid Carrier、invalid history、Stopなどを既に観測した場合は、valid Contractがないことを理由に無視しない。定義済みの`halt`、`stopped`またはAcquisition Errorを返す。

`unmanaged`は、recognized GTP Carrierがなく詳細なlifecycleを再構成しないことだけを表す。GTPの禁止、既存instructionsの未適用、適合、違反、作業権限を意味しない。

## 理由

GTPの入力をGitHub上のRecordへ限定すれば、入口やAgentごとの自己申告に依存せず、同じhistoryから同じstateを導出できる。既存instructionsのownerを元resourceへ残せば、GTPが運用の主人になる誤解も避けられる。

valid Contractは既にGTPが持つRecordであり、新しいmode、profile、configurationを追加せずにlifecycleの開始を一意に判断できる。

## 検討した代替案

### GTPが既存rulesの内容と優先順位を正準化する

不採用。GTPのRecord解釈を越えてrepositoryやユーザーの運用を所有し、既存ownerと競合する。

### setup時に既存instructionsをGTP形式へ書き換える

不採用。非破壊導入ではなくなり、意味とauthorityを自動変換する必要が生じる。

### ユーザーへmodeまたはprofileを選ばせる

不採用。実際のContract historyより自己申告を優先し、独自用語とconfigurationを増やす。

### Contractがなければinvalid Carrierも無視する

不採用。recognized不適合を通常commentへ降格し、fail-closed境界を壊す。

## 結果と限界

- GTPは既存instructionsを保持し、Record解釈だけを追加できる。
- valid Contractの有無からGTP lifecycleを自動判定し、mode選択を要求しない。
- `unmanaged`から既存rulesの状態や作業authorityを推論しない。
- preflightは取得したresourceとの共存可能性を観測するが、既存instructionsの正しさ、遵守、実効性を証明しない。
