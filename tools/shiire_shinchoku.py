#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""34547番：仕入れの進捗（完了・残り）を1枚で見れるようにする。

たまごさん（2026-08-05・スマホから）：
  「どこまで仕入れが完了しているか、これから何件残っているかが分かるように
   進捗を管理してください。」

★なぜ今まで無かったか（調べて分かったこと）
  仕入れは1つの作業ではなく複数系統に分かれていて、それぞれ別の場所に
  数字だけ記録されていた（店主が見れる1枚のページが無かった）：
    ① フェス名簿からの仕入れ（1044/1049番・tools/shiire_loop.py が毎日回す）
       → status/shiire_kouho/_run.json、status/shiire_shoko/_index.json、
         status/shiire_loop.log（最新行）に数字はあるが、JSONの生ファイルのまま。
    ② 日次の入荷見回り（756番）→ status/public/daily_ingest_summary.json
    ③ 工場の作業キュー（status/queue.json）にある「仕入れ」を含む依頼の
       待機・保留・走行中の件数
    ④ ごきげん補給所（joy-relief-station）側の在庫の実数
       （アーティスト数・曲数・YouTube ID充足率）

  ★数字を1つに盛って「仕入れ進捗◯%」のような嘘くさい統合指標は作らない
  （店主の方針「正しいより楽しい。ただし嘘は禁止」「確認が取れる情報を
    1つ入れると信頼が積み重なる」＝不正確な統合より正確な個別の数字）。
  系統ごとに「今ある数・残りの数」をそのまま並べる。

使い方
    python3 tools/shiire_shinchoku.py            # 集計して status/public/ へ書く
    python3 tools/shiire_shinchoku.py --print    # 標準出力にも出す
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
PUBLIC = os.path.join(ST, "public")
OUT = os.path.join(PUBLIC, "shiire_shinchoku.json")
JST_NOW = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")

# ごきげん補給所の実体（デスクトップのクローン。読むだけ・書かない）。
# 無ければ在庫の実数は省略し、無かったことを隠さずそのまま書く。
JOY_CANDIDATES = [
    os.path.expanduser("~/Desktop/joy-relief-station"),
    os.path.expanduser("~/tamago/joy-relief-station"),
]


def _safe_json(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def fes_meibo_shiire():
    """①フェス名簿からの仕入れ（1044/1049番）。"""
    run = _safe_json(os.path.join(ST, "shiire_kouho", "_run.json"), {}) or {}
    shoko = _safe_json(os.path.join(ST, "shiire_shoko", "_index.json"), {}) or {}

    last_line = {}
    log_path = os.path.join(ST, "shiire_loop.log")
    if os.path.exists(log_path):
        try:
            with io.open(log_path, encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if line.startswith("{"):
                    last_line = json.loads(line)
                    break
        except Exception:
            last_line = {}

    todo_path = os.path.join(ST, "1044_shiire_todo.txt")
    todo_total = 0
    if os.path.exists(todo_path):
        try:
            with io.open(todo_path, encoding="utf-8") as f:
                todo_total = len([l for l in f.read().splitlines() if l.strip()])
        except Exception:
            todo_total = 0

    return {
        "kouho": run.get("candidates"),
        "runs": run.get("runs"),
        "shokoKensu": shoko.get("kensu"),
        "shokoHonninKakutei": shoko.get("honninKakutei"),
        "shokoHoryuu": shoko.get("horyuu"),
        "todoTotal": todo_total or None,
        "sozaiMachi": last_line.get("ato", {}).get("sozaiMachi", last_line.get("sozaiMachi")),
        "sozaiNokori": last_line.get("sozaiNokori"),
        "lastRunAt": last_line.get("at"),
    }


def nikkan_nyuka():
    """②日次の入荷見回り（756番）。"""
    d = _safe_json(os.path.join(PUBLIC, "daily_ingest_summary.json"), {}) or {}
    if not d:
        return None
    return {
        "date": d.get("date"),
        "total": d.get("total"),
        "fixed": d.get("fixed"),
        "ok": d.get("ok"),
        "unsure": d.get("unsure"),
        "updatedAt": d.get("updatedAt"),
    }


def koujou_queue_shiire():
    """③工場の作業キュー（status/queue.json）の「仕入れ」を含む依頼。"""
    data = _safe_json(os.path.join(ST, "queue.json"), None)
    if data is None:
        return None
    items = data if isinstance(data, list) else data.get("items", data.get("queue", []))
    counts = {"waiting": 0, "hold": 0, "running": 0, "awaiting_check": 0, "other": 0}
    total = 0
    for it in items or []:
        if not isinstance(it, dict):
            continue
        title = (it.get("title") or "") + (it.get("hyoudai") or "")
        if "仕入れ" not in title and "shiire" not in title.lower():
            continue
        total += 1
        st = it.get("status", "other")
        counts[st if st in counts else "other"] += 1
    return {"total": total, "byStatus": counts}


def joy_zaiko():
    """④ごきげん補給所の在庫実数（origin/main の静的データファイルから数える近似値）。

    ★DBの生の値ではない。リポジトリに入っている静的ファイル
      （coverGuideLite.generated.ts）から数えたスナップショット。
      店主向けの正式な在庫数は /admin/inventory（ログイン必須）が正。
      ここでは「だいたい今どれくらいか」を店主にも見える場所に出すために使う。

    ★ローカルのワーキングツリーを直接読まない（他セッションの未コミット変更が
      混ざって数字がブレた実例があった）。`git show origin/main:<path>` で
      常にmain最新のコミット済み内容だけを読む。
    """
    import subprocess

    for base in JOY_CANDIDATES:
        if not os.path.isdir(base):
            continue
        rel = "src/lib/coverGuideLite.generated.ts"
        try:
            subprocess.run(
                ["git", "-C", base, "fetch", "origin", "main", "--quiet"],
                timeout=60, capture_output=True,
            )
            p = subprocess.run(
                ["git", "-C", base, "show", "origin/main:" + rel],
                timeout=30, capture_output=True, text=True,
            )
            if p.returncode != 0 or not p.stdout:
                continue
            text = p.stdout
            commit_at = subprocess.run(
                ["git", "-C", base, "log", "-1", "--format=%ci", "origin/main", "--", rel],
                timeout=15, capture_output=True, text=True,
            ).stdout.strip()[:10]
        except Exception:
            continue

        songs_objs = re.findall(r'\{"id":"[^"]*","title":"[^"]*"[^}]*\}', text)
        artist_lines = re.findall(r'^\s*\{"id":"', text, re.M)
        yt = sum(1 for s in songs_objs if '"youtubeId"' in s)
        songs = len(songs_objs)
        rate = round((yt / songs) * 100, 1) if songs else None
        return {
            "artists": len(artist_lines),
            "songs": songs,
            "youtubeIds": yt,
            "youtubeRate": rate,
            "snapshotFrom": "origin/main",
            "snapshotCommitDate": commit_at or None,
        }
    return None


def main():
    out = {
        "updatedAt": JST_NOW,
        "fesMeibo": fes_meibo_shiire(),
        "dailyIngest": nikkan_nyuka(),
        "koujouQueue": koujou_queue_shiire(),
        "joyZaiko": joy_zaiko(),
    }
    os.makedirs(PUBLIC, exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    if "--print" in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("書いた: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
