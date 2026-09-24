#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1075番【Spotifyの入り口】たまごさんが押すのを**URL1本**に削る。

たまごさん（2026-09-24・原文）:
  「Spotifyにログインって毎回やらないといけないの。地味にストレスだね。」
  「人が1回だけ同意を押す必要があるなら、押す入り口のURL1つだけを出す。」

━━ これが何か ━━
  Macの中（127.0.0.1）にだけ立つ、1枚きりの受け口。
  たまごさんは **http://127.0.0.1:41999/ を開く → Client IDを貼る → 「同意する」を押す**。
  それで終わり。以後Spotifyのログインは**二度と要らない**（refresh_token に替わる）。

━━ なぜClient IDだけは人が要るか（推測ではない）━━
  Spotify Web API は **client_id の無いリクエストを一切受けない**。
  private のプレイリストを読む道は Authorization Code(+PKCE) しかなく、
  その入口に client_id が要る。＝こちらでは作れない。Dashboardは本人ログインの中。
  ★PKCEなので **client_secret は要らない**。たまごさんの秘密の値を1つも預からない。

━━ 決まり ━━
  ① ★127.0.0.1 の外に口を開けない（外から繋がらない）。
  ② ★鍵の値（clientId / refreshToken / accessToken）を画面にもログにも出さない。
  ③ ★保管は ~/.tamago/spotify.json（600・git管理外）。
  ④ ★たまごさんの普段のブラウザ（Brave）に**こちらからは触らない**。開くのは本人。
  ⑤ ★課金0。

口:
  python3 tools/spotify_iriguchi.py            … 受け口を立てて待つ（最大30分）
  run_job({"op":"tateru"})                     … gaibu_runner から裏で立てる
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

PORT = 41999
REDIRECT = "http://127.0.0.1:%d/callback" % PORT
IRIGUCHI = "http://127.0.0.1:%d/" % PORT
SCOPES = ("playlist-read-private playlist-read-collaborative "
          "user-library-read "
          "playlist-modify-public playlist-modify-private")
AUTH = "https://accounts.spotify.com/authorize"
TOKEN = "https://accounts.spotify.com/api/token"
STAMP = os.path.join(REPO, "status", "1075_spotify", "iriguchi.json")

_S = {}   # 途中の控え（メモリだけ。ディスクに client_id を書かない）


def _post_token(fields):
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(TOKEN, data=body, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


def _page(body):
    return ("<!doctype html><html lang=ja><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>Spotifyの入り口</title><style>"
            "body{font:17px/1.9 -apple-system,'Hiragino Sans',sans-serif;"
            "max-width:620px;margin:0 auto;padding:48px 24px;color:#1a1a1a}"
            "h1{font-size:23px;letter-spacing:.02em;margin:0 0 6px}"
            ".sub{color:#666;font-size:14px;margin:0 0 28px}"
            "input{width:100%;box-sizing:border-box;font:16px/1.6 ui-monospace,monospace;"
            "padding:14px;border:1px solid #d5d5d5;border-radius:10px;margin:6px 0 18px}"
            "button{font:600 17px/1 -apple-system,sans-serif;background:#1db954;color:#fff;"
            "border:0;border-radius:999px;padding:16px 34px;cursor:pointer}"
            "ol{padding-left:1.2em}li{margin:.5em 0}"
            "a{color:#0a7a3d}.ok{font-size:21px;font-weight:600}"
            "</style>" + body + "</html>").encode("utf-8")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, html, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)

        if u.path == "/":
            self._send(_page(
                "<h1>Spotifyをつなぐ（今回1回きり）</h1>"
                "<p class=sub>終わったらもうSpotifyのログインは要りません。</p>"
                "<ol>"
                "<li><a href='https://developer.spotify.com/dashboard/create' target=_blank "
                "rel=noopener>この画面</a>を開いて、名前は何でもよいので作る</li>"
                "<li><b>Redirect URI</b> に <code>%s</code> を入れる</li>"
                "<li><b>Web API</b> にチェック → Save</li>"
                "<li>出てきた <b>Client ID</b> を下に貼って押す</li>"
                "</ol>"
                "<form method=GET action='/susumu'>"
                "<input name=cid placeholder='Client ID' autocomplete=off autofocus>"
                "<button type=submit>同意へ進む</button></form>"
                "<p class=sub>※ Client secret は使いません（PKCEなので要りません）。</p>"
                % REDIRECT))
            return

        if u.path == "/susumu":
            cid = (q.get("cid") or [""])[0].strip()
            if not cid:
                self._send(_page("<h1>Client ID が空でした</h1>"
                                 "<p><a href='/'>戻る</a></p>"), 400)
                return
            verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
            challenge = base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
            state = secrets.token_urlsafe(16)
            _S.clear()
            _S.update({"cid": cid, "verifier": verifier, "state": state})
            url = AUTH + "?" + urllib.parse.urlencode({
                "client_id": cid, "response_type": "code", "redirect_uri": REDIRECT,
                "scope": SCOPES, "code_challenge_method": "S256",
                "code_challenge": challenge, "state": state})
            self.send_response(302)
            self.send_header("Location", url)
            self.end_headers()
            return

        if u.path == "/callback":
            code = (q.get("code") or [None])[0]
            err = (q.get("error") or [None])[0]
            if err or not code:
                self._send(_page("<h1>受け取れませんでした</h1>"
                                 "<p>%s</p><p><a href='/'>もう一度</a></p>"
                                 % (err or "code が来ませんでした")), 400)
                return
            if (q.get("state") or [""])[0] != _S.get("state"):
                self._send(_page("<h1>合い札が違いました</h1>"
                                 "<p><a href='/'>もう一度</a></p>"), 400)
                return
            try:
                tok = _post_token({"grant_type": "authorization_code", "code": code,
                                   "redirect_uri": REDIRECT, "client_id": _S["cid"],
                                   "code_verifier": _S["verifier"]})
            except Exception as e:
                self._send(_page("<h1>しくじりました</h1><p>%s</p>" % str(e)[:200]), 500)
                return
            if not tok.get("refresh_token"):
                self._send(_page("<h1>refresh_token が返りませんでした</h1>"
                                 "<p><a href='/'>もう一度</a></p>"), 500)
                return
            import spotify_ninshou as sn
            sn._save600(sn.STORE, {"clientId": _S["cid"],
                                   "refreshToken": tok["refresh_token"],
                                   "scope": tok.get("scope", ""),
                                   "savedAt": time.strftime("%F %T")})
            _S.clear()
            try:
                os.makedirs(os.path.dirname(STAMP), exist_ok=True)
                json.dump({"ok": True, "at": time.strftime("%F %T"),
                           "memo": "同意が済みました。値は書いていません。"},
                          io.open(STAMP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            except Exception:
                pass
            self._send(_page("<h1 class=ok>終わりました ✅</h1>"
                             "<p>もうSpotifyのログインは要りません。<br>"
                             "この画面は閉じて大丈夫です。あとはこちらでやります。</p>"))
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        self._send(_page("<h1>…</h1><p><a href='/'>入り口へ</a></p>"), 404)


def tateru(wait_sec=43200):   # ★12時間。たまごさんが押すまで閉めない（同意が済めば自分で閉じる）
    srv = HTTPServer(("127.0.0.1", PORT), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    t.join(wait_sec)
    return 0


def _ikiteru():
    try:
        urllib.request.urlopen(IRIGUCHI, timeout=3).read()
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def run_job(payload):
    """gaibu_runner から kind="spotifyiri" で呼ばれる（＝工場＝Macの上）。
    受け口を**裏で**立てて、押すURLを1本だけ返す。鍵の値は返さない。"""
    payload = payload or {}
    op = payload.get("op") or "tateru"
    if op == "kenpin":
        # ★「立てました」で終わらせない。中身が本当に出るかを工場側から読む。
        try:
            body = urllib.request.urlopen(IRIGUCHI, timeout=6).read().decode("utf-8", "replace")
        except Exception as e:
            return {"ok": False, "error": "入り口が開きませんでした: %s" % str(e)[:120],
                    "totalYen": 0.0}
        return {"ok": ("Client ID" in body and "同意へ進む" in body),
                "iriguchi": IRIGUCHI, "nagasa": len(body),
                "redirect": REDIRECT, "totalYen": 0.0}
    if op == "tatenaosu":
        # ★古い受け口を閉じて、長い時間待つものに入れ替える。
        #   たまごさんが押すまで閉まっていないようにするため。
        import signal as _sg
        killed = []
        try:
            r = subprocess.run(["lsof", "-ti", "tcp:%d" % PORT],
                               capture_output=True, text=True, timeout=15)
            for pid in (r.stdout or "").split():
                try:
                    os.kill(int(pid), _sg.SIGTERM)
                    killed.append(int(pid))
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(1.5)
        payload = {"op": "tateru"}
        op = "tateru"
    if op != "tateru":
        return {"ok": False, "error": "知らない op です", "totalYen": 0.0}

    # もう同意済みなら立てない
    try:
        import spotify_ninshou as sn
        d = sn._load(sn.STORE)
        if d and d.get("refreshToken"):
            return {"ok": True, "sudeNi": True,
                    "memo": "すでに同意済みです。たまごさんが押すものはありません。",
                    "totalYen": 0.0}
    except Exception:
        pass

    if not _ikiteru():
        log = os.path.join(REPO, "status", "1075_spotify", "iriguchi.log")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        f = io.open(log, "a")
        subprocess.Popen([sys.executable, os.path.abspath(__file__)],
                         stdout=f, stderr=f, stdin=subprocess.DEVNULL,
                         start_new_session=True, cwd=REPO)
        for _ in range(20):
            time.sleep(0.5)
            if _ikiteru():
                break

    return {"ok": _ikiteru(), "iriguchi": IRIGUCHI,
            "memo": "たまごさんが押すのはこの1本だけ（今回1回きり）",
            "totalYen": 0.0}


if __name__ == "__main__":
    print("★押すのはこの1本だけです： %s" % IRIGUCHI)
    sys.exit(tateru())
