#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""930番(4/7)：awaiting_check 10件を鬼監督基準で仕分けてqueue.jsonへ反映する。
   直接queue.jsonを書かず、queue_store.py経由(差分マージ・世代バックアップ付き)で書く。
"""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import queue_store as qs

now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

# (b) 鬼監督PASS→done化
DONE = {
    726: "【930番棚卸し・2026-09-17】鬼監督判定PASS。queue_light.json分離を実測確認(本番transfer 1,477,174→74,420バイト・95%減、遅い回線27.80秒→2.16秒、初回表示32.13秒→6.49秒、9項目すべてPASS、確認ページshare/check/726-queue-light.html)。技術的事実確認のみで店主の好み判断は不要のため完了扱い。",
    796: "【930番棚卸し・2026-09-17】鬼監督判定PASS。進捗表のぐるぐる読み込み・週の目盛り食い違いを実測修正確認(本来ここ80.0%=使用率80.0%で一致・以前は64.0%と食い違っていた、9箇所に前回比較ガード追加、410本のログを退避、確認ページshare/check/796-shinchoku-loading-loop-fix.html)。技術的事実確認のみで完了扱い。",
    802: "【930番棚卸し・2026-09-17】鬼監督判定PASS。できたもの284件→開いた瞬間5件だけに削減、裏方213件は畳んで温存(0件削除なし)、判断待ちバナーを最上部に常時表示。実測・前後スクショあり(確認ページshare/check/802-dekimono-read-less.html)。店主の言葉『理屈は分からないけど治ったんだねで判断する』の対象であり、③の画像で数の激減が確認できるため完了扱い。",
    884: "【930番棚卸し・2026-09-17】鬼監督判定PASS。machine_load.sh参照切れを修正しmainへ反映(commit ba42a286c)、本番health.jsonのload/diskFreeGBがnullから実数に復帰、heartbeat.logの🚨🚨💤が19:20:54を最後に71分以上再発なしを本番実測(確認ページshare/check/884-machine-load-restore.html)。原因特定→修正→本番実測確認まで完結しており完了扱い。",
}

# (c) 完了目的が上位案件に吸収された→hold化
HOLD = {
    719: "【930番棚卸し・2026-09-17】719番(デスクトップ整理+iMac HDD引っ越し、7回目・09-11時点で空き84GB/目標100GB未達)は、より新しく包括的な876番(容量最優先・2026-09-15、空き容量33.2GBまで回復・Googleドライブのミラーモード/tmp.driveuploadキューという真犯人を特定・worktree残骸削除・自動化接続まで実施済み)に実質統合された。719番単独での継続調査は不要と判断しholdへ。iMacへの追加移動候補は876番側で店主のOK待ちとして継続する。",
    731: "【930番棚卸し・2026-09-17】731番(719番の検証=移動したもの19件中18件の行き先確認、ZoomRecordingsのみ未発見)は、719番自体が876番に実質統合されたため、残りの厳密一致証明・ZoomRecordings追跡の優先度は低いと判断しholdへ。容量まわりの調査は876番の継続として扱う。",
}

# (a) 店主にしか判断できない→判断待ちのまま残す(理由だけ result 相当のnoteとして残すため何もステータス変更しないが、追跡用に一覧化)
KEEP_FOR_OWNER = {
    734: "写真(静止画)2件を食べ物棚に追加・本番反映済み(curlでHTTP200確認、確認ページshare/check/734-photo-cards-food-shelf.html)。『実物を見てどう見えるか、たまごさんが見て決める』という実験が目的のため、実装完了後の見た目の可否判断は店主のみ可能。",
    771: "ltx-2.5 fast海辺1本の実費は計算値8.22円まで確定・カメラ固定もスタビライズで達成(確認ページshare/check/771-ltx25-mist-oneway-cost.html)。fal.ai公式Billing APIは403(admin権限不足)で実測不能、たまごさん本人にしかできない1点(admin scope APIキー発行 or 生成前後で一度だけダッシュボード確認)が必要なため判断待ちのまま残す。",
    792: "亮太さん向けパーソナライズページの実プレイリスト反映はmainマージ済み(commit 7a523a65)だが、環境I/O遅延でLovable公開が未完了(30分おき自動便待ち)。かつ『好きそうで知らないものが出せているか』の実演確認自体が店主にしかできないテストのため判断待ちのまま残す。",
    876: "容量調査・掃除・自動化接続は完了(空き33.2GB回復・目標30GB達成、worktree残骸44件削除、日次自動化接続済み、確認ページshare/check/876-yoryou.html)。Googleドライブのミラーモード→ストリーミング切替(69GB解放見込み)・.tmp.driveuploadキューの再起動・iMacへ逃がす候補の実行はいずれもGUI操作か店主のOKが必要なため判断待ちのまま残す。",
}

q = qs.load_queue()
snap = qs.snapshot_items(q)
items = q["items"]

changed = []
for it in items:
    n = it.get("n")
    if n in DONE:
        it["status"] = "done"
        it["finishedAt"] = now
        prev = it.get("result") or ""
        it["result"] = (prev + "\n\n" if prev else "") + DONE[n]
        changed.append((n, "done"))
    elif n in HOLD:
        it["status"] = "hold"
        it["holdNote"] = HOLD[n]
        changed.append((n, "hold"))

ok = qs.save_queue(q, snapshot=snap)
print("save_queue ok:", ok)
for n, st in changed:
    print(f"n={n} -> {st}")

print()
print("判断待ちに残した件数:", len(KEEP_FOR_OWNER))
for n in KEEP_FOR_OWNER:
    print(" -", n)
