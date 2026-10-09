#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Googleドライブ（Mac の Drive デスクトップ）から、いつでもファイルを取る道具。

経路：~/Library/CloudStorage/GoogleDrive-*/マイドライブ/ を直接読む（ログイン・API不要。
Driveアプリが起動していれば常に読める）。

  python3 tools/drive_get.py "SNS/TikTok投稿用"                 # 一覧
  python3 tools/drive_get.py "SNS/TikTok投稿用/tiktok_post_08.png"   # → ~/.tamago/drive_cache/ に複製して絶対パスを出す
  python3 tools/drive_get.py "SNS/TikTok投稿用/tiktok_post_08.png" --publish
        # → joy-relief-station/public/drive/ にも置き、公開予定URLを出す
        #   ★pushはしない（外に出る操作）。URLが生きるのは次のデプロイ後。
  python3 tools/drive_get.py --check                            # 生死チェック（読めた枚数を出す。0=異常で終了コード1）

キャッシュは ~/.tamago/drive_cache（Vault・Desktopの外）。
"""
import glob, os, shutil, sys

CACHE = os.path.expanduser("~/.tamago/drive_cache")
SITE = "/Users/mac/Desktop/joy-relief-station"      # 既存の作業フォルダ（新規作成ではない）
SITE_URL = "https://joy-relief-station.lovable.app"
CHECK_DIRS = ["SNS/TikTok投稿用", "SNS/TikTokプロフィール用"]


def roots():
    return glob.glob(os.path.expanduser("~/Library/CloudStorage/GoogleDrive-*/マイドライブ")) + \
           glob.glob(os.path.expanduser("~/Library/CloudStorage/GoogleDrive-*/My Drive"))


def resolve(rel):
    for r in roots():
        p = os.path.join(r, rel)
        if os.path.exists(p):
            return p
    return None


def fetch(rel, publish=False):
    src = resolve(rel)
    if not src:
        raise FileNotFoundError("Driveに無い／Driveアプリが未起動: " + rel)
    dst = os.path.join(CACHE, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(src, "rb") as f:                 # 読めた＝ダウンロード済み（オンライン専用でも読むと実体化する）
        data = f.read()
    with open(dst, "wb") as g:
        g.write(data)
    out = {"local": dst, "bytes": len(data)}
    if publish:
        pub = os.path.join(SITE, "public", "drive", os.path.basename(rel))
        os.makedirs(os.path.dirname(pub), exist_ok=True)
        shutil.copyfile(dst, pub)
        out["site_file"] = pub
        out["url_after_deploy"] = "%s/drive/%s" % (SITE_URL, os.path.basename(rel))
    return out


def check():
    n = 0
    for d in CHECK_DIRS:
        p = resolve(d)
        if not p:
            continue
        for f in os.listdir(p):
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".mp4")):
                try:
                    fetch(os.path.join(d, f)); n += 1
                except Exception:
                    pass
    return n


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--check" in a:
        n = check()
        print("Drive取得 %d 枚" % n)
        sys.exit(0 if n > 0 else 1)
    if not a:
        print(__doc__); sys.exit(2)
    p = resolve(a[0])
    if p and os.path.isdir(p):
        print("\n".join(sorted(os.listdir(p)))); sys.exit(0)
    print(fetch(a[0], "--publish" in a))
