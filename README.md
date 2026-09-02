# 進捗表（スマホ用アプリ）

たまごさんがスマホのホーム画面から開くタスク進捗表。ごきげん補給所とは別の独立したアプリ。

- 土台：Obsidian Vault の `AI出力/_ルール/進捗表.html`（2026-09-02 に移植）
- 中身の正本：`data.js`（依頼一覧＋「いま動いているもの」＋TODAY）
- 公開：GitHub Pages（このリポジトリの main をそのまま配信）

## 更新のしかた（AIセッション向け）

1. `data.js` を書き換える（`running` が「いま動いているもの」。手更新でよい）
2. `git commit` → `git push origin main`
3. 数分で公開URLに反映される

リンクは `links:[{label:"…", url:"obsidian://open?vault=tamago_brain&file=<URLエンコードしたパス>"}]` の形で付ける。パスの文字列だけを置かない。
