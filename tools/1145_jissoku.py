#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1145番【実測】全YouTube動画IDを1本ずつ oEmbed で叩いて、本当に再生できるか確かめる。

★工場（Mac）側で走る。サンドボックス（Cowork）からは youtube.com に出られない（実測000）。
★1本ごとに status/1145/oembed.jsonl へ追記する。まとめて書かない＝落ちても続きから。
★弾かれたら待って続ける。止まらない。
★「不明」を死亡に混ぜない。生きている動画を隠すのが一番の恥。

判定:
  200            alive            再生できる
  401            embedDenied      埋め込み禁止（ページ上では再生できない）
  403            forbidden        拒否（地域制限・年齢制限の疑い）
  404            gone             削除または非公開
  429/503        （死亡にしない）待って再試行。最後まで駄目なら unknown
  それ以外/失敗  unknown          隠さない。次回もう一度見る

使い方:
  python3 tools/1145_jissoku.py           # 未実測のぶんを全部
  python3 tools/1145_jissoku.py --limit N
  python3 tools/1145_jissoku.py --recheck # 最初からやり直す
"""
from __future__ import annotations
import io, json, os, random, sys, threading, time
import urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, "status", "1145")
IDS  = os.path.join(ROOT, "status", "1140", "all_video_ids.txt")
JSONL = os.path.join(OUT, "oembed.jsonl")
PROG  = os.path.join(OUT, "oembed_progress.json")
SUM   = os.path.join(OUT, "oembed_summary.json")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0 Safari/537.36")
WORKERS = 6
BASE_PAUSE = 0.12

_lock = threading.Lock()
_n = {"done": 0, "alive": 0, "ng": 0, "unknown": 0, "waited": 0}
_started = time.time()


def _emit(rec):
    line = json.dumps(rec, ensure_ascii=False)
    with _lock:
        with io.open(JSONL, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        _n["done"] += 1
        v = rec["v"]
        if v == "alive":
            _n["alive"] += 1
        elif v == "unknown":
            _n["unknown"] += 1
        else:
            _n["ng"] += 1
        if _n["done"] % 50 == 0:
            el = time.time() - _started
            json.dump({"時刻": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "この回で叩いた": _n["done"], "生きている": _n["alive"],
                       "再生できない": _n["ng"], "不明": _n["unknown"],
                       "待たされた回数": _n["waited"],
                       "秒": round(el, 1),
                       "本/分": round(_n["done"] / el * 60, 1) if el > 0 else 0},
                      io.open(PROG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _hit(vid):
    url = "https://www.youtube.com/oembed?" + urllib.parse.urlencode(
        {"url": "https://www.youtube.com/watch?v=" + vid, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "ja,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.getcode(), json.loads(r.read().decode("utf-8", "ignore"))


CODE2V = {401: "embedDenied", 403: "forbidden", 404: "gone", 400: "gone"}


def check(vid):
    """弾かれたら待って続ける。最大6回、指数で下がる。"""
    delay = 3.0
    last = None
    for attempt in range(6):
        try:
            code, d = _hit(vid)
            rec = {"id": vid, "v": "alive", "code": code,
                   "title": d.get("title", ""), "author": d.get("author_name", ""),
                   "t": int(time.time())}
            time.sleep(BASE_PAUSE + random.random() * 0.1)
            _emit(rec)
            return
        except urllib.error.HTTPError as e:
            if e.code in CODE2V:
                _emit({"id": vid, "v": CODE2V[e.code], "code": e.code, "t": int(time.time())})
                time.sleep(BASE_PAUSE)
                return
            last = "HTTP%d" % e.code
        except Exception as e:
            last = type(e).__name__
        # 429 / 5xx / 通信失敗 → 待って続ける
        with _lock:
            _n["waited"] += 1
        time.sleep(delay + random.random() * 2)
        delay = min(delay * 2, 90)
    _emit({"id": vid, "v": "unknown", "err": last, "t": int(time.time())})


def _already():
    seen = {}
    if not os.path.exists(JSONL):
        return seen
    for line in io.open(JSONL, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("id"):
            seen[r["id"]] = r
    return seen


def summarize():
    seen = _already()
    buckets = {}
    for r in seen.values():
        buckets.setdefault(r.get("v", "?"), []).append(r["id"])
    ids = [x.strip() for x in io.open(IDS, encoding="utf-8") if x.strip()]
    out = {"生成": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "動画IDの実数": len(ids),
           "実測した": len(seen),
           "未実測": len(ids) - len([v for v in ids if v in seen]),
           "生きている": len(buckets.get("alive", [])),
           "再生できない合計": sum(len(v) for k, v in buckets.items()
                                   if k not in ("alive", "unknown")),
           "型ごと": {k: len(v) for k, v in sorted(buckets.items())},
           "再生できないID": {k: sorted(v) for k, v in sorted(buckets.items())
                             if k not in ("alive", "unknown")},
           "不明ID": sorted(buckets.get("unknown", []))}
    json.dump(out, io.open(SUM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out


def main(limit=None, recheck=False):
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(IDS):
        print("all_video_ids.txt が無い", file=sys.stderr)
        return 1
    ids = [x.strip() for x in io.open(IDS, encoding="utf-8") if x.strip()]
    if recheck and os.path.exists(JSONL):
        os.rename(JSONL, JSONL + ".bak%d" % int(time.time()))
    seen = set() if recheck else set(_already())
    todo = [v for v in ids if v not in seen]
    if limit:
        todo = todo[:int(limit)]
    print("全%d本／実測済み%d本／これから%d本" % (len(ids), len(seen), len(todo)), flush=True)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(check, todo))
    out = summarize()
    print(json.dumps({k: v for k, v in out.items() if not k.endswith("ID")},
                     ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    lim = None
    if "--limit" in sys.argv:
        lim = sys.argv[sys.argv.index("--limit") + 1]
    if "--summary" in sys.argv:
        print(json.dumps({k: v for k, v in summarize().items() if not k.endswith("ID")},
                         ensure_ascii=False, indent=1))
        sys.exit(0)
    sys.exit(main(limit=lim, recheck="--recheck" in sys.argv))
