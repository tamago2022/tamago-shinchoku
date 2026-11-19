# 次のセッションへの申し送り（2026-09-18・931番）

※ たまごさん指定の `~/Documents/AI作業/` はこのセッションの接続フォルダ外で書けなかったため、
　 工場の `docs/` に置いた。必要なら `~/Documents/AI作業/` へコピーしてください。

## ★★★ Coworkのサンドボックスから git commit / push をしない

**発見（実測・同じ穴に4回落ちた）：**
サンドボックスはマウント越しに `.git` 配下を**作れるが消せない**（`unlink`＝Operation not permitted）。
gitは「ロックを作る→処理→ロックを消す」で動くので、commit / update-ref のたびに
`HEAD.lock` / `index.lock` / `refs/heads/main.lock` が**必ず取り残される**。

取り残されたロックは**工場全体のgitを止める**（add/commit/pull/push が全て `rc=128`）。
実測：03:00:23 に5分便の `git pull(merge)` が失敗した。

- `git commit` は `.git/COMMIT_EDITMSG` を書いてから読み直すが、その読み直しがマウント越しでは
  `could not read commit message: No such file or directory` で落ちる。
  → `commit-tree` + `update-ref` の配管コマンドが必要になり、その `update-ref` が `HEAD.lock` を残す。
- `push` はできない（サンドボックスに `gh` が無い＝`gh auth git-credential` が引けない）。

**正しい作法：**

```
git add -- <触ったファイルだけをパス指定>     # ← ここまでで止める
```

あとは**Mac側の5分便（`tools/machine_status_push.sh`）が commit → pull → push をやる。**
「積むだけ積んで、押すのはMacに任せる」。

**`git add -A` / `git add .` は絶対にやらない**（他セッションが載せかけている物・`status/` の
生きた台帳・`__pycache__` を巻き込む。queue.jsonが28件/5件/271件消えた3回の事故と同じ経路）。

もう一つ：**他セッションが古いtreeを基にcommitすると、自分が足した行がHEADから消える**
（実測：866号のcommitで `heartbeat.sh` の相乗り行と `INDEX.json` の登録が消えた。作業ツリー側には
残っていたので実動は止まらなかった）。commit後に
`git show HEAD:<file> | grep <自分の行>` でもう一度確認すること。

取り残されたロックは `tools/git_lock_reaper.py` が自動で片付ける（5分放置＋gitプロセス無し、
または15分放置なら走行中でも片付ける）。**それでも最大15分は工場が止まるので、作らないのが一番。**

## ★★★ heartbeat.sh に行を足しても、すぐには効かない

**走っている心臓（bash）はループ本体をメモリに持っているので、心臓が入れ替わるまで
新しい行は実行されない。** 一方 python のファイルは呼び出しごとに読み直される。

→ すぐ効かせたいものは、**毎サイクル必ず呼ばれる `tools/launch_watchdog.py` から呼ぶ。**
（931番では `git_lock_reaper.reap()` と `chrome_tab_sweeper.py` をここから呼んでいる）

5分便（launchd）も当てにしきれない：**実測で21:50〜02:52の約5時間停止していた**
（心臓が15秒おきに蹴り直しを試み続けて、ようやく復活した）。**経路は複数持つこと。**

## ★ ブラウザの振り分け（931番で決めたこと）

**Chromeが要るのは、たまごさんのログインが必要なときだけ**（Lovable・Gmail・Devin・xAIコンソール）。
それ以外（公開ページの実測・ドキュメント閲覧・検証）は**Claudeの内蔵ブラウザ
（`mcp__Claude_Browser__*`）**でやる。あれはClaudeアプリの中のペインなので
**たまごさんのChromeにタブが増えない。**

Chromeを使う場合も：新しいタブを作らない（1枚を `navigate` で使い回す）／同時に1枚まで／
**終わる前に必ず `tabs_close_mcp` で0枚にする。**

- 正本：`tools/prompt_rules/always-21-browser-routing.md`（全セッションへ毎回注入）
- 掃除機（最後の保険）：`tools/chrome_tab_sweeper.py`
- gitロック掃除：`tools/git_lock_reaper.py`
- 設計と実機ログ：工場の `README.md`「ブラウザの振り分けと、Chromeタブの孤児を自分で片付ける」節
