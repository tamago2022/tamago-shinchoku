#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完了・取消したものを1週間で片づけて、あとから辿れる場所へ移す。

2026-09-05 たまごさんの言葉：
  「**完了も1週間経ったら自動で消えるようにしといて。だけどその後でたどれるようにしといて。**
   完了も溜まってきて長くなると探せなくなるから。たどることはほぼほぼないんだけど、
   一応そこもスッキリしたいので。」

やること:
  1. status/queue.json の done・cancelled のうち、判定から7日以上たったものを取り出す
  2. status/done_archive.json に足す（消さない・ここが「あとから辿れる場所」）
  3. share/done/index.html を作り直す（スマホで開ける一覧。新しい順）
  4. queue.json からは外す（進捗表の完了欄が短く保たれる）

【2026-09-10 716番で発見】この処理は元々 cancelled を見ておらず、queue.jsonが
390件・1.8MBまで肥大化していた。進捗表(index.html)は10秒おきにqueue.jsonを
丸ごと取り直して再描画するため、これが「進捗表のタブがずっとぐるぐる回る」
「パソコンが重い」の実測できた原因の1つだった。かつ、この片づけ自体が
launchdに登録されておらず一度も自動実行されていなかった（tools/tamago_maintenance.py
の日次点検から呼ぶように変更・今後は毎日自動で片づく）。

台帳を触るので、心臓・中継所と同じ鍵をかける。
"""
import fcntl
import io
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
QUEUE = os.path.join(REPO, "status", "queue.json")
ARCHIVE = os.path.join(REPO, "status", "done_archive.json")
PAGE_DIR = os.path.join(REPO, "share", "done")
PAGE = os.path.join(PAGE_DIR, "index.html")
LOCK = os.path.join(REPO, "status", ".queue.lock")
KEEP_DAYS = 7


@contextmanager
def queue_lock(timeout=10.0):
    f = io.open(LOCK, "a+")
    t0 = time.time()
    while True:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except Exception:
            if time.time() - t0 > timeout:
                break
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


def load(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def save(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    json.dump(d, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def when(it):
    for k in ("checkedAt", "finishedAt", "startedAt"):
        v = it.get(k)
        if not v:
            continue
        s = str(v)[:19].replace("T", " ")
        for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(s, f)
            except Exception:
                pass
    return None


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def write_page(items):
    os.makedirs(PAGE_DIR, exist_ok=True)
    rows = []
    for it in sorted(items, key=lambda x: str(x.get("checkedAt") or ""), reverse=True):
        d = str(it.get("checkedAt") or it.get("finishedAt") or "")[:16].replace("T", " ")
        urls = "".join('<a href="%s" target="_blank" rel="noopener">%s</a>' % (esc(u), esc(u))
                       for u in (it.get("urls") or []))
        note = esc(it.get("checkNote") or "")
        rows.append(
            '<div class="r"><div class="t">#%s %s</div>'
            '<div class="d">%s%s</div>%s</div>'
            % (esc(it.get("n")), esc(it.get("title")), esc(d),
               ("・" + note) if note else "", urls))
    html = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>完了のひかえ</title>
<style>
:root{--bg:#12161c;--fg:#e9eef4;--sub:#a9b6c4;--line:#2a323c;--green:#5fd996}
body{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif;padding:22px 16px 60px;line-height:1.65}
h1{font-size:1.15rem;margin:0 0 4px}.sub{color:var(--sub);font-size:0.8rem;margin-bottom:14px}
.r{border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:8px 0;background:#161c24}
.t{font-weight:700;font-size:0.95rem}.d{color:var(--sub);font-size:0.76rem;margin-top:2px}
a{display:block;color:var(--green);font-size:0.76rem;margin-top:6px;word-break:break-all}
.back{color:var(--green);font-size:0.85rem;display:inline-block;margin-top:18px}
</style></head><body>
<h1>完了のひかえ</h1>
<div class="sub">1週間より前に完了したもの・%d件（新しい順）。進捗表の完了欄はここへ移して短く保っています。</div>
%s
<a class="back" href="https://tamago2022.github.io/tamago-shinchoku/">← 進捗表にもどる</a>
</body></html>""" % (len(items), "\n".join(rows) or '<div class="sub">まだありません。</div>')
    tmp = PAGE + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(html)
    os.replace(tmp, PAGE)


def main():
    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
    with queue_lock():
        q = load(QUEUE, {})
        items = q.get("items") or []
        keep, moved = [], []
        for it in items:
            # 2026-09-10 716番で発見：ここは元々 status=="done" しか見ておらず、
            # cancelled(95件)が永久にqueue.jsonへ居座っていた（1.8MBに肥大化し、
            # 進捗表が10秒おきにこれを丸ごと取り直して描き直す原因になっていた）。
            # cancelledも同じ扱いで片づける。タイムスタンプが無いもの(壊れた記録)は
            # 判定しようがないので即座に片づけて良い(消すのではなくアーカイブへ移すだけ)。
            if it.get("status") in ("done", "cancelled"):
                t = when(it)
                if t is None or t < cutoff:
                    moved.append(it)
                    continue
            keep.append(it)
        arch = load(ARCHIVE, {"items": []})
        have = {x.get("n") for x in arch.get("items", [])}
        for it in moved:
            if it.get("n") not in have:
                arch.setdefault("items", []).append(it)
        arch["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
        if moved:
            q["items"] = keep
            q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
            save(QUEUE, q)
            save(ARCHIVE, arch)
            print("完了を%d件、ひかえへ移しました" % len(moved))
    write_page(load(ARCHIVE, {"items": []}).get("items", []))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
