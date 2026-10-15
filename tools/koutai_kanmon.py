#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""101885番【サイトを後退させない関所】重さと見た目が「前より悪くなる変更」を、出す前に機械で止める。

たまごさん（2026-10-15 19時）：
  「軽くした・90点にしたサイトが、次の変更で重くなったり見た目が崩れたりして戻るのを、出す前に機械で止める。」

物差し（status/public/koutai_kijun.json に控える）
  ・1ページ目の時間  … LCP（4G相当・headless shell）  ★基準より +10% 超で止める
  ・送る量          … JS/CSS/データ/画像…のKB合計    ★基準より +5% 超で止める
  ・見た目の点数    … design-critique 5観点のうち機械で測れる4観点の合計（40点満点）★1点でも下がれば止める
                       創造性は機械で測れないので null のまま控える（測ったふりをしない）
  対象4ページ：トップ／棚／曲ページ／マガジン。良くなった時だけ基準値を更新する。

使い方
  python3 tools/koutai_kanmon.py --jissoku --target prod            本番を測って status/koutai_last_prod.json に書く（判定しない）
  python3 tools/koutai_kanmon.py --kijun   --target prod            いまの測定を基準値にする（基準が無い時・良くなった時だけ。--force で強制）
  python3 tools/koutai_kanmon.py --check   --target prod            測って基準と比べる。悪化なら exit 2 ＋「何が増えたか」1行
  python3 tools/koutai_kanmon.py --check   --dist <distフォルダ>     ビルド成果物をローカル配信して測る（main合流前の口）
  python3 tools/koutai_kanmon.py --check-files a.html b.html ...     静的ファイルの送る量だけ比べる（マガジン put_prod.sh の口・ブラウザ不要）
  python3 tools/koutai_kanmon.py --pre-publish                       直近のローカル検査が FAIL なら公開を止める（kohyou_osu の口）
  python3 tools/koutai_kanmon.py --after-publish                     公開後に本番を測る。悪化なら作業キューと Dispatch へ票（kohyou_kanshi の口）
  python3 tools/koutai_kanmon.py --self-test                         ブラウザ無しで判定の逆テスト（悪化で止まる・通常は通る・良化で基準更新）

倣ったもの：tools/perf_watch.mjs（+10%で赤）／tools/omosa_mihari.py（+5%で赤・1か所にしか線を書かない）／
          tools/main_kanmon.py（通った/弾いたを台帳に残す・exitで止める）。オリジナル禁止票 hyo-1792079434。
安全：GETだけ・課金0・外部AIを呼ばない・たまごさんのChrome/Braveに触らない・音を鳴らさない。
"""
from __future__ import annotations

import argparse
import glob
import http.server
import io
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
PUB = os.path.join(ST, "public")
KIJUN = os.path.join(PUB, "koutai_kijun.json")
LATEST_PUB = os.path.join(PUB, "koutai_kanmon.json")
DAICHO = os.path.join(ST, "koutai_kanmon_daicho.jsonl")
LOG = os.path.join(ST, "koutai_log.jsonl")
SOKUTEI = os.path.join(HERE, "koutai_sokutei.mjs")
SAGYOU_QUEUE = os.path.join(ST, "vault_soto", "作業キュー.md")
OUTBOX = os.path.join(ST, "dispatch_outbox.jsonl")
JOY = "/Users/mac/Desktop/joy-relief-station"

PROD_BASE = "https://joy-relief-station.lovable.app"
# ★線はここ1か所にしか書かない（omosa_mihari.py と同じ思想）
SEN = {"time_pct": 10.0, "bytes_pct": 5.0, "score_drop": 1, "load_per_cpu": 0.8}
# ★時間はMacの混雑で何倍にもゆれる（2026-10-16 実測：別セッションの vite build 中に本番が +13〜156%）。
#   1分平均の負荷が CPU数×load_per_cpu を超えている時は、時間を判定から外し「混雑のため時間は参考値」と記録する。送る量・見た目は混雑に左右されないので常に判定する。
PAGE_PATHS = [
    ("top", "/"),
    ("shelf", "/shelf/music/covers"),
    ("song", "/cover-guide?artist=akiko&song=love-theme-from-spartacus"),
    ("magazine", "/magazine/rei-harakami.html"),
]


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _load(path, default):
    if not os.path.exists(path):
        return default
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _append(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    # 台帳（status/ は非公開）の控えを、公開側 status/public/koutai_kanmon.json の rireki（直近40件）にも残す
    if path == DAICHO:
        try:
            cur = _load(LATEST_PUB, {})
            cur.setdefault("rireki", []).append(obj)
            cur["rireki"] = cur["rireki"][-40:]
            _write(LATEST_PUB, cur)
        except Exception:
            pass


def _joy_sha():
    try:
        return subprocess.check_output(["git", "-C", JOY, "rev-parse", "--short", "origin/main"], text=True, timeout=10).strip()
    except Exception:
        return ""


# ────────────────────────────────────────────────────────────
# 測る（測る係 koutai_sokutei.mjs を呼ぶだけ。判定しない）
# ────────────────────────────────────────────────────────────
def sokutei(base, runs=2, throttle="fast4g", width=375, label="prod", keys=None):
    pages = [{"key": k, "url": base.rstrip("/") + p} for k, p in PAGE_PATHS if not keys or k in keys]
    tmpd = os.path.join(ST, "tmp")
    os.makedirs(tmpd, exist_ok=True)
    pf = os.path.join(tmpd, "koutai_pages_%s.json" % label)
    of = os.path.join(tmpd, "koutai_result_%s.json" % label)
    with io.open(pf, "w", encoding="utf-8") as f:
        json.dump(pages, f)
    cmd = ["node", SOKUTEI, "--pages", pf, "--out", of, "--runs", str(runs), "--throttle", throttle, "--width", str(width)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1500)
    if r.returncode != 0 or not os.path.exists(of):
        raise RuntimeError("測る係が失敗: rc=%s %s" % (r.returncode, (r.stderr or "")[-600:]))
    res = _load(of, {})
    res["target"] = label
    res["base"] = base
    try:
        os.remove(pf)
        os.remove(of)
    except Exception:
        pass
    return res


def summary_of(res):
    """測定結果 → 比べるための小さな形（ページごとに time/bytes/score）。"""
    out = {}
    for p in res.get("pages", []):
        sc = p.get("scores") or {}
        out[p["key"]] = {
            "url": p.get("url"),
            "status": p.get("status"),
            "firstPageMs": p.get("firstPageMs"),
            "totalBytes": (p.get("ownBytes") or p.get("bytes") or {}).get("total", 0),   # ★自分のサイトから送る量（YouTube等の外部は毎回ゆれるので入れない）
            "allBytes": (p.get("bytes") or {}).get("total", 0),
            "kb": p.get("ownKb") or p.get("kb") or {},
            "score": sc.get("kikai_gokei"),
            "scores": sc,
            "top": p.get("top") or [],
            "navErr": p.get("navErr") or "",
        }
    return out


# ────────────────────────────────────────────────────────────
# ★関所そのもの：基準と比べて、通すか止めるか（ここだけが判定を書く）
# ────────────────────────────────────────────────────────────
def mac_konzatsu():
    """Macが混んでいるか（1分平均負荷 / CPU数）。返り値 (konzatsu: bool, load1: float, ncpu: int)"""
    try:
        load1 = os.getloadavg()[0]
        ncpu = os.cpu_count() or 1
        return load1 > ncpu * SEN["load_per_cpu"], round(load1, 1), ncpu
    except Exception:
        return False, 0.0, 0


def hikaku(kijun: dict, ima: dict, sen=SEN, time_ok=True):
    """kijun/ima は summary_of の形。戻り値 dict(tooru, riyuu[], warui[], yoku_natta(bool), nani_fueta(str))"""
    riyuu, warui, better_any, worse_any = [], [], False, False
    fueta = []
    for key, k in kijun.items():
        i = ima.get(key)
        if not i:
            riyuu.append("%s: 今回測れていない" % key)
            worse_any = True
            warui.append(key)
            continue
        if i.get("status") and i["status"] >= 400:
            riyuu.append("%s: HTTP %s" % (key, i["status"]))
            worse_any = True
            warui.append(key)
            continue
        # 時間
        kt, it = k.get("firstPageMs"), i.get("firstPageMs")
        if not time_ok:
            pass  # 混雑中：時間は判定しない（riyuu には呼び元が注記を足す）
        elif kt and it:
            pct = (it - kt) * 100.0 / kt
            if pct > sen["time_pct"]:
                riyuu.append("%s: 1ページ目 %dms→%dms（+%.0f%%）" % (key, kt, it, pct))
                worse_any = True
                warui.append(key)
            elif pct < -sen["time_pct"] / 2:
                better_any = True
        elif kt and not it and time_ok:
            riyuu.append("%s: 1ページ目の時間が取れていない" % key)
            worse_any = True
            warui.append(key)
        # 送る量
        kb_, ib = k.get("totalBytes") or 0, i.get("totalBytes") or 0
        if kb_ and ib:
            pct = (ib - kb_) * 100.0 / kb_
            if pct > sen["bytes_pct"]:
                riyuu.append("%s: 送る量 %dKB→%dKB（+%.0f%%）" % (key, kb_ // 1024, ib // 1024, pct))
                worse_any = True
                warui.append(key)
                fueta.append((key, _nani_fueta(k, i)))
            elif pct < -sen["bytes_pct"] / 2:
                better_any = True
        # 見た目の点数（機械4観点の合計）
        ks, is_ = k.get("score"), i.get("score")
        if ks is not None and is_ is not None:
            if ks - is_ >= sen["score_drop"]:
                ochita = [n for n in ("ikkansei", "kaisou", "saibu", "kinou")
                          if (k.get("scores") or {}).get(n) is not None and (i.get("scores") or {}).get(n) is not None
                          and (i["scores"][n] < k["scores"][n])]
                riyuu.append("%s: 見た目 %d→%d点（下がった観点: %s）" % (key, ks, is_, ",".join(ochita) or "?"))
                worse_any = True
                warui.append(key)
            elif is_ > ks:
                better_any = True
    tooru = not worse_any
    nani = "；".join("%s=%s" % (k, s) for k, s in fueta) if fueta else ""
    return {"tooru": tooru, "riyuu": riyuu, "warui": sorted(set(warui)), "yoku_natta": tooru and better_any, "nani_fueta": nani}


def _nani_fueta(k, i):
    """何が増えたかを1行で。種類別KBの差が一番大きいものと、新しく増えた/太った資源の名前。"""
    kk, ik = k.get("kb") or {}, i.get("kb") or {}
    diffs = sorted(((ik.get(n, 0) - kk.get(n, 0)), n) for n in set(kk) | set(ik) if n != "total")
    kind = "%s +%dKB" % (diffs[-1][1], diffs[-1][0]) if diffs and diffs[-1][0] > 0 else ""
    before = {t["name"]: t["kb"] for t in (k.get("top") or [])}
    grown = sorted(((t["kb"] - before.get(t["name"], 0)), t["name"]) for t in (i.get("top") or []))
    who = "%s(+%dKB)" % (grown[-1][1], grown[-1][0]) if grown and grown[-1][0] > 0 else ""
    return " ".join(x for x in (kind, who) if x) or "種類別では特定できず"


# ────────────────────────────────────────────────────────────
# 基準値の読み書き
# ────────────────────────────────────────────────────────────
def load_kijun():
    return _load(KIJUN, {"_": "101885番 サイトを後退させない関所の基準値。良くなった時だけ更新。線: 時間+10%・送る量+5%・点数低下", "sen": SEN, "targets": {}, "files": {}})


def save_kijun(kj, target, summ, res, riyuu):
    kj.setdefault("targets", {})[target] = {
        "setAt": now(), "riyuu": riyuu, "throttle": res.get("throttle"), "width": res.get("width"),
        "joyMainSha": _joy_sha(), "pages": summ,
    }
    kj["sen"] = SEN
    _write(KIJUN, kj)


def ima_kijun_update_ok(kj, target, summ):
    """基準が無い → 控えてよい。基準がある → hikaku が『良くなった』と言う時だけ。"""
    t = (kj.get("targets") or {}).get(target)
    if not t:
        return True, "基準が無かったので初回として控える"
    h = hikaku(t["pages"], summ)
    if h["yoku_natta"]:
        return True, "良くなったので更新"
    return False, "良くなっていない（悪化=%s）" % ("あり" if not h["tooru"] else "なし")


# ────────────────────────────────────────────────────────────
# dist をローカル配信（SPAなので、拡張子の無いパスは index.html へ）
# ────────────────────────────────────────────────────────────
class _SpaHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def translate_path(self, path):
        p = super().translate_path(path)
        clean = path.split("?", 1)[0]
        if not os.path.exists(p) and not os.path.splitext(clean)[1]:
            return os.path.join(self.directory, "index.html")
        return p


def serve_dist(dist):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    handler = lambda *a, **kw: _SpaHandler(*a, directory=dist, **kw)  # noqa: E731
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    httpd.daemon_threads = True
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    return httpd, "http://127.0.0.1:%d" % port


def serve_output(server_mjs):
    """TanStack Start/Nitro のビルド成果物（.output/server/index.mjs）を空きポートで起こす。使い終わったら呼び元が kill する。"""
    import urllib.request
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    env = dict(os.environ, PORT=str(port), HOST="127.0.0.1", NITRO_PORT=str(port), NITRO_HOST="127.0.0.1", NODE_ENV="production")
    logf = io.open(os.path.join(ST, "koutai_local_server.log"), "a", encoding="utf-8")
    proc = subprocess.Popen(["node", server_mjs], env=env, stdout=logf, stderr=subprocess.STDOUT, cwd=os.path.dirname(os.path.dirname(os.path.dirname(server_mjs))))
    base = "http://127.0.0.1:%d" % port
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/", timeout=3).read(64)
            return proc, base
        except Exception:
            if proc.poll() is not None:
                raise RuntimeError("ローカルサーバが落ちた（status/koutai_local_server.log）")
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("ローカルサーバが30秒で起きなかった")


# ────────────────────────────────────────────────────────────
# 入口ごとの処理
# ────────────────────────────────────────────────────────────
def do_check(target, base, runs, kijun_only=False, force=False, dist_label=None, after_publish=False, from_last=False):
    last = os.path.join(ST, "koutai_last_%s.json" % target)
    if kijun_only and from_last and os.path.exists(last):
        res = _load(last, {})
    else:
        res = sokutei(base, runs=runs, label=target)
    summ = summary_of(res)
    _append(LOG, {"ts": now(), "target": target, "base": base, "pages": {k: {"ms": v["firstPageMs"], "kb": v["kb"].get("total"), "score": v["score"], "status": v["status"]} for k, v in summ.items()}})
    kj = load_kijun()
    if kijun_only:
        ok, why = (True, "--force") if force else ima_kijun_update_ok(kj, target, summ)
        if ok:
            save_kijun(kj, target, summ, res, why)
            print("KOUTAI_KIJUN: 控えました（%s）→ %s" % (why, KIJUN))
            _publish_latest(target, summ, {"tooru": True, "riyuu": [], "warui": [], "yoku_natta": False, "nani_fueta": ""}, kijun=kj["targets"][target], note="基準値を控えた")
            return 0
        print("KOUTAI_KIJUN: 更新しません（%s）" % why)
        return 1
    konzatsu, load1, ncpu = mac_konzatsu()
    time_ok = not konzatsu
    t = (kj.get("targets") or {}).get(target)
    if not t:
        save_kijun(kj, target, summ, res, "基準が無かったので初回として控える")
        rec = {"ts": now(), "target": target, "base": base, "result": "PASS", "riyuu": ["基準が無かったので今回を基準にした"], "joyMainSha": _joy_sha()}
        _append(DAICHO, rec)
        print("KOUTAI_KANMON_RESULT: PASS（基準が無かったので今回を基準として控えました）")
        return 0
    h = hikaku(t["pages"], summ, time_ok=time_ok)
    if not h["tooru"] and h["warui"]:
        # ★確かめ直し：落ちたページだけもう1回測り、良い方の回を採ってから決める（Lighthouse流・たまたまで止めない）
        try:
            res2 = sokutei(base, runs=1, label=target + "-saikakunin", keys=h["warui"])
            s2 = summary_of(res2)
            for k, v in s2.items():
                cur = summ.get(k)
                if not cur or (v["firstPageMs"] or 10**9) < (cur["firstPageMs"] or 10**9):
                    if cur:
                        v["totalBytes"] = max(v["totalBytes"] or 0, cur["totalBytes"] or 0)
                        v["score"] = max(v["score"] or 0, cur["score"] or 0) if (v["score"] is not None and cur["score"] is not None) else (v["score"] if v["score"] is not None else cur["score"])
                    summ[k] = v
                elif cur:
                    cur["totalBytes"] = max(v["totalBytes"] or 0, cur["totalBytes"] or 0)
                    if v["score"] is not None and cur["score"] is not None:
                        cur["score"] = max(v["score"], cur["score"])
            h = hikaku(t["pages"], summ, time_ok=time_ok)
            h["saikakunin"] = True
        except Exception as e:
            h["riyuu"].append("確かめ直しに失敗: %s" % str(e)[:120])
    if not time_ok:
        h["riyuu"].append("Macが混雑（負荷%.1f/CPU%d）のため時間は参考値・判定から外した" % (load1, ncpu))
    rec = {"ts": now(), "target": target, "base": base, "result": "PASS" if h["tooru"] else "FAIL", "riyuu": h["riyuu"],
           "nani_fueta": h["nani_fueta"], "joyMainSha": _joy_sha(), "kijunSetAt": t.get("setAt"), "load1": load1, "timeJudged": time_ok,
           "pages": {k: {"ms": v["firstPageMs"], "kb": v["kb"].get("total"), "score": v["score"]} for k, v in summ.items()}}
    _append(DAICHO, rec)
    if h["tooru"] and h["yoku_natta"]:
        save_kijun(kj, target, summ, res, "良くなったので更新")
        rec["kijunUpdated"] = True
    _publish_latest(target, summ, h, kijun=t)
    if h["tooru"]:
        print("KOUTAI_KANMON_RESULT: PASS%s" % ("（良くなったので基準値を更新）" if h["yoku_natta"] else ""))
        return 0
    line = "KOUTAI_KANMON_RESULT: FAIL ｜ 止めました：%s%s" % ("／".join(h["riyuu"]), ("｜増えたもの→" + h["nani_fueta"]) if h["nani_fueta"] else "")
    print(line)
    if after_publish:
        _hyou(line, target)
    return 2


def _publish_latest(target, summ, h, kijun=None, note=""):
    cur = _load(LATEST_PUB, {})
    cur["_"] = "101885番 後退させない関所の最新判定（進捗表から見える）"
    cur.setdefault("targets", {})[target] = {
        "at": now(), "result": "PASS" if h["tooru"] else "FAIL", "riyuu": h["riyuu"], "nani_fueta": h["nani_fueta"], "note": note,
        "pages": {k: {"ms": v["firstPageMs"], "kb": v["kb"].get("total"), "score": v["score"],
                      "kijun_ms": ((kijun or {}).get("pages") or {}).get(k, {}).get("firstPageMs"),
                      "kijun_kb": (((kijun or {}).get("pages") or {}).get(k, {}).get("totalBytes") or 0) // 1024 or None,
                      "kijun_score": ((kijun or {}).get("pages") or {}).get(k, {}).get("score")} for k, v in summ.items()},
    }
    _write(LATEST_PUB, cur)


def _hyou(line, target):
    """公開後に悪化していたら、作業キューと Dispatch へ票を1行ずつ。直さない（直すのは人か別の便）。"""
    try:
        with io.open(SAGYOU_QUEUE, "a", encoding="utf-8") as f:
            f.write("\n| %s | 【後退関所の票・%s】本番が基準より悪化。%s | 🔴 |\n" % (time.strftime("%Y-%m-%d"), target, line.replace("KOUTAI_KANMON_RESULT: FAIL ｜ ", "")[:300]))
    except Exception:
        pass
    _append(OUTBOX, {"ts": now(), "n": "101885-koutai", "title": "後退関所：本番が基準より悪化", "ok": False, "urls": [PROD_BASE + "/"], "result": line[:400]})


def do_check_files(files):
    kj = load_kijun()
    fk = kj.setdefault("files", {})
    bad, changed = [], False
    for f in files:
        if not os.path.exists(f):
            continue
        name = os.path.basename(f)
        size = os.path.getsize(f)
        prev = fk.get(name)
        if prev and prev.get("bytes"):
            pct = (size - prev["bytes"]) * 100.0 / prev["bytes"]
            if pct > SEN["bytes_pct"]:
                bad.append("%s %dKB→%dKB（+%.0f%%）" % (name, prev["bytes"] // 1024, size // 1024, pct))
                continue
            if size < prev["bytes"]:
                fk[name] = {"bytes": size, "setAt": now()}
                changed = True
        else:
            fk[name] = {"bytes": size, "setAt": now()}
            changed = True
    if changed:
        _write(KIJUN, kj)
    rec = {"ts": now(), "target": "files", "result": "FAIL" if bad else "PASS", "riyuu": bad, "files": [os.path.basename(f) for f in files]}
    _append(DAICHO, rec)
    if bad:
        print("KOUTAI_KANMON_RESULT: FAIL ｜ 止めました：送る量が増えた → " + "／".join(bad))
        return 2
    print("KOUTAI_KANMON_RESULT: PASS（%d件、送る量は基準以内）" % len(files))
    return 0


def do_pre_publish():
    """直近のローカル(dist)検査が FAIL で、それが今の main と同じ sha なら公開を止める。記録が無ければ通す（人質にしない）。"""
    sha = _joy_sha()
    last = None
    if os.path.exists(DAICHO):
        with io.open(DAICHO, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("target") == "local":
                    last = r
    if last and last.get("result") == "FAIL" and sha and last.get("joyMainSha") == sha:
        print("KOUTAI_KANMON_RESULT: FAIL ｜ 公開を止めました：main %s のローカル検査が後退（%s）" % (sha, "／".join(last.get("riyuu") or [])))
        return 2
    print("KOUTAI_KANMON_RESULT: PASS（直近のローカル検査=%s, main=%s）" % ((last or {}).get("result", "記録なし"), sha or "?"))
    return 0


# ────────────────────────────────────────────────────────────
# 逆テスト（ブラウザ無し）
# ────────────────────────────────────────────────────────────
def self_test():
    import copy
    import tempfile
    base = {"top": {"status": 200, "firstPageMs": 2000, "totalBytes": 400 * 1024, "kb": {"total": 400, "JS": 300, "CSS": 40, "HTML": 30, "画像": 30},
                    "score": 36, "scores": {"ikkansei": 10, "kaisou": 9, "saibu": 9, "kinou": 8, "souzousei": None},
                    "top": [{"name": "site/assets/index.js", "kind": "JS", "kb": 280}]}}
    fails = []

    def case(name, cond):
        print(("  OK  " if cond else "  NG  ") + name)
        if not cond:
            fails.append(name)

    same = copy.deepcopy(base)
    h = hikaku(base, same)
    case("同じ数字なら通る", h["tooru"] and not h["yoku_natta"])
    t = copy.deepcopy(base); t["top"]["firstPageMs"] = 2250
    case("時間 +12.5% は止める", not hikaku(base, t)["tooru"])
    t = copy.deepcopy(base); t["top"]["firstPageMs"] = 2180
    case("時間 +9% は通す", hikaku(base, t)["tooru"])
    t = copy.deepcopy(base); t["top"]["totalBytes"] = int(400 * 1024 * 1.06); t["top"]["kb"] = {"total": 424, "JS": 324, "CSS": 40, "HTML": 30, "画像": 30}
    t["top"]["top"] = [{"name": "site/assets/index.js", "kind": "JS", "kb": 280}, {"name": "site/assets/omoi.js", "kind": "JS", "kb": 24}]
    h = hikaku(base, t)
    case("送る量 +6% は止める", not h["tooru"])
    case("何が増えたかを1行で出す（JS +24KB / omoi.js）", "JS +24KB" in h["nani_fueta"] and "omoi.js" in h["nani_fueta"])
    t = copy.deepcopy(base); t["top"]["totalBytes"] = int(400 * 1024 * 1.04)
    case("送る量 +4% は通す", hikaku(base, t)["tooru"])
    t = copy.deepcopy(base); t["top"]["score"] = 35; t["top"]["scores"] = dict(base["top"]["scores"], kinou=7)
    h = hikaku(base, t)
    case("見た目 1点低下は止める（観点名つき）", not h["tooru"] and "kinou" in "".join(h["riyuu"]))
    t = copy.deepcopy(base); t["top"]["firstPageMs"] = 1700; t["top"]["totalBytes"] = 380 * 1024
    h = hikaku(base, t)
    case("良くなった時だけ『基準更新』の印が立つ", h["tooru"] and h["yoku_natta"])
    t = copy.deepcopy(base); t["top"]["firstPageMs"] = 5000
    case("Mac混雑中（time_ok=False）は時間+150%でも止めない（送る量・見た目は判定）", hikaku(base, t, time_ok=False)["tooru"])
    t = copy.deepcopy(base); t["top"]["firstPageMs"] = 5000; t["top"]["totalBytes"] = int(400 * 1024 * 1.06)
    case("Mac混雑中でも送る量+6%は止める", not hikaku(base, t, time_ok=False)["tooru"])
    t = copy.deepcopy(base); t["top"]["status"] = 500
    case("HTTP 500 は止める", not hikaku(base, t)["tooru"])
    case("測れていないページは止める", not hikaku(base, {})["tooru"])
    # --check-files の逆テスト（本物の基準値ファイルは触らない）
    global KIJUN, DAICHO
    kj_bak, dc_bak = KIJUN, DAICHO
    with tempfile.TemporaryDirectory() as d:
        KIJUN = os.path.join(d, "kijun.json"); DAICHO = os.path.join(d, "daicho.jsonl")
        f1 = os.path.join(d, "mag.html")
        with open(f1, "wb") as f: f.write(b"x" * 100000)
        case("ファイル初回は控えて通す", do_check_files([f1]) == 0)
        with open(f1, "wb") as f: f.write(b"x" * 110000)
        case("ファイル +10% は止める", do_check_files([f1]) == 2)
        with open(f1, "wb") as f: f.write(b"x" * 90000)
        case("ファイルが小さくなれば通して基準更新", do_check_files([f1]) == 0 and _load(KIJUN, {})["files"]["mag.html"]["bytes"] == 90000)
        with open(f1, "wb") as f: f.write(b"x" * 93000)
        case("更新後の基準(90000)に対し +3.3% は通す", do_check_files([f1]) == 0)
        # dist 配信：拡張子無しは index.html へ
        os.makedirs(os.path.join(d, "dist"), exist_ok=True)
        with open(os.path.join(d, "dist", "index.html"), "w") as f: f.write("<h1>ok</h1>")
        httpd, url = serve_dist(os.path.join(d, "dist"))
        try:
            import urllib.request
            body = urllib.request.urlopen(url + "/shelf/music/covers", timeout=5).read().decode()
            case("dist配信：SPAのパスが index.html に落ちる", "ok" in body)
        finally:
            httpd.shutdown()
    KIJUN, DAICHO = kj_bak, dc_bak
    case("測る係の構文が通る", subprocess.run(["node", "--check", SOKUTEI], capture_output=True).returncode == 0)
    print("KOUTAI_SELF_TEST: %s（%d件中 %d件NG）" % ("PASS" if not fails else "FAIL", 18, len(fails)))
    return 0 if not fails else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--jissoku", action="store_true")
    g.add_argument("--kijun", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--check-files", nargs="+", metavar="FILE")
    g.add_argument("--pre-publish", action="store_true")
    g.add_argument("--after-publish", action="store_true")
    g.add_argument("--self-test", action="store_true")
    ap.add_argument("--target", default="prod", help="prod（本番）／local（--dist と一緒）／任意の名前")
    ap.add_argument("--base", default="", help="測る先のURL（省略時 prod は本番、--dist 時はローカル配信）")
    ap.add_argument("--dist", default="", help="ビルド成果物フォルダ。ローカル配信して測る")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--from-last", action="store_true", help="--kijun の時、直前の --jissoku の結果（status/koutai_last_<target>.json）から控える")
    ap.add_argument("--output", default="", help="TanStack Start のビルド成果物 .output（server/index.mjs をローカル起動して測る）")
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if a.check_files:
        files = []
        for f in a.check_files:
            files += glob.glob(f) or [f]
        return do_check_files(files)
    if a.pre_publish:
        return do_pre_publish()
    if a.after_publish:
        return do_check("prod", PROD_BASE, a.runs, after_publish=True)

    httpd = None
    proc = None
    target, base = a.target, a.base
    if a.output:
        srv = os.path.join(os.path.abspath(a.output), "server", "index.mjs")
        if not os.path.exists(srv):
            print("KOUTAI_KANMON_RESULT: FAIL ｜ .output/server/index.mjs が無い: %s" % a.output)
            return 2
        proc, base = serve_output(srv)
        target = a.target if a.target != "prod" else "local"
    elif a.dist:
        if not os.path.isdir(a.dist) or not os.path.exists(os.path.join(a.dist, "index.html")):
            print("KOUTAI_KANMON_RESULT: FAIL ｜ dist に index.html が無い: %s" % a.dist)
            return 2
        httpd, base = serve_dist(os.path.abspath(a.dist))
        target = a.target if a.target != "prod" else "local"
    elif not base:
        base = PROD_BASE
    try:
        if a.jissoku:
            res = sokutei(base, runs=a.runs, label=target)
            summ = summary_of(res)
            out = os.path.join(ST, "koutai_last_%s.json" % target)
            _write(out, res)
            for k, v in summ.items():
                print("%-8s status=%s 1ページ目=%sms 送る量=%sKB 見た目=%s/40 %s" % (k, v["status"], v["firstPageMs"], v["kb"].get("total"), v["score"], v["navErr"]))
            print("→", out)
            return 0
        return do_check(target, base, a.runs, kijun_only=a.kijun, force=a.force, from_last=a.from_last)
    finally:
        if httpd:
            httpd.shutdown()
        if proc:
            try:
                proc.kill()
                proc.wait(timeout=10)
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
