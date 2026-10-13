#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Devinの今のセッション一覧を1行ずつ出す（ブラウザ無しでDispatchが進捗を見るための道具）。

使い方:
  python3 tools/devin_sessions.py

.env の DEVIN_API_KEY を読む。キーが無い／APIが401・403を返したら、
その理由を1行だけ出して終わる（黙って空リストにしない）。
"""
import json
import os
import sys
import urllib.request
import urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(REPO, ".env")


def load_env_key():
    if not os.path.exists(ENV_PATH):
        return None
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            if line.startswith("DEVIN_API_KEY="):
                return line.strip().split("=", 1)[1]
    return None


def main():
    key = os.environ.get("DEVIN_API_KEY") or load_env_key()
    if not key:
        print("DEVIN_API_KEYが.envに見つかりません。")
        return 1

    req = urllib.request.Request(
        "https://api.devin.ai/v1/sessions",
        headers={"Authorization": "Bearer %s" % key},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            data = json.load(res)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        print("Devin APIエラー %s: %s" % (e.code, body[:200]))
        return 1
    except Exception as e:
        print("Devin APIに繋がりませんでした: %s" % e)
        return 1

    sessions = data.get("sessions") or []
    if not sessions:
        print("セッションはありません。")
        return 0

    for s in sessions:
        sid = s.get("session_id") or ""
        title = s.get("title") or "(無題)"
        status = s.get("status_enum") or s.get("status") or "?"
        updated = s.get("updated_at") or ""
        url = "https://app.devin.ai/sessions/%s" % sid
        print("%s ｜ %s ｜ 更新 %s ｜ %s" % (title, status, updated, url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
