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



def _mk_jissoku():
    """実測(oembed.jsonl)を 1140_kensa.py が読む形(status/1140/jissoku.json)に直す。"""
    import json as _j
    rows = {}
    p = os.path.join(OUT, "oembed.jsonl")
    for line in io.open(p, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                r = _j.loads(line)
            except Exception:
                continue
            if r.get("id"):
                rows[r["id"]] = r
    dead = sorted(k for k, v in rows.items() if v.get("v") not in ("alive", "unknown"))
    unknown = sorted(k for k, v in rows.items() if v.get("v") == "unknown")
    alive = {k: {"title": v.get("title", ""), "author": v.get("author", "")}
             for k, v in rows.items() if v.get("v") == "alive"}
    out = {"生成": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "_出どころ": "1145番 status/1145/oembed.jsonl（oEmbedで1本ずつ実測・0円）",
           "checked": sorted(rows), "dead": dead, "unknown": unknown,
           "alive_n": len(alive), "alive": alive}
    _j.dump(out, io.open(os.path.join(REPO, "status", "1140", "jissoku.json"),
                         "w", encoding="utf-8"), ensure_ascii=False)


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

    # ⑤ 実測が全部終わったら、隠す表を作り直して本番に押す（聞かずに押す・0円）
    #    ★推測ではなく実測でしか隠さない。生きている動画を隠すのが一番の恥。
    flag = os.path.join(OUT, ".kensa_done_at")
    kdone = os.path.getmtime(flag) if os.path.exists(flag) else 0
    if done >= total > 0 and time.time() - kdone > 3 * 3600:
        io.open(flag, "w").write(str(int(time.time())))
        try:
            _mk_jissoku()
            r1 = subprocess.run([PY, "tools/1140_kensa.py"], cwd=REPO,
                                capture_output=True, timeout=1800)
            note("1140_kensa rc=%d" % r1.returncode)
            r2 = subprocess.run([PY, "tools/1145_push_hidden.py"], cwd=REPO,
                                capture_output=True, timeout=600)
            note("押した rc=%d %s" % (r2.returncode,
                                     (r2.stdout or b"").decode("utf-8", "ignore")[-300:]))
        except Exception as e:
            note("検査・押しで失敗 %s" % e)

    # ④ 1日1回、全部を最初からやり直す（★たまごさん「日ごとにどんどん少なくなってくればいい」）
    #    済んだ分は捨てずに arch/ に退避。次の回は0本から積み直すので、増減が正しく出る。
    dstamp = os.path.join(OUT, ".day_at")
    dlast = os.path.getmtime(dstamp) if os.path.exists(dstamp) else 0
    if done >= total > 0 and time.time() - dlast > 20 * 3600:
        io.open(dstamp, "w").write(str(int(time.time())))
        arch = os.path.join(OUT, "arch")
        os.makedirs(arch, exist_ok=True)
        tag = time.strftime("%Y%m%d")
        for name in ("oembed.jsonl", "page.jsonl"):
            src = os.path.join(OUT, name)
            if os.path.exists(src):
                os.replace(src, os.path.join(arch, "%s.%s" % (name, tag)))
        note("1日1回の流し直し：%s へ退避して0本から積み直す" % tag)



if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        note("guard失敗 %s" % e)
