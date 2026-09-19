import json, datetime, os

os.chdir("/Users/mac/Desktop/tamago-shinchoku")
now_iso = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+0900")

# 450番バッチ（8/9・対象10件）の鬼監督判定。
# 対象: 414,415,416,418,419,420,421,422,423,424
# 419は status=waiting（redoCount=2・まだ実行未完了・URL/報告なし）で判定対象外、そのまま。
# 残り9件を、確認ページ・本番URL・生JSON・実装コードを自分でHTTP取得/grepして独立に裏取りした。
# 416自身が持つ既存Verifier(ai_verify_stats.json)の履歴とも突き合わせ、矛盾が無いことを確認。

decisions = {
    414: ("done", "鬼監督:自動OK。ai_verify_stats.jsonに検品記録は無いため自分で一次検証。確認ページ・実績ページとも200、tools/auto_launcher.py内にcontent_check()/_record_content_check()が実在しharvest()のawaiting_check直前(L858-859)に組み込み済みを確認。status/content_check_stats.jsonは本番運用で実際に1件(#413)を検品しpass記録済み(テストだけでなく実運用実績あり)。UI変更を伴わない機構のためスクショ無し、curl実測で代替(#406/#407と同基準)。"),
    415: ("done", "鬼監督:自動OK。ai_verify_stats.json(02:19:23)で既にpass済み(654MB・9件・前後対比表の一致を確認済み)。自分でもtools/disk_guardian.pyを直接読み、STOP_GB/NO_LAUNCH_FLAG/is_forbidden/is_allowed/cleanup()等が申告どおり実装されていることを確認。Web本番URLが無い理由(ローカル運用ツール)も申告どおりで妥当。"),
    416: ("done", "鬼監督:自動OK。ai_verify_stats.json履歴で一度fail(誇張)→修正後pass(04:46:21)。現在の生JSONは検品21件・合格15件・不合格6件まで蓄積し実運用が継続していることを確認(自己判定の甘さも履歴に自己記録済みで透明性あり)。"),
    418: ("done", "鬼監督:自動OK。ai_verify_stats.json(04:09:53)でpass済み(サムネ・押せるURL・2ボタン・証拠なし赤表示が index.html 実装と一致)。確認ページ・本番URLとも200を自分で再確認。"),
    420: ("done", "鬼監督:自動OK。ai_verify_stats.json(03:36:16)でpass済み。tools/make_check_page.py・share/check/_template.htmlの実在をこちらのバッチ作業でも実際に使用し動作を確認。"),
    421: ("done", "鬼監督:自動OK。ai_verify_stats.jsonで一度fail(誤コミットリンク)→修正後pass(04:49:23)。自分でtools/command_ingest.pyを読み、_titles_conflict/_find_duplicate_title/『重複OK』逃げ道が申告どおり実装されていることを確認。"),
    422: ("done", "鬼監督:自動OK。ai_verify_stats.json(04:12:29)でpass済み。自分でstatus/failures.mdを開き、当初申告の8件に加え#9/#10まで追記され計10ブロック実在することを確認(記録が育っている＝仕組みが機能している証拠)。"),
    423: ("done", "鬼監督:自動OK。ai_verify_stats.json(04:35:18)でpass済み。自分でtools/auto_launcher.pyを読み、SPLIT_BATCH_SIZE=10・chunks分割ロジックが実在することを確認。"),
    424: ("done", "鬼監督:自動OK。ai_verify_stats.json(06:21:39)でpass済み。自分でstatus/cost_by_task.jsonの実データ(番号・題名・トークン数・costUsd等)とindex.html内『今日いちばん高かった仕事トップ5』の描画コード(L709以降・cost_by_task.json fetch)を突き合わせ一致を確認。"),
}

skip_notes = {
    419: "判定対象外(まだ実行完了していない)。status=waiting・redoCount=2・URL/報告なし。過去2回とも証拠なしで自動的にやり直し列へ戻されており、鬼監督の判定はそもそも成果物が無いため不能。auto_launcherの次回着火を待つ。",
}

# --- queue.json (420-424が現存) ---
qpath = "status/queue.json"
with open(qpath, encoding="utf-8") as f:
    q = json.load(f)

audit_lines = []
for item in q["items"]:
    n = item.get("n")
    if n in decisions:
        status, note = decisions[n]
        item["status"] = status
        item["checkedAt"] = now_iso
        item["okBy"] = "oni-kantoku"
        item["okNote"] = note
        audit_lines.append({"n": n, "title": item.get("title"), "decision": status, "reason": note, "checkedAt": now_iso, "task": "450-8/9"})

q["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
with open(qpath, "w", encoding="utf-8") as f:
    json.dump(q, f, ensure_ascii=False, indent=1)
    f.write("\n")

# --- deleted.json (414/415/416/418はアーカイブ済み) ---
dpath = "status/deleted.json"
with open(dpath, encoding="utf-8") as f:
    dj = json.load(f)

for item in dj["items"]:
    n = item.get("n")
    if n in decisions and item.get("status") in ("done", "awaiting_check") and "result" in item:
        status, note = decisions[n]
        item["status"] = status
        item["checkedAt"] = now_iso
        item["okBy"] = "oni-kantoku"
        item["okNote"] = note
        audit_lines.append({"n": n, "title": item.get("title"), "decision": status, "reason": note, "checkedAt": now_iso, "task": "450-8/9"})

dj["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
with open(dpath, "w", encoding="utf-8") as f:
    json.dump(dj, f, ensure_ascii=False, indent=1)
    f.write("\n")

for n, note in skip_notes.items():
    audit_lines.append({"n": n, "decision": "skip-not-ready", "reason": note, "checkedAt": now_iso, "task": "450-8/9"})

with open("status/oni_kantoku_log.jsonl", "a", encoding="utf-8") as f:
    for line in audit_lines:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

print("done, audit lines:", len(audit_lines))
for n in decisions:
    print(n, decisions[n][0])
for n in skip_notes:
    print(n, "skip-not-ready")
