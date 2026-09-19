import json, datetime

import os
os.chdir("/Users/mac/Desktop/tamago-shinchoku")
path = "status/queue.json"
with open(path, encoding="utf-8") as f:
    d = json.load(f)

now_iso = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+0900")

decisions = {
    42: ("done", "鬼監督:自動OK。確認ページ200・コミットe8768c75実在。本番3件をcurlで独立再取得しはるみ節/志村正彦/サグネ発の覆面ロックデュオを実測確認。スクショ無しだが理由(店主画面を邪魔しない運用)が明記され本番実データで代替済み。"),
    48: ("done", "鬼監督:自動OK。ローカルscheduled-tasks.jsonを直接読みenabled:trueを実測、lastRunAt=2026-09-05T23:14:57Zで確認ページ記載(00:44)より新しい30分毎稼働を確認。SKILL.mdの停止ブロック撤去も実物確認。"),
    113: ("done", "鬼監督:自動OK。カバー側/原曲側の本番URL2本をnode fetchで独立再取得し、この流れで広がったカバー/2095328423782846561/日本の高校生ジャズバンドの双方向リンクを実測確認。スクショ無しだが理由(ブラウザ道具なし)明記の上で本番実データ代替。"),
    213: ("done", "鬼監督:自動OK。本番の曲ページ(bee-gees/too-much-heaven)をcurlで独立再取得し、Your Face Sounds Familiar/too-much-heaven/no_earthquakeを実測確認。"),
    214: ("done", "鬼監督:自動OK。前セッションが「mainへの反映を確認できなかった」と正直に書いていた点を、git merge-base --is-ancestorとgit show origin/main:で独立検証しcbddb94bがorigin/mainに実在・ファイル内容も一致することを確認。UI変化なしの運用ツール追加という報告内容と整合。"),
}

audit_lines = []
for item in d["items"]:
    n = item.get("n")
    if n in decisions:
        status, note = decisions[n]
        item["status"] = status
        item["checkedAt"] = now_iso
        item["checkNote"] = note
        audit_lines.append({"n": n, "title": item.get("title"), "decision": status, "reason": note, "checkedAt": now_iso, "task": "446-4/9"})

d["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

with open(path, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
    f.write("\n")

with open("status/oni_kantoku_log.jsonl", "a", encoding="utf-8") as f:
    for line in audit_lines:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

print("done, audit lines:", len(audit_lines))
