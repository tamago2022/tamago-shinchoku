#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TikTok・Instagram のサムネを、サイト側（joy-relief-station/public/images/）に保存する係。

なぜ要るか（2026-11-14 店主差し戻し2回目）：
  iPhone の実機で TikTok／Instagram の枠が真っ白になった。外部の iframe を最初から置くと、
  中身が出ない時に白い枠しか残らない。lite-youtube-embed と同じ「ファサード方式」に替え、
  最初に見せるのは自前のサムネ画像と自前の再生ボタンだけにした（SocialFacade.tsx）。
  そのサムネは外部CDN（tiktokcdn の署名つき・cdninstagram の期限つき）だと消えるので、
  ここで一度だけ取って自前のURLに置く。置き場の決まり（部品と同じ）：
    TikTok    → public/images/tiktok/<動画ID>.jpg
    Instagram → public/images/instagram/<投稿コード>.jpg

使い方（Mac の上で。curl と sips を使う。ブラウザ・許可は使わない）：
  python3 tools/social_thumb_hozon.py --repo <joy-relief-stationの場所> [--extra URL ...]
  → src の中の TikTok 動画URL・Instagram 投稿URL（＋DBの倉庫 admin_stock の分）を全部拾い、
    まだ保存していないものだけ取りに行く。結果は1行ずつ表示。取れなかったものは exit 1。
  python3 tools/social_thumb_hozon.py --self-test
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
TT_RE = re.compile(r"tiktok\.com/@[A-Za-z0-9_.]*/video/(\d{15,22})")
TT_PLAYER_RE = re.compile(r"tiktokMain:\s*\{\s*videoId:\s*\"(\d{15,22})\"")
IG_RE = re.compile(r"instagram\.com/(?:[A-Za-z0-9_.]{1,40}/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]{5,30})")
SKIP_IG = {"CODE"}


def find_refs(text):
    tt = set(TT_RE.findall(text)) | set(TT_PLAYER_RE.findall(text))
    ig = set(IG_RE.findall(text)) - SKIP_IG
    return tt, ig


def scan_repo(repo):
    tt, ig = set(), set()
    for base in ("src",):
        for root, _dirs, files in os.walk(os.path.join(repo, base)):
            for n in files:
                if not n.endswith((".ts", ".tsx")):
                    continue
                if n.endswith(".generated.ts") or n == "instagram.ts":
                    continue
                try:
                    t = open(os.path.join(root, n), encoding="utf-8", errors="ignore").read()
                except Exception:
                    continue
                a, b = find_refs(t)
                tt |= a
                ig |= b
    return tt, ig


def curl(url, out=None, timeout=30):
    cmd = ["curl", "-sL", "-m", str(timeout), "-A", UA, url]
    if out:
        cmd[1:1] = ["-o", out, "-w", "%{http_code}"]
    p = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    if out:
        return p.stdout.decode().strip()
    return p.stdout.decode("utf-8", "ignore")


def resolve_short(url):
    """vt.tiktok.com などの短縮URLを、動画IDの入ったURLへ。"""
    p = subprocess.run(["curl", "-sIL", "-m", "20", "-A", UA, url], capture_output=True, timeout=30)
    m = re.findall(r"(?im)^location:\s*(\S+)", p.stdout.decode("utf-8", "ignore"))
    for loc in m:
        mm = re.search(r"/video/(\d{15,22})", loc)
        if mm:
            return mm.group(1)
    return None


def tiktok_cover_url(vid):
    html = curl("https://www.tiktok.com/@x/video/%s" % vid)
    for key in ("originCover", "cover", "dynamicCover"):
        m = re.search(r'"%s":"(https:[^"]+)"' % key, html)
        if m:
            return m.group(1).encode().decode("unicode_escape").replace("\\/", "/")
    return None


def instagram_image_url(code):
    html = curl("https://www.instagram.com/p/%s/embed/captioned/" % code)
    m = re.search(r'class="EmbeddedMediaImage"[^>]*src="([^"]+)"', html) or \
        re.search(r'<img class="EmbeddedMediaImage"[^>]*src="([^"]+)"', html)
    if not m:
        return None
    return m.group(1).replace("&amp;", "&")


def save_jpeg(src_url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".img")
    os.close(fd)
    try:
        code = curl(src_url, out=tmp)
        if code != "200" or os.path.getsize(tmp) < 2000:
            return "HTTP %s" % code
        # 形式を問わず jpeg・長辺720に（軽く）。sips は macOS 標準。
        r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "80",
                            "-Z", "720", tmp, "--out", dest], capture_output=True, timeout=60)
        if r.returncode != 0 or not os.path.exists(dest) or os.path.getsize(dest) < 2000:
            return "sips失敗"
        return None
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


def db_refs(repo):
    """倉庫（admin_stock）の TikTok・Instagram。公開鍵の読み取りだけ（行は数件）。"""
    env = os.path.join(repo, ".env")
    try:
        t = open(env, encoding="utf-8").read()
        url = re.search(r'^VITE_SUPABASE_URL="([^"]+)"', t, re.M).group(1)
        key = re.search(r'^VITE_SUPABASE_PUBLISHABLE_KEY="([^"]+)"', t, re.M).group(1)
    except Exception:
        return []
    q = url + "/rest/v1/admin_stock?select=ref&or=(ref.ilike.*tiktok.com*,ref.ilike.*instagram.com*)"
    p = subprocess.run(["curl", "-s", "-m", "30", "-H", "apikey: " + key, "-H", "Authorization: Bearer " + key, q],
                       capture_output=True, timeout=40)
    try:
        return [r["ref"] for r in json.loads(p.stdout.decode())]
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo")
    ap.add_argument("--extra", nargs="*", default=[])
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        t = ('x "https://www.tiktok.com/@a.b/video/7706902530252475661" '
             'tiktokMain: { videoId: "7649641223090752782", '
             'https://www.instagram.com/p/C-c9MLwpdeo/ https://www.instagram.com/user1/reel/DaiCdw3k0U9/ '
             'https://www.instagram.com/p/CODE/')
        tt, ig = find_refs(t)
        ok = tt == {"7706902530252475661", "7649641223090752782"} and ig == {"C-c9MLwpdeo", "DaiCdw3k0U9"}
        print("SELF-TEST", "PASS" if ok else "FAIL", sorted(tt), sorted(ig))
        sys.exit(0 if ok else 1)
    repo = a.repo
    tt, ig = scan_repo(repo)
    for u in list(a.extra) + db_refs(repo):
        x, y = find_refs(u)
        if not x and re.search(r"(vt|vm)\.tiktok\.com/", u):
            v = resolve_short(u)
            if v:
                x = {v}
        tt |= x
        ig |= y
    bad = 0
    for vid in sorted(tt):
        dest = os.path.join(repo, "public", "images", "tiktok", vid + ".jpg")
        if os.path.exists(dest):
            print("ある   tiktok", vid)
            continue
        src = tiktok_cover_url(vid)
        err = save_jpeg(src, dest) if src else "表紙のURLが取れない"
        print(("保存   " if not err else "失敗   ") + "tiktok", vid, err or "")
        bad += 1 if err else 0
    for code in sorted(ig):
        dest = os.path.join(repo, "public", "images", "instagram", code + ".jpg")
        if os.path.exists(dest):
            print("ある   instagram", code)
            continue
        src = instagram_image_url(code)
        err = save_jpeg(src, dest) if src else "画像のURLが取れない"
        print(("保存   " if not err else "失敗   ") + "instagram", code, err or "")
        bad += 1 if err else 0
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
