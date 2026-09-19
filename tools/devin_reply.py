#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""blocked状態のDevinセッションへ日本語で返事を送り、再開させる道具。

たまごさんの希望：「日本語で指示を出して欲しい。俺もどういう指示をしたか見たいから」
→ 引数の文章をそのままmessageとして送る。翻訳はしない。

使い方:
  python3 tools/devin_reply.py "<セッションID>" "<日本語の返事>"

このスクリプト自体は「送る道具」を用意するだけで、いつ・何を送るかはDispatchが決める。
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
    if len(sys.argv) < 3 or not sys.argv[1].strip() or not sys.argv[2].strip():
        print("使い方: python3 tools/devin_reply.py \"<セッションID>\" \"<日本語の返事>\"")
        return 1
    session_id = sys.argv[1]
    message = sys.argv[2]

    key = os.environ.get("DEVIN_API_KEY") or load_env_key()
    if not key:
        print("DEVIN_API_KEYが.envに見つかりません。")
        return 1

    body = json.dumps({"message": message}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.devin.ai/v1/sessions/%s/message" % session_id,
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer %s" % key,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            res.read()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", "ignore")
        print("Devin APIエラー %s: %s" % (e.code, err_body[:200]))
        return 1
    except Exception as e:
        print("Devin APIに繋がりませんでした: %s" % e)
        return 1

    print("送信しました: https://app.devin.ai/sessions/%s" % session_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
