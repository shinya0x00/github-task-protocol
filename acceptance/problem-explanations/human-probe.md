# 修復後の短いhuman probe

Status: accepted

Candidate: `46103e0fdd41364f98e098518f6b91211fb1f5ea` / CLI `1.0.3`

回答者へ: 分かりにくい表現があれば、その箇所だけを指摘してください。全項目の回答や言い換えは不要です。A／Bとも判断に必要な分かりにくさがなければ「問題なし」と回答してください。

## A. GTP記録を一意に確定できない

1. 何が問題か: GTP Recordの形式、内容、編集状態のいずれかが不正です
2. どこが問題か: 対象IssueのGTP記録があるcomment
3. なぜそう判断したか: Issue commentを、変更されていない一意のGTP記録として確定できませんでした
4. どこを直すか: 最初のURLのcomment内容を確認し、過去commentは直さず、人間が必要ならStopと後継Issueを選ぶ（修正候補。根本的な修正責任は未確定）
5. 何を直さないか: 過去のIssue commentを編集・削除しない。GTPの仕様を変更しない
6. 次の安全な一手: 最初のURLのcommentと前後のGTP記録をread-onlyで確認する
7. 最初に確認するURL: `https://github.com/o/r/issues/1#issuecomment-101`
8. 解決したと判断する条件: 過去commentを変更せず、人間判断後のvalid Stopで元Issueをstoppedにし、必要なら後継Issueで再開する

回答: 問題なし

## B. PRに変更範囲外のfileがある

1. 何が問題か: PRに、このIssueで変更してよい範囲外のfile `README.md`があります
2. どこが問題か: Issueで変更してよい範囲とbranch・PRの対応
3. なぜそう判断したか: このIssueで変更してよい範囲は`src/`ですが、PRに範囲外のfile `README.md`が含まれています
4. どこを直すか: 範囲外のfileをこのPRから外すか、必要なら通常の後継Issueで扱う（修正候補。最終判断は人間）
5. 何を直さないか: Issueに既に投稿された記録と`GTP.md`の仕様
6. 次の安全な一手: 最初のURLでIssueの変更範囲とPRの変更fileをread-onlyで比較する
7. 最初に確認するURL: `https://github.com/o/r/issues/1#issuecomment-102`
8. 解決したと判断する条件: 再取得でIssueに記録されたbranch、PR、変更範囲の対応を確認できる、または人間判断後に後継Issueへ移る

回答: 問題なし

## 判定欄

- Aの分かりにくい表現: なし
- Bの分かりにくい表現: なし
- Aで「次に確認するもの」と「勝手に変更しないもの」を判断できた: はい
- Bで「次に確認するもの」と「勝手に変更しないもの」を判断できた: はい
- 追加説明なしで受け入れ可能: はい
