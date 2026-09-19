#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""759番・第2便（2026-09-12・AI検品で再指摘を受けての修正）。

たまごさんが例に挙げた「中目黒のやつ」（#749）が、756番backfill後もdekimono.jsonに
存在しないと検品で突き止められた。原因調査の結果：

  backfill_dekimono_kind.py は status/queue.json と status/done_archive.json の
  status=="done" だけを見ていたが、この2つは**ロールする一覧**（done_archive.jsonは
  直近100件程度でどんどん入れ替わる）。#749は2026-09-11完了、759番backfillが走った
  2026-09-12夜には、queue.json からも done_archive.json からもすでに流れて消えていた。
  →「できたもの」に登録する前に、登録元のデータ自体が消えていた。

一方、**share/check/*.html（確認ページ）は「一度渡したURLは殺さない」原則で消さない
運用**なので、ここが唯一の永続記録。これを正本にして巻き戻す。

やること：share/check/*.html を全件走査し、ファイル名の先頭番号(n)が現在の
status/dekimono.json にまだ無いものだけ、ページ内の<h1>・.date・.fix から
title/what/addedAtを取り出し、dekimono_lib.record_done()と同じ判定
（新しく作った／直した／内部作業で対象外）で1件ずつ積む。

一度きりの引っ越し作業。何度実行しても、すでに載っているnは_append内のnチェックで
スキップされるだけなので安全（冪等）。
"""
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import dekimono_lib  # noqa: E402

DEKI_PATH = os.path.join(REPO, "status", "dekimono.json")
CHECK_DIR = os.path.join(REPO, "share", "check")

FNAME_RE = re.compile(r"^(\d+)-")
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
DATE_RE = re.compile(r'<div class="date">(\d{4}-\d{2}-\d{2})', re.S)
FIX_RE = re.compile(r'<div class="fix">(.*?)</div>', re.S)
TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(s):
    return TAG_RE.sub("", s or "").strip()


def load_deki():
    try:
        return json.load(io.open(DEKI_PATH, encoding="utf-8"))
    except Exception:
        return {"updatedAt": "", "items": []}


def main():
    d = load_deki()
    existing_ns = set(it.get("n") for it in d.get("items", []))

    files = sorted(glob.glob(os.path.join(CHECK_DIR, "*.html")))
    # 同じnで複数ファイルがある場合は最初の1件だけ使う（例：734が2本ある等）
    seen_n_in_run = set()
    added_new, added_fixed, skipped_internal, skipped_existing, skipped_noparse = 0, 0, 0, 0, 0

    for path in files:
        fname = os.path.basename(path)
        m = FNAME_RE.match(fname)
        if not m:
            continue
        n = int(m.group(1))
        if n in existing_ns:
            skipped_existing += 1
            continue
        if n in seen_n_in_run:
            continue

        try:
            html = io.open(path, encoding="utf-8", errors="ignore").read()
        except Exception:
            skipped_noparse += 1
            continue

        h1m = H1_RE.search(html)
        title_raw = strip_tags(h1m.group(1)) if h1m else fname
        # 先頭の "#749 " を落とす
        title = re.sub(r"^#\d+\s*", "", title_raw).strip() or title_raw

        datem = DATE_RE.search(html)
        date_str = datem.group(1) if datem else None

        fixm = FIX_RE.search(html)
        what_full = strip_tags(fixm.group(1)) if fixm else title

        url = "https://tamago2022.github.io/tamago-shinchoku/share/check/%s" % fname
        added_at = ("%sT12:00:00+09:00" % date_str) if date_str else None

        kind = dekimono_lib.record_done(n, title, what_full, [url], added_at)
        seen_n_in_run.add(n)
        if kind == "new":
            added_new += 1
        elif kind == "fixed":
            added_fixed += 1
        else:
            skipped_internal += 1

    print("確認ページ走査: %d件" % len(files))
    print("新規追加：新しく作った+%d件・直した+%d件" % (added_new, added_fixed))
    print("対象外（内部作業などでどちらにも載せない）：%d件" % skipped_internal)
    print("すでに棚にあったのでスキップ：%d件" % skipped_existing)
    print("読めなかった：%d件" % skipped_noparse)

    d2 = load_deki()
    items = d2.get("items", [])
    print("合計：%d件（うち新しく作った %d件・直した %d件）" % (
        len(items),
        len([x for x in items if x.get("kind") == "new"]),
        len([x for x in items if x.get("kind") == "fixed"]),
    ))
    hit749 = [x for x in items if x.get("n") == 749]
    print("#749（中目黒）:", json.dumps(hit749, ensure_ascii=False))


if __name__ == "__main__":
    main()
