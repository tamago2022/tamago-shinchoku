#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""962番：Lovableの同意ボタンを「いつ押しても」拾えるようにする見張り。

なぜ要るか（2026-09-19 実測）：
  Lovable MCPはOAuthだけ（公式FAQ「API key authentication is not currently available」）。
  認可サーバのメタデータに device_code は無く、authorization_code + refresh_token だけ。
  ChromeはLovableにログイン済みで、同意画面（"Allow access to Lovable"）までは人の手ゼロで
  到達できた。**残りはボタン1つ。**
  ところが受け皿（127.0.0.1:41999）がその瞬間に居ないと、押しても何も起きない。
  だから「トークンが取れるまで受け皿を立て続ける」係をここに置く。

  トークンが取れたら（~/.tamago/lovable_oauth.json ができたら）即座に何もしなくなる。
"""
import os
import subprocess
import time

TOKEN = os.path.expanduser("~/.tamago/lovable_oauth.json")
LISTENER = os.path.expanduser("~/.tamago/lovable_listener.py")
GATE = os.path.expanduser("~/.tamago/.keeper_gate")


def _token_ok():
    try:
        import json
        d = json.load(open(TOKEN, encoding="utf-8"))
        return bool(d.get("access_token") or d.get("refresh_token"))
    except Exception:
        return False


def run():
    # 鍵があるなら、期限の5分前に自動で更新（失敗しても鍵は消さない）。
    try:
        import lovable_token_keeper
        lovable_token_keeper.ensure_fresh()
    except Exception:
        pass
    # ★2026-10-04：「ファイルがある」だけでは足りない。0バイト／壊れた中身も「鍵が無い」と見なして
    #   受け皿を立て続ける（0バイトのまま放置され、鍵が24時間以上戻らなかった）。
    if _token_ok() or not os.path.exists(LISTENER):
        return
    # 30秒に1回だけ見る（心臓は15秒おき）
    try:
        if os.path.exists(GATE) and time.time() - os.path.getmtime(GATE) < 30:
            return
        open(GATE, "w").write(str(time.time()))
    except Exception:
        return
    try:
        p = subprocess.run(["pgrep", "-f", "lovable_listener.py"],
                           capture_output=True, text=True, timeout=10)
        if p.returncode == 0 and (p.stdout or "").strip():
            return
        subprocess.Popen(["/usr/bin/python3", LISTENER],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception:
        pass
