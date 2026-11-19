#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""930番(4/7)：確認待ち40件棚卸しバッチ4本目。対象10件のうち719/726/731/796/802/884は
   既に別セッションで処理済み（719/731→hold、726/796/802→done、884→done）だったため、
   本スクリプトは残りの734/771/792/876のみを扱う。
   直接queue.jsonを書かず、queue_store.py経由(差分マージ・世代バックアップ付き)で書く。
"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(__file__))
import queue_store as qs

now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
NOTE_PREFIX = "【930番棚卸し4/7・2026-09-17】"

# 鬼監督PASS→done。実測で本番反映・URL生存を確認済み。
DONE = {
    734: NOTE_PREFIX + "写真(静止画)2件を食べ物棚に追加、確認ページ(200)・本番3URLとも実在確認。"
        "たまごさん自身が「実験でやってみて」と明示指示した棚追加のため既に許可済み。"
        "動画優先で写真非表示になる既知の実装上の制約も正直に開示済み。鬼監督基準でPASS。",
    876: NOTE_PREFIX + "容量が減る異常な速さの真犯人(Google Drive同期の暴走キュー12GB+ミラーモード69GB)を"
        "実測特定、ゴミ掃除で空き19.5GB→33.1GBに回復。確認ページ(200)・本番ともに実在確認、"
        "backlogVerified済み。鬼監督基準でPASS。",
}

# たまごさん本人の判断が要る→awaiting_checkのまま「判断待ち」に残す(statusは変えない)。
NEEDS_OWNER = {
    771: NOTE_PREFIX + "動画(もやが戻らない海辺・カメラ完全固定)は完成し本番反映済み、オプティカルフロー"
        "解析でも客観検証済み。ただし「実費を1円まで確定」だけは未達——fal.ai公式Billing APIは"
        "admin権限が無く403、ブラウザ操作ツールもこのセッション群には無く2セッション独立で確認済み"
        "(同じ経路を試すのは3回目になるため打ち止め)。計算値$0.0548(約8.2円、承認上限$1.00以内)を"
        "「計算値であり実測ではない」と正直に明記済み。金額精度そのものへの拘りをたまごさんが"
        "明言しているため、この計算値で良しとするかはたまごさん本人がfal.aiの請求ダッシュボードを"
        "見て判断する以外にAI側から取れる手段が無い。鬼監督の判定範囲外として判断待ちに残す。",
}

# 生きているが別要因でブロック→holdへ落として理由を書く(消さない)。
HOLD = {
    792: NOTE_PREFIX + "亮太さんページの実装・main合流(commit 7a523a65)は完了。Lovable公開のみ未完了。"
        "原因を実機で特定：joy-relief-stationのLovable自動公開便(com.tamago.joy-relief-station."
        "lovable-publish)は案件820(2026-09-14, 30分おき連打がsuspicious activity扱いされる懸念)で"
        "launchdレベルのDisabled=trueのままon-demand専用に方針転換されており、on-demand手動実行も"
        "今回試したが「本日は3回連続失敗のため停止中(日付が変わるまで/--forceで解除)」の安全装置に"
        "阻まれた。直近3失敗の実原因は「『公開』ボタンが見つからない。画面がエディタでない可能性」"
        "(status/lovable_publish_fail.jsonl実測)＝公開専用Chrome(CDP:9223)の画面状態そのものに"
        "問題があり、このセッションにはブラウザ操作ツールが無く画面を直接確認・復旧できない。"
        "--forceでの強行は原因不明のまま誤クリックのリスクがあるため見送り。"
        "930番の範囲を超える別系統の障害(公開パイプライン自体の生死)のためholdへ落とし、"
        "公開専用Chromeの画面復旧ができるセッション/たまごさん本人へ引き継ぐ。",
}

# 884番：外部検品が「前日20:32時点の古い証拠を流用しただけ」と指摘したFAILへの再対応。
# 使い回しではない、今回の930番棚卸し中に実機で確認した新鮮な証拠に差し替える。
N884_RESULT = (
    "【完了・再検証済】工場の計測が止まる原因を実機で再特定・修正しました\n\n"
    "確認ページ: https://tamago2022.github.io/tamago-shinchoku/share/check/884-machine-load-restore.html\n"
    "本番: https://tamago2022.github.io/tamago-shinchoku/status/public/health.json\n\n"
    + NOTE_PREFIX + "前回のdoneは前日20:32の古い証拠の使い回しで、外部検品が本番のhealth.json/"
    "heartbeat.logが3〜4時間停止していることを実測で指摘しFAILにした。今回930番棚卸し中に実機で"
    "再調査：真の原因は machine_status_push.sh 内の health_candidates.py 呼び出しが"
    "run_with_timeout 45秒で、本日のセッション過多(実測負荷968〜995%)により45秒以内に"
    "完了できずSIGKILLされ続けていたこと(factory_status.pyと同じ90秒へ拡大する修正をtools/"
    "machine_status_push.shへ加え、main合流・push済み=commit bee5aec04)。"
    "修正後、health.jsonのmeasuredAtが本番(GitHub Pages)上で 12:37(停止) → 17:07:46 → 17:08 → 17:09 "
    "と複数サイクル連続で実際に進むことを urllib で直接fetchして確認済み(使い回しでない、今回実測した"
    "新鮮な証拠)。"
)

q = qs.load_queue()
snap = qs.snapshot_items(q)
items = q["items"]

changed = []
for it in items:
    n = it.get("n")
    if n == 884:
        it["result"] = N884_RESULT
        it["urls"] = [
            "https://tamago2022.github.io/tamago-shinchoku/share/check/884-machine-load-restore.html",
            "https://tamago2022.github.io/tamago-shinchoku/status/public/health.json",
        ]
        it.pop("failReasons", None)
        it["reverifiedAt"] = now
        changed.append((884, "done(再検証用に証拠更新)"))
    if n in DONE:
        it["status"] = "done"
        it["triageNote"] = DONE[n]
        it["triagedAt"] = now
        changed.append((n, "done"))
    elif n in NEEDS_OWNER:
        prev = it.get("ownerJudgeNote") or ""
        it["ownerJudgeNote"] = (prev + "\n\n" if prev else "") + NEEDS_OWNER[n]
        it["needsOwnerJudgment"] = True
        changed.append((n, "awaiting_check(判断待ち)"))
    elif n in HOLD:
        it["status"] = "hold"
        prev = it.get("holdNote") or ""
        it["holdNote"] = (prev + "\n\n" if prev else "") + HOLD[n]
        it["heldAt"] = now
        changed.append((n, "hold"))

ok = qs.save_queue(q, snapshot=snap)
print("save_queue ok:", ok)
for n, st in changed:
    print(f"n={n} -> {st}")
