#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Spotifyの許可を**1回だけ**で終わらせ、以後は人を動かさない（PKCE方式・Client Secret不要）。

━━ たまごさん ━━
  2026-09-24「Spotifyにログインって毎回やらないといけないの。何回もやってるんだよ。」
  2026-10-14「キーを1回作ったら仕組み化しといて。何回もログインさせないで。基本は人間を動かさない」

━━ 形（2026-10-14 作り直し）━━
  Redirect URI ＝ http://127.0.0.1:8888/callback（固定。たまごさんはこの値でアプリを作成済み）
  鍵帳（tools/kagi.py）に保存するもの：
      SPOTIFY_CLIENT_ID      … アプリのClient ID（PKCEなので秘密ではないが、置き場は鍵帳に一本化）
      SPOTIFY_REFRESH_TOKEN  … 許可の本体。access_token（1時間）はここから毎回自動で作り直す
  ~/.tamago/spotify.json  … 許可した日時などの控えだけ（600・git管理外）。トークンの正本は鍵帳
  ~/.tamago/spotify_client_id.txt … Client ID の受け取り口（置かれたら鍵帳へ移して消す）
  ~/.tamago/spotify_auth_url.txt  … たまごさんが押す許可URL（Dispatchにも1行で出す）

━━ 使い方（Mac）━━
  python3 tools/spotify_ninshou.py --machi [--then "コマンド"]
      Client ID を待つ → 届いたら許可URLを Dispatch に1行 → 127.0.0.1:8888 で待ち受け（最低30分・既定6時間）
      → 受け取ったら鍵帳へ保存 → --then を実行（例：プレイリスト作り）
  python3 tools/spotify_ninshou.py --tameshi     # 通るか確かめるだけ（ブラウザ不要）
  python3 tools/spotify_ninshou.py --self-test

━━ 切れたら ━━
  refresh_token が失効（invalid_grant）・6か月の期限 → Dispatch に1行だけ（1日1回まで）。
  そのあと --machi を走らせ直せば、押すURLがまた1本出る。

公式：https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow
      https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens
"""
import argparse
import base64
import calendar
import datetime
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
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import kagi

PORT = 8888
REDIRECT = "http://127.0.0.1:%d/callback" % PORT
SCOPES = "playlist-modify-public playlist-modify-private playlist-read-private"
AUTH = "https://accounts.spotify.com/authorize"
TOKEN = "https://accounts.spotify.com/api/token"

HOME = os.path.expanduser("~")
TDIR = os.path.join(HOME, ".tamago")
STORE = os.path.join(TDIR, "spotify.json")
PKCE = os.path.join(TDIR, "spotify_pkce.json")
CID_DROP = os.path.join(TDIR, "spotify_client_id.txt")
AUTH_URL_FILE = os.path.join(TDIR, "spotify_auth_url.txt")
REPO = os.path.dirname(HERE)
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
SHIRASE_GATE = os.path.join(TDIR, "spotify_shirase_last.txt")

K_CID = "SPOTIFY_CLIENT_ID"
K_RT = "SPOTIFY_REFRESH_TOKEN"


def log(*a):
    print(time.strftime("%m-%d %H:%M:%S"), *a, flush=True)


def _save600(path, obj):
    os.makedirs(TDIR, exist_ok=True)
    os.chmod(TDIR, stat.S_IRWXU)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(tmp, path)


def _load(path):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return None


def dispatch(text, gate_key=None):
    """Dispatch に1行。gate_key があれば同じ知らせは1日1回まで。"""
    if gate_key:
        last = {}
        try:
            last = json.load(open(SHIRASE_GATE))
        except Exception:
            pass
        if time.time() - last.get(gate_key, 0) < 86400:
            return
        last[gate_key] = time.time()
        _save600(SHIRASE_GATE, last)
    with io.open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                            "from": "spotify_ninshou", "text": text}, ensure_ascii=False) + "\n")


def _post_token(fields):
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(TOKEN, data=body, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


def client_id():
    v = kagi.get(K_CID)
    if v:
        return v
    if os.path.exists(CID_DROP):
        c = io.open(CID_DROP, encoding="utf-8").read().strip()
        if c and c.isalnum() and 20 <= len(c) <= 64:
            kagi.put(K_CID, c)
            os.remove(CID_DROP)
            log("Client ID を鍵帳へ移しました（値は出しません）")
            return c
    return None


def _save_refresh(rt, scope=None, fresh=False):
    kagi.put(K_RT, rt)
    meta = _load(STORE) or {}
    meta.pop("refreshToken", None)  # 正本は鍵帳。古い控えに残さない
    if fresh:
        meta["authorizedAt"] = time.time()
        meta["scope"] = scope or ""
        meta.pop("reauthorizationRequired", None)
    meta["savedAt"] = time.strftime("%F %T")
    meta["store"] = "kagi:" + K_RT
    _save600(STORE, meta)


# ───────────────────────── 許可（1回だけ） ─────────────────────────

class Handler(BaseHTTPRequestHandler):
    result = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path != "/callback":
            self.send_response(404); self.end_headers(); return
        q = urllib.parse.parse_qs(u.query)
        code = (q.get("code") or [None])[0]
        err = (q.get("error") or [None])[0]
        msg = "うまくいきませんでした: %s" % err if err else "受け取りました。この画面は閉じて大丈夫です。"
        if err:
            Handler.result = {"ok": False, "why": err}
        if code:
            try:
                p = _load(PKCE) or {}
                st = (q.get("state") or [""])[0]
                if not p.get("state") or not secrets.compare_digest(st, p["state"]):
                    raise ValueError("state が一致しません（古いURLを押した可能性）")
                tok = _post_token({"grant_type": "authorization_code", "code": code,
                                   "redirect_uri": REDIRECT, "client_id": p.get("clientId"),
                                   "code_verifier": p.get("verifier")})
                if not tok.get("refresh_token"):
                    raise ValueError("refresh_token が返りませんでした")
                _save_refresh(tok["refresh_token"], tok.get("scope"), fresh=True)
                try:
                    os.remove(PKCE)
                except OSError:
                    pass
                msg = "許可を保存しました。もう押さなくて大丈夫です（以後は自動）。この画面は閉じてください。"
                Handler.result = {"ok": True}
            except Exception as e:
                msg = "うまくいきませんでした: %s" % e
                Handler.result = {"ok": False, "why": str(e)[:200]}
        body = ("<html><meta charset='utf-8'><body style='font:20px/1.8 -apple-system;padding:60px'>"
                "<p>%s</p></body></html>" % msg).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def auth_url(cid):
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(16)
    _save600(PKCE, {"clientId": cid, "verifier": verifier, "state": state, "at": time.time()})
    return AUTH + "?" + urllib.parse.urlencode({
        "client_id": cid, "response_type": "code", "redirect_uri": REDIRECT, "scope": SCOPES,
        "code_challenge_method": "S256", "code_challenge": challenge, "state": state})


def machi(wait_cid_sec, listen_sec, then=None):
    listen_sec = max(listen_sec, 1800)  # 最低30分
    # 受け口を先に立てる（ポートが塞がっていたら、ここで分かる）
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    srv.timeout = 1
    log("受け口 %s を立てました" % REDIRECT)
    t0 = time.time()
    cid = client_id()
    while not cid and time.time() - t0 < wait_cid_sec:
        time.sleep(10)
        cid = client_id()
    if not cid:
        log("Client ID が届かないまま時間切れ"); return 2
    url = auth_url(cid)
    io.open(AUTH_URL_FILE, "w", encoding="utf-8").write(url + "\n")
    os.chmod(AUTH_URL_FILE, stat.S_IRUSR | stat.S_IWUSR)
    dispatch("Spotify：MacのChromeでこのURLを1回だけ押してください（以後は自動・%d分待ちます） %s" % (listen_sec // 60, url))
    log("許可URLを出しました（%s）。待ち受け %d分" % (AUTH_URL_FILE, listen_sec // 60))
    t1 = time.time()
    while time.time() - t1 < listen_sec and not Handler.result.get("ok"):
        srv.handle_request()
    srv.server_close()
    if not Handler.result.get("ok"):
        log("受け取れませんでした:", Handler.result.get("why") or "時間切れ")
        return 1
    log("✅ 許可を鍵帳に保存しました（値は出しません）")
    try:
        os.remove(AUTH_URL_FILE)
    except OSError:
        pass
    if then:
        log("続けて実行:", then)
        return subprocess.call(then, shell=True, cwd=REPO)
    return 0


# ───────────────────────── 以後（人を動かさない） ─────────────────────────

def _kireta(why):
    meta = _load(STORE) or {}
    meta["reauthorizationRequired"] = True
    _save600(STORE, meta)
    dispatch("Spotifyの許可が切れました（%s）。python3 tools/spotify_ninshou.py --machi を走らせると、押すURLが1本出ます" % why,
             gate_key="kireta")
    raise SystemExit("Spotifyの許可が切れました（%s）。Dispatchに知らせました。" % why)


def access_token():
    """鍵帳の refresh_token から access_token を作る。ブラウザを開かない。"""
    meta = _load(STORE) or {}
    rt = kagi.get(K_RT) or meta.get("refreshToken")
    cid = client_id() or meta.get("clientId")
    if not rt or not cid:
        _kireta("まだ許可が無い")
    a = meta.get("authorizedAt")
    if isinstance(a, (int, float)):  # 公式：許可から6か月で失効
        s = datetime.datetime.fromtimestamp(a, datetime.timezone.utc)
        mi = s.year * 12 + s.month - 1 + 6
        y, m0 = divmod(mi, 12)
        exp = s.replace(year=y, month=m0 + 1, day=min(s.day, calendar.monthrange(y, m0 + 1)[1]))
        if datetime.datetime.now(datetime.timezone.utc) >= exp:
            _kireta("6か月の期限")
    try:
        tok = _post_token({"grant_type": "refresh_token", "refresh_token": rt, "client_id": cid})
    except urllib.error.HTTPError as e:
        try:
            reason = json.loads(e.read()).get("error")
        except Exception:
            reason = None
        if e.code == 400 and reason == "invalid_grant":
            _kireta("失効")
        raise SystemExit("Spotify認証の更新に失敗しました（HTTP %s）。" % e.code)
    if tok.get("refresh_token") and tok["refresh_token"] != rt:  # PKCEは入れ替わることがある
        _save_refresh(tok["refresh_token"])
    return tok["access_token"]


def tameshi():
    t = access_token()
    req = urllib.request.Request("https://api.spotify.com/v1/me", headers={"Authorization": "Bearer " + t})
    with urllib.request.urlopen(req, timeout=20) as r:
        me = json.loads(r.read().decode())
    print("通りました: %s ／ ブラウザは使っていません" % (me.get("display_name") or me.get("id")))
    return 0


def self_test():
    assert REDIRECT == "http://127.0.0.1:8888/callback"
    q = AUTH + "?" + urllib.parse.urlencode({"redirect_uri": REDIRECT})
    assert "127.0.0.1%3A8888%2Fcallback" in q
    print("self-test OK")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--machi", action="store_true", help="Client IDを待ち、許可を1回受け取る")
    ap.add_argument("--then", default=None, help="許可が取れたら続けて実行するコマンド")
    ap.add_argument("--cid-matsu", type=int, default=86400, help="Client IDを待つ秒数")
    ap.add_argument("--matsu", type=int, default=6 * 3600, help="許可を待つ秒数（最低1800）")
    ap.add_argument("--tameshi", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.tameshi:
        return tameshi()
    if a.machi:
        return machi(a.cid_matsu, a.matsu, a.then)
    ap.error("--machi か --tameshi を付けてください")


if __name__ == "__main__":
    sys.exit(main())
