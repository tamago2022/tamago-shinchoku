#!/usr/bin/env python3
"""受付台帳_自動記録.md から「たまごさんが言ったこと」だけを拾って said.js を作る。
埋もれて消えるのを防ぐための受け皿。実行: python3 build_said.py（そのあと git push）"""
import re, json, pathlib

SRC = pathlib.Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain/AI出力/_ルール/受付台帳_自動記録.md"
OUT = pathlib.Path(__file__).with_name("said.js")
LIMIT = 60

rows = []
for line in SRC.read_text(encoding="utf-8").splitlines():
    m = re.match(r"^\|\s*(\d\d-\d\d \d\d:\d\d)\s*\|\s*(.*?)\s*\|\s*$", line)
    if not m:
        continue
    when, text = m.group(1), m.group(2)
    if text.startswith("<") or "scheduled-task" in text or "task-notification" in text:
        continue  # 機械の通知は除外
    # たまごさん本人の言葉を優先して拾う（「たまごさんから:「…」」の形）
    q = re.search(r"たまごさん(?:から|の言葉|から追加の[^:：「]*|の要求)[^「:：]{0,12}[:：]?\s*「(.+?)」", text)
    if q:
        said = q.group(1)
    else:
        # 「たまごさんの言葉:」のあとに引用行（> …）が続く形
        b = re.search(r"たまごさんの言葉[:：]?\s*⏎\s*>\s*(.+?)(?:\s*⏎\s*⏎|\s*⏎\s*【|$)", text)
        if not b:
            continue
        said = re.sub(r"\s*⏎\s*>\s*", " ", b.group(1))
    said = re.sub(r"\*\*", "", said).strip()
    if len(said) > 220:
        said = said[:220] + "…"
    rows.append({"when": when, "said": said})

rows = rows[-LIMIT:][::-1]  # 新しい順
OUT.write_text("// 受付台帳_自動記録.md から build_said.py が作る。手で編集しない。\nwindow.SHINCHOKU_SAID = "
               + json.dumps(rows, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
print(f"said.js: {len(rows)}件")
