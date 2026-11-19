#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Suno MCP のサインインを工場が自分で回す係（2026-10-31）

なぜ要るか（実測 10-31 05:10〜06:20）：公式の `claude mcp login suno` は、Mac の負荷で claude の起動だけで
6分半かかり、37分待っても画面に何も出さず（承認URLが取れず）終わった。`claude --version` すら 6分半。
Suno の認可サーバは公式メタデータで「動的クライアント登録・PKCE(S256)・refresh_token」を公開しているので、
Python だけで承認URLを作り、受け皿（127.0.0.1:41998）で待つ。ブラウザは開かない（URLを出すだけ）。

  --signin  : 登録→承認URLを status/suno_mcp/jotai.json と Dispatch に出す→受け皿で待つ（URL_HOURS 時間）。
              押されたら鍵を ~/.tamago/suno_oauth.json（0600・中身はどこにも書かない）に保存し、
              Claude Code の suno を「headersHelper＝この係の --header」に付け替え、--kakunin まで自動で走る。
  --header  : Claude Code が接続のたびに呼ぶ。{"Authorization": "Bearer …"} を出す（期限が近ければ更新）。
  --kakunin : MCP に直接つないで道具一覧を取り、残高を見る道具だけを呼ぶ（作る道具は呼ばない）。
              1曲あたりの消費は、道具の説明・返り値に書いてある文言だけを拾う（推測しない）。
  --self-test
"""
import base64
import hashlib
import http.server
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(REPO, "status", "suno_mcp")
JOTAI = os.path.join(ST, "jotai.json")
LOCK = os.path.join(ST, "oauth.lock")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
TAMAGO = os.path.expanduser("~/.tamago")
TOKEN = os.path.join(TAMAGO, "suno_oauth.json")
CLIENT = os.path.join(TAMAGO, "suno_client.json")
CLAUDE_JSON = os.path.expanduser("~/.claude.json")
CLAUDE = os.path.expanduser("~/.local/bin/claude")
AS = "https://studio-api-prod.suno.com/api/v2/external/oauth"
AUTHZ = AS + "/authorize/"
TOKEN_EP = AS + "/token/"
REG_EP = AS + "/register/"
RESOURCE = "https://api.suno.com/mcp"
# 保護リソースのメタデータ（api.suno.com/.well-known/oauth-protected-resource/mcp）の scopes_supported そのまま
SCOPE = "api:v0 credits:spend download library:read library:search library:write offline_access profile:read"
PORT = 41998
REDIRECT = "http://127.0.0.1:%d/callback" % PORT
URL_HOURS = 24
UA = "tamago-kojo-suno/1"


def now():
    return time.strftime("%F %T")


def yomu(p=JOTAI):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return {}


def kaku(**kw):
    os.makedirs(ST, exist_ok=True)
    d = yomu()
    d.update(kw)
    d["koushin"] = now()
    tmp = JOTAI + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
    os.replace(tmp, JOTAI)


def himitsu_kaku(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    fd = os.open(tmp, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(d, f)
    os.replace(tmp, p)


def dispatch(msg):
    try:
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": now(), "type": "suno_mcp", "text": msg}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def post(url, data, form=True, headers=None, timeout=40):
    body = urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()
    h = {"User-Agent": UA, "Accept": "application/json",
         "Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers or {})


def client_id():
    c = yomu(CLIENT)
    if c.get("client_id") and c.get("redirect") == REDIRECT:
        return c["client_id"]
    st, body, _ = post(REG_EP, {"client_name": "tamago-kojo (Claude Code)", "redirect_uris": [REDIRECT],
                                "grant_types": ["authorization_code", "refresh_token"],
                                "response_types": ["code"], "token_endpoint_auth_method": "none",
                                "scope": SCOPE}, form=False)
    d = json.loads(body) if body.strip().startswith("{") else {}
    if not d.get("client_id"):
        raise RuntimeError("クライアント登録に失敗 HTTP %s %s" % (st, body[:200]))
    himitsu_kaku(CLIENT, {"client_id": d["client_id"], "redirect": REDIRECT, "at": now()})
    return d["client_id"]


def pkce():
    v = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    c = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    return v, c


def authorize_url(cid, challenge, state):
    q = {"response_type": "code", "client_id": cid, "redirect_uri": REDIRECT, "scope": SCOPE,
         "state": state, "code_challenge": challenge, "code_challenge_method": "S256", "resource": RESOURCE}
    return AUTHZ + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)


def token_hozon(d):
    d = dict(d)
    d["expires_at"] = time.time() + int(d.get("expires_in") or 3600)
    old = yomu(TOKEN)
    if not d.get("refresh_token") and old.get("refresh_token"):
        d["refresh_token"] = old["refresh_token"]
    himitsu_kaku(TOKEN, d)


def access_token():
    t = yomu(TOKEN)
    if not t.get("access_token"):
        return ""
    if time.time() < float(t.get("expires_at", 0)) - 120:
        return t["access_token"]
    if not t.get("refresh_token"):
        return ""
    st, body, _ = post(TOKEN_EP, {"grant_type": "refresh_token", "refresh_token": t["refresh_token"],
                                  "client_id": yomu(CLIENT).get("client_id", ""), "resource": RESOURCE})
    if st == 200:
        token_hozon(json.loads(body))
        return yomu(TOKEN)["access_token"]
    kaku(jotai="鍵の更新に失敗（承認のやり直しが要る）", koushin_err="HTTP %s" % st)
    return ""


def header():
    t = access_token()
    print(json.dumps({"Authorization": "Bearer " + t} if t else {}))
    return 0


def claude_tsukekae():
    """Claude Code の suno を headersHelper 付きに付け替える（~/.claude.json を直に・控えを取ってから）。"""
    helper = "%s %s --header" % ("/usr/bin/python3", os.path.abspath(__file__))
    try:
        d = json.load(io.open(CLAUDE_JSON, encoding="utf-8"))
        bk = os.path.join(TAMAGO, "backup")
        os.makedirs(bk, exist_ok=True)
        shutil.copy2(CLAUDE_JSON, os.path.join(bk, "claude.json.suno-%s" % time.strftime("%Y%m%d%H%M%S")))
        d.setdefault("mcpServers", {})["suno"] = {"type": "http", "url": RESOURCE, "headersHelper": helper}
        tmp = CLAUDE_JSON + ".suno.tmp"
        io.open(tmp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2))
        os.replace(tmp, CLAUDE_JSON)
        # 控えは最新3つだけ残す（使ったらしまう）
        ks = sorted(f for f in os.listdir(bk) if f.startswith("claude.json.suno-"))
        for f in ks[:-3]:
            os.remove(os.path.join(bk, f))
        return "ok"
    except Exception as e:
        return "失敗 %r" % (e,)


def mcp_call(method, params, sid=None, rid=1):
    h = {"Authorization": "Bearer " + access_token(), "Accept": "application/json, text/event-stream",
         "MCP-Protocol-Version": "2025-06-18"}
    if sid:
        h["Mcp-Session-Id"] = sid
    msg = {"jsonrpc": "2.0", "method": method, "params": params}
    if rid is not None:
        msg["id"] = rid
    st, body, hd = post(RESOURCE, msg, form=False, headers=h, timeout=60)
    sid = sid or next((v for k, v in hd.items() if k.lower() == "mcp-session-id"), None)
    res = None
    for chunk in [body] + [l[5:].strip() for l in body.splitlines() if l.startswith("data:")]:
        try:
            j = json.loads(chunk)
            if isinstance(j, dict) and ("result" in j or "error" in j):
                res = j
        except Exception:
            pass
    return st, res, sid


YOMU = re.compile(r"credit|balance|plan|account|profile|whoami|usage|billing|subscription|me$", re.I)
TSUKURU = re.compile(r"(?:^|[_\-.])(?:create|generate|gen|make|cover|extend|remix|mashup|upload|speech|tts|write|add|delete|remove|playlist|edit|update|set|stem|voice|spend|song|songs|music)(?:$|[_\-.])", re.I)


def yomu_dake(tools):
    out = []
    for t in tools:
        nm = t.get("name", "")
        req = ((t.get("inputSchema") or {}).get("required") or [])
        ann = t.get("annotations") or {}
        if YOMU.search(nm) and not TSUKURU.search(nm) and not re.search(r"create|generate|remix|upload", nm, re.I) and not req and ann.get("readOnlyHint") is not False:
            out.append(nm)
    return out


def kakunin():
    if not access_token():
        kaku(kakunin={"at": now(), "kekka": "鍵がまだ無い（承認待ち）"})
        return 1
    k = {"at": now()}
    st, r, sid = mcp_call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                         "clientInfo": {"name": "tamago-kojo", "version": "1"}})
    k["initialize"] = st
    if st != 200:
        k["kekka"] = "MCP に入れない HTTP %s %s" % (st, json.dumps(r, ensure_ascii=False)[:300])
        kaku(kakunin=k)
        dispatch("Suno MCP：鍵は取れたが MCP に入れない（HTTP %s）。早期アクセスの申し込みが要るかも：https://suno.com/mcp" % st)
        return 1
    mcp_call("notifications/initialized", {}, sid, rid=None)
    st, r, _ = mcp_call("tools/list", {}, sid, rid=2)
    tools = ((r or {}).get("result") or {}).get("tools") or []
    k["tools"] = [t.get("name") for t in tools]
    # 1曲の消費：道具の説明に書いてある「credit」を含む文だけ拾う（推測しない）
    k["setsumei_credit"] = {t.get("name"): s.strip() for t in tools
                            for s in re.split(r"(?<=[.。])\s*", t.get("description") or "")
                            if re.search(r"credit", s, re.I)}
    k["yonda"] = {}
    for i, nm in enumerate(yomu_dake(tools)):
        st, r, _ = mcp_call("tools/call", {"name": nm, "arguments": {}}, sid, rid=10 + i)
        txt = json.dumps((r or {}).get("result") or (r or {}).get("error"), ensure_ascii=False)
        k["yonda"][nm] = txt[:1500]
    kaku(jotai="つながった", kakunin=k)
    nokori = " / ".join("%s=%s" % (n, v[:160]) for n, v in k["yonda"].items()) or "残高を見る道具なし"
    dispatch("Suno MCP つながりました（道具 %d 本）。%s" % (len(tools), nokori))
    return 0


class Uke(http.server.BaseHTTPRequestHandler):
    kekka = {}

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        Uke.kekka = q
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = "code" in q
        self.wfile.write(("<meta charset=utf-8><p style='font:20px sans-serif;padding:40px'>%s</p>" % (
            "Suno とつながりました。このタブは閉じて大丈夫です。" if ok else "承認されませんでした：" + q.get("error", "?"))).encode())

    def log_message(self, *a):
        pass


def lock_toru():
    os.makedirs(ST, exist_ok=True)
    try:
        if os.path.exists(LOCK):
            pid = int((io.open(LOCK).read().split() or ["0"])[0])
            try:
                os.kill(pid, 0)
                return False
            except Exception:
                pass
        io.open(LOCK, "w").write("%d %s\n" % (os.getpid(), now()))
        return True
    except Exception:
        return False


def signin():
    if not lock_toru():
        return 0
    try:
        if access_token():
            kaku(jotai="鍵あり", claude=claude_tsukekae())
            return kakunin()
        cid = client_id()
        verifier, challenge = pkce()
        state = secrets.token_urlsafe(16)
        url = authorize_url(cid, challenge, state)
        srv = http.server.HTTPServer(("127.0.0.1", PORT), Uke)
        srv.timeout = 5
        kigen = time.time() + URL_HOURS * 3600
        kaku(jotai="承認待ち", url=url, url_deta=now(), url_kigen=time.strftime("%F %T", time.localtime(kigen)),
             uketori=REDIRECT, houhou="工場の Python（suno_oauth.py）")
        dispatch("Suno の許可（Macのブラウザで押すだけ・%s まで）：%s" % (time.strftime("%m/%d %H:%M", time.localtime(kigen)), url))
        while time.time() < kigen and not Uke.kekka:
            srv.handle_request()
        srv.server_close()
        q = Uke.kekka
        if not q:
            kaku(jotai="期限切れ（押されず）", url="")
            return 1
        if q.get("state") != state or "code" not in q:
            kaku(jotai="承認されなかった", url="", err=q.get("error", "state 不一致"))
            dispatch("Suno の許可が通りませんでした（%s）。新しいURLを出し直します。" % q.get("error", "state 不一致"))
            return 1
        st, body, _ = post(TOKEN_EP, {"grant_type": "authorization_code", "code": q["code"], "redirect_uri": REDIRECT,
                                      "client_id": cid, "code_verifier": verifier, "resource": RESOURCE})
        if st != 200:
            kaku(jotai="鍵の受け取りに失敗", url="", err="HTTP %s %s" % (st, body[:200]))
            return 1
        token_hozon(json.loads(body))
        kaku(jotai="鍵あり", url="", oshita=now(), claude=claude_tsukekae())
        return kakunin()
    except Exception as e:
        kaku(jotai="失敗", err=repr(e)[:300])
        return 1
    finally:
        try:
            os.remove(LOCK)
        except Exception:
            pass


def self_test():
    ok = True
    v, c = pkce()
    ok &= len(v) >= 43 and c == base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    u = authorize_url("cid1", c, "st1")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(u).query))
    ok &= u.startswith(AUTHZ) and q["redirect_uri"] == REDIRECT and q["resource"] == RESOURCE and q["code_challenge_method"] == "S256"
    tl = [{"name": "get_credits"}, {"name": "create_song"}, {"name": "get_account", "inputSchema": {"required": ["x"]}},
          {"name": "credits_spend_generate"}, {"name": "add_song_to_playlist"}, {"name": "createCredits"}]
    ok &= yomu_dake(tl) == ["get_credits"]
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "--self-test"
    sys.exit({"--signin": signin, "--header": header, "--kakunin": kakunin, "--self-test": self_test}[a]())
