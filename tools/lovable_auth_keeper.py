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
        if not (d.get("access_token") or d.get("refresh_token")):
            return False
        # ★2026-10-15【鍵はあるのに死んでいる】refresh_token が invalid_grant で死ぬと
        #   ファイルは残るので「鍵あり」と見なされ、受け皿が立たない＝承認URLを開いても
        #   誰も受け取らない状態で止まっていた（10/14〜15、1144が押せなくなった件）。
        #   keeper が「同意のやり直しが必要」と記録し、その後に新しい鍵が来ていなければ
        #   「鍵が無い」と同じ扱いにして受け皿を立てる。
        st_path = os.path.expanduser("~/.tamago/lovable_keeper_state.json")
        try:
            st = json.load(open(st_path, encoding="utf-8"))
        except Exception:
            st = {}
        if st.get("needConsent") and os.path.getmtime(TOKEN) <= os.path.getmtime(st_path):
            return False
        return True
    except Exception:
        return False


def _jotai_kakidashi(listener_ok=None):
    """★2026-10-15：承認URLと受け皿の状態は ~/.tamago にしか無く、Cowork から読めなかった。
    公開しない status/ 直下（.gitignore の status/*）へ写す。鍵（token）の値は書かない。"""
    try:
        import json
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        url_file = os.path.expanduser("~/.tamago/lovable_authorize_url.txt")
        url, url_at = "", None
        if os.path.exists(url_file):
            url = open(url_file, encoding="utf-8").read().strip()
            url_at = time.strftime("%F %T", time.localtime(os.path.getmtime(url_file)))
        if listener_ok is None:
            p = subprocess.run(["pgrep", "-f", "lovable_listener.py"],
                               capture_output=True, text=True, timeout=10)
            listener_ok = p.returncode == 0 and bool((p.stdout or "").strip())
        out = {"at": time.strftime("%F %T"), "url": url, "url_at": url_at,
               "uketori_machi": bool(listener_ok), "listener_file_aru": os.path.exists(LISTENER),
               "kagi_ok": _token_ok()}
        dst = os.path.join(here, "status", "lovable_shounin.json")
        tmp = dst + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        os.replace(tmp, dst)
    except Exception:
        pass


def run():
    try:
        g2 = GATE + "_jotai"
        if not (os.path.exists(g2) and time.time() - os.path.getmtime(g2) < 30):
            open(g2, "w").write(str(time.time()))
            _jotai_kakidashi()
    except Exception:
        pass
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
