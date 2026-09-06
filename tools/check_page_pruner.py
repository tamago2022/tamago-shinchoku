#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""確認ページ（share/check）の自動間引き（2026-09-07・620番）。

たまごさんの言葉：「絶対なんか要らないものが溜まってると思うよ。おかしい。」

正体：`share/check/` は毎回の確認ページ作成のたびに増える一方で、
上限も自動削除の仕組みも無かった（実測：本体185MB＋img40MB＋video92MB＋
assets35MB＋videos16MB、日々のスクショ・動画で確認ページが増え続ける）。

やること：
  ① `share/check/` トップの `*.html` と `img/`・`video/`・`videos/`・`assets/`
     配下の個別ファイル/フォルダのうち、**60日以上さわられていないもの**だけ
     `~/.Trash/check_page_pruner/` へ退避する（rmはしない。店主が後で拾える）。
  ② 何を退避したかを1行ずつ `status/check_page_pruner.log` に残す。
  ③ 壺・金庫（Vault・Drive実体・写真等）には一切降りない。対象は
     `share/check/` 配下だけに固定。
"""
import io
import os
import shutil
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)  # /Users/mac/Desktop/tamago-shinchoku
CHECK_DIR = os.path.join(REPO, "share", "check")
LOG = os.path.join(REPO, "status", "check_page_pruner.log")
STAMP = os.path.join(REPO, "status", ".check_page_pruner_at")
TRASH = os.path.join(os.path.expanduser("~"), ".Trash", "check_page_pruner")

INTERVAL = 21600          # 6時間に1回でよい
MAX_AGE_SEC = 60 * 86400  # 60日以上さわられていないものだけ対象


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def prune_dir(sub):
    """CHECK_DIR/sub 配下の直下エントリのうち、古いものだけ退避する。"""
    root = os.path.join(CHECK_DIR, sub) if sub else CHECK_DIR
    if not os.path.isdir(root):
        return []
    moved = []
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        # トップ直下は *.html のみ対象（サブフォルダ自体はsub側で個別に処理する）
        if sub == "" and os.path.isdir(path):
            continue
        if sub == "" and not name.endswith(".html"):
            continue
        try:
            age = time.time() - os.path.getmtime(path)
        except Exception:
            continue
        if age < MAX_AGE_SEC:
            continue
        try:
            os.makedirs(TRASH, exist_ok=True)
            dest = os.path.join(TRASH, "%s_%s" % (sub or "top", name))
            if os.path.exists(dest):
                dest = "%s_%d" % (dest, int(time.time()))
            shutil.move(path, dest)
            moved.append(os.path.join(sub, name) if sub else name)
        except Exception as e:
            log("退避失敗 %s: %s" % (path, e))
    return moved


def main():
    try:
        if time.time() - os.path.getmtime(STAMP) < INTERVAL:
            return 0
    except Exception:
        pass
    io.open(STAMP, "w", encoding="utf-8").write(str(int(time.time())))

    if not os.path.isdir(CHECK_DIR):
        return 0

    total_moved = []
    for sub in ("", "img", "video", "videos", "assets"):
        total_moved += prune_dir(sub)

    if total_moved:
        log("🧹 60日超の確認ページ素材を退避 %d件（%sに残っています）: %s"
            % (len(total_moved), TRASH, ", ".join(total_moved[:15])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
