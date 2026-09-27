#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1168番【予約済み10本を1本ずつ検品して1枚にする】

たまごさんの言葉（2026-09-27）:
  「予約済みの内容見せて。入り口やページリンク、文言確認したい。
    動画の有無、関連等すべてクリアしてますか」
  「『クリアしています』と書くだけは不可。1本ずつ◯✕と数字で」

1本につき見るもの（全部 実測。推定しない）:
  ① 出る日時（Bufferから取り直した dueAt）
  ② 本文そのまま
  ③ リンク先URL（HTTPコードを自分で叩いて確かめる）
  ④ 本人の動画があるか（一番大きい動画。幅500px以上）＋そのURL
  ⑤ 関連が何本か（4本以上か）
  ⑥ ページが完成しているか（欠けているものを名指し）
  ⑦ 重複していないか（予約どうし＋もう出したものの台帳）

出す: status/public/1168_kenpin.html（暗い配色・スマホ幅）
     status/public/1168_kenpin.json

使い方:
  python3 tools/1168_kenpin_hyou.py            … 検品して1枚つくる
  python3 tools/1168_kenpin_hyou.py --hazusu   … ✕のものを予約から外す
"""
import io
import json
import os
import re
import subprocess
import sys
import time
import datetime
import urllib.request
import urllib.error
import html as H

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import kagi          # noqa: E402
import buffer_waku   # noqa: E402

SNAP = os.path.join(REPO, "status", "1168", "snapshot.json")

API = "https://api.buffer.com"
JST = datetime.timezone(datetime.timedelta(hours=9))
PUB = os.path.join(REPO, "status", "public")
D = os.path.join(REPO, "status", "1168")
OUT_HTML = os.path.join(PUB, "1168_kenpin.html")
OUT_JSON = os.path.join(PUB, "1168_kenpin.json")
DASHITA = os.path.join(REPO, "status", "buffer_queue", "dashita.jsonl")
WANT = "oasisjoyrelief"
FORBID = ["eggypop2014"]
KANREN_SAITEI = 4
MAIN_HABA = 500

Q_POSTS = """
query($o: OrganizationId!, $c: [ChannelId!], $s: [PostStatus!]) {
  posts(input: { organizationId: $o, sort: [{ field: dueAt, direction: asc }],
                 filter: { status: $s, channelIds: $c } }) {
    edges { node { id text dueAt status channelId } }
  }
}
"""
M_DEL = """
mutation($input: DeletePostInput!) {
  deletePost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id } }
    ... on MutationError { message }
  }
}
"""


def gql(tok, q, v=None):
    """★429（枠オーバー）は待って何度でも取り直す。黙って止まらない。

    Bufferの枠は 24時間250回／15分100回。心臓の係と重なると429が返るので、
    ここは 20→40→80→160→300秒 と待ってから同じ問い合わせをやり直す。
    """
    b = {"query": q}
    if v:
        b["variables"] = v
    machi = [20, 40, 80, 160, 300, 300, 300]
    for i in range(len(machi) + 1):
        r = urllib.request.Request(API, data=json.dumps(b).encode(),
                                   headers={"Content-Type": "application/json",
                                            "Authorization": "Bearer %s" % tok,
                                            "User-Agent": "tamago-1168-kenpin"})
        try:
            with urllib.request.urlopen(r, timeout=40) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code != 429 or i >= len(machi):
                raise
            print("  429（枠オーバー）。%d秒待って取り直す" % machi[i], flush=True)
            time.sleep(machi[i])


def jst(s):
    for f in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return (datetime.datetime.strptime(s, f)
                    .replace(tzinfo=datetime.timezone.utc).astimezone(JST))
        except Exception:
            continue
    return None


def url_no(text):
    for ln in reversed([x for x in (text or "").split("\n") if x.strip()]):
        m = re.search(r'https?://\S+', ln)
        if m:
            return m.group(0), (ln.strip() == m.group(0))
    return "", False


def http(u):
    try:
        r = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 tamago-1168"})
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def page_sekisho(urls):
    """headless Chrome でページを1本ずつ開いて数える（たまごさんのChromeには触らない）。"""
    os.makedirs(D, exist_ok=True)
    lst = os.path.join(D, "urls.txt")
    out = os.path.join(D, "pages.json")
    io.open(lst, "w", encoding="utf-8").write("\n".join(urls) + "\n")
    env = dict(os.environ, SEKISHO_SETTLE_MS="14000")
    subprocess.run(["node", os.path.join(HERE, "1164_page_sekisho.mjs"), lst, out],
                   cwd=REPO, env=env, timeout=60 * 12,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    d = json.load(io.open(out, encoding="utf-8"))
    rows = d["rows"] if isinstance(d, dict) else d
    return {r["url"]: (r.get("data") or {}) for r in rows}


def torinaosu(tok):
    """Bufferから取り直す。枠切れのときは前に取り直した控えを使う。

    ★控えを使ったときは deta に「いつ取り直したものか」を必ず書き、
      画面にもそう出す。取り直したフリをしない。
    """
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
        raise RuntimeError("チャンネル %s が無い" % WANT)

    def rows(st):
        e = ((gql(tok, Q_POSTS, {"o": org, "c": [ch["id"]], "s": st})
              .get("data") or {}).get("posts") or {}).get("edges") or []
        return [x["node"] for x in e]

    d = {"at": datetime.datetime.now(JST).strftime("%F %H:%M"),
         "org": org, "ch": ch["id"],
         "yoyaku": rows(["scheduled"]), "sent": rows(["sent"])}
    os.makedirs(os.path.dirname(SNAP), exist_ok=True)
    json.dump(d, io.open(SNAP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return d, "いま取り直した"


def main():
    tok = kagi.get("BUFFER_ACCESS_TOKEN")
    if not tok:
        print("鍵が無い")
        return 2

    if buffer_waku.ake():
        snap, itsu = torinaosu(tok)
    else:
        # ★枠切れ。叩かずに前の控えで作る。いつのものかを画面に出す。
        print(buffer_waku.riyuu())
        try:
            snap = json.load(io.open(SNAP, encoding="utf-8"))
        except Exception:
            print("控えも無い。出せない。")
            return 12
        itsu = "%s にBufferから取り直したもの（いまは枠切れで取り直せない）" % snap.get("at")
    yoyaku, sent = snap.get("yoyaku") or [], snap.get("sent") or []
    return kenpin(yoyaku, sent, itsu, tok, snap)


def kenpin(yoyaku, sent, itsu, tok, snap):
    print("予約 %d 本／もう出た %d 本（%s）" % (len(yoyaku), len(sent), itsu))

    urls = []
    for p in yoyaku:
        u, _ = url_no(p.get("text"))
        if u and u not in urls:
            urls.append(u)
    print("ページを %d 本ぶん開いて数えます（約 %d 分）" % (len(urls), max(1, len(urls) * 15 // 60)))
    pg = page_sekisho(urls)

    sent_txt = set((p.get("text") or "").strip() for p in sent)
    mita_txt = {}
    mita_url = {}
    out = []
    for i, p in enumerate(sorted(yoyaku, key=lambda x: x.get("dueAt") or ""), 1):
        text = (p.get("text") or "").strip()
        u, owari = url_no(text)
        k = pg.get(u) or {}
        vids = k.get("videos") or []
        main_v = vids[0] if vids else None
        kanren = int(k.get("kanren_honsuu") or 0)
        code = http(u) if u else 0

        ng = []
        if not u:
            ng.append("本文にURLが無い")
        elif code != 200:
            ng.append("リンクが %s（200でない）" % code)
        if not owari:
            ng.append("URLが本文のいちばん最後に無い")
        if not main_v or main_v.get("w", 0) < MAIN_HABA:
            ng.append("本人の動画（大きい方）が無い")
        if kanren < KANREN_SAITEI:
            ng.append("関連が %d 本（最低 %d 本）" % (kanren, KANREN_SAITEI))
        if not k.get("h1"):
            ng.append("ページの見出しが出ていない＝未完成")
        if text in sent_txt:
            ng.append("もう出したものと同じ本文")
        if text in mita_txt:
            ng.append("予約の %d 番目と同じ本文" % mita_txt[text])
        if u and u in mita_url:
            ng.append("予約の %d 番目と同じリンク先" % mita_url[u])
        mita_txt[text] = i
        if u:
            mita_url[u] = i

        t = jst(p.get("dueAt") or "")
        out.append({
            "n": i, "post_id": p.get("id"),
            "due": t.strftime("%F %H:%M") if t else "?",
            "youbi": "月火水木金土日"[t.weekday()] if t else "",
            "text": text, "url": u, "http": code, "url_owari": owari,
            "midashi": k.get("h1") or "", "title": k.get("title") or "",
            "main": ("https://youtu.be/" + main_v["id"]) if main_v else "",
            "main_size": ("%dx%d" % (main_v["w"], main_v["h"])) if main_v else "",
            "main_ok": bool(main_v and main_v.get("w", 0) >= MAIN_HABA),
            "kanren": kanren, "kanren_ok": kanren >= KANREN_SAITEI,
            "doga_zen": k.get("videos_all") or len(vids),
            "kanren_list": [{"url": "https://youtu.be/" + v["id"],
                             "title": v.get("alt") or ""} for v in vids[1:5]],
            "hantei": "◯" if not ng else "✕",
            "ng": ng,
        })

    data = {"at": datetime.datetime.now(JST).strftime("%F %H:%M"),
            "itsu": itsu, "waku": buffer_waku.riyuu(),
            "channel": "@" + WANT, "n": len(out),
            "ng": len([x for x in out if x["hantei"] == "✕"]),
            "rows": out}
    os.makedirs(PUB, exist_ok=True)
    json.dump(data, io.open(OUT_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    if "--hazusu" in sys.argv and not buffer_waku.ake():
        print("★枠切れなので外せない。", buffer_waku.riyuu())
    elif "--hazusu" in sys.argv:
        for x in out:
            if x["hantei"] != "✕":
                continue
            r = gql(tok, M_DEL, {"input": {"id": x["post_id"]}})
            dp = (r.get("data") or {}).get("deletePost") or {}
            x["hazushita"] = bool((dp.get("post") or {}).get("id"))
            x["hazushita_err"] = dp.get("message") or ""
            print("外した" if x["hazushita"] else "外せなかった",
                  x["n"], x["due"], x["hazushita_err"])
        json.dump(data, io.open(OUT_JSON, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    io.open(OUT_HTML, "w", encoding="utf-8").write(html(data))
    print("書いた:", OUT_HTML)
    for x in out:
        print(" %2d %s %s %s 関連%d 主%s %s"
              % (x["n"], x["hantei"], x["due"], x["http"], x["kanren"],
                 x["main_size"] or "なし", "／".join(x["ng"])))
    return 0


def html(d):
    e = H.escape
    cards = []
    for x in d["rows"]:
        ngli = ("".join("<li>%s</li>" % e(s) for s in x["ng"])
                if x["ng"] else "<li class=ok>欠けているものは無い</li>")
        kan = "".join(
            '<li><a href="%s" target="_blank" rel="noopener">%s</a></li>'
            % (e(v["url"]), e(v["title"] or v["url"])) for v in x["kanren_list"]) \
            or "<li class=ng>関連が無い</li>"
        cards.append("""
<article class="card %(cls)s" id="p%(n)d">
 <header><span class="no">%(n)02d</span>
  <span class="due">%(due)s (%(youbi)s)</span>
  <span class="han %(cls)s">%(han)s</span></header>

 <div class="lab">本文（このまま出ます。直したい所があれば番号と行を言ってください）</div>
 <pre class="honbun">%(text)s</pre>

 <table>
  <tr><td>リンク先</td><td><a href="%(url)s" target="_blank" rel="noopener">%(url)s</a><br>
      <span class="%(hcls)s">HTTP %(http)s</span>
      ・URLは本文の最後：<span class="%(ocls)s">%(owari)s</span></td></tr>
  <tr><td>ページ</td><td>%(midashi)s<br><span class="dim">%(title)s</span></td></tr>
  <tr><td>本人の動画</td><td><span class="%(mcls)s">%(mtxt)s</span>%(mlink)s</td></tr>
  <tr><td>関連</td><td><span class="%(kcls)s">%(kanren)d 本</span>
      <span class="dim">（最低4本／ページ内の動画は全部で %(zen)s 本）</span>
      <ul class="kan">%(kan)s</ul></td></tr>
  <tr><td>重複</td><td><span class="%(dcls)s">%(dtxt)s</span></td></tr>
 </table>

 <div class="lab">欠けているもの</div>
 <ul class="ng">%(ngli)s</ul>
</article>""" % {
            "n": x["n"], "due": e(x["due"]), "youbi": e(x["youbi"]),
            "han": x["hantei"], "cls": "ok" if x["hantei"] == "◯" else "ng",
            "text": e(x["text"]), "url": e(x["url"]),
            "http": x["http"], "hcls": "ok" if x["http"] == 200 else "ng",
            "owari": "◯" if x["url_owari"] else "✕",
            "ocls": "ok" if x["url_owari"] else "ng",
            "midashi": e(x["midashi"] or "（見出しが出ていない）"),
            "title": e(x["title"]),
            "mcls": "ok" if x["main_ok"] else "ng",
            "mtxt": ("あり %s" % x["main_size"]) if x["main_ok"] else "なし",
            "mlink": ('　<a href="%s" target="_blank" rel="noopener">動画を見る</a>'
                      % e(x["main"])) if x["main"] else "",
            "kanren": x["kanren"], "kcls": "ok" if x["kanren_ok"] else "ng",
            "zen": x["doga_zen"], "kan": kan,
            "dcls": "ok" if not any("同じ" in s for s in x["ng"]) else "ng",
            "dtxt": "なし" if not any("同じ" in s for s in x["ng"]) else "★あり",
            "ngli": ngli,
        })

    return """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>予約済みの中身｜1168</title><style>
*{box-sizing:border-box}
body{margin:0;background:#0d0f12;color:#e8e6e1;
 font-family:"Hiragino Sans","Yu Gothic",system-ui,sans-serif;line-height:1.7}
.wrap{max-width:760px;margin:0 auto;padding:30px 16px 80px}
h1{font-size:21px;margin:0 0 4px;letter-spacing:.03em}
.at{color:#7d8590;font-size:13px;margin:0 0 6px}
.waku{font-size:12.5px;color:#e3b341;background:#1c1a12;border:1px solid #3d3417;
 border-radius:10px;padding:9px 12px;margin:10px 0 0}
.sum{background:#15181d;border:1px solid #23272e;border-radius:12px;
 padding:14px 16px;margin:16px 0 26px;font-size:14px}
.sum b{font-size:22px;font-variant-numeric:tabular-nums}
.card{background:#15181d;border:1px solid #23272e;border-radius:14px;
 padding:16px 16px 18px;margin:0 0 16px}
.card.ng{border-color:#5c2b28;background:#1a1415}
.card header{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
 padding-bottom:10px;border-bottom:1px solid #23272e;margin-bottom:12px}
.no{font-variant-numeric:tabular-nums;font-size:13px;color:#7d8590;
 border:1px solid #2c3138;border-radius:6px;padding:1px 7px}
.due{font-size:16px;font-weight:600;font-variant-numeric:tabular-nums}
.han{margin-left:auto;font-size:19px;font-weight:700}
.lab{font-size:11.5px;color:#8b949e;letter-spacing:.06em;margin:14px 0 6px}
pre.honbun{margin:0;font-family:"Hiragino Sans",system-ui,sans-serif;
 font-size:14.5px;line-height:1.75;white-space:pre-wrap;word-break:break-word;
 background:#0a0c0f;border:1px solid #23272e;border-radius:10px;padding:13px 14px}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:12px}
td{padding:7px 6px;border-bottom:1px solid #1d2126;vertical-align:top}
td:first-child{color:#7d8590;white-space:nowrap;width:1%;padding-right:12px}
ul{margin:6px 0 0;padding-left:1.1em}
li{margin:0 0 4px;font-size:13px;color:#c9d1d9}
ul.kan li{font-size:12.5px}
ul.ng li{color:#ff9d96}
a{color:#79b8ff;word-break:break-all}
.ok{color:#5ddba0}.ng{color:#ff7b72}.dim{color:#7d8590}
h2{font-size:14px;color:#8b949e;letter-spacing:.06em;margin:34px 0 10px;
 border-top:1px solid #23272e;padding-top:16px}
@media(max-width:420px){
 .wrap{padding:22px 12px 70px}
 td:first-child{width:auto;display:block;border:0;padding-bottom:0}
 td{display:block;padding:4px 0}
 tr{display:block;border-bottom:1px solid #1d2126;padding:6px 0}
}
</style></head><body><div class="wrap">
<h1>予約済みの中身（1本ずつ検品）</h1>
<p class="at">%(at)s 作成・%(channel)s<br>
予約の中身：<b>%(itsu)s</b><br>
ページの数字（動画・関連・見出し）：この表を作ったときに1本ずつ実際に開いて数えたものです。</p>
<p class="waku">%(waku)s</p>
<div class="sum">
 予約 <b>%(n)d</b> 本　／　◯ <b class="ok">%(nok)d</b> 本　／　✕ <b class="ng">%(nng)d</b> 本<br>
 <span class="dim">✕は「本人の動画なし」「関連4本未満」「リンクが200でない」
 「URLが本文の最後にない」「重複」のどれかに当たったものです。</span>
</div>
%(cards)s
<h2>この表の見かた</h2>
<ul>
<li>本文は<b>そのまま出ます</b>。直したい所があれば「3番の2行目」のように言ってください。</li>
<li>「本人の動画」＝ページの一番大きい動画（幅500px以上）。</li>
<li>「関連」＝ページの「この曲の関連動画」の本数。最低4本。</li>
<li>予約欄：<a href="https://publish.buffer.com/all-channels/queue">publish.buffer.com</a></li>
<li>★Bufferの予約は<b>10本が上限</b>。1本出るたびに待機列から1本繰り上がります。</li>
</ul>
</div></body></html>""" % {
        "at": e(d["at"]), "channel": e(d["channel"]), "n": d["n"],
        "itsu": e(d.get("itsu") or ""), "waku": e(d.get("waku") or ""),
        "nok": d["n"] - d["ng"], "nng": d["ng"], "cards": "".join(cards)}


if __name__ == "__main__":
    sys.exit(main())
