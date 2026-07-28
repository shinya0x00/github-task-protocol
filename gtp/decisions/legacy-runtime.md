## 未決定事項

公開済み1.xとPython runtimeを、2.0のmainへ複製または隔離して残すか、公開tagへ固定してmainから除くか。

## 採用した手段

公開済み1.xはtag、GitHub Release、PyPIへ変更せず残す。mainには案内だけを置き、2.0から参照されないPython runtime、package、test、acceptance、CIはmainから除く。
