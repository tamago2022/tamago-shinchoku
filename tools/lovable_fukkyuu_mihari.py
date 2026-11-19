#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lovable の公開の鍵が戻ったら、自分で気づいて公開を押し、本番が変わったことまで確かめる見張り（2026-10-29）。

なぜ要るか（2026-10-29 実測）：
  ・10-14 06:24 から refresh_token が invalid_grant（.prev の古い鍵も invalid_grant）。押さずに戻す道は無い。
  ・10-22 に作られた承認URLは、~/.tamago/lovable_pkce.json の verifier と code_challenge が対になっていなかった
    （sha256(verifier) ≠ challenge）。押しても鍵の交換で落ちる URL を、10-22〜10-29 に何度も人に渡していた。
    → 10-29 06:35 に verifier/challenge/state を作り直し、受け皿（lovable_listener.py）も立て直した。
  ・公開押し係 kohyou_osu は「見る係が赤」の時しか押さない（今は黄と赤を行き来）ので、鍵が戻っても
    すぐ押されるとは限らない。だからこの見張りが、鍵が戻った瞬間に1回だけ押す。

やること（課金0・Lovable への書き込みは deploy_project だけ＝lovable_kinshi の白名簿どおり）：
  1. 30秒おきに ~/.tamago/lovable_oauth.json が「見張り開始より新しい・access_token あり」になったかを見る
  2. なったら MCP initialize → 本番の deployment-id を控える → deploy_project を1回
  3. tools/koukai_kakunin.py --before <ID> --wait 12 で本番が変わったかを確かめる（変わらなければ落ちた関所を出す）
  4. queue の「Lovable の鍵で公開待ち」の便を古い順に並べ、それぞれの本番URLを1本ずつ開いて 200 かを記録
  5. 結果を status/lovable_fukkyuu.json、Dispatch へ1行（status/dispatch_outbox.jsonl）。終わったら止まる。
  一時ファイルは作らない（記録は status/ だけ）。72時間で諦めて止まる。

使い方：
  python3 tools/lovable_fukkyuu_mihari.py --mihari     # 常駐（鍵が戻るまで待つ。mac_jobs から nohup で起こす）
  python3 tools/lovable_fukkyuu_mihari.py --tick       # 1回だけ見る
  python3 tools/lovable_fukkyuu_mihari.py --self-test
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUT = os.path.join(ST, "lovable_fukkyuu.json")
OUTBOX = os.path.join(ST, "dispatch_outbox.jsonl")
QUEUE = os.path.join(ST, "queue.json")
TOKEN = os.path.expanduser("~/.tamago/lovable_oauth.json")
PROJECT_ID = "8ebdb648-3686-4457-b42c-d01c493793b1"
MCP = "https://mcp.lovable.dev"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
KAGIRI_SEC = 72 * 3600
PROD_RE = re.compile(r"https://joy-relief-station\.lovable\.app/[^\s)）\]>`*]*")
MACHI_RE = re.compile(r"(Lovable|公開).{0,40}(鍵|同意|認証|OAuth|invalid_grant|need_consent|401|403)|公開待ち")

sys.path.insert(0, HERE)


def _load(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def _save(d):
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)


def _outbox(title, message):
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%FT%T+09:00"), "n": "lovable-fukkyuu",
                            "type": "lovable_fukkyuu", "title": title, "message": message},
                           ensure_ascii=False) + "\n")


def kagi_modotta(started_ts, token_path=TOKEN):
    """見張り開始より後に新しい鍵が置かれ、access_token があれば True。"""
    try:
        if os.path.getmtime(token_path) <= started_ts:
            return False
        return bool((_load(token_path) or {}).get("access_token"))
    except Exception:
        return False


def machi_bin(queue):
    """queue から「Lovable の鍵で公開待ち」の便を古い順（番号順）に。本番URLつき。"""
    items = queue if isinstance(queue, list) else (queue or {}).get("queue") or (queue or {}).get("items") or []
    out = []
    for it in items:
        if not isinstance(it, dict) or it.get("status") not in ("awaiting_check", "waiting", "hold"):
            continue
        res = str(it.get("result") or "")
        if not MACHI_RE.search(res):
            continue
        urls = []
        for u in PROD_RE.findall(res):
            u = u.rstrip(".,、。")
            if u not in urls:
                urls.append(u)
        try:
            n = int(it.get("n"))
        except Exception:
            continue
        out.append({"n": n, "title": str(it.get("title") or "")[:60], "urls": urls[:3]})
    out.sort(key=lambda x: x["n"])
    return out


def _mcp(at, method, params, sid):
    import lovable_kinshi  # 白名簿（deploy_project と読むだけ）を必ず通す
    if method == "tools/call":
        lovable_kinshi.mamoru("tools/call", params)
    pl = json.dumps({"jsonrpc": "2.0", "id": int(time.time() * 1000) % 100000, "method": method,
                     "params": params or {}}).encode()
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
         "Authorization": "Bearer " + at, "User-Agent": UA}
    if sid.get("v"):
        h["Mcp-Session-Id"] = sid["v"]
    try:
        with urllib.request.urlopen(urllib.request.Request(MCP, data=pl, method="POST", headers=h), timeout=90) as r:
            if r.headers.get("Mcp-Session-Id"):
                sid["v"] = r.headers.get("Mcp-Session-Id")
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")[:400]
    except Exception as e:
        return 0, "ERR %r" % (e,)


def _dep_id():
    import koukai_kakunin
    return koukai_kakunin.dep_id()


def _http(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "tamago-lovable-fukkyuu", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def oshite_tashikameru(d):
    at = (_load(TOKEN) or {}).get("access_token") or ""
    sid = {}
    st, body = _mcp(at, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                        "clientInfo": {"name": "tamago-fukkyuu", "version": "1"}}, sid)
    d["initialize"] = st
    if st != 200:
        d["kekka"] = "鍵は来たが MCP initialize が %s" % st
        return d
    try:
        before = _dep_id()
    except Exception:
        before = ""
    d["before"] = before
    st, body = _mcp(at, "tools/call", {"name": "deploy_project", "arguments": {"project_id": PROJECT_ID}}, sid)
    d["deploy"] = {"http": st, "at": time.strftime("%F %T"), "body": body[:200]}
    p = subprocess.run([sys.executable, os.path.join(HERE, "koukai_kakunin.py"), "--before", before, "--wait", "12"],
                       cwd=REPO, capture_output=True, text=True, timeout=3600)
    kk = _load(os.path.join(ST, "koukai_kakunin.json"), {}) or {}
    d["honban"] = {"kawatta": bool(kk.get("ok")), "before": kk.get("before"), "after": kk.get("after"),
                   "ochita_kanmon": [x.get("kanmon") for x in kk.get("ochita") or []]}
    # 公開待ちだった便を古い順に1本ずつ本番で確かめる
    bins = machi_bin(_load(QUEUE, []))
    for b in bins:
        b["honban"] = [{"url": u, "http": _http(u)} for u in b["urls"]]
        time.sleep(1)
    d["machi_bin"] = bins
    d["kekka"] = ("本番が変わった %s→%s・公開待ちだった便 %d件を本番で確認" % (kk.get("before"), kk.get("after"), len(bins))
                  if kk.get("ok") else
                  "押したが本番が変わらない（落ちた関所：%s）" % (", ".join(d["honban"]["ochita_kanmon"]) or "なし＝Lovable側を疑う"))
    return d


def tick(d):
    if d.get("owari"):
        return d
    d["mitaAt"] = time.strftime("%F %T")
    if kagi_modotta(d["startedTs"]):
        d["kagiModottaAt"] = time.strftime("%F %T")
        _save(d)
        d = oshite_tashikameru(d)
        d["owari"] = True
        _outbox("Lovableの鍵が戻った", d.get("kekka", ""))
    elif time.time() - d["startedTs"] > KAGIRI_SEC:
        d["owari"] = True
        d["kekka"] = "72時間待ったが承認が押されなかった（見張りを止めた）"
        _outbox("Lovableの承認待ち 72時間", "承認URLは status/lovable_shounin.json の url")
    _save(d)
    return d


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        return self_test()
    d = _load(OUT) or {}
    if not d or d.get("owari") and "--atarashiku" in a:
        d = {"startedAt": time.strftime("%F %T"), "startedTs": time.time(), "pid": os.getpid()}
    if "--tick" in a:
        tick(d)
        print(json.dumps(d, ensure_ascii=False)[:500])
        return 0
    if "--mihari" in a:
        d["pid"] = os.getpid()
        _save(d)
        while not d.get("owari"):
            d = tick(d)
            if not d.get("owari"):
                time.sleep(30)
        return 0
    print(__doc__)
    return 0


def self_test():
    import tempfile
    ng = []
    td = tempfile.mkdtemp(prefix="fukkyuu_selftest_")
    try:
        tp = os.path.join(td, "tok.json")
        json.dump({"refresh_token": "x"}, open(tp, "w"))
        t0 = time.time()
        if kagi_modotta(t0 + 10, tp):
            ng.append("古い鍵を『戻った』と誤判定")
        json.dump({"access_token": "a"}, open(tp, "w"))
        os.utime(tp, (t0 + 20, t0 + 20))
        if not kagi_modotta(t0 + 10, tp):
            ng.append("新しい鍵を見逃した")
        q = [{"n": 300, "status": "awaiting_check", "result": "Lovableの鍵が切れて公開待ち 本番: https://joy-relief-station.lovable.app/notes 。"},
             {"n": 100, "status": "awaiting_check", "result": "公開待ち（Lovableの鍵） https://joy-relief-station.lovable.app/world/cute"},
             {"n": 200, "status": "done", "result": "公開待ち"},
             {"n": 150, "status": "awaiting_check", "result": "関係ない完了"}]
        b = machi_bin(q)
        if [x["n"] for x in b] != [100, 300]:
            ng.append("公開待ちの便の拾い方・並び順が違う %r" % [x["n"] for x in b])
        if b and b[-1]["urls"] != ["https://joy-relief-station.lovable.app/notes"]:
            ng.append("本番URLの切り出しが違う %r" % b[-1]["urls"])
        import lovable_kinshi
        try:
            lovable_kinshi.mamoru("tools/call", {"name": "send_message", "arguments": {}})
            ng.append("send_message が白名簿で止まらない")
        except Exception:
            pass
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)
    print("自己試験：%s" % ("OK" if not ng else "NG"))
    for x in ng:
        print("  ★NG", x)
    return 1 if ng else 0


if __name__ == "__main__":
    sys.exit(main())
