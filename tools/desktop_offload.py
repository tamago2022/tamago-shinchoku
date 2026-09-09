#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desktop直下の大きい生成物・アーカイブを、Mac本体ではなく外付け(iMac HDD)へ
既定の置き場として逃がす係（2026-09-09・685番「ディスクが1日20GB以上減る原因を
徹底追及して止める＋外付けを既定の置き場にする」）。

たまごさんの指示（そのまま）：
  「ダウンロードとか動画・画像の生成物は全部iMac HDDを使うようにしてほしい」

downloads_offload.py（~/Downloads担当）と同じ考え方をDesktopにも広げる。
Desktopは作業中のファイルも多いため、Downloadsより慎重な条件にする：
  - 500MB以上の「単体ファイル」だけを対象にする（フォルダ・小さいファイルは触らない）
  - 7日以上更新されていないものだけ（すぐ使う生成物を持っていかない）
  - .app / エイリアス / tamago-shinchoku・joy-relief-station等の作業リポジトリ
    自体（フォルダ）は対象外（このスクリプトはファイル単体しか動かさない設計
    なので実質的にリポジトリフォルダごと巻き込むことはない）
  - 既に~/Desktop直下にある「◯◯退避」系フォルダ自体（前回までの手動退避の
    受け皿）は移動対象から除外する
"""
import io
import os
import shutil
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

HOME = os.path.expanduser("~")
SRC_DIR = os.path.join(HOME, "Desktop")
EXTERNAL_VOLUME = "/Volumes/iMac HDD"
DEST_DIR = os.path.join(EXTERNAL_VOLUME, "Mac標準置き場", "Desktop生成物退避")

LOG = os.path.join(REPO, "status", "desktop_offload.log")
STAMP = os.path.join(REPO, "status", ".desktop_offload_at")
INTERVAL_SEC = 6 * 3600        # 6時間に1回でよい（downloads_offloadと同じ間隔）
OFFLOAD_AFTER_HOURS = 24 * 7   # 7日間は手元に残す（作業中のものを持っていかない）
MIN_SIZE_MB = 500              # これ未満のファイルは対象外（小物まで漁らない）

SKIP_PREFIXES = (".",)
SKIP_SUFFIXES = (".download", ".crdownload", ".part")
# tamago-shinchoku / joy-relief-station 等の作業リポジトリ本体、既存の退避先
# フォルダ自体は名指しで除外（誤ってリポジトリを動かす事故を防ぐ）。
SKIP_NAMES_CONTAINING = (
    "tamago-shinchoku", "joy-relief-station", "退避", "Vault",
)


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def external_available():
    return os.path.isdir(EXTERNAL_VOLUME)


def unique_dest(dest):
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
        log("Desktop一覧取得失敗: %s" % e)
        return 0

    for name in names:
        if name.startswith(SKIP_PREFIXES):
            continue
        if name.endswith(SKIP_SUFFIXES):
            continue
        if any(k in name for k in SKIP_NAMES_CONTAINING):
            continue
        src = os.path.join(SRC_DIR, name)
        # フォルダは対象外（今回は単体ファイルのみ、誤動作リスクを下げる）
        if not os.path.isfile(src):
            continue
        try:
            mtime = os.path.getmtime(src)
            size_mb = os.path.getsize(src) / 1024.0 / 1024.0
        except Exception:
            continue
        if mtime > cutoff:
            continue
        if size_mb < MIN_SIZE_MB:
            continue
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
