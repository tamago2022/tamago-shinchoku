# 進捗表（スマホ用アプリ）

たまごさんがスマホのホーム画面から開くタスク進捗表。ごきげん補給所とは別の独立したアプリ。

- 土台：Obsidian Vault の `AI出力/_ルール/進捗表.html`（2026-09-02 に移植）
- 中身の正本：`data.js`（依頼一覧＋「いま動いているもの」＋TODAY）
- 公開：GitHub Pages（このリポジトリの main をそのまま配信）

## 中身

| 場所 | 何か |
|---|---|
| `/`（index.html） | 進捗表アプリ本体（PWA）。いま動いているもの／言ったこと／TODAY／依頼一覧 |
| `data.js` | 依頼一覧・いま動いているもの・TODAY の正本（手更新） |
| `said.js` | たまごさん本人の言葉（埋もれ防止）。**公開ページなので本人の言葉だけを手で選ぶ。**第三者の事情・機密・作業の内幕は載せない |
| `/share/` | ChatGPT等に「このURLを見て」と渡すための共有資料。1資料1ページ、静的HTML、画像はインライン。制作物と検討資料だけ |

## 更新のしかた（AIセッション向け）

1. `data.js` を書き換える（`running` が「いま動いているもの」。手更新でよい）
2. `git commit` → `git push origin main`
3. 数分で公開URLに反映される

リンクは `links:[{label:"…", url:"obsidian://open?vault=tamago_brain&file=<URLエンコードしたパス>"}]` の形で付ける。パスの文字列だけを置かない。

## Dispatchへの完了報告（2026-09-06新設・413番）

子セッションが完了するたびに `tools/auto_launcher.py` の `harvest()` が
`status/dispatch_outbox.jsonl` へ1行追記する（JSON Lines。1行＝1件の完了）。
項目：`ts`（完了時刻）／`n`（番号）／`title`（題名）／`ok`（成否）／
`elapsedMin`（着火〜完了の経過分）／`urls`（本番・確認ページURL）／`result`（報告文の抜粋）。

**Dispatch（たまごさんとの会話）は、会話開始時に次の2ファイルを読み比べて報告する：**

1. `status/dispatch_outbox.jsonl` の全行
2. `status/dispatch_reported.json` の `ns`（すでに報告済みの番号一覧）

`ns` に無い `n` の行だけを「まだ報告していない完了」として、3時間の区切り（`elapsedMin`）が
分かる形でまとめて話す。話し終えたら、報告した `n` を `dispatch_reported.json` の `ns` へ追記する
（読み取り・突き合わせ側は今回新設せず、既存の `ns` 台帳とこの運用手順だけで足りる）。

## お金がかかるタスクの確認（2026-09-09新設・676番）

2026-09-08にfalで15ドル溶けた事故のガード。`tools/cost_risk.py` がタスクの文面（fal.ai／生成API／
課金／有料／ドル／円 など）から自動でお金の匂いを判定し、`status/queue.json` の各項目に
`costsMoney: true`（654番で作った既存フィールドと共用）を立てる。`costsMoney` が立っていて
`costApproved` が無い項目は、**`tools/auto_launcher.py` が絶対に自動発車しない。**

止めた最初の1回だけ、`status/dispatch_outbox.jsonl` に次の形の行を追記する：

```
{"ts": "...", "n": "<番号>-cost", "type": "cost_confirm", "title": "...", "message": "💰お金の確認：..."}
```

**`n` は通常の完了報告（数値）と衝突しないよう文字列 `"<番号>-cost"` にしてある。**
`dispatch_reported.json` の `ns`（数値の配列）とは絶対に一致しないので、これを読んでも
本来の完了報告の既読判定を壊さない。

Dispatch（たまごさんとの会話）は、`type: "cost_confirm"` の行を見つけたら `message` をそのまま
たまごさんに見せて、進捗表の💴マークにある「💰OKで発車を許可」ボタンを押してもらう
（押すと `queue_cost_ok` コマンドが飛び、`costApproved` が立って次の周回で発車する）。
たまごさんの「やってみて」という会話上の一言だけでは発車しない——**必ずこのボタンを押す操作が要る。**

## 優先度A〜E＋F・一括仕分け（2026-09-09新設・682番）

発車待ちの優先度は画面上A〜Eの文字で表示するが、`status/queue.json`の`priority`は昔からの
数字（1=A〜5=E）のまま変えていない。`tools/auto_launcher.py`の`rank()`はこの数字だけを見る。

- **F（優先度6・空き枠）**：「やってほしいが今は枠を使いたくない」もの。`auto_launcher.py`は
  A〜E（優先度1〜5・未設定9）の発車待ちが**1本でも**残っていればFを対象から除外する。
  A〜Eが空の時だけFも発車候補に入る（`has_non_f_waiting`のフィルタ）。
- **一括仕分け**：発車待ちの各行にチェックボックス(`.qsel`)があり、選ぶと画面上部に
  `.qbulkbar`（A〜F・最後尾のボタン）が出る。何件選んでも1タップで全部へ`queue_prio`を送る。
- 実装時の落とし穴は`status/failures.md`の20番（`PRIO_DOT`のスコープ）を参照。
