#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1046番：Spotifyの認証を**今回1回だけ**で終わらせる（PKCE方式）。

━━ なぜこれを作るか（2026-09-24・たまごさん）━━
  「Spotifyにログインって毎回やらないといけないの。何回もやってるんだよ。
    毎回俺がログインするんだけど。地味にストレスだね。」
  ブラウザのログインはセッションが切れるたびに6桁コードを要求する＝毎回たまごさんが要る。
  これは設計ミス。→ **refresh_token に切り替える。**

━━ 公式で確かめたこと（推測ではない）━━
  https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens
    「refresh token … allows client applications to obtain new access tokens
      **without requiring users to reauthorize** the application」
    access_token の寿命は **1時間**。refresh_token から何度でも作り直せる。
  https://developer.spotify.com/documentation/web-api/reference/add-tracks-to-playlist
    プレイリストに足すのに要る scope ＝ **playlist-modify-public / playlist-modify-private**

━━ PKCEを選んだ理由 ━━
  PKCE は **client_secret が要らない**（client_id だけ）。
  ＝たまごさんの秘密の値をこちらが1文字も受け取らない。事故りようがない。

━━ 置き場所 ━━
  ~/.tamago/spotify.json   … refresh_token の保管先。**600・git管理外・値は絶対に出さない**
  ~/.tamago/spotify_pkce.json … 途中の控え（同意が終わったら消す）

━━ 使い方（Mac側で）━━
  1) たまごさんが Dashboard でアプリを作る（1回だけ）
       https://developer.spotify.com/dashboard/create
       Redirect URI: http://127.0.0.1:41999/callback
       Which API/SDKs: Web API
  2) python3 tools/spotify_ninshou.py --hajime --client-id <Client ID>
       → 受け口が立ち上がり、**押すURLが1本**表示される
  3) たまごさんがそのURLを1回だけ押して「同意する」
       → refresh_token が保存される。**以後ブラウザは二度と要らない。**
  4) python3 tools/spotify_ninshou.py --tameshi   # 通るか確かめるだけ
"""
import argparse
import base64
import hashlib
import io
import json
import os
import secrets
import stat
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 41999
REDIRECT = "http://127.0.0.1:%d/callback" % PORT
SCOPES = "playlist-modify-public playlist-modify-private playlist-read-private"
AUTH = "https://accounts.spotify.com/authorize"
TOKEN = "https://accounts.spotify.com/api/token"

HOME = os.path.expanduser("~")
TDIR = os.path.join(HOME, ".tamago")
STORE = os.path.join(TDIR, "spotify.json")
PKCE = os.path.join(TDIR, "spotify_pkce.json")


def _save600(path, obj):
    os.makedirs(TDIR, exist_ok=True)
    os.chmod(TDIR, stat.S_IRWXU)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)   # 600
    os.replace(tmp, path)


def _load(path):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return None


def _post_token(fields):
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        TOKEN, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


# ───────────────────────── 同意（今回1回だけ） ─────────────────────────

class Handler(BaseHTTPRequestHandler):
    result = {}

    def log_message(self, *a):
        pass  # 端末を汚さない

    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code = (q.get("code") or [None])[0]
        err = (q.get("error") or [None])[0]
        msg = "しくじりました: %s" % err if err else "受け取りました。この画面は閉じて大丈夫です。"
        if code:
            try:
                p = _load(PKCE) or {}
                tok = _post_token({
                    "grant_type": "authorization_code", "code": code,
                    "redirect_uri": REDIRECT, "client_id": p.get("clientId"),
                    "code_verifier": p.get("verifier")})
                if tok.get("refresh_token"):
                    _save600(STORE, {"clientId": p.get("clientId"),
                                     "refreshToken": tok["refresh_token"],
                                     "scope": tok.get("scope", ""),
                                     "savedAt": time.strftime("%F %T")})
                    try:
                        os.remove(PKCE)
                    except OSError:
                        pass
                    msg = "終わりました。もうSpotifyのログインは要りません。この画面は閉じて大丈夫です。"
                    Handler.result = {"ok": True}
                else:
                    msg = "refresh_token が返りませんでした"
                    Handler.result = {"ok": False, "why": "no refresh_token"}
            except Exception as e:
                msg = "しくじりました: %s" % e
                Handler.result = {"ok": False, "why": str(e)[:200]}
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(("<html><meta charset='utf-8'><body "
                          "style='font:20px/1.8 -apple-system;padding:60px'>"
                          "<p>%s</p></body></html>" % msg).encode("utf-8"))
        threading.Thread(target=self.server.shutdown, daemon=True).start()


def hajime(client_id, wait_sec=600):
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(16)
    _save600(PKCE, {"clientId": client_id, "verifier": verifier, "state": state})

    url = AUTH + "?" + urllib.parse.urlencode({
        "client_id": client_id, "response_type": "code",
        "redirect_uri": REDIRECT, "scope": SCOPES,
        "code_challenge_method": "S256", "code_challenge": challenge,
        "state": state})

    print("★たまごさんが押すのは、この1本だけです（今回1回きり）：")
    print(url)
    print("\n受け口 %s で待っています（最大%d秒）…" % (REDIRECT, wait_sec))
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    srv.timeout = wait_sec
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    t.join(wait_sec)
    if Handler.result.get("ok"):
        print("✅ 保存しました: %s（値は出しません）" % STORE)
        return 0
    print("⚠️ まだ受け取れていません: %s" % (Handler.result.get("why") or "時間切れ"))
    return 1


# ───────────────────────── 以後（ブラウザ不要） ─────────────────────────

def access_token():
    """保存した refresh_token から access_token を作る。ブラウザを開かない。"""
    d = _load(STORE)
    if not d or not d.get("refreshToken"):
        raise SystemExit("まだ同意が終わっていません。"
                         "先に --hajime を1回だけ走らせてください。")
    tok = _post_token({"grant_type": "refresh_token",
                       "refresh_token": d["refreshToken"],
                       "client_id": d["clientId"]})
    # ★PKCEでは refresh_token が入れ替わって返ることがある。来たら必ず上書きする。
    if tok.get("refresh_token") and tok["refresh_token"] != d["refreshToken"]:
        d["refreshToken"] = tok["refresh_token"]
        d["savedAt"] = time.strftime("%F %T")
        _save600(STORE, d)
    return tok["access_token"]


def tameshi():
    t = access_token()
    req = urllib.request.Request("https://api.spotify.com/v1/me",
                                 headers={"Authorization": "Bearer " + t})
    with urllib.request.urlopen(req, timeout=20) as r:
        me = json.loads(r.read().decode())
    print("通りました: %s（%s）／ ブラウザは使っていません"
          % (me.get("display_name"), me.get("id")))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hajime", action="store_true", help="同意を1回だけ取る")
    ap.add_argument("--client-id", default=os.environ.get("SPOTIFY_CLIENT_ID"))
    ap.add_argument("--matsu", type=int, default=600, help="待つ秒数")
    ap.add_argument("--tameshi", action="store_true", help="鍵が通るか確かめるだけ")
    a = ap.parse_args()
    if a.tameshi:
        return tameshi()
    if a.hajime:
        if not a.client_id:
            raise SystemExit("--client-id が要ります（Dashboardで作ったアプリのClient ID）")
        return hajime(a.client_id, a.matsu)
    ap.error("--hajime か --tameshi を付けてください")


if __name__ == "__main__":
    sys.exit(main())
