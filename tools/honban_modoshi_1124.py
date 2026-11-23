#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""11/08以降に「完了」になったのに、本番で中身を確かめられなかった便を、完了から外してやり直しの列の先頭へ戻す
（2026-11-24・ループエンジニアリング_現状と計画_1122／local_e6882fc9 の引き継ぎ）。

honban_kanmon.py は 11-22 から「これから done を付ける所」を守っている。これはその前に done になった分の後始末。

対象：okBy=ai-verifier-auto（AI検品PASS→自動完了）で、完了時刻（checkedAt）が 2026-11-08 以降の票。
     queue.json の done／完了 と、done_archive.json に移された分の両方。
     （awaiting_check は「店主の確認待ち」で完了ではないので対象外。ただし --tsuika N で個別に足せる）

判定は2つの方法で照合する：
  ①honban_kanmon.hantei()（本番URLを叩いて200・本文300字以上・「準備中」等が無い）
  ②URLの種類だけで数える（確認ページ以外のURLが1本も無い＝本番の証拠ゼロ）
  ①でNGのものを戻す。①が「測れない（None）」のものは戻さず、未確定として出す。

  python3 tools/honban_modoshi_1124.py --shirabe            # 読むだけ → status/honban_kanmon/modoshi_1124.json
  python3 tools/honban_modoshi_1124.py --modosu             # 戻す（台帳の鍵を取って差分で保存）
  python3 tools/honban_modoshi_1124.py --tsuika 35636 ...   # 対象に足す票
  python3 tools/honban_modoshi_1124.py --self-test
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import honban_kanmon as hk  # noqa: E402

QUEUE = os.path.join(REPO, "status", "queue.json")
ARCH = os.path.join(REPO, "status", "done_archive.json")
OUT = os.path.join(REPO, "status", "honban_kanmon", "modoshi_1124.json")
KARA = "2026-11-08"
KANRYO = ("done", "完了")


def _load(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def _t(it):
    return str(it.get("checkedAt") or it.get("doneAt") or it.get("okAt") or "")


def kouho(q_items, a_items, tsuika=()):
    out = []
    for src, L in (("queue", q_items), ("archive", a_items)):
        for it in L:
            n = it.get("n")
            if n in tsuika:
                out.append((src, it))
                continue
            if it.get("okBy") != "ai-verifier-auto" or _t(it)[:10] < KARA:
                continue
            if src == "queue" and it.get("status") not in KANRYO:
                continue
            out.append((src, it))
    return out


def katachi_dake(it):
    """②URLの種類だけ：確認ページ以外の本番URLが1本でもあるか。"""
    return any(not hk.KAKUNIN.search(u) for u in hk.urls_of(it))


def shirabe(tsuika=(), fetch=None):
    q = _load(QUEUE, {})
    a = _load(ARCH, {})
    rows = []
    for src, it in kouho(q.get("items") or [], a.get("items") or [], tsuika):
        res = hk.hantei(it, fetch=fetch)
        rows.append({"n": it.get("n"), "src": src, "status": it.get("status"), "kanryo": _t(it)[:16],
                     "title": str(it.get("title") or "")[:60], "ok": res.get("ok"), "naze": res.get("naze"),
                     "url": res.get("url"), "honbanUrlAri": katachi_dake(it)})
    ng = [r for r in rows if r["ok"] is False]
    d = {"at": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"), "kouho": len(rows), "ng": len(ng),
         "hakarenai": sum(1 for r in rows if r["ok"] is None),
         "ng_url_nashi": sum(1 for r in ng if not r["honbanUrlAri"]),
         "ng_honban_dame": sum(1 for r in ng if r["honbanUrlAri"]), "rows": rows}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
    return d


def modosu(d):
    """NGの票を waiting・urgent・order=0 にして列の先頭へ。archive の票は queue へ戻す。"""
    import queue_store
    ng = {r["n"]: r for r in d["rows"] if r["ok"] is False}
    if not ng:
        return []
    done = []
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S+0900")
    with queue_store.queue_lock():
        q = queue_store.load_queue()
        snap = queue_store.snapshot_items(q)
        have = {it.get("n"): it for it in q.get("items") or []}
        a = _load(ARCH, {})
        a_items = a.get("items") or []
        for it in a_items:
            if it.get("n") in ng and it.get("n") not in have:
                c = dict(it)
                q["items"].append(c)
                have[c.get("n")] = c
        for n, r in ng.items():
            it = have.get(n)
            if not it:
                continue
            it["honbanModoshi"] = {"at": stamp, "mae": it.get("status"), "kaisuu": int(it.get("hasshaKaisuu") or 0), "naze": r["naze"], "url": r.get("url")}
            it["status"] = "waiting"
            it["urgent"] = True
            it["urgentReason"] = "本番の関所で完了を外した（11-24）・やり直しの先頭"
            it["order"] = 0
            it["priority"] = 1
            it["checkedAt"] = stamp        # 759番ガード：完了報告より新しい正当な再オープン
            it.pop("okBy", None)
            it["what"] = (it.get("what") or "") + hk.modosu_bun({"naze": r["naze"]})
            done.append(n)
        queue_store.save_queue(q, snapshot=snap)
        # archive から外す（queue に戻した分だけ）
        a["items"] = [it for it in a_items if it.get("n") not in ng]
        tmp = ARCH + ".tmp"
        io.open(tmp, "w", encoding="utf-8").write(json.dumps(a, ensure_ascii=False))
        os.replace(tmp, ARCH)
    d["modoshita"] = done
    io.open(OUT, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
    return done


def _self_test():
    q = [{"n": 1, "status": "done", "okBy": "ai-verifier-auto", "checkedAt": "2026-11-10T00:00:00+0900",
          "urls": ["https://tamago2022.github.io/tamago-shinchoku/share/check/1.html"]},
         {"n": 2, "status": "done", "okBy": "ai-verifier-auto", "checkedAt": "2026-11-01T00:00:00+0900"},
         {"n": 3, "status": "awaiting_check", "okBy": "ai-verifier-auto", "checkedAt": "2026-11-10T00:00:00+0900"}]
    a = [{"n": 4, "status": "done", "okBy": "ai-verifier-auto", "checkedAt": "2026-11-12T00:00:00+0900"}]
    k = [it["n"] for _, it in kouho(q, a)]
    ok = k == [1, 4] and [it["n"] for _, it in kouho(q, a, (3,))] == [1, 3, 4]
    ok = ok and not katachi_dake(q[0]) and katachi_dake({"urls": ["https://joy-relief-station.lovable.app/x"]})
    print("SELF-TEST", "OK" if ok else "NG", k)
    return 0 if ok else 1


if __name__ == "__main__":
    av = sys.argv[1:]
    if "--self-test" in av:
        sys.exit(_self_test())
    tsuika = ()
    if "--tsuika" in av:
        tsuika = tuple(int(x) for x in av[av.index("--tsuika") + 1:] if x.isdigit())
    d = shirabe(tsuika)
    if "--modosu" in av:
        if d["hakarenai"] and not d["ng"]:
            print("回線が無く測れない → 戻さない")
        else:
            print("戻した:", modosu(d))
    print(json.dumps({k: v for k, v in d.items() if k != "rows"}, ensure_ascii=False))
    for r in d["rows"]:
        print(r["n"], r["src"], r["status"], r["ok"], r["naze"][:60], "|", r["title"][:30])
