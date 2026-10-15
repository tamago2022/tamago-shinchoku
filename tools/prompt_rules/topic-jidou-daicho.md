## 自動処理を足すなら、台帳に「作るもの・置き場・消す役」を書く（2026-10-16・たまごさん「全部に責任を持て」）
- 心臓（`tools/heartbeat.sh`・`tools/top_status.py`）・launchd・cron・GitHub Actions に新しい自動処理を足すときは、同じ変更で `tools/jidou_daicho.json` に1行足す：`"名前": {"tsukuru": 作るもの, "okiba": 置き場, "kesu": 消す役}`。
- 書いていないと、push は `.githooks/pre-push` で止まり、心臓の相乗りは起動されない（`python3 tools/jidou_tanaoroshi.py --check`）。
- 一時フォルダ・ブラウザのプロフィール・複製・中間ファイルを作る処理は、終わるときに自分で消す。消し忘れの受け皿は `tools/youryou_jougen.py`（使い捨て1時間）・`tools/chukan_shimau.py`・`tools/worktree_taihi.py`。
