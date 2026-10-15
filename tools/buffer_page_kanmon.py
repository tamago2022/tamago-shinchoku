#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【ところてん #642】Bufferに入れる前の「ページの関所」。

たまごさん（2026-10-04）:
  「動画が貼ってないとかはもうあり得ない。」「サムネイルがない状態で投稿されるのもやめてね。」
  「関連も4つは確実に貼っておいてほしい。」

通らない投稿は Buffer に入れない（buffer_yoyaku.run_one の頭で呼ばれる＝補填側も同じ道を通る）。

■ 止めるもの（投稿文の中の うちのURL ごとに、Twitterbot として本番を叩いて数える）
  ① 曲のURL（&song=）なのに、曲ページにならない（canonical から song= が消える）
  ② og:image / twitter:image が無い、または共通の「四つの扉」（曲固有でない）
  ③ 画像のURLが 200 でない・空っぽ判定（og_kanmon に委譲）
  ④ 動画が再生できない（og:image の動画IDを oEmbed と playableInEmbed で見る）
  ⑤ 「この流れで、もう一本」が 4 枚に満たない
  ⑥ 本文が薄い（基準ページ＝亜蘭知子 Midnight Pretenders の密度に届かない）:
     本文40文字未満／発売年などの数字が無い（事実が書かれていない）

  ※ アーティストページ（song= 無し）は ① ④ ⑤ の対象外。② ③ だけ見る。
  ※ 外のAIを呼ばない。0円。ブラウザを使わない。
  ※ 緊急時のみ PAGE_KANMON_SKIP=1 で素通り（使ったら必ず報告）。

使い方:  python3 tools/buffer_page_kanmon.py <URL> [<URL>...]   rc=0 全部通過 / rc=1 止めた
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

TWITTERBOT = "Twitterbot/1.0"
MIN_RELATED = 4
FOUR_DOORS = "og-four-doors"
SHARE_IMG = re.compile(r"/api/public/share-image/([A-Za-z0-9_-]{11})")
OGIMG = re.compile(r'property="og:image" content="([^"]+)"')
TWIMG = re.compile(r'name="twitter:image" content="([^"]+)"')
CANON = re.compile(r'rel="canonical" href="([^"]+)"')
DESC = re.compile(r'name="description" content="([^"]*)"')
EMBED = re.compile(r"youtube\.com/embed/([A-Za-z0-9_-]{11})")


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": TWITTERBOT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.getcode(), r.read(2_500_000).decode("utf-8", "ignore")


def _embeddable(vid):
    """oEmbed が 200 で、watch ページの playableInEmbed が true か。"""
    try:
        req = urllib.request.Request(
            "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=%s&format=json" % vid,
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.getcode() != 200:
                return False, "oEmbed %s" % r.getcode()
    except Exception as e:
        return False, "oEmbed %s" % (getattr(e, "code", None) or repr(e)[:40])
    try:
        req = urllib.request.Request("https://www.youtube.com/watch?v=%s" % vid,
                                     headers={"User-Agent": "Mozilla/5.0", "Cookie": "CONSENT=YES+1"})
        with urllib.request.urlopen(req, timeout=20) as r:
            h = r.read(3_000_000).decode("utf-8", "ignore")
        m = re.search(r'"playableInEmbed":(true|false)', h)
        if m and m.group(1) == "false":
            return False, "埋め込み再生できない"
    except Exception:
        pass  # watch が読めない時は oEmbed の結果を信じる（門を塞がない）
    return True, ""


def _related_count(html):
    i = html.find("この流れで、もう一本")
    if i < 0:
        return 0
    seg = html[i:]
    j = seg.find("</section>")
    seg = seg[: j if j > 0 else 20000]
    return len(set(re.findall(r"img\.youtube\.com/vi/([A-Za-z0-9_-]{11})/", seg)))


def shiraberu(url):
    riyuu = []
    try:
        code, html = _get(url)
    except Exception as e:
        return {"url": url, "tsuuka": False, "riyuu": ["ページが返ってこない: %s" % repr(e)[:80]]}
    if code != 200:
        riyuu.append("ページが %s を返す" % code)
    is_song = "song=" in url
    canon = (CANON.search(html) or [None, ""])[1].replace("&amp;", "&")
    if is_song and "song=" not in canon:
        riyuu.append("曲ページにならない（アーティストページに落ちる）")
    og = (OGIMG.search(html) or [None, ""])[1].replace("&amp;", "&")
    tw = (TWIMG.search(html) or [None, ""])[1].replace("&amp;", "&")
    if not og or not tw:
        riyuu.append("og:image / twitter:image が無い")
    elif FOUR_DOORS in og or FOUR_DOORS in tw:
        riyuu.append("サムネが共通の「四つの扉」（曲固有でない）")
    elif is_song and not SHARE_IMG.search(og):
        # スローバラード／さよなら夏の日の事故：文字だけの自作カード（/og/*.png）は「サムネ無し」と同じ扱い
        riyuu.append("サムネが動画の絵でない（文字だけのカード等）: %s" % og[-60:])
    # 画像200・空っぽ・3秒・よその倉庫は既存の og_kanmon に任せる（二つ目の実装を作らない）
    try:
        import og_kanmon
        r = og_kanmon.shiraberu(url)
        for x in r.get("riyuu") or []:
            if x not in riyuu:
                riyuu.append(x)
    except Exception as e:
        riyuu.append("og_kanmon が読めない: %s" % str(e)[:60])
    if is_song:
        m = SHARE_IMG.search(og)
        vid = m.group(1) if m else (EMBED.search(html) or [None, None])[1]
        if not vid:
            riyuu.append("動画が見つからない（og:imageにも埋め込みにも動画IDが無い）")
        else:
            ok, why = _embeddable(vid)
            if not ok:
                riyuu.append("動画が再生できない（%s・%s）" % (vid, why))
        d = (DESC.search(html) or [None, ""])[1]
        body = d.split(" — ", 1)[1] if " — " in d else d
        body = body.replace("&#x27;", "'").replace("&quot;", '"')
        if len(body) < 40:
            riyuu.append("本文が薄い（%d文字。基準は40文字以上）" % len(body))
        elif not re.search(r"(19|20)\d\d", body):
            riyuu.append("本文に年・作品名などの事実が無い（基準ページと同じ密度にする）")
        n = _related_count(html)
        if n < MIN_RELATED:
            riyuu.append("「この流れで」が %d 枚（%d 枚必要）" % (n, MIN_RELATED))
    return {"url": url, "tsuuka": not riyuu, "riyuu": riyuu}


def kanmon(text):
    """投稿文を受け取り (ok, why) を返す。buffer_yoyaku.run_one から呼ぶ。"""
    if os.environ.get("PAGE_KANMON_SKIP") == "1":
        return True, "ページの関所を素通り（PAGE_KANMON_SKIP=1）"
    urls = re.findall(r"https://joy-relief-station\.lovable\.app/\S+", text or "")
    if not urls:
        return True, "うちのURLが無いのでページの関所の対象外"
    for u in urls:
        u = u.rstrip("）)、。,.")
        r = shiraberu(u)
        if not r["tsuuka"]:
            return False, "ページの関所で止めた（HOLD＝直るまで投稿しない）: %s\n    - %s" % (
                u, "\n    - ".join(r["riyuu"]))
    return True, "ページの関所を通過（og:image曲固有・動画再生可・関連4）"


def main():
    urls = sys.argv[1:]
    if not urls:
        print("URLをください")
        return 2
    ng = 0
    for u in urls:
        r = shiraberu(u)
        print(("◯ " if r["tsuuka"] else "✕ ") + u)
        for x in r["riyuu"]:
            print("    - " + x)
        ng += 0 if r["tsuuka"] else 1
    return 1 if ng else 0


if __name__ == "__main__":
    sys.exit(main())
