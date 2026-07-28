## 未決定事項

pull request本文とcommit trailerからDecision Recordを参照するとき、どのtreeを基準にpathを解決し、複数の判断をどう表すか。

## 採用した手段

pull request本文のrepository-relative pathはPR headのtreeを基準とし、merge後は同じpathをmainのtreeから参照する。`Decision-Ref`はcommitのtree上で解決できるpathを1件につき1行置き、参照先が同じcommitのdiffに含まれることは要求しない。
