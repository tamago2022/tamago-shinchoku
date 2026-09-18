#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""944番【本丸】工場側の代行係 — サンドボックスの代わりに外部AIを叩く。

■ なぜ要るか（2026-09-18 実測）
  Cowork/Dispatch のサンドボックスからは api.openai.com / api.x.ai /
  generativelanguage.googleapis.com に**回線が出ない**（名前解決で落ちる）。
  たまごさんのMac（＝工場）からは**出る**（tools/kenpin_gate.py が実際に往復している）。
  だから「外部AIを叩くコード」は工場側で動かす。この1本がその窓口。

■ 動き方（新しいlaunchd常駐は増やさない＝既存方針）
  tools/machine_status_push.sh の 15秒おきの軽い巡回（quick_tick）から呼ばれる。
  status/gaibu_jobs/pending/ が空なら**数ミリ秒で何もせず終わる**ので、工場は重くならない。

■ 仕事の種類
  kiku   … tools/kiku.py   の run_job（3社に同じ前提で聞く）
  tanomu … tools/tanomu.py の run_job（リサーチ・画像などの成果物を作らせる）

■ 二重起動しない
  status/gaibu_jobs/.runner.lock を見る。古い（10分超）ロックは壊れたものとみなして奪う。
"""
import argparse
import io
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gaibu_kuchi as gkuchi  # noqa: E402

LOCK = os.path.join(gkuchi.JOBS_DIR, ".runner.lock")
RUNLOG = os.path.join(REPO, "status", "gaibu_runner.log")
LOCK_STALE_SEC = 600


def _log(msg):
    try:
        with io.open(RUNLOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def _take_lock():
    os.makedirs(gkuchi.JOBS_DIR, exist_ok=True)
    if os.path.exists(LOCK):
        try:
            age = time.time() - os.path.getmtime(LOCK)
        except Exception:
            age = 0
        # ★中身が「released」なら、消せなかっただけの抜け殻。塞いでいない。
        try:
            head = io.open(LOCK, encoding="utf-8").read(16)
        except Exception:
            head = ""
        if not head.startswith("released") and age < LOCK_STALE_SEC:
            return False
        if not head.startswith("released"):
            _log("古いロック(%.0f秒)を奪いました" % age)
    try:
        with io.open(LOCK, "w", encoding="utf-8") as f:
            f.write("%d %s\n" % (os.getpid(), time.strftime("%Y-%m-%d %H:%M:%S")))
        return True
    except Exception:
        return False


def _release_lock():
    """ロックを外す。
    ★2026-09-18 実測：Cowork(サンドボックス)のマウント越しだと os.remove が通らないことがある
    （.git の index.lock が片付けられなかったのと同じ現象・tools/git_lock_reaper.py の経緯）。
    消せなかった場合に次の起動が門前払いされ続けると、窓口が丸ごと死ぬ。
    そこで **消せなければ更新時刻を大昔にする**。上の _take_lock() は経過時間で
    「壊れたロック」と判定して奪うので、どちらに転んでも詰まらない。"""
    try:
        os.remove(LOCK)
        return
    except Exception:
        pass
    try:
        with io.open(LOCK, "w", encoding="utf-8") as f:
            f.write("released %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        os.utime(LOCK, (0, 0))
    except Exception:
        pass


def _pending():
    try:
        return sorted(f for f in os.listdir(gkuchi.JOBS_PENDING) if f.endswith(".json"))
    except Exception:
        return []


def run_once(max_jobs=3, quiet=True, only_job=None):
    """only_job … その仕事票1枚だけを処理する（自己テストが本物の待ち行列を食べないため）。"""
    # ★空なら即終了。15秒おきに呼ばれるので、ここが軽いことが一番大事。
    if not os.path.isdir(gkuchi.JOBS_PENDING) or not _pending():
        return 0
    if not gkuchi.net_ok():
        _log("回線が出ないホストで起動されました。何もしません。")
        return 0
    if not _take_lock():
        return 0

    done_n = 0
    try:
        todo = _pending()
        if only_job:
            todo = [f for f in todo if f.startswith(only_job)]
        for name in todo[:max_jobs]:
            src = os.path.join(gkuchi.JOBS_PENDING, name)
            try:
                job = json.load(io.open(src, encoding="utf-8"))
            except Exception as e:
                _log("読めない仕事票を退けました %s: %s" % (name, e))
                try:
                    os.replace(src, os.path.join(gkuchi.JOBS_RUNNING, name + ".broken"))
                except Exception:
                    pass
                continue

            jid = job.get("jobId") or name[:-5]
            os.makedirs(gkuchi.JOBS_RUNNING, exist_ok=True)
            try:  # pendingから外して二重実行を防ぐ
                os.replace(src, os.path.join(gkuchi.JOBS_RUNNING, name))
            except Exception:
                continue

            t0 = time.time()
            _log("開始 %s kind=%s" % (jid, job.get("kind")))
            try:
                if job.get("kind") == "kiku":
                    import kiku
                    out = kiku.run_job(job["payload"])
                elif job.get("kind") == "tanomu":
                    import tanomu
                    out = tanomu.run_job(job["payload"])
                elif job.get("kind") == "sweep":
                    # Chromeタブ掃除機を工場側で今すぐ走らせる（サンドボックスからは
                    # osascriptが使えないため）。呼べるのはこの1本だけ＝白名簿。
                    import subprocess
                    cmd = [sys.executable, os.path.join(HERE, "chrome_tab_sweeper.py"),
                           "--recon", "--sweep", "--force"]
                    if job["payload"].get("dryRun"):
                        cmd.append("--dry-run")
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    out = {"ok": r.returncode == 0, "stdout": r.stdout[-2000:],
                           "stderr": r.stderr[-1000:], "totalYen": 0.0}
                elif job.get("kind") == "diag":
                    # 窓口が通らないとき「向こうに何が有るのか」を工場側で聞きに行く。
                    # 鍵の値は出さない（gaibu_diag.py 側で保証）。
                    import gaibu_diag
                    out = gaibu_diag.run_job(job["payload"])
                else:
                    out = {"ok": False, "error": "知らない仕事の種類です: %s" % job.get("kind")}
            except Exception:
                out = {"ok": False, "error": "工場側で例外が出ました:\n" + traceback.format_exc()[-1500:]}

            out["jobId"] = jid
            out["ranOn"] = "factory"
            out["ranAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
            out["elapsedSec"] = round(time.time() - t0, 1)
            gkuchi.write_job_result(jid, out)
            _log("完了 %s ok=%s %.1f秒 %.3f円" % (jid, out.get("ok"), out["elapsedSec"],
                                                out.get("totalYen") or 0))
            try:
                os.remove(os.path.join(gkuchi.JOBS_RUNNING, name))
            except Exception:
                pass
            done_n += 1
            if not quiet:
                print("処理しました: %s (ok=%s)" % (jid, out.get("ok")))
    finally:
        _release_lock()
    return done_n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--max-jobs", type=int, default=3)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    if a.status:
        print("回線（api.openai.com）：%s" % ("出る ✅" if gkuchi.net_ok() else "出ない ❌"))
        print("鍵：%s" % json.dumps(gkuchi.key_status(), ensure_ascii=False))
        print("待ち：%d件 / 済み：%d件"
              % (len(_pending()),
                 len(os.listdir(gkuchi.JOBS_DONE)) if os.path.isdir(gkuchi.JOBS_DONE) else 0))
        return 0

    n = run_once(max_jobs=a.max_jobs, quiet=a.quiet)
    if not a.quiet:
        print("処理件数: %d" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
