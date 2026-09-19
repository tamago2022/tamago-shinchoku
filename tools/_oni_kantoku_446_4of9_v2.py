import json, datetime

path = "/Users/mac/Desktop/tamago-shinchoku/status/queue.json"
with open(path, encoding="utf-8") as f:
    d = json.load(f)

now_iso = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+0900")
now_disp = datetime.datetime.now().strftime("%m-%d %H:%M")

# 訂正：本番URLの実データは強く裏付けが取れたが、
# 姉妹バッチ(444番)で「スクショが残っている」不履行を理由に鬼監督の自動OKが
# AI Verifierに実際に差し戻された前例(n=20, n=13)を確認した。
# 依頼で定めた必須条件①②③はAND条件であり、①②が強くてもスクショ欠如は自動OK不可と判断し直す。
redo_reason = (
    "鬼監督:差し戻し(訂正)。本番URL・本文一致は独立再検証で確認したが、"
    "確認ページに実物の画面キャプチャ(<img>)が無く、必須条件「③スクショが残っている」を満たさない。"
    "姉妹バッチ444番でAI Verifierが同じ理由(n=20,13)で自動OKを差し戻した実例あり、同基準で統一。"
    "次回はclaude-in-chrome等ブラウザ内蔵のスクリーンショット機能(OSのscreencapture/画面収録は使わない)で"
    "本番ページの実物キャプチャを撮り確認ページに<img>で貼ること。"
)

targets = [42, 48, 113, 213, 214]

audit_lines = []
for item in d["items"]:
    n = item.get("n")
    if n in targets:
        note = f"\n\n【鬼監督差し戻し・{now_disp}】{redo_reason}"
        item["what"] = item.get("what", "") + note
        item["status"] = "waiting"
        item["redoCount"] = item.get("redoCount", 0) + 1
        item["checkedAt"] = now_iso
        item["checkNote"] = redo_reason
        for k in ("startedAt", "finishedAt", "sessionId", "pid", "cutCount"):
            item.pop(k, None)
        audit_lines.append({"n": n, "title": item.get("title"), "decision": "redo", "reason": redo_reason, "checkedAt": now_iso, "task": "446-4/9-correction"})

d["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

with open(path, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
    f.write("\n")

with open("/Users/mac/Desktop/tamago-shinchoku/status/oni_kantoku_log.jsonl", "a", encoding="utf-8") as f:
    for line in audit_lines:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

print("corrected, audit lines:", len(audit_lines))
