#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
たまごさんがPWAで付けた優先度（1=今すぐ … 5=後回し）を取り込む（2026-09-03）。

流れ:
  PWA（スマホ）でPを1タップ → 端末内に保存 → 「Obsidianへ送る」1タップで
  obsidian://new が Vault に `AI出力/_ルール/優先度_受信*.md`（JSON）を作る → iCloud で Mac に届く
  → このスクリプト（5分おきの launchd から呼ばれる）が最新の受信ファイルを読んで
     ① status/priority.json に書く（形は whiteboard.py と合わせる: {"priority": {"T004": 1, ...}}）
     ② `whiteboard.py sync` を呼ぶ → ホワイトボード正本の優先度列に入り、status/whiteboard.json（PWAが読む写し）が更新される
  受信ファイルは消さない（ルール）。一番新しいものだけ使う。

PWAが作る受信JSONの形:
  {"updatedAt":"…","prio":{"4":{"p":1,"t":"…"},"21":{"p":3,"t":"…"}}}   キー＝225件リストの番号（= T番号）
"""
import glob
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "status", "priority.json")
VAULT = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
INBOX_GLOB = os.path.join(VAULT, "AI出力", "_ルール", "優先度_受信*.md")
WB_PY = "/Users/mac/Desktop/joy-relief-station/ai-brain/live/whiteboard.py"


def load_json(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def newest_inbox():
    files = glob.glob(INBOX_GLOB)
    if not files:
        return None, None
    files.sort(key=os.path.getmtime)
    p = files[-1]
    try:
        txt = open(p, encoding="utf-8").read()
    except Exception:
        return p, None
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return p, None
    try:
        return p, json.loads(m.group(0))
    except Exception:
        return p, None


def tid(k):
    k = str(k).strip()
    return k if k.startswith("T") else "T%03d" % int(k)


def main():
    cur = load_json(OUT, {})
    stamps = cur.get("stamps") or {}          # {"T004": "ISO時刻"} 新しい方が勝つための記録
    pmap = dict(cur.get("priority") or {})
    src, inc = newest_inbox()
    changed = False
    if inc and isinstance(inc.get("prio"), dict):
        for k, v in inc["prio"].items():
            try:
                t = tid(k); p = int(v.get("p", 0)); ts = str(v.get("t", ""))
            except Exception:
                continue
            if ts < str(stamps.get(t, "")):
                continue
            if p < 1 or p > 5:
                if t in pmap:
                    del pmap[t]; changed = True
                stamps[t] = ts
                continue
            if pmap.get(t) != p:
                pmap[t] = p; changed = True
            stamps[t] = ts
    if changed or not os.path.exists(OUT) or "priority" not in cur:
        out = {"updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "source": os.path.basename(src) if src else None,
               "scale": {"1": "今すぐ", "2": "高", "3": "普通", "4": "低", "5": "後回し"},
               "priority": pmap, "stamps": stamps}
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        tmp = OUT + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        os.replace(tmp, OUT)
        print("priority.json 更新 %d件" % len(pmap))
    # ホワイトボードへ（正本に取り込み＋whiteboard.json を書き直す）。優先度に変更が無くても写しは毎回更新する
    if os.path.exists(WB_PY):
        try:
            r = subprocess.run([sys.executable, WB_PY, "sync"], capture_output=True, text=True, timeout=30)
            print("whiteboard sync:", (r.stdout or r.stderr).strip()[:160] or "ok")
        except Exception as e:
            print("whiteboard sync 失敗:", e)


if __name__ == "__main__":
    main()
