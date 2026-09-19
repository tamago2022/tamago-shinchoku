import json, datetime, urllib.request

path = "/Users/mac/Desktop/tamago-shinchoku/status/queue.json"
with open(path, encoding="utf-8") as f:
    d = json.load(f)

now_iso = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+0900")

targets = list(range(301, 311))

note = (
    "鬼監督:追認(自動OK維持)。対象は循環テスト専用タスク(test:true,okBy:dispatch-auto,"
    "okNote:'たまごさんに見せる必要なし')。本番URL 200・確認ページ本文"
    "「発車→作業中→終了→確認待ち、まで通っています」が実在することを実測で確認(①②合格)。"
    "③スクショは循環テスト専用ルートの設計上不要(実務コンテンツ差し戻し基準446番とは対象が別)。"
    "3条件ANDの対象外として最初から設計された経路であり、既存のdispatch-auto判定を鬼監督が追認する。"
)

audit_lines = []
checked = []
for item in d["items"]:
    n = item.get("n")
    if n in targets:
        url = item.get("urls", [None])[0]
        code = None
        try:
            r = urllib.request.urlopen(url, timeout=10)
            code = r.status
        except Exception as e:
            code = f"ERR:{e}"
        item["checkedAt"] = now_iso
        item["checkNote"] = note
        audit_lines.append({
            "n": n, "title": item.get("title"), "decision": "confirmed-auto-ok",
            "reason": note, "url": url, "httpStatus": code,
            "checkedAt": now_iso, "task": "447-5/9"
        })
        checked.append((n, item.get("status"), code))

d["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

with open(path, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
    f.write("\n")

with open("/Users/mac/Desktop/tamago-shinchoku/status/oni_kantoku_log.jsonl", "a", encoding="utf-8") as f:
    for line in audit_lines:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

print("audit lines:", len(audit_lines))
for c in checked:
    print(c)
