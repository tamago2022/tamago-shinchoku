#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1166番【次に何がいつ出るか・1枚】

たまごさんが見るのはこの1枚だけ。スマホで開ける。
  https://tamago2022.github.io/tamago-shinchoku/status/public/1166_yotei.html

出すもの:
  ・Bufferの予約（実測。取り直したもの。自己申告ではない）
  ・その後ろに並んでいる待機列（machi.json）が、ところてん式にどの枠へ繰り上がるか
  ・関所で外したもの（理由1行）

心臓（tools/top_status.py の末尾）から毎周回呼ばれる。鍵が無い周回は何もせず戻る。
"""
import io
import json
import os
import sys
import datetime
import urllib.request
import urllib.error
import html as H

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
API = "https://api.buffer.com"
JST = datetime.timezone(datetime.timedelta(hours=9))
PUB = os.path.join(REPO, "status", "public")
OUT_HTML = os.path.join(PUB, "1166_yotei.html")
OUT_JSON = os.path.join(PUB, "1166_yotei.json")
MACHI = os.path.join(REPO, "status", "buffer_queue", "machi.json")
HAZURE = os.path.join(REPO, "status", "1166", "hazureta.json")
WANT = "oasisjoyrelief"
FORBID = ["eggypop2014"]
SLOTS = [(9, 0), (20, 0)]
CAP = 10          # ★Bufferの予約は10本が上限（2026-09-27 実測：11本目は
                  #   「Scheduled posts limit reached. You have 10 scheduled posts out of 10 allowed.」）


def gql(tok, q, v=None):
    b = {"query": q}
    if v:
        b["variables"] = v
    r = urllib.request.Request(API, data=json.dumps(b).encode(),
                               headers={"Content-Type": "application/json",
                                        "Authorization": "Bearer %s" % tok,
                                        "User-Agent": "tamago-1166-yotei"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())


Q_POSTS = """
query($o: OrganizationId!, $c: [ChannelId!], $s: [PostStatus!]) {
  posts(input: { organizationId: $o, sort: [{ field: dueAt, direction: asc }],
                 filter: { status: $s, channelIds: $c } }) {
    edges { node { id text dueAt status } }
  }
}
"""


def jst(iso):
    for f in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            t = datetime.datetime.strptime(iso, f)
            return t.replace(tzinfo=datetime.timezone.utc).astimezone(JST)
        except Exception:
            continue
    return None


def atomaru(taken, n):
    """予約で埋まっていない先の枠を n 個。"""
    now = datetime.datetime.now(JST)
    out, day = [], now.date()
    for _ in range(80):
        for (h, mi) in SLOTS:
            c = datetime.datetime(day.year, day.month, day.day, h, mi, tzinfo=JST)
            if c <= now + datetime.timedelta(minutes=10):
                continue
            if c.strftime("%F %H:%M") in taken:
                continue
            out.append(c)
            if len(out) >= n:
                return out
        day += datetime.timedelta(days=1)
    return out


def midashi(t):
    """本文から「誰の・何の曲か」の行を拾う（2行目の — を含む行）。"""
    for ln in (t or "").split("\n"):
        if "—" in ln:
            return ln.strip()
    return (t or "").split("\n")[0][:60]


def build():
    import kagi
    tok = kagi.get("BUFFER_ACCESS_TOKEN")
    if not tok:
        return 3
    orgs = ((gql(tok, "query{account{organizations{id name}}}").get("data") or {})
            .get("account") or {}).get("organizations") or []
    ch = org = None
    for o in orgs:
        cs = (gql(tok, "query($o:OrganizationId!){channels(input:{organizationId:$o})"
                  "{id name displayName}}", {"o": o["id"]})
              .get("data") or {}).get("channels") or []
        for c in cs:
            ns = [(c.get(k) or "").strip().lstrip("@").lower()
                  for k in ("name", "displayName") if (c.get(k) or "").strip()]
            if any(n in FORBID for n in ns):
                continue
            if WANT in ns:
                ch, org = c, o["id"]
    if not ch:
        return 4

    def rows(statuses):
        e = ((gql(tok, Q_POSTS, {"o": org, "c": [ch["id"]], "s": statuses})
              .get("data") or {}).get("posts") or {}).get("edges") or []
        return [x["node"] for x in e]

    yoyaku = rows(["scheduled"])
    dashita = rows(["sent"])[-5:]

    taken = set()
    for p in yoyaku:
        t = jst(p.get("dueAt") or "")
        if t:
            taken.add(t.strftime("%F %H:%M"))

    machi = []
    try:
        machi = (json.load(io.open(MACHI, encoding="utf-8")).get("machi") or [])
    except Exception:
        pass
    waku = atomaru(taken, len(machi))

    hazure = []
    try:
        hazure = json.load(io.open(HAZURE, encoding="utf-8"))
    except Exception:
        pass

    data = {
        "at": datetime.datetime.now(JST).strftime("%F %H:%M"),
        "channel": "@" + WANT,
        "cap": CAP,
        "yoyaku": [{"due": (jst(p["dueAt"]).strftime("%F %H:%M") if jst(p.get("dueAt") or "") else "?"),
                    "midashi": midashi(p.get("text")),
                    "text": p.get("text") or ""} for p in yoyaku],
        "machi": [{"yotei": (waku[i].strftime("%F %H:%M") if i < len(waku) else "枠待ち"),
                   "midashi": midashi(m.get("text") if isinstance(m, dict) else str(m)),
                   "text": (m.get("text") if isinstance(m, dict) else str(m))}
                  for i, m in enumerate(machi)],
        "dashita": [{"due": (jst(p["dueAt"]).strftime("%F %H:%M") if jst(p.get("dueAt") or "") else "?"),
                     "midashi": midashi(p.get("text"))} for p in dashita],
        "hazureta": [{"nani": "%s / %s" % (x.get("artist"), x.get("song")),
                      "riyuu": x.get("riyuu", "")} for x in hazure],
    }
    io.open(OUT_JSON, "w", encoding="utf-8").write(
        json.dumps(data, ensure_ascii=False, indent=1))

    e = H.escape

    def li(items, key):
        if not items:
            return '<p class="none">なし</p>'
        out = ['<ol class="list">']
        for x in items:
            out.append('<li><b>%s</b><span>%s</span></li>'
                       % (e(x.get(key) or ""), e(x.get("midashi") or "")))
        out.append("</ol>")
        return "".join(out)

    if data["hazureta"]:
        haz = "".join('<li><b>%s</b><span>%s</span></li>'
                      % (e(x["nani"]), e(x["riyuu"])) for x in data["hazureta"])
    else:
        haz = '<p class="none">なし</p>'

    doc = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>次に何がいつ出るか</title>
<style>
:root{color-scheme:light dark}
body{margin:0;padding:18px 14px 60px;font:16px/1.7 -apple-system,"Hiragino Sans",sans-serif;
 background:#faf8f4;color:#1c1a17;max-width:720px;margin-inline:auto}
h1{font-size:20px;margin:0 0 4px}
.at{color:#7a7367;font-size:13px;margin:0 0 22px}
h2{font-size:15px;margin:30px 0 8px;padding-bottom:6px;border-bottom:1px solid #e2dcd0}
.n{font-weight:400;color:#7a7367}
ol.list{list-style:none;margin:0;padding:0}
ol.list li{display:flex;gap:10px;padding:9px 0;border-bottom:1px dotted #e2dcd0;align-items:baseline}
ol.list li b{flex:0 0 118px;font-variant-numeric:tabular-nums;font-size:13px;color:#4a4338}
ol.list li span{flex:1}
.none{color:#9a9287}
.machi ol.list li b{color:#8a7a52}
footer{margin-top:34px;color:#7a7367;font-size:13px}
a{color:#3a6ea5}
</style></head><body>
<h1>次に何がいつ出るか</h1>
<p class="at">%(at)s 時点・%(channel)s・実測（Bufferから取り直した数字）</p>

<h2>予約に入っている <span class="n">%(nyoyaku)d 本／上限 %(cap)d 本</span></h2>
%(yoyaku)s

<h2 class="machi">その後ろで待っている <span class="n">%(nmachi)d 本</span></h2>
<p class="at">上の予約が1本出るたびに、毎朝6時の補充便が上から順に繰り上げます。</p>
<div class="machi">%(machi)s</div>

<h2>関所で外したもの</h2>
<ol class="list">%(hazureta)s</ol>

<h2>もう出たもの</h2>
%(dashita)s

<footer>
Bufferの予約欄：<a href="https://publish.buffer.com/all-channels/queue">publish.buffer.com</a><br>
★Bufferの予約は10本が上限。だから11本目以降はこのページの「待っている」に並びます。
</footer>
</body></html>"""
    io.open(OUT_HTML, "w", encoding="utf-8").write(doc % {
        "at": e(data["at"]), "channel": e(data["channel"]), "cap": CAP,
        "nyoyaku": len(data["yoyaku"]), "nmachi": len(data["machi"]),
        "yoyaku": li(data["yoyaku"], "due"),
        "machi": li(data["machi"], "yotei"),
        "dashita": li(data["dashita"], "due"),
        "hazureta": haz,
    })
    return 0


def main():
    try:
        return build()
    except Exception as ex:
        try:
            io.open(os.path.join(REPO, "status", "1166", "yotei.log"),
                    "a", encoding="utf-8").write(
                "%s %s\n" % (datetime.datetime.now(JST).strftime("%F %T"), ex))
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
