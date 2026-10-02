#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Buffer予約前の「ページ関所」（Chromeは憲法1186で起動禁止なので、データとcurlだけで見る）。
投稿文の曲ページURL（cover-guide?artist=A&song=S）について、本番(origin/main)のデータで
  ①曲が存在する ②youtubeIdがある ③その動画が死んでいない（非表示台帳に無い＋YouTube oEmbedが200）
  ④ヘッダーのnote（コピー）が水道水でない
を確認。1つでも落ちたら予約しない。金はかからない。
使い方: python3 tools/buffer_page_kanmon.py "<投稿文 or URL>"  → 終了コード 0=通過 1=落ち
組み込み: buffer_yoyaku.run_one が覆面客の関所の直後に呼ぶ（BUFFER_PAGE_SKIP=1 のときだけ素通り）。
"""
import os, re, subprocess, sys, urllib.parse, urllib.request, urllib.error

REPO = os.path.expanduser("~/Desktop/joy-relief-station")
SUISUI = ["代表曲のひとつ", "代表曲の一つ", "代表曲。", "名曲です", "人気の曲です", "おすすめの曲", "ぜひ聴いてみてください", "ぜひお聴きください", "多くの人に愛される"]


def _git(*a):
    return subprocess.run(["git", "-C", REPO] + list(a), capture_output=True, text=True, timeout=120).stdout


def _entry(song):
    pat = 'id: "%s"' % song
    for ln in _git("grep", "-hF", pat, "origin/main", "--", "src/lib/coverGuide.ts").splitlines():
        m = re.search(r'note: "((?:[^"\\]|\\.)*)"', ln)
        y = re.search(r'youtubeId: "([\w-]{11})"', ln)
        return {"note": m.group(1) if m else "", "yt": y.group(1) if y else ""}
    return None


def _oembed_ok(yt):
    u = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote("https://www.youtube.com/watch?v=" + yt)
    try:
        return urllib.request.urlopen(u, timeout=20).status == 200
    except urllib.error.HTTPError as e:
        return False
    except Exception:
        return True  # 通信不調は落とさない（誤検知で止めない）


def check(url):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    a, s = (q.get("artist") or [""])[0], (q.get("song") or [""])[0]
    if not (a and s):
        return True, "曲ページ形式でないので対象外: " + url
    _git("fetch", "-q", "origin", "main")
    e = _entry(s)
    if not e:
        return False, "曲データに無い（ページが出ない恐れ）: %s/%s" % (a, s)
    if not e["yt"]:
        return False, "youtubeIdが空（動画なし）: %s/%s" % (a, s)
    if _git("grep", "-lF", e["yt"], "origin/main", "--", "src/lib/deadYoutubeAll.ts", "src/lib/kanseiHidden.generated.ts").strip():
        return False, "動画が死亡/非表示台帳に載っている(%s): %s/%s" % (e["yt"], a, s)
    if not _oembed_ok(e["yt"]):
        return False, "YouTubeが動画を返さない(%s): %s/%s" % (e["yt"], a, s)
    for w in SUISUI:
        if w in e["note"]:
            return False, "水道水コピー「%s」: %s/%s → note=%s" % (w, a, s, e["note"][:60])
    if len(e["note"]) < 12:
        return False, "コピー(note)が短すぎ/空: %s/%s" % (a, s)
    return True, "OK %s/%s yt=%s" % (a, s, e["yt"])


def kanmon(text):
    if os.environ.get("BUFFER_PAGE_SKIP") == "1":
        return True, "ページ関所を素通り（BUFFER_PAGE_SKIP=1）"
    urls = [u.rstrip("）)、。,.") for u in re.findall(r"https://joy-relief-station\.lovable\.app/\S+", text or "")]
    if not urls:
        return True, "うちのURLが無いので対象外"
    for u in urls:
        ok, why = check(u)
        if not ok:
            return False, "ページ関所: " + why
    return True, "ページ関所を通過"


if __name__ == "__main__":
    ok, why = kanmon(" ".join(sys.argv[1:]))
    print(("OK " if ok else "NG ") + why)
    sys.exit(0 if ok else 1)
