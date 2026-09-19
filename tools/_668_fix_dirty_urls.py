#!/usr/bin/env python3
"""
668番：queue.jsonのurls欄に「URL＋日本語説明文」が1つの文字列として
連結されている『記録ミス』を機械的に修正する。

これはVerifierが420番で実測した「404」の正体そのもの
（urls欄の値をそのまま開こうとすると、末尾の日本語がURLの一部として
渡ってしまい壊れる）。urls欄はクリーンなURLだけに直し、説明文は
resultフィールド側（既に本文として残っている）に任せて捨てる。
"""
import json
import re
import fcntl
import io
import time
import datetime
from contextlib import contextmanager

REPO = "/Users/mac/Desktop/tamago-shinchoku"
QUEUE = REPO + "/status/queue.json"
QUEUE_LOCK = REPO + "/status/.queue.lock"

STOP_CHARS = "（`　\n\t"


def extract_real_url(raw):
    u = raw.strip()
    cut = len(u)
    for ch in STOP_CHARS:
        idx = u.find(ch)
        if idx != -1:
            cut = min(cut, idx)
    real = u[:cut].rstrip("`").strip()
    return real


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

        fixed = []
        for it in d["items"]:
            urls = it.get("urls") or []
            new_urls = []
            changed = False
            for u in urls:
                if re.search(r"[ぁ-んァ-ヶ一-龠（）]", u):
                    real = extract_real_url(u)
                    if real and real != u:
                        new_urls.append(real)
                        changed = True
                        fixed.append({"n": it.get("n"), "before": u, "after": real})
                    elif real:
                        new_urls.append(real)
                else:
                    new_urls.append(u)
            if changed:
                # 重複除去（順序維持）
                seen = set()
                dedup = []
                for u in new_urls:
                    if u not in seen:
                        seen.add(u)
                        dedup.append(u)
                it["urls"] = dedup
                it["urlsFixedAt"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+0900")
                it["urlsFixedNote"] = "668番:urls欄の『URL＋日本語説明の連結』記録ミスを機械修正（説明文を除去しクリーンなURLのみへ）"

        d["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        with open(QUEUE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
            f.write("\n")

    print("修正件数(URL単位)=%d" % len(fixed))
    for x in fixed:
        print("n=%s" % x["n"])
        print("  before: %s" % x["before"])
        print("  after : %s" % x["after"])


if __name__ == "__main__":
    main()
