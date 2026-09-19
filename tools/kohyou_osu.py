#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1041番【公開押し】見る係が赤になったら、Lovableの公開ボタンを自動で押す係。

━━ なぜ要るか（2026-09-23 実測）━━

  ★**Lovableは main に push しても本番に出ない。**GitHub同期は `latest_commit_sha` まで
    来るが、公開（Publish）はまったく別の操作。だから「pushした＝出た」は永久に嘘になる。

  1040番で人が1回押して、実際に出た：
    x-deployment-id  psr2.80cf3e85-… → psr2.bc75840a-…（15:49押す → 15:51変わった）
  押すのは**無料**（deployは全プラン無料）。だから人を待たせる理由が無い。

━━ 係の分け方（★ここを混ぜない）━━

  見る係  tools/kohyou_kanshi.py … 測って赤/黄/青を出すだけ。**押さない。**
  押す係  tools/kohyou_osu.py（これ） … 赤のときだけ押して、**押した事実**を書くだけ。
                                      **判定を書かない**（赤を青に書き替えない）。
  規則    tools/hantei.py kohyou_osu_han() … 押してよいかの規則は1か所だけ。

  なぜ分けるか：押した本人が「出た」と言うと、誰も嘘を見つけられなくなる。
  出たかどうかは、押していない見る係が次の回に測って決める。

━━ 押したあと ━━

  押した直後は何も決めない（Lovableは公開に1〜2分かかる）。
  次の回から `x-deployment-id` を見に行き、
    変わった  → 「★出ました 前→後」をログに書いて終わり（青にするのは見る係）
    10分変わらない → **諦めて赤のまま残す**。同じコミットではもう押さない（人を呼ぶ）。

━━ 安全 ━━

  - 呼ぶ道具は **get_project と deploy_project の2つだけ**（白名簿で弾く）。
    send_message / create_project / エージェント / ビルドは**呼ばない**（金に直結）。
  - 15分に1回まで・1日12回まで。
  - Lovableが持つコミットが main と合っていなければ**押さない**（別の中身を出さない）。
  - 心臓を待たせない：1回の呼び出しでHTTPは最大2〜3本、押すとき以外は数百ミリ秒。
"""
import io
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
KANSHI = os.path.join(ST, "kohyou_kanshi.json")
STATE = os.path.join(ST, "kohyou_osu.json")
LOG = os.path.join(ST, "kohyou_osu.log")
GATE = os.path.join(ST, ".kohyou_osu_gate")
TOKEN_PATH = os.path.expanduser("~/.tamago/lovable_oauth.json")

INTERVAL_SEC = 60        # 心臓は15秒おきに呼ぶ。実際に動くのは1分に1回
VERIFY_LIMIT_SEC = 600   # 押してから10分変わらなければ諦めて赤のまま残す

MCP_URL = "https://mcp.lovable.dev"
TOKEN_URL = "https://lovable.dev/oauth/token"
CLIENT_ID = "6d465f583e1e4ce5801b1616f735670c"
# ★mcp.lovable.dev は User-Agent が無いと Cloudflare 1010 で 403（1040aで実測）
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
YURUSU = ("get_project", "deploy_project")   # ★これ以外は呼ばない

# 押す相手。見る係の WATCH と名前で結びつける。
MATO = {
    "ごきげん補給所": {
        "project_id": "8ebdb648-3686-4457-b42c-d01c493793b1",
        "url": "https://joy-relief-station.lovable.app/",
        "repo": "tamago2022/joy-relief-station",
    },
}


def _now():
    return time.strftime("%F %T")


def _log(line):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (_now(), line))
    except Exception:
        pass


def _load(path, default=None):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def _save(d):
    tmp = STATE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def _deploy_key(dep):
    """x-deployment-id のうち**公開ごとに変わるUUID部分だけ**（見る係と同じ切り方）。"""
    parts = (dep or "").split(".")
    return parts[1] if len(parts) >= 2 else (dep or "")


def _honban_key(url, timeout=15):
    """本番を1回叩いて deploymentId のUUID部分を返す。中身は読まない。"""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={
            "User-Agent": "tamago-kohyou-osu/1.0 (+1041)",
            "Cache-Control": "no-cache", "Pragma": "no-cache"})
        with urllib.request.urlopen(req, timeout=timeout,
                                    context=ssl.create_default_context()) as res:
            for k, v in res.getheaders():
                if k.lower() == "x-deployment-id":
                    return _deploy_key(v.strip())
    except Exception as e:
        _log("本番のヘッダが取れません：%s: %s" % (type(e).__name__, str(e)[:120]))
    return ""


# ───────────────────────── Lovable MCP（白名簿つき） ─────────────────────────

class Lovable(object):
    def __init__(self):
        self.tok = _load(TOKEN_PATH, {})
        self.sid = ""
        self._n = 0
        self._refreshed = False

    def ok(self):
        return bool(self.tok.get("access_token"))

    def _refresh(self):
        """access_token が切れていたら refresh_token で取り直す（人を呼ばない）。"""
        rt = self.tok.get("refresh_token")
        if not rt or self._refreshed:
            return False
        self._refreshed = True
        body = urllib.parse.urlencode({
            "grant_type": "refresh_token", "refresh_token": rt,
            "client_id": CLIENT_ID}).encode()
        try:
            req = urllib.request.Request(TOKEN_URL, data=body, method="POST", headers={
                "Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as res:
                d = json.loads(res.read().decode("utf-8", "ignore"))
        except Exception as e:
            _log("鍵の取り直しに失敗：%s: %s" % (type(e).__name__, str(e)[:160]))
            return False
        if not d.get("access_token"):
            return False
        self.tok.update(d)
        self.sid = ""
        try:
            with io.open(TOKEN_PATH, "w", encoding="utf-8") as f:
                json.dump(self.tok, f)
        except Exception:
            pass
        _log("鍵を取り直しました（refresh_token）")
        return True

    def _rpc(self, method, params=None, retry=True):
        self._n += 1
        payload = json.dumps({"jsonrpc": "2.0", "id": self._n,
                              "method": method, "params": params or {}}).encode()
        h = {"Content-Type": "application/json", "User-Agent": UA,
             "Accept": "application/json, text/event-stream",
             "MCP-Protocol-Version": "2025-06-18",
             "Authorization": "Bearer %s" % self.tok.get("access_token", "")}
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        req = urllib.request.Request(MCP_URL, data=payload, method="POST", headers=h)
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                s = res.headers.get("Mcp-Session-Id")
                if s:
                    self.sid = s
                return res.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:200]
            if e.code in (401, 403) and retry and self._refresh():
                self.hello()
                return self._rpc(method, params, retry=False)
            return "HTTP %s %s" % (e.code, body)
        except Exception as e:
            return "ERR %s: %s" % (type(e).__name__, str(e)[:160])

    def hello(self):
        return self._rpc("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "tamago-kohyou-osu", "version": "1041"}})

    def call(self, name, args):
        if name not in YURUSU:
            return None, "★白名簿にない道具は呼びません：%s" % name
        raw = self._rpc("tools/call", {"name": name, "arguments": args})
        try:
            line = [x for x in raw.splitlines() if x.startswith("data: ")][-1][6:]
            txt = json.loads(line)["result"]["content"][0]["text"]
            return json.loads(txt), ""
        except Exception:
            return None, (raw or "")[:300]


# ───────────────────────────── 本体 ─────────────────────────────

def _today():
    return time.strftime("%F")


def _kanshi_item():
    """見る係が書いたものを読むだけ（自分では測り直さない＝物差しを2本にしない）。"""
    doc = _load(KANSHI, {})
    for it in (doc.get("items") or []):
        if it.get("name") in MATO:
            return it
    return None


def _verify(st, it):
    """押したあと、出たかを確かめる。★出たと決めるのはここではなく見る係。"""
    mato = MATO[it["name"]]
    before = st.get("pressedBeforeKey") or ""
    now_key = _honban_key(mato["url"])
    if now_key and before and now_key != before:
        _log("★出ました %s 前=%s → 後=%s（押したのは %s / コミット %s）"
             % (it["name"], before, now_key, st.get("pressedAt", "?"),
                st.get("pressedSha", "?")))
        st["phase"] = ""
        st["lastResult"] = "出た"
        st["lastAfterKey"] = now_key
        return st
    machi = time.time() - (st.get("pressedAtTs") or 0)
    if machi > VERIFY_LIMIT_SEC:
        _log("★押しても変わりませんでした %s（%s のまま %d分）。"
             "赤のまま残します。%s では**もう押しません**"
             % (it["name"], before, int(machi) // 60, st.get("pressedSha", "?")))
        st["phase"] = ""
        st["lastResult"] = "押しても出なかった"
        st["akirametaSha"] = st.get("pressedSha", "")
        return st
    st["lastResult"] = "確かめ中（%d秒）" % int(machi)
    return st


def _press(st, it):
    """押す。★押す前にもう一度「同じ企画か」を確かめる。"""
    mato = MATO[it["name"]]
    lv = Lovable()
    if not lv.ok():
        _log("鍵がありません（%s）。押せないので赤のまま残します" % TOKEN_PATH)
        st["lastResult"] = "鍵が無い"
        return st
    lv.hello()
    o, err = lv.call("get_project", {"project_id": mato["project_id"]})
    if o is None:
        _log("get_project が読めません：%s" % err)
        st["lastResult"] = "get_project が読めない"
        return st
    sha = (o.get("latest_commit_sha") or "")[:8]
    machi_sha = (it.get("machiSha") or "")[:8]
    main_sha = (it.get("mainSha") or "")[:8]
    if sha not in (machi_sha, main_sha) or not sha:
        _log("★押しません：Lovableが持つコミット %s が main(%s)／待ち(%s) と合いません"
             % (sha or "-", main_sha or "-", machi_sha or "-"))
        st["lastResult"] = "Lovableがmainをまだ取り込んでいない"
        return st

    before = _honban_key(mato["url"]) or it.get("deployKey") or ""
    r, err = lv.call("deploy_project", {"project_id": mato["project_id"]})
    if r is None:
        _log("deploy_project の返事が読めません：%s" % err)
        st["lastResult"] = "deploy_project が読めない"
        return st
    _log("押しました %s ← %s（Lovableのコミット %s / 前=%s / 返事 status=%s id=%s url=%s）"
         % (it["name"], "赤", sha, before or "-", r.get("status"),
            (r.get("deployment_id") or "")[:8], r.get("url")))
    d = _today()
    if st.get("day") != d:
        st["day"], st["pressCountToday"] = d, 0
    st["pressCountToday"] = int(st.get("pressCountToday") or 0) + 1
    st["phase"] = "verifying"
    st["pressedAt"] = _now()
    st["pressedAtTs"] = time.time()
    st["pressedBeforeKey"] = before
    st["pressedSha"] = sha
    st["lastPressAt"] = st["pressedAtTs"]
    st["lastPressSha"] = sha
    st["lastResult"] = "押した（確かめ待ち）"
    st["lastDeployId"] = r.get("deployment_id") or ""
    return st


def run_now():
    """1回分。押すか押さないかを決めて、決めた理由を必ず残す。"""
    st = _load(STATE, {})
    if st.get("day") != _today():
        st["day"], st["pressCountToday"] = _today(), 0
    it = _kanshi_item()
    if not it:
        st["checkedAt"] = _now()
        st["riyuu"] = "見る係の記録がまだありません"
        _save(st)
        return st

    if st.get("phase") == "verifying":
        st = _verify(st, it)

    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import hantei
    han = hantei.kohyou_osu_han(
        hantei=it.get("hantei") or "", machi_sha=(it.get("machiSha") or "")[:8],
        now=time.time(), last_press_at=st.get("lastPressAt") or 0.0,
        last_press_sha=st.get("lastPressSha") or "",
        press_count_today=int(st.get("pressCountToday") or 0),
        akirameta_sha=st.get("akirametaSha") or "", phase=st.get("phase") or "")
    st["checkedAt"] = _now()
    st["hanteiOfKanshi"] = it.get("hantei")
    st["riyuu"] = han["riyuu"]
    if han["osu"]:
        _log("判断：%s" % han["riyuu"])
        st = _press(st, it)
    _save(st)
    return st


def run():
    """心臓から毎回呼ばれる入口。INTERVAL_SEC に1回しか動かない。"""
    try:
        if os.path.exists(GATE) and time.time() - os.path.getmtime(GATE) < INTERVAL_SEC:
            return
        io.open(GATE, "w").write(str(time.time()))
    except Exception:
        return
    try:
        run_now()
    except Exception as e:
        _log("押す係が転びました：%s: %s" % (type(e).__name__, str(e)[:160]))


if __name__ == "__main__":
    print(json.dumps(run_now(), ensure_ascii=False, indent=1))
