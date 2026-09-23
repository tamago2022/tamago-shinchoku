# -*- coding: utf-8 -*-
"""【工場の待ち行列・正本】仕事を1件置く／結果を待つ／結果を書く。**ここ1か所だけ。**

★このファイルは「待ち行列」以外のことを一切しない。外部AIも叩かない。鍵も読まない。
　だから**書き換える理由が発生しない。**

■ なぜ独立したファイルにしたか（2026-09-24 実測の事故）
  09-24 03:35:42  工場のrunnerが最後の仕事を終える
  09-24 03:38     `tools/gaibu_kuchi.py` が**丸ごと書き替えられた**（外部の判定役を呼ぶ別物に）。
                  その拍子に JOBS_DIR / enqueue_job / wait_job が**巻き添えで消えた。**
  09-24 03:42     積まれた仕事が pending/ に残ったまま、以後ひとつも動かない。
                  `gaibu_runner.py` は import の行で落ちるので、ログにも何も出ない。

  ＝**待ち行列が「外部AIを叩く道具」と同じ家に同居していたのが原因。**
  同居している限り、道具を作り直すたびに待ち行列が道連れになる。2回目は必ず来る。

  だから穴を塞がない。**パイプごと替える：待ち行列を自分の家に出す。**
  ・`gaibu_runner.py` と各道具は **このファイルを直接 import する。**
  ・`gaibu_kuchi.py` は互換のため再輸出するだけ（消えても工場は死なない）。
  ・`python3 tools/shigoto_queue.py --selftest` で**置く→書く→待つ**が1秒で確認できる。
"""
import io
import json
import os
import socket
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

JOBS_DIR = os.path.join(REPO, "status", "gaibu_jobs")
JOBS_PENDING = os.path.join(JOBS_DIR, "pending")
JOBS_DONE = os.path.join(JOBS_DIR, "done")
JOBS_RUNNING = os.path.join(JOBS_DIR, "running")

__all__ = ["JOBS_DIR", "JOBS_PENDING", "JOBS_DONE", "JOBS_RUNNING",
           "enqueue_job", "wait_job", "write_job_result", "pending_names"]


def _dirs():
    for d in (JOBS_PENDING, JOBS_DONE, JOBS_RUNNING):
        os.makedirs(d, exist_ok=True)


def _job_id():
    return time.strftime("%Y%m%d-%H%M%S") + "-%04d" % (int(time.time() * 1000) % 10000)


def _atomic_write(path, obj):
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def enqueue_job(kind, payload):
    """工場にやらせる仕事を1件置く。戻り値: job_id"""
    _dirs()
    jid = _job_id()
    _atomic_write(os.path.join(JOBS_PENDING, jid + ".json"),
                  {"jobId": jid, "kind": kind, "payload": payload,
                   "queuedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "queuedFrom": socket.gethostname()})
    return jid


def wait_job(jid, wait_sec=420, poll=5, on_tick=None):
    """結果が出るまで待つ。戻り値: 結果dict / None（時間切れ）"""
    done_path = os.path.join(JOBS_DONE, jid + ".json")
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        if os.path.exists(done_path):
            for _ in range(5):  # 書き込み途中を掴まないよう軽くリトライ
                try:
                    return json.load(io.open(done_path, encoding="utf-8"))
                except Exception:
                    time.sleep(0.4)
        if on_tick:
            on_tick(int(deadline - time.time()))
        time.sleep(poll)
    return None


def write_job_result(jid, result):
    os.makedirs(JOBS_DONE, exist_ok=True)
    _atomic_write(os.path.join(JOBS_DONE, jid + ".json"), result)


def pending_names():
    try:
        return sorted(f for f in os.listdir(JOBS_PENDING) if f.endswith(".json"))
    except Exception:
        return []


def _selftest():
    """置く→書く→待つ が通るか。工場を起こさずに1秒で確かめる。"""
    jid = enqueue_job("_selftest", {"n": 1})
    src = os.path.join(JOBS_PENDING, jid + ".json")
    ok1 = os.path.exists(src)
    write_job_result(jid, {"ok": True, "jobId": jid})
    got = wait_job(jid, wait_sec=3, poll=0.2)
    for p in (src, os.path.join(JOBS_DONE, jid + ".json")):
        try:
            os.remove(p)
        except Exception:
            pass
    ok = bool(ok1 and got and got.get("ok"))
    print(json.dumps({"ok": ok, "置けた": ok1, "待って取れた": bool(got),
                      "待ち行列": JOBS_DIR, "いま積まれている": len(pending_names())},
                     ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    print(json.dumps({"待ち行列": JOBS_DIR, "いま積まれている": pending_names()},
                     ensure_ascii=False, indent=1))
