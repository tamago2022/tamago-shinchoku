import json, datetime

path = "status/queue.json"
with open(path, encoding="utf-8") as f:
    d = json.load(f)

now_iso = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+0900")

decisions = {
    16: ("done", "鬼監督:自動OK。確認ページ200・分析報告(捨てて良い37/陳腐化疑い35/反映候補83/要精査61=216本、内訳CSV・compareリンク実在)を実測。実削除は元々スコープ外と明記済み。"),
    26: ("done", "鬼監督:自動OK。確認ページ内の判定表(9件中PASS6/FAIL3)を実測、PASS根拠のうち3件(ハナレグミ↔サントリー双方向・食レーダー・The Knack)の本番URLをcurlで200確認。"),
    31: ("done", "鬼監督:自動OK。本番の進捗表(index.html)にobsidian://new経由のqueue_ok/queue_redo実装コード実在、Mac側command_ingest.pyにqueue_ok/queue_redoハンドラ実在を確認。"),
    33: ("done", "鬼監督:自動OK。本番の進捗表(index.html)にスマホからの新規タスク入力欄(queue_add)実装コード実在、Mac側command_ingest.pyにqueue_addハンドラ実在を確認。"),
    40: ("done", "鬼監督:自動OK。双方向リンクを本番HTMLで実測(畠山美由紀『故郷』⇄スウェーデンの旅カード、はなれぐみ『家族の風景』⇄イタリアアルプスの旅カード、両方向とも相手の語を検出)。"),
    35: ("hold", "鬼監督:自動OK不可・エスカレーション。Google Drive更新版アプリの/Applicationsへの設置はAI安全装置が全経路ブロック済み(2回目)。円卓デザインフォルダも未発見。たまごさん本人の1回の操作が必要（判断ではなく実行権限の壁）。"),
}

audit_lines = []
for item in d["items"]:
    n = item.get("n")
    if n in decisions:
        status, note = decisions[n]
        item["status"] = status
        item["checkedAt"] = now_iso
        item["checkNote"] = note
        audit_lines.append({"n": n, "title": item.get("title"), "decision": status, "reason": note, "checkedAt": now_iso, "task": "445-3/9"})

d["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

with open(path, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
    f.write("\n")

with open("status/oni_kantoku_log.jsonl", "a", encoding="utf-8") as f:
    for line in audit_lines:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

print("done, audit lines:", len(audit_lines))
