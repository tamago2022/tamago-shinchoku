# 進捗表の題名を「何をする仕事か」1行に戻す（2026-10-01）

URL：https://tamago2022.github.io/tamago-shinchoku/ （1本のまま・新ページは作らない）

## どこで壊れたか
- 前の良い題名＝Dispatch が queue_add に手で渡していた短い label。
- 自動で積む係（判定日赤の繰り上げ・kioku 取り込み）が label にたまごさんの発言そのものを入れるようになり、そのまま題名に出ていた。

## 進捗
- [x] tools/hyoudai.py：表示用1行（item.hyoudai）を作る係。機械掃除＋AI書き直し
- [x] command_ingest.queue_add：積んだ瞬間に hyoudai（rule）を付ける → 今後の追加も自動
- [x] heartbeat.sh：約10分おきに hyoudai.py --fill（AIで書き直し、走っている→次に発車の順）
- [x] top_status.py / build_queue_light.py：hyoudai を公開JSONへ。実データで確認済（例「Grok Realtime Voice機能を埋め込む」）
- [x] index.html：題名＝hyoudai、原文は押すと開く畳みの中
- [x] 「1,980件ほか」→「残っている仕事 1,980」（18:50 修正・commit_inbox で載せ待ち）
- [x] hyoudai.py の良い例に「次に発射、差し戻し最優先」を追加
- [x] index_full.html（前の進捗表）：本番で開くことを確認
- [ ] スマホ幅の目視：指定のChrome（7d965dae）がつながっておらず未実施。次のセッションで確認
