#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""783番: 読み聞かせ絵本・声3種類聞き比べ用に、fal上のTTSモデル候補を確認する（課金なし・検索のみ）。"""
import json
import os
import urllib.request

KEY_PATH = os.path.expanduser("~/.fal_key")
with open(KEY_PATH) as f:
    FAL_KEY = f.read().strip()


def get(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Key {FAL_KEY}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8")


for kw in ["tts", "speech", "voice"]:
    try:
        body = get(f"https://fal.ai/api/models?keywords={kw}")
        print(f"--- {kw} ---")
        print(body[:3000])
    except Exception as e:
        print(f"--- {kw} error: {e} ---")
