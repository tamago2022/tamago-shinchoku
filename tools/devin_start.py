#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日本語の指示文でDevinの新しいセッションを立て、セッションURLだけを返す。

たまごさんの希望：「日本語で指示を出して欲しい。俺もどういう指示をしたか見たいから」
→ 引数の文章をそのままprompt（日本語のまま）としてDevinへ渡す。翻訳はしない。

使い方:
  python3 tools/devin_start.py "<日本語のプロンプト>"
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
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("使い方: python3 tools/devin_start.py \"<日本語のプロンプト>\"")
        return 1
    prompt = sys.argv[1]

    key = os.environ.get("DEVIN_API_KEY") or load_env_key()
    if not key:
        print("DEVIN_API_KEYが.envに見つかりません。")
        return 1

    # ★1034番【予算の栓】Devinは1セッションが高い（9/18〜9/20 の15本で $8.85＝1,327円＝
    #   1本あたり約88円・972番の公式画面差分より）。立てる前に必ず通す。
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import yosan
        ok, why = yosan.mitsumori("devin", 93.0, "Devinのセッションを1本立てる")
        if not ok:
            print(why)
            return 1
    except Exception as e:
        print("予算の栓（tools/yosan.py）が読めませんでした: %s。お金の話なので止めます。" % e)
        return 1

    body = json.dumps({"prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.devin.ai/v1/sessions",
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer %s" % key,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = json.load(res)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", "ignore")
        print("Devin APIエラー %s: %s" % (e.code, err_body[:200]))
        return 1
    except Exception as e:
        print("Devin APIに繋がりませんでした: %s" % e)
        return 1

    url = data.get("url") or ("https://app.devin.ai/sessions/%s" % data.get("session_id", ""))
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
