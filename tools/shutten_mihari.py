#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""曲ページの「出典」の見え方の見張り（2026-10-29 たまごさん赤入れ・Treasure）。

たまごさん：「Wikipedia の記述が長すぎて美しくない。全部載せる必要ある？ せめてメモの中に出典として隠しておいて、
  押すと開くようにできない？ リンクを押すと F の Facebook アイコンだったり capitalfm.com に飛んだりするけど、
  これは Wikipedia なの？ Englishman in New York みたいに1行で収まっているならいい」

決まり（joy-relief-station src/components/SongShutten.tsx・src/lib/shuttenCore.ts）：
  出典は最大3つ。1つなら1行（Englishman in New York の見た目）、2つ以上は小さく「出典」→押すと開く・1出典1行・サイト名。
  公開前の関所は joy-relief-station の prebuild scripts/patrol/check-song-shutten.mjs。これは本番の見張り。

見ること（本番の曲ページの HTML・1日1回）：
  ① 出典を「 ／ 」で横に並べた古い出し方が残っている（長い）
  ② 出典が4つ以上出ている
  ③ Wikipedia でないリンクに「Wikipedia」と書いてある／見出しがURLの切れ端（アイコン・名前違い）
  ④ 出典にファビコンの画像が付いている
見る曲：SNSに出した曲（status/public/toukou_daicho.json）＋手本の2曲（Treasure・Englishman in New York）。最大60曲。

使い方
  python3 tools/shutten_mihari.py [--daily]      本番を見て status/public/shutten_mihari.json。NG があれば Dispatch へ1行
  python3 tools/shutten_mihari.py --self-test
安全：本番の公開ページを GET するだけ（課金0・ブラウザなし・一時ファイルなし）。
"""
import html as _html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUT = os.path.join(ST, "public", "shutten_mihari.json")
STAMP = os.path.join(ST, ".shutten_mihari_at")
DAICHO = os.path.join(ST, "public", "toukou_daicho.json")
SITE = "https://joy-relief-station.lovable.app"
JST = timezone(timedelta(hours=9))
TEHON = ["bruno-mars/treasure", "sting/englishman-in-new-york"]
MAX_SONGS = 60
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) tamago-shutten-mihari"

A_RE = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)


def _text(s):
    return _html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def kensa(page):
    """ページの HTML から、出典の見え方の NG を返す（[文字列]）と、出ていた出典の数。"""
    ng = []
    n_max = 0
    # 新しい出し方（SongShutten）：data-song-shutten="N"
    for m in re.finditer(r'<(p|details)\b[^>]*data-song-shutten="(\d+)"[^>]*>(.*?)</\1>', page, re.S):
        n = int(m.group(2))
        n_max = max(n_max, n)
        if n > 3:
            ng.append("出典が%d個出ている（3つまで）" % n)
        for href, inner in A_RE.findall(m.group(3)):
            ng += _label_ng(href, _text(inner))
        if re.search(r"favicon|s2/favicons|<img", m.group(3), re.I):
            ng.append("出典に画像（ファビコン）が付いている")
    # 古い出し方：「出典：」のあとにリンクを「 ／ 」で横に並べる
    for m in re.finditer(r"出典：(.{0,6000}?)</p>", page, re.S):
        block = m.group(1)
        links = A_RE.findall(block)
        if not links:
            continue
        if " ／ " in block and len(links) >= 2:
            ng.append("出典を横に%d個並べている（長い・押すと開く形にする）" % len(links))
            n_max = max(n_max, len(links))
        for href, inner in links:
            ng += _label_ng(href, _text(inner))
    return sorted(set(ng)), n_max


def _label_ng(href, label):
    ng = []
    host = urllib.parse.urlparse(_html.unescape(href)).netloc.lower()
    if "wikipedia" in label.lower() and "wikipedia.org" not in host:
        ng.append("Wikipedia でないリンク（%s）に Wikipedia と書いてある" % host)
    if "/" in label and not label.startswith("Wikipedia"):
        ng.append("出典の見出しがURLの切れ端（%s）" % label[:40])
    return ng


def songs():
    keys = list(TEHON)
    try:
        d = json.load(open(DAICHO, encoding="utf-8"))
        for p in d.get("posts", []):
            k = p.get("songKey")
            if k and "/" in k and k not in keys:
                keys.append(k)
    except Exception:
        pass
    return keys[:MAX_SONGS]


def fetch(key):
    a, s = key.split("/", 1)
    url = "%s/cover-guide?artist=%s&song=%s" % (SITE, urllib.parse.quote(a), urllib.parse.quote(s))
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return url, r.read().decode("utf-8", "replace")


def mimawari(daily=False):
    if daily and os.path.exists(STAMP) and time.time() - os.path.getmtime(STAMP) < 20 * 3600:
        print("SHUTTEN_MIHARI: 20時間以内に見た（間引き）")
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(STAMP, "w").write(datetime.now(JST).isoformat())
    rows, aka, mirenai = [], [], []
    for k in songs():
        try:
            url, page = fetch(k)
        except Exception as e:
            mirenai.append({"song": k, "why": str(e)[:120]})
            continue
        ng, n = kensa(page)
        rows.append({"song": k, "url": url, "shutten": n, "ng": ng})
        if ng:
            aka.append(rows[-1])
        time.sleep(0.5)
    doc = {"updatedAt": datetime.now(JST).isoformat(timespec="seconds"),
           "what": "曲ページの出典の見え方（最大3つ・1つなら1行・2つ以上は押すと開く・サイト名・ファビコンなし）。tools/shutten_mihari.py",
           "ok": not aka and bool(rows), "mita": len(rows), "aka": aka, "mirenai": mirenai, "rows": rows}
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if aka or not rows:
        line = {"ts": doc["updatedAt"], "n": "shutten-" + datetime.now(JST).strftime("%m%d"), "type": "shutten_mihari",
                "title": ("曲ページの出典の見え方 NG %d曲" % len(aka)) if aka else "出典の見張りが本番を見られなかった",
                "message": "；".join("%s：%s" % (x["song"], x["ng"][0]) for x in aka[:3]) + "。詳しくは status/public/shutten_mihari.json"}
        open(os.path.join(ST, "dispatch_outbox.jsonl"), "a").write(json.dumps(line, ensure_ascii=False) + "\n")
    print("SHUTTEN_MIHARI: 見た %d曲・NG %d曲・見られない %d" % (len(rows), len(aka), len(mirenai)))
    return 0 if doc["ok"] else 2


def self_test():
    old = ('<p class="mt-2 text-[11px] opacity-80">出典：<span><a href="https://en.wikipedia.org/wiki/Treasure_(song)">Wikipedia（en）「Treasure (song)」CC BY-SA 4.0</a></span>'
           '<span> ／ <a href="https://www.capitalfm.com/artists/bruno-mars/videos/treasure/">capitalfm.com/artists/bruno-mars/videos/treasure/</a></span></p>')
    one = ('<p class="mt-2 text-[11px] opacity-80" data-song-shutten="1">出典：<span><a href="https://en.wikipedia.org/wiki/Englishman_in_New_York">'
           'Wikipedia（en）「Englishman in New York」CC BY-SA 4.0</a></span></p>')
    new3 = ('<details class="mt-2" data-song-shutten="3"><summary>出典</summary><ul><li><a href="https://en.wikipedia.org/wiki/Treasure_(song)">Wikipedia（en）「Treasure (song)」CC BY-SA 4.0</a></li>'
            '<li><a href="https://musictech.com/x/">MusicTech</a></li><li><a href="https://www.xxlmag.com/y/">XXL</a></li></ul></details>')
    bad4 = new3.replace('data-song-shutten="3"', 'data-song-shutten="4"')
    liar = new3.replace(">MusicTech<", ">Wikipedia MusicTech<")
    ico = new3.replace("<li><a href=\"https://musictech", "<li><img src=\"https://www.google.com/s2/favicons?domain=musictech.com\"><a href=\"https://musictech")
    cases = [(old, True), (one, False), (new3, False), (bad4, True), (liar, True), (ico, True)]
    bad = 0
    for i, (page, want_ng) in enumerate(cases):
        ng, _ = kensa(page)
        if bool(ng) != want_ng:
            print("self-test NG case %d: %s" % (i, ng))
            bad += 1
    print("self-test OK" if not bad else "self-test NG")
    return 0 if not bad else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(self_test())
    sys.exit(mimawari(daily="--daily" in a))
