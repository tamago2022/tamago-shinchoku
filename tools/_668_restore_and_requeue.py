#!/usr/bin/env python3
"""
668番 追加修正:
① urls欄が空だがローカルにshare/check/{n}-*.htmlが実在するdoneアイテム
   → GitHub PagesのURLをurls欄へ復元する（渡す手段が無かっただけで仕事は終わっている）。
② urls欄も確認ページも無く、result欄がプレースホルダー（検品結果の通知を待っています等）の
   doneアイテム → 仕事が終わっていない疑いが濃いのでwaitingへ正直に差し戻す。
"""
import json
import glob
import fcntl
import io
import time
import datetime
from contextlib import contextmanager

REPO = "/Users/mac/Desktop/tamago-shinchoku"
QUEUE = REPO + "/status/queue.json"
QUEUE_LOCK = REPO + "/status/.queue.lock"
PAGES_BASE = "https://tamago2022.github.io/tamago-shinchoku/"

RESTORE_NS = [419, 37, 23, 22, 19, 10, 460, 467, 475, 491, 512, 615, 622]
REQUEUE_NS = [4, 17]


@contextmanager
def queue_lock(timeout=180.0):
    f = io.open(QUEUE_LOCK, "a+")
    t0 = time.time()
    while True:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except Exception:
            if time.time() - t0 > timeout:
                f.close()
                raise RuntimeError("queue_lock timeout")
            time.sleep(0.2)
    try:
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


def main():
    with queue_lock():
        with open(QUEUE, encoding="utf-8") as f:
            d = json.load(f)

        restored, requeued = [], []
        for it in d["items"]:
            n = it.get("n")
            if n in RESTORE_NS and not it.get("urls"):
                pages = sorted(glob.glob(REPO + "/share/check/%s-*.html" % n))
                if pages:
                    urls = [PAGES_BASE + "share/check/" + p.split("/share/check/")[-1] for p in pages]
                    it["urls"] = urls
                    it["urlsFixedAt"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+0900")
                    it["urlsFixedNote"] = "668番:urls欄が空だったがローカルに確認ページが実在したため復元"
                    restored.append({"n": n, "urls": urls})
            if n in REQUEUE_NS and it.get("status") == "done":
                note = (
                    "\n\n【668番・差し戻し】queue.jsonのurls欄が空で確認ページも見つからず、"
                    "result欄が「%s」というプレースホルダーのままdoneになっていました。"
                    "仕事が終わった証拠が無いため、正直にwaitingへ戻します。"
                ) % (it.get("result") or "")
                it["what"] = it.get("what", "") + note
                it["status"] = "waiting"
                it["redoCount"] = it.get("redoCount", 0) + 1
                for k in ("okBy", "okNote", "startedAt", "finishedAt", "sessionId", "pid", "checkedAt"):
                    it.pop(k, None)
                requeued.append({"n": n, "title": it.get("title")})

        d["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        with open(QUEUE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
            f.write("\n")

    print("復元(urls空→復元)=%d件" % len(restored))
    for r in restored:
        print("  n=%s urls=%s" % (r["n"], r["urls"]))
    print("差し戻し(done→waiting)=%d件" % len(requeued))
    for r in requeued:
        print("  n=%s title=%s" % (r["n"], r["title"]))


if __name__ == "__main__":
    main()
