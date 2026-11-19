#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ダウンロード・生成物を、Mac本体ではなく外付け(iMac HDD)へ既定の置き場として
逃がす係（2026-09-09・685番「ディスクが1日20GB以上減る原因を徹底追及して止める
＋外付けを既定の置き場にする」）。

たまごさんの指示（そのまま）：
  「もうiMac HDDっていうのが容量があるから、ダウンロードとかもう全部そっちを
   使うようにしてほしい。」

★理想は ~/Downloads そのものを外付け上のフォルダへのシンボリックリンクに
  置き換えることだったが、実測でmacOSのTCC(プライバシー保護フォルダ)により
  `os.rename('/Users/mac/Downloads', ...)` が Permission denied で拒否される
  ことを確認済み（中のファイル削除・移動は許可されるが、フォルダ自体の
  リネーム/削除だけがブロックされる）。GUI側で「フルディスクアクセス」を
  許可すれば解決するが、それは店主にしかできない操作のため、次善策として
  「一定時間経ったファイルを自動で外付けへ退避する」方式に倒す。

  ダウンロード直後はすぐ使うので手元(Mac本体)に残し、OFFLOAD_AFTER_HOURS
  経過したら自動的に /Volumes/iMac HDD/Mac標準置き場/Downloads/ へ移す。
  ~/Downloads からは無くなるが、Finderの「最近使った項目」等では変わらず
  たどれる（実体が外付けに移るだけ、パスが変わる点は既知のトレードオフ）。
"""
import io
import json
import os
import shutil
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

HOME = os.path.expanduser("~")
SRC_DIR = os.path.join(HOME, "Downloads")
EXTERNAL_VOLUME = "/Volumes/iMac HDD"
DEST_DIR = os.path.join(EXTERNAL_VOLUME, "Mac標準置き場", "Downloads")

LOG = os.path.join(REPO, "status", "downloads_offload.log")
STAMP = os.path.join(REPO, "status", ".downloads_offload_at")
INTERVAL_SEC = 6 * 3600       # 6時間に1回でよい（軽く作る）
OFFLOAD_AFTER_HOURS = 72      # 3日間は手元に残す（すぐ使うものを消さないため）

# 拡張子を問わず動かすが、これらは触らない（隠しファイル・作業中の一時ファイル）
SKIP_PREFIXES = (".",)
SKIP_SUFFIXES = (".download", ".crdownload", ".part")


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def external_available():
    return os.path.isdir(EXTERNAL_VOLUME)


def unique_dest(dest):
    """同名ファイルが既に外付け側にあれば、上書きせず連番を振る。"""
    if not os.path.exists(dest):
        return dest
    base, ext = os.path.splitext(dest)
    i = 1
    while True:
        cand = "%s_%d%s" % (base, i, ext)
        if not os.path.exists(cand):
            return cand
        i += 1


def main():
    try:
        if time.time() - os.path.getmtime(STAMP) < INTERVAL_SEC:
            return 0
    except Exception:
        pass
    io.open(STAMP, "w", encoding="utf-8").write(str(int(time.time())))

    if not os.path.isdir(SRC_DIR):
        return 0
    if not external_available():
        log("外付け(iMac HDD)が未接続のため見送り")
        return 0

    try:
        os.makedirs(DEST_DIR, exist_ok=True)
    except Exception as e:
        log("退避先フォルダ作成失敗: %s" % e)
        return 0

    # 重いときは何もしない（掃除でMacを重くしない。他のtamago-shinchoku係と同じ流儀）
    try:
        if os.getloadavg()[0] > 15:
            return 0
    except Exception:
        pass

    moved = []
    freed_mb = 0.0
    cutoff = time.time() - OFFLOAD_AFTER_HOURS * 3600
    try:
        names = os.listdir(SRC_DIR)
    except Exception as e:
        log("Downloads一覧取得失敗: %s" % e)
        return 0

    for name in names:
        if name.startswith(SKIP_PREFIXES):
            continue
        if name.endswith(SKIP_SUFFIXES):
            continue
        src = os.path.join(SRC_DIR, name)
        try:
            mtime = os.path.getmtime(src)
        except Exception:
            continue
        if mtime > cutoff:
            continue  # まだ新しい＝すぐ使うかもしれないので触らない
        try:
            if os.path.isdir(src):
                size_mb = sum(
                    os.path.getsize(os.path.join(dp, f))
                    for dp, _, fs in os.walk(src) for f in fs
                ) / 1024.0 / 1024.0
            else:
                size_mb = os.path.getsize(src) / 1024.0 / 1024.0
        except Exception:
            size_mb = 0.0
        dest = unique_dest(os.path.join(DEST_DIR, name))
        try:
            shutil.move(src, dest)
            moved.append(name)
            freed_mb += size_mb
        except Exception as e:
            log("退避失敗 %s: %s" % (name, e))

    if moved:
        log("📦 %d件・約%.0fMBを外付けへ退避（%s）: %s" % (
            len(moved), freed_mb, DEST_DIR, ", ".join(moved[:15])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
