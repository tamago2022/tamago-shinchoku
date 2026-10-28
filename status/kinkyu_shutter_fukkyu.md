# 緊急停止（シャッター）の復旧手順

- 状態確認: `python3 tools/kinkyu_shutter.py --status`（ON＝停止中）
- 止まる範囲: 受付（queue_add）と発車（auto_launcher）。理由はフラグ `status/KINKYU_SHUTTER` の中身と Dispatch の通報にある。
- 解除は店主だけ。AIは解除しない（このツールに解除機能は無い）。
  1. 保留された命令文 `status/kinkyu_hold.jsonl` と通報を読み、本物の攻撃か、会話要約の紛れ込みかを判断する。
  2. 問題なければ店主が `status/KINKYU_SHUTTER` を手で消す。
  3. 設定の変化で立った場合は、正当な変更なら `python3 tools/kinkyu_shutter.py --baseline` で基準を書き直す。
- 保留した番号を再開するには、queue.json の該当票の status を waiting に戻す（店主確認後）。
