#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1145番【見張り】実測と、ページの実物見が「黙って止まる」のを防ぐ常駐の一部。

★前の便で起きたこと：実測を nohup で走らせたら213本で黙って消えた（ログに何も残らない＝誰かに殺された）。
  → 生きているか毎周回で見て、居なければ**続きから**立て直す。1本ずつjsonlに追記してあるので続きから再開できる。
★process group ごと殺されても生き残るよう start_new_session=True で離す。
★1日1回、推移（suii）を書き直す。

心臓（tools/top_status.py の末尾）から投げっぱなしで呼ばれる。1秒もかからない。
"""
from __future__ import annotations
import io, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "status", "1145")
PY = sys.executable or "/usr/bin/python3"
LOG = os.path.join(OUT, "guard.log")


def note(s):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%F %T"), s))
    except Exception:
        pass


def running(pat):
    try:
        r = subprocess.run(["/usr/bin/pgrep", "-f", pat], capture_output=True, timeout=10)
        return bool((r.stdout or b"").strip())
    except Exception:
        return True   # 分からないときは「居る」扱い。二重起動より安全。


def launch(args, log):
    f = io.open(os.path.join(OUT, log), "a", buffering=1, encoding="utf-8")
    subprocess.Popen([PY] + args, cwd=REPO, stdout=f, stderr=subprocess.STDOUT,
                     start_new_session=True, close_fds=True)
    note("立て直した: " + " ".join(args))


def count_lines(p):
    if not os.path.exists(p):
        return 0
    n = 0
    for _ in io.open(p, encoding="utf-8", errors="replace"):
        n += 1
    return n


def main():
    os.makedirs(OUT, exist_ok=True)
    ids = os.path.join(REPO, "status", "1140", "all_video_ids.txt")
    total = count_lines(ids)

    # ① 動画の実測
    done = count_lines(os.path.join(OUT, "oembed.jsonl"))
    if done < total and not running("1145_jissoku.py"):
        launch(["tools/1145_jissoku.py"], "jissoku_run.log")

    # ② ページを実物で見る
    todo = os.path.join(OUT, "page_todo.txt")
    ptotal = count_lines(todo)
    pdone = count_lines(os.path.join(OUT, "page.jsonl"))
    if pdone < ptotal and not running("1145_page.py"):
        launch(["tools/1145_page.py", "--list", "status/1145/page_todo.txt",
                "--limit", "2000"], "page_run.log")

    # ③ 推移は10分に1回だけ書き直す（毎周回はやらない）
    stamp = os.path.join(OUT, ".suii_at")
    last = os.path.getmtime(stamp) if os.path.exists(stamp) else 0
    if time.time() - last > 600:
        io.open(stamp, "w").write(str(int(time.time())))
        try:
            subprocess.run([PY, "tools/1145_suii.py"], cwd=REPO,
                           capture_output=True, timeout=180)
        except Exception as e:
            note("suii失敗 %s" % e)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        note("guard失敗 %s" % e)
