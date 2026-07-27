# v1.0.4 plain-first human probe

Status: accepted

Candidate: package `1.0.4` / protocol `1.1` / [PR #141](https://github.com/shinya0x00/github-task-protocol/pull/141)

Reader boundary: 実装と文言作成に参加せず、README、GitHub上のPR本文、提示された複合halt出力だけを読んだ新規contextの独立Agentが回答した。実在の人間による調査ではない。

回答者への追加説明は行わず、次の5点を自分の言葉で説明できるか確認した。

1. 具体的に何が起きたか
2. 最初に何を確認するか
3. merge前に何を直す必要があるか
4. 何を勝手に変更してはいけないか
5. 表示がmergeや公開を禁止または許可するか

## 提示した複合halt

Presented SHA-256: `0bb8868ac72ef62bffd3d1f234c50240c0bddbef4913f90a3ffed28f5dfc3e9b`

```text
問題の整理:
  1. 何が問題か: 完了条件を追加した後にPRの内容が変わり、前回のDoneでは現在の完成候補を確認できません
  2. どこが問題か: 前回のDone、追加後の現在の完了条件、現在のPRの最新commit、条件ごとの確認資料
  3. なぜそう判断したか: 前回のDoneと確認資料は変更前のcommitを指しています。その後、完了条件が追加され、PRの最新commitも変わりました
  4. どこを直すか: まず現在のPRの内容が追加後の現在の完了条件を満たすか人が確認する。merge前なら必要なPR修正を行い、現在のPRの最新commitについて、すべての完了条件の確認資料をそろえてDoneを出し直す
  5. 何を直さないか: 過去のDone、確認資料のURL、commit履歴を書き換えない。PRの内容が完了条件を満たすかをGTPだけで決めない
  6. 次の安全な一手: 最初のURLを開き、追加後の現在の完了条件、前回のDone、現在のPRの最新commit、条件ごとの確認資料をread-onlyで比べる
  7. 最初に確認するURL: https://github.com/o/r/issues/1#issuecomment-103
  8. 解決したと判断する条件: 追加後の現在の完了条件に合わせ、現在のPRの最新commitについて、すべての完了条件の確認資料をそろえたDoneを出し直すと、このhaltが消える。merge済みなら同じIssueではDoneを出し直せない
```

## 独立読者の回答

1. 完了条件を追加した後にPRの最新commitも変わったため、前回のDoneと確認資料が古いcommitを指し、現在の完成候補を確認できなくなった。
2. 最初のURLを開き、追加後の現在の完了条件、前回のDone、現在のPRの最新commit、条件ごとの確認資料をread-onlyで比較する。
3. 人が現在のPR内容を全完了条件と照合し、不足があればPRを直す。その後、最新commitについて全条件の確認資料をそろえ、merge前にDoneを出し直す。
4. 過去のDone、確認資料のURL、commit履歴を書き換えない。PRが条件を満たすかをGTPだけで決めず、既存instructionsやrulesも勝手に変えない。
5. `halt`はmergeや公開の禁止命令でも許可でもない。最終判断は人間が行う。

## 反復と限界

最初のreadでは代表出力を提示せず、PR修正が常に必要かが曖昧だった。同じPR内で、人が条件充足を判断し、必要な場合だけPRを直すという文へ修正した。その実出力を加え、別の独立読者で再確認した。

独立読者は5点すべてに回答できた。実際の完了条件とPR内容は入力に含めていないため、PR修正が本当に必要か、条件が満たされたかはこのprobeでは判断しない。例示URLの内容とmerge後の別作業も確認していない。この限界は、GTPが条件充足、merge、公開を人間の代わりに決めない境界と一致する。

---

# Issue／PR producer external human probe

Status: accepted

Targets:

- Issue: https://github.com/agent-operated/cyan-tigers/issues/5
- PR-only: https://github.com/agent-operated/cyan-tigers/pull/6

Reader boundary: 各artifactごとに`fork_turns: none`のfresh sub-agentを起動した。与えたのは「非エンジニアとして、理解したことと分からなかった点を説明する」というroleとURL 1件だけである。期待回答、確認項目、GTPの説明、実装contextは与えていない。

## Issue

最初のreaderは目的、完了条件、非許可境界を説明できたが、投稿後GETが完了済みか本文から分からないと指摘した。同じIssue本文の現在地を置き換え、別のfresh readerへ同じURLだけを渡した。

修正後readerは、次を説明できた。

- ソフトウェア開発ではなく、実際に投稿されたIssue本文を非エンジニアが理解できるかの確認である。
- 投稿前checkと投稿後の本文一致は完了している。
- 最初のfindingを受けて本文を修正し、別readerで確認する現在地である。
- 読解後にIssueをcloseしてURLを残す。
- この結果は作業、merge、公開を禁止も許可もしない。

Decision record追加後も、同じclosed Issueの本文を投稿前checkし、GitHubへeditした後に再取得した。入力と再取得本文のSHA-256はともに`b02e2b58578c3f5a4871c712e411b545aee5a1a48f138570c8a8c975e2a1cc4c`だった。fresh readerはURLだけから、通常の投稿経路を使って本文一致を確認する方針、template／workflow／required check／常駐botを導入しない境界、このIssueがmergeや公開を決めないことを説明できた。検査の内部手順や根拠を同じURLだけで独立検証できないことはunknownとして残した。

## PR-only

最初の2 readerは全体目的と非許可境界を説明できたが、READMEを変更材料にする理由、現在地、合格基準、titleの関係が曖昧と指摘した。同じPRでtitleと本文の現在地を置き換え、古い進捗を先頭へ積まず、3人目のfresh readerへURLだけを渡した。

修正後readerは、次を説明できた。

- 製品機能ではなく、非エンジニアがPR URLだけで理解できるかの受け入れ確認である。
- PRを実際に作るための安全な比較材料としてREADME 1 fileを追加した。
- mainは変わらず、この受け入れPRはmergeせずcloseする。
- 投稿内容とGET本文の一致を2回確認し、残る確認は独立readerだった。
- 人が判断するのは目的、変更、影響、現在地、unknownと、読解合格をmerge／公開許可から分けられるかである。

## 結果と限界

IssueとPRのreaderは、目的、現在地、次の判断、非許可境界をURLだけから説明できた。PR readerは変更fileも読み、本文の目的と実diffを対応付けた。受け入れ後、IssueとPRをcloseし、PRが未mergeであることをGETで確認した。

readerは実在の人間ではなくAgentであり、一つの日本語artifactと観測時点に限られる。Decision record更新後の2人目のretry readerは、自身のGitHub取得経路でprivate repositoryを404として取得できず、本文を評価しなかった。このretryを読解成功数へ数えず、URL-only probeはreader側の閲覧権限にも依存する限界として残す。checker内部、cyan-tigersの製品用途、実製品のmerge／公開ownerは受け入れ対象外であり、理解済みとClaimしない。ユーザーがmerge後に独立実projectで行う手動品質確認は、このprobeでは未実施である。
