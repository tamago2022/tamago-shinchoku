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


# 2026-09-09追加（674番「引き継ぎが100分の1にならない仕組み」事故点検）:
# 「60日以上さわられていないものを自動退避する」設計は、確認ページの本体(HTML)は
# 一度作ったら二度と編集しないため、60日経てば必ず対象になり、結局は
# 「一度たまごさんに渡したURLは絶対に殺さない」(2026-09-08決定)と正面衝突する。
# 2026-09-08の256件誤退避事故は別のワンオフ掃除スクリプトが原因だが、
# 同じ穴をこのツールが再現し得る設計のまま残っていたため無効化する。
# share/check配下は実測で軽い(258件のHTMLを全部足しても33MB)ため、
# 自動削除する必要そのものが無い。容量が心配なら「新規生成時に軽くする」側で対処する。
DISABLED = True


def main():
    if DISABLED:
        log("SKIP: 2026-09-09以降このツールは無効化（674番）。"
            "share/check配下(確認ページ・画像・動画とも)は自動では一切削除しない。"
            "『一度渡したURLは絶対に殺さない』方針のため。容量対策は生成時に軽くする側で行う。")
        return 0
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
