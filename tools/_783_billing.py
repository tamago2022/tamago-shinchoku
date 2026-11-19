#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""783番: fal公式Billing APIをadmin keyで叩き、現在のSubtotal等を取得する（課金なし・読み取りのみ）。"""
import json
import os
import sys
import urllib.request
import urllib.error

KEY_PATH = os.path.expanduser("~/.fal_admin_key")
with open(KEY_PATH) as f:
    ADMIN_KEY = f.read().strip()


def get(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Key {ADMIN_KEY}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8"), dict(resp.getheaders())


urls = [
    "https://api.fal.ai/v1/account/billing",
    "https://api.fal.ai/v1/billing",
    "https://rest.alpha.fal.ai/billing",
]

for u in urls:
    try:
        body, headers = get(u)
        print("OK", u)
        print(body[:2000])
        print("---headers---")
        print(json.dumps(headers, indent=2))
    except urllib.error.HTTPError as e:
        print("HTTPError", u, e.code, e.read()[:500])
    except Exception as e:
        print("ERR", u, e)
    print("=====")
