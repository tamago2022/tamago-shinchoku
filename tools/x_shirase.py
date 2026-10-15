#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【出たら押し出す】Xに投稿が出た瞬間に、たまごさんの手元へリンクを1行。

たまごさんの言葉（2026-09-27）:
  「投稿が出たら『投稿されました＋Xの実リンク』を1行。たまごさんが見に行かなくていい。」

出たことに気づくのは 1167_ireru1（Bufferから取り直す係）だけなので、そこから呼ばれる。
呼ばれたら同じ1行を3か所へ置く。

  1. status/dispatch_outbox.jsonl      … 心臓が拾ってたまごさんへ押し出す口
  2. status/public/1170_deta.jsonl     … 出たものの台帳（1行1本・消さない）
  3. status/public/1170_deta.html      … スマホで開く1枚

★Xの実リンクについて（正直に書く）
  Buffer の GraphQL の「公開後のURL」の項目名は、こちらから試して確かめるしかない。
  だから **1回の呼び出しで候補を1つだけ試す**（枠を無駄に使わないため）。
  ・当たった項目名は .x_link_field.json に覚えて、以後そこだけ読む
  ・全部外れたら二度と試さず、プロフィールのURLを出して「実リンクは取れなかった」と書く。
    取れていないものを取れたフリにはしない。
"""
import datetime
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
JST = datetime.timezone(datetime.timedelta(hours=9))
STATUS = os.path.join(REPO, "status")
PUB = os.path.join(STATUS, "public")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")
DAICHO = os.path.join(PUB, "1170_deta.jsonl")
OUT_HTML = os.path.join(PUB, "1170_deta.html")
FIELD = os.path.join(STATUS, "buffer_queue", ".x_link_field.json")
PROFILE = "https://x.com/oasisjoyrelief"

KOUHO = ["postUrl", "serviceLink", "permalink", "serviceUrl", "link"]


def q_x_link(field):
    """その項目名を1つだけ聞くクエリ。呼ぶ側の gql に渡す。"""
    return "query($id: PostId!){ post(input:{id:$id}){ id %s } }" % field


def _yomu(p, kara):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return kara


def _kaku(p, d):
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(d, io.open(p, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    except Exception:
        pass


def atatta():
    return (_yomu(FIELD, {}).get("atari") or "")


def akirameta():
    return bool(_yomu(FIELD, {}).get("akirameta"))


def _tsugi_no_kouho():
    hazure = _yomu(FIELD, {}).get("hazure") or []
    for k in KOUHO:
        if k not in hazure:
            return k
    return ""


def x_link(gql, tok, post_id):
    """出た投稿のXのURLを取ろうとする。取れなければ ""。

    gql … 呼ぶ側の叩き手（門番を通るもの）。gql(tok, query, variables) の形。
    """
    if not post_id:
        return ""
    d = _yomu(FIELD, {})
    tameshi = atatta() or ("" if akirameta() else _tsugi_no_kouho())
    if not tameshi:
        return ""
    try:
        res = gql(tok, q_x_link(tameshi), {"id": post_id}) or {}
    except Exception:
        return ""
    if res.get("errors"):
        hazure = list(d.get("hazure") or [])
        if tameshi not in hazure:
            hazure.append(tameshi)
        d["hazure"] = hazure
        d["akirameta"] = len(hazure) >= len(KOUHO)
        d["saigo"] = datetime.datetime.now(JST).strftime("%F %T")
        d["errors"] = str(res.get("errors"))[:200]
        _kaku(FIELD, d)
        return ""
    node = ((res.get("data") or {}).get("post") or {})
    v = node.get(tameshi)
    url = v if (isinstance(v, str) and v.startswith("http")) else ""
    if url:
        d["atari"] = tameshi
        d["saigo"] = datetime.datetime.now(JST).strftime("%F %T")
        _kaku(FIELD, d)
    return url


def sumi():
    """もう知らせた投稿IDの集合。"""
    out = set()
    try:
        for ln in io.open(DAICHO, encoding="utf-8"):
            try:
                out.add(json.loads(ln).get("post_id"))
            except Exception:
                continue
    except Exception:
        pass
    return out


def midashi(t):
    for ln in (t or "").split("\n"):
        if "—" in ln:
            return ln.strip()
    return (t or "").split("\n")[0][:60]


def hitotsu(post_id, due, text, url=""):
    """1本ぶんを3か所へ置く。すでに知らせていれば何もしない。"""
    if not post_id or post_id in sumi():
        return False
    ima = datetime.datetime.now(JST)
    honmono = bool(url)
    rec = {"ts": ima.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
           "post_id": post_id, "due": due or "",
           "midashi": midashi(text), "x_url": url or "",
           "x_url_wa_honmono": honmono, "profile": PROFILE}
    try:
        os.makedirs(PUB, exist_ok=True)
        with io.open(DAICHO, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass

    if honmono:
        msg = "投稿されました（%s）%s\n%s" % (due or "", rec["midashi"], url)
        urls = [url]
    else:
        msg = ("投稿されました（%s）%s\n★XのURLはBufferのAPIから取れていません。"
               "こちらで見えます: %s" % (due or "", rec["midashi"], PROFILE))
        urls = [PROFILE]
    try:
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": rec["ts"], "n": "1170-deta-%s" % post_id,
                "type": "x_toukou_deta", "title": "Xに投稿されました",
                "message": msg, "urls": urls, "ok": True,
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    kaku_html()
    return True


def kaku_html():
    import html as H
    e = H.escape
    rows = []
    try:
        for ln in io.open(DAICHO, encoding="utf-8"):
            try:
                rows.append(json.loads(ln))
            except Exception:
                continue
    except Exception:
        pass
    rows = rows[::-1][:80]
    li = []
    for r in rows:
        u = r.get("x_url") or ""
        if u:
            a = '<a href="%s">Xで見る</a>' % e(u)
        else:
            a = ('<span class="nashi">実リンク未取得</span> '
                 '<a href="%s">プロフィール</a>' % e(r.get("profile") or PROFILE))
        li.append('<li><b>%s</b><span>%s</span><em>%s</em></li>'
                  % (e(r.get("due") or r.get("ts") or ""),
                     e(r.get("midashi") or ""), a))
    body = "".join(li) or '<li class="none">まだありません</li>'
    doc = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>出た投稿</title>
<style>
:root{color-scheme:light dark}
body{margin:0;padding:18px 14px 60px;font:16px/1.7 -apple-system,"Hiragino Sans",sans-serif;
 background:#faf8f4;color:#1c1a17;max-width:720px;margin-inline:auto}
h1{font-size:20px;margin:0 0 4px}
.at{color:#7a7367;font-size:13px;margin:0 0 22px}
ol{list-style:none;margin:0;padding:0}
li{display:flex;flex-wrap:wrap;gap:4px 10px;padding:10px 0;
 border-bottom:1px dotted #e2dcd0;align-items:baseline}
li b{flex:0 0 118px;font-variant-numeric:tabular-nums;font-size:13px;color:#4a4338}
li span{flex:1 1 200px}
li em{flex:0 0 auto;font-style:normal;font-size:13px}
li.none{display:block;color:#9a9287;border:0}
.nashi{color:#a8452f}
a{color:#3a6ea5}
</style></head><body>
<h1>出た投稿</h1>
<p class="at">%(at)s 時点・新しい順。出るたびにここと手元のお知らせへ1行増えます。
見に行かなくていいように作った1枚です。</p>
<ol>%(body)s</ol>
</body></html>""" % {"at": e(datetime.datetime.now(JST).strftime("%F %H:%M")),
                     "body": body}
    try:
        os.makedirs(PUB, exist_ok=True)
        io.open(OUT_HTML, "w", encoding="utf-8").write(doc)
    except Exception:
        pass


if __name__ == "__main__":
    kaku_html()
    print("台帳 %d 本" % len(sumi()))
    print("Xの項目名:", json.dumps(_yomu(FIELD, {}), ensure_ascii=False))
