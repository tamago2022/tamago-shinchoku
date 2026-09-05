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
