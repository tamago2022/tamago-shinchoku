#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
貼る前のサムネイル点検。
URLを1つずつ見て「今なら出る／まだ出ない」を出すだけ。投稿はしない。

判定の基準（Xが実際に見ているもの）:
  1. ページが3秒以内に返ってくるか   ← ここで落ちるのが一番多い
  2. og:image が入っているか
  3. twitter:card が summary_large_image か
  4. その画像URLが本当に開けるか（200で返るか）
  5. 画像が小さすぎないか（幅300未満は大きい絵にならない）

使い方: tools/点検するURL.txt に1行1URLで書いて、
       tools/サムネ点検_押すだけ.command をダブルクリック
"""
import os, re, sys, time, urllib.request, urllib.error, struct, io

BASE = os.path.dirname(os.path.abspath(__file__))
LIST = os.path.join(BASE, "点検するURL.txt")
OUT  = os.path.join(BASE, "サムネ点検の結果.txt")

UA = "Twitterbot/1.0"
LIMIT_SEC = 3.0          # Xが待ってくれる目安
MIN_W = 300              # これ未満だと大きい絵にならない

RED = "\033[31m"; GRN = "\033[32m"; YEL = "\033[33m"; OFF = "\033[0m"


def get(url, timeout, head_only=False, max_bytes=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    if head_only:
        req.get_method = lambda: "HEAD"
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = b"" if head_only else r.read(max_bytes) if max_bytes else r.read()
        return r.status, dict(r.headers), body, time.time() - t0


def meta(html, prop):
    for pat in (
        r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']*)["\']' % re.escape(prop),
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']%s["\']' % re.escape(prop),
    ):
        m = re.search(pat, html, re.I)
        if m:
            return m.group(1)
    return None


def image_size(data):
    """JPEG/PNG/GIF の幅・高さを先頭バイトから読む。分からなければ None"""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", data[16:24]); return w, h
        if data[:3] == b"\xff\xd8\xff":
            f = io.BytesIO(data); f.read(2)
            while True:
                b = f.read(1)
                while b and b != b"\xff":
                    b = f.read(1)
                mk = f.read(1)
                while mk == b"\xff":
                    mk = f.read(1)
                if not mk:
                    return None
                if mk[0] in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    f.read(3)
                    h, w = struct.unpack(">HH", f.read(4)); return w, h
                ln = struct.unpack(">H", f.read(2))[0]; f.read(ln - 2)
        if data[:6] in (b"GIF87a", b"GIF89a"):
            w, h = struct.unpack("<HH", data[6:10]); return w, h
    except Exception:
        pass
    return None


def check(url):
    ng = []
    # 1. ページが時間内に返るか
    try:
        status, hdr, body, sec = get(url, timeout=10)
    except Exception as e:
        return False, ["ページが返ってこない（%s）" % type(e).__name__], None
    if status != 200:
        return False, ["ページが %d を返した" % status], None
    if sec > LIMIT_SEC:
        ng.append("返ってくるのが遅い（%.1f秒・Xは約%.0f秒で諦める）" % (sec, LIMIT_SEC))

    html = body.decode("utf-8", "replace")

    # 2. og:image
    img = meta(html, "og:image") or meta(html, "twitter:image")
    if not img:
        return False, ng + ["サムネイルの指定（og:image）が無い"], None
    if img.startswith("/"):
        ng.append("サムネイルの住所が途中までしか書かれていない（相対パス）")
        from urllib.parse import urljoin
        img = urljoin(url, img)

    # 3. twitter:card
    card = meta(html, "twitter:card")
    if card != "summary_large_image":
        ng.append("大きい絵の指定になっていない（twitter:card = %s）" % (card or "無し"))

    # 4-5. 画像が開けるか・大きさ
    try:
        st, ih, idata, isec = get(img, timeout=10, max_bytes=200_000)
        if st != 200:
            ng.append("サムネイル画像が %d を返す（開けない）" % st)
        else:
            size = image_size(idata)
            if size and size[0] < MIN_W:
                ng.append("サムネイル画像が小さい（%d×%d・幅%d未満は小さい四角になる）" % (size[0], size[1], MIN_W))
            elif size:
                ng.append("画像の実寸 %d×%d" % size) if size[0] < 1200 else None
    except Exception as e:
        ng.append("サムネイル画像が開けない（%s）" % type(e).__name__)

    hard = [x for x in ng if "実寸" not in x]
    return (len(hard) == 0), ng, img


def main():
    if not os.path.exists(LIST):
        open(LIST, "w", encoding="utf-8").write(
            "# 1行に1つ、点検したいURLを書いてください（#で始まる行は無視）\n"
            "https://joy-relief-station.lovable.app/\n")
        print("%s を作りました。URLを書いてから、もう一度押してください。" % LIST)
        return 0

    urls = [l.strip() for l in open(LIST, encoding="utf-8")
            if l.strip() and not l.strip().startswith("#")]
    if not urls:
        print("点検するURLが1つも書かれていません。"); return 1

    ok_n = 0
    lines = []
    print("\n■ サムネイル点検 — 全%d件\n" % len(urls))
    for i, u in enumerate(urls, 1):
        ok, ng, img = check(u)
        if ok:
            ok_n += 1
            print("%s[出る]%s %s" % (GRN, OFF, u))
            lines.append("[出る] %s" % u)
        else:
            col = RED if any("返ってこない" in x or "無い" in x or "開けない" in x for x in ng) else YEL
            print("%s[出ない]%s %s" % (col, OFF, u))
            lines.append("[出ない] %s" % u)
            for x in ng:
                print("         └ %s" % x)
                lines.append("         └ %s" % x)
        sys.stdout.flush()

    head = "全%d件中 %d件が今なら出る（%d件はまだ出ない）" % (len(urls), ok_n, len(urls) - ok_n)
    print("\n" + "=" * 60 + "\n■ " + head + "\n")
    open(OUT, "w", encoding="utf-8").write(head + "\n\n" + "\n".join(lines) + "\n")
    print("結果は %s にも書きました。" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
