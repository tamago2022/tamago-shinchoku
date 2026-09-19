import json, datetime, os

os.chdir("/Users/mac/Desktop/tamago-shinchoku")
path = "status/queue.json"
with open(path, encoding="utf-8") as f:
    d = json.load(f)

now_iso = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+0900")

# 443番バッチ（1/9・対象10件）の鬼監督最終判定。
# 37/34/8/41/9/28/27/3 は、私が着手する前に既に「done」化済み（人間の実タップ or 既存AI検品パイプラインのPASS）。
# 216/25 だけが status=awaiting_check のまま残っていたため、今回あらためて実データで再検品した。
decisions = {
    216: ("done", "鬼監督:自動OK。ai_verify_stats.json記録済みのAI検品PASS(07:35:30・$0.328)に加え、自分でも本番2URLをcurlで再実測。bee-gees側HTMLに'your-face-sounds-familiar-kids'/'too-much-heaven-kids-cover'への言及、kids側HTMLに originalRef:{artistId:\"bee-gees\",songId:\"too-much-heaven\"} を実データで確認、双方向リンク成立を確認した。"),
    25: ("done", "鬼監督:自動OK。origin/main(HEAD 17074e76)にd5f91a6cが祖先として実在し、src/lib/aiImageTextureGuides.tsのSTOPMOTION_PUPPET_TEXTURE_GUIDE(8項目の質感指定を全て含む)がsrc/lib/henshin.functions.tsのプロンプト生成に実配線されていることをgit showで確認。本番/room/henshinのJSチャンク(room.henshin-*.js)に'人形劇の救助隊員'テーマ(style:\"stopmotion\")が実在することをcurlで確認。テンプレ本体はサーバ関数側のみで使われる設計のためクライアントJSに文字列が出ないのは仕様どおり(誤検知ではない)。"),
}

audit_lines = []
for item in d["items"]:
    n = item.get("n")
    if n in decisions:
        status, note = decisions[n]
        item["status"] = status
        item["checkedAt"] = now_iso
        item["okBy"] = "oni-kantoku"
        item["okNote"] = note
        audit_lines.append({"n": n, "title": item.get("title"), "decision": status, "reason": note, "checkedAt": now_iso, "task": "443-1/9"})

d["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

with open(path, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
    f.write("\n")

with open("status/oni_kantoku_log.jsonl", "a", encoding="utf-8") as f:
    for line in audit_lines:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

print("done, audit lines:", len(audit_lines))
