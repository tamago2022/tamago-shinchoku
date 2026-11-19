#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""財布の関所（saifu_kanmon）— 有料APIは全部ここを通る。2026-10-15。

たまごさん（2026-10-15・原文）：
  「音声系の料金が飛び出てるかもしれない。10ドルどころか72ドルと書いてあった。
    AI が何百回も叩いて、本当に請求が来たらマジでやばい。払うのは俺。マジで気をつけて」

━━ この1本でやること ━━
  ① 停止札（status/saifu_teishi.json）。札があれば有料APIは1回も通さない（全財布）。
       止める：python3 tools/saifu_kanmon.py --teishi "理由"
       戻す  ：python3 tools/saifu_kanmon.py --kaijo        ← 一言で元に戻る
  ② 財布ごとの上限（status/saifu_kanmon.json）
       nichi_yen    … 1日に使ってよい円
       ikkai_yen    … 1回の作業（1回の見積り）の上限円
       nichi_kaisuu … 1日に叩いてよい回数（★失敗・再試行も1回と数える）
       jikan_kaisuu … 1時間に叩いてよい回数（ループ・再試行の暴走止め）
     超えたら止めて、status/dispatch_outbox.jsonl に1行（同じ理由は1時間に1回だけ）。
  ③ 家計簿の「API 従量課金」欄（status/okane/api_juuryou.json）を毎日更新（--nikki）。
       出典：status/yosan.jsonl の「使った」行・status/kakeibo.jsonl・status/fal_cost_ledger.json・
             status/subsc.json の xai 行（声）・status/ta_new/kakin.jsonl。推測では埋めない。

━━ つながっている所（ここを通らない口を作らない）━━
  tools/yosan.py の mitsumori() / tsukatta()      … gaibu_kuchi・kenpin_gate・tanomu・fal・devin・x_grok ほか全部
  tools/gaibu_kenpin.py の check_cost_cap()       … kenpin_gate・nyuka_sekisho の直叩き
  tools/gaibu_runner.py                            … 有料の仕事（kiku/tanomu/yomu/xgrok/gsk/douga）を札で門前払い
  単発の台本（_636_* 等）                          … 冒頭の mon(__name__) で札があれば終了
  ★このリポの外：Supabase の voice-session（ブラウザ→xAI の声）は、ここを通らない。
    止める場所は xAI コンソールの上限だけ（status/okane/api_juuryou.json の soto に名指し）。

━━ 決まり ━━
  ・AIを1回も呼ばない。足し算とファイルだけ。課金0。
  ・読めない・壊れているときは「通さない」側に倒す（お金の関所は fail closed）。
  ・--self-test：一時フォルダで、札・1回上限・回数上限・日上限が全部止まるかを確かめる。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
TEISHI = os.path.join(STATUS, "saifu_teishi.json")
SETTEI = os.path.join(STATUS, "saifu_kanmon.json")
KAISUU = os.path.join(STATUS, "saifu_kaisuu.json")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")
NIKKI = os.path.join(STATUS, "okane", "api_juuryou.json")
NIKKI_PUB = os.path.join(STATUS, "public", "api_juuryou.json")
JST = timezone(timedelta(hours=9))

# ★初期値。止まっている間は関係ないが、--kaijo の後はこれが効く。低めに置く。
KITEI = {
    "openai":   {"nichi_yen": 100, "ikkai_yen": 30,  "nichi_kaisuu": 150, "jikan_kaisuu": 30},
    "xai":      {"nichi_yen": 50,  "ikkai_yen": 20,  "nichi_kaisuu": 100, "jikan_kaisuu": 20},
    "gemini":   {"nichi_yen": 50,  "ikkai_yen": 20,  "nichi_kaisuu": 150, "jikan_kaisuu": 30},
    "fal":      {"nichi_yen": 500, "ikkai_yen": 200, "nichi_kaisuu": 200, "jikan_kaisuu": 60},
    "eleven":   {"nichi_yen": 0,   "ikkai_yen": 0,   "nichi_kaisuu": 0,   "jikan_kaisuu": 0},
    "minimax":  {"nichi_yen": 0,   "ikkai_yen": 0,   "nichi_kaisuu": 0,   "jikan_kaisuu": 0},
    "devin":    {"nichi_yen": 300, "ikkai_yen": 100, "nichi_kaisuu": 10,  "jikan_kaisuu": 3},
    "genspark": {"nichi_yen": 0,   "ikkai_yen": 0,   "nichi_kaisuu": 0,   "jikan_kaisuu": 0},
    "anthropic": {"nichi_yen": 0,  "ikkai_yen": 0,   "nichi_kaisuu": 0,   "jikan_kaisuu": 0},
    "typesafe": {"nichi_yen": 10,  "ikkai_yen": 5,   "nichi_kaisuu": 100, "jikan_kaisuu": 30},
}
YURE = {"OpenAI": "openai", "Grok": "xai", "Gemini": "gemini", "elevenlabs": "eleven"}


def _now():
    return datetime.now(JST)


def _rj(path, default):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default


def _wj(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp.%d" % os.getpid()
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _append(path, row):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


class _Lock:
    def __init__(self):
        self.f = None

    def __enter__(self):
        try:
            import fcntl
            self.f = io.open(KAISUU + ".lock", "a+")
            fcntl.flock(self.f.fileno(), fcntl.LOCK_EX)
        except Exception:
            pass
        return self

    def __exit__(self, *a):
        try:
            self.f and self.f.close()
        except Exception:
            pass


# ---------------------------------------------------------------- 停止札
def teishi_chuu():
    """(止まっているか, 理由)。札が壊れていても『止まっている』とみなす。"""
    if not os.path.exists(TEISHI):
        return False, ""
    d = _rj(TEISHI, None)
    if not isinstance(d, dict):
        return True, "停止札が読めない（読めないときは止める）"
    if d.get("on", True):
        return True, "停止札あり（%s・%s）。戻す：python3 tools/saifu_kanmon.py --kaijo" % (
            d.get("at", "?")[:16], d.get("why", ""))
    return False, ""


def teishi(why):
    d = {"on": True, "at": _now().isoformat(), "why": why,
         "modosu": "python3 tools/saifu_kanmon.py --kaijo"}
    _wj(TEISHI, d)
    _append(OUTBOX, {"at": _now().isoformat(), "from": "saifu_kanmon",
                     "text": "【財布の関所】有料APIを全停止しました：%s（戻す：python3 tools/saifu_kanmon.py --kaijo）" % why})
    return d


def kaijo():
    if os.path.exists(TEISHI):
        d = _rj(TEISHI, {}) or {}
        d["on"] = False
        d["kaijo_at"] = _now().isoformat()
        _append(os.path.join(STATUS, "saifu_teishi_rireki.jsonl"), d)
        os.remove(TEISHI)
    _append(OUTBOX, {"at": _now().isoformat(), "from": "saifu_kanmon",
                     "text": "【財布の関所】停止を解除しました。以後は財布ごとの上限（status/saifu_kanmon.json）で止まります"})


def mon(name="__main__", saifu="?"):
    """単発の台本の冒頭に置く。札があれば何も叩かずに終わる。"""
    on, why = teishi_chuu()
    if on and name == "__main__":
        sys.stderr.write("【財布の関所】%s\n" % why)
        sys.exit(3)


# ---------------------------------------------------------------- 上限
def settei():
    s = _rj(SETTEI, None)
    if not isinstance(s, dict) or "saifu" not in s:
        s = {"saifu": KITEI, "note": "財布ごとの上限。円は1日・1回、回数は失敗も数える。tools/saifu_kanmon.py"}
        try:
            _wj(SETTEI, s)
        except Exception:
            pass
    return s


def _jougen(saifu):
    s = settei()["saifu"]
    return s.get(saifu) or {"nichi_yen": 0, "ikkai_yen": 0, "nichi_kaisuu": 0, "jikan_kaisuu": 0}


def _kaisuu():
    k = _rj(KAISUU, {})
    day, hour = _now().strftime("%Y-%m-%d"), _now().strftime("%Y-%m-%dT%H")
    if k.get("day") != day:
        k = {"day": day, "saifu": {}}
    k.setdefault("saifu", {})
    for v in k["saifu"].values():
        if v.get("hour") != hour:
            v["hour"], v["jikan"] = hour, 0
    return k, hour


def _shiraseru(saifu, kind, text):
    """同じ財布・同じ理由は1時間に1回だけ Dispatch に1行。"""
    k = _rj(KAISUU, {})
    key = "%s|%s|%s" % (saifu, kind, _now().strftime("%Y-%m-%dT%H"))
    sent = k.get("shiraseta") or []
    if key in sent:
        return
    sent = (sent + [key])[-50:]
    k["shiraseta"] = sent
    try:
        _wj(KAISUU, k)
        _append(OUTBOX, {"at": _now().isoformat(), "from": "saifu_kanmon", "text": "【財布の関所】" + text})
    except Exception:
        pass


def toosu(saifu, yen, what=""):
    """★叩く前。(ok, 理由)。ok=False なら叩かない。通したら回数を1つ数える（失敗しても戻さない）。"""
    saifu = YURE.get(saifu, saifu)
    on, why = teishi_chuu()
    if on:
        with _Lock():
            k, _ = _kaisuu()
            v = k["saifu"].setdefault(saifu, {})
            v["tometa"] = v.get("tometa", 0) + 1
            _wj(KAISUU, k)
        return False, "【財布の関所】" + why
    try:
        j = _jougen(saifu)
        yen = float(yen or 0)
        with _Lock():
            k, hour = _kaisuu()
            v = k["saifu"].setdefault(saifu, {"kaisuu": 0, "yen": 0.0, "hour": hour, "jikan": 0})
            v.setdefault("kaisuu", 0); v.setdefault("yen", 0.0); v.setdefault("jikan", 0); v.setdefault("hour", hour)
            ng = None
            if yen > j["ikkai_yen"]:
                ng = ("ikkai", "%s：1回の見積り %.1f円 が1回の上限 %.0f円 を超えるので止めました（%s）" % (saifu, yen, j["ikkai_yen"], what))
            elif v["kaisuu"] + 1 > j["nichi_kaisuu"]:
                ng = ("nichi_kaisuu", "%s：今日の回数上限 %d回 に達したので止めました（失敗・再試行も数える）" % (saifu, j["nichi_kaisuu"]))
            elif v["jikan"] + 1 > j["jikan_kaisuu"]:
                ng = ("jikan_kaisuu", "%s：この1時間の回数上限 %d回 に達したので止めました（ループ・再試行の暴走止め）" % (saifu, j["jikan_kaisuu"]))
            elif v["yen"] + yen > j["nichi_yen"]:
                ng = ("nichi_yen", "%s：今日の上限 %.0f円（使用 %.1f円）を超えるので止めました" % (saifu, j["nichi_yen"], v["yen"]))
            if ng:
                v["tometa"] = v.get("tometa", 0) + 1
                _wj(KAISUU, k)
            else:
                v["kaisuu"] += 1
                v["jikan"] += 1
                v["mikomi"] = round(v.get("mikomi", 0.0) + yen, 2)
                _wj(KAISUU, k)
        if ng:
            _shiraseru(saifu, ng[0], ng[1] + "。上限は status/saifu_kanmon.json")
            return False, "【財布の関所】" + ng[1]
        return True, "通した"
    except Exception as e:  # ★読めないときは止める
        return False, "【財布の関所】上限が読めないので止めました（%s）" % e


def kiroku(saifu, yen):
    """★叩いた後の実額。日上限はこの合計で効く。"""
    saifu = YURE.get(saifu, saifu)
    try:
        with _Lock():
            k, hour = _kaisuu()
            v = k["saifu"].setdefault(saifu, {"kaisuu": 0, "yen": 0.0, "hour": hour, "jikan": 0})
            v["yen"] = round(float(v.get("yen", 0.0)) + float(yen or 0), 4)
            _wj(KAISUU, k)
    except Exception:
        pass


# ---------------------------------------------------------------- 家計簿（API 従量課金）
def nikki(days=31):
    """status/okane/api_juuryou.json を作り直す。日×サービスの円。出典つき。"""
    since = (_now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = {}  # (day, svc) -> {"yen":, "kaisuu":, "moto": set}

    def add(day, svc, yen, moto, n=1):
        if not day or day < since:
            return
        r = rows.setdefault((day, svc), {"yen": 0.0, "kaisuu": 0, "moto": set()})
        r["yen"] += float(yen or 0)
        r["kaisuu"] += n
        r["moto"].add(moto)

    # ① yosan.jsonl の「使った」（工場が叩いて記録した実額・推定）
    p = os.path.join(STATUS, "yosan.jsonl")
    if os.path.exists(p):
        size = os.path.getsize(p)
        with io.open(p, encoding="utf-8", errors="ignore") as f:
            if size > 30_000_000:
                f.seek(size - 30_000_000); f.readline()
            for line in f:
                if '"使った"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                add(str(r.get("at"))[:10], r.get("saifu"), r.get("yen"), "status/yosan.jsonl（使った）")
    # ②〜④ ほかの台帳。同じ1回が複数の台帳に載るので、日×サービスごとに「いちばん大きい台帳」を採る（足さない）。
    alt = {}

    def alt_add(day, svc, yen, moto):
        if not day or day < since:
            return
        svc = YURE.get(svc, svc).lower()
        a = alt.setdefault(moto, {})
        a[(day, svc)] = a.get((day, svc), 0.0) + float(yen or 0)

    for r in _rj(os.path.join(STATUS, "fal_cost_ledger.json"), {}).get("records", []):
        alt_add(r.get("date"), "fal", r.get("totalCostYen"), "status/fal_cost_ledger.json")
    for r in _rj(os.path.join(STATUS, "gaibu_kenpin_ledger.json"), {}).get("records", []):
        alt_add(r.get("date"), r.get("provider"), r.get("costYen"), "status/gaibu_kenpin_ledger.json")
    kb = os.path.join(STATUS, "kakeibo.jsonl")
    for line in (io.open(kb, encoding="utf-8", errors="ignore") if os.path.exists(kb) else []):
        try:
            r = json.loads(line)
        except Exception:
            continue
        alt_add(str(r.get("at"))[:10], r.get("svc"), r.get("yen"), "status/kakeibo.jsonl")
    for moto, a in alt.items():
        for (d, s), y in a.items():
            cur = rows.get((d, s))
            if cur is None or y > cur["yen"] + 0.05:
                rows[(d, s)] = {"yen": y, "kaisuu": 0, "moto": {moto}}
    # ③ 声（xAI・ブラウザ→Supabase→xAI。工場の外）
    for line in io.open(os.path.join(STATUS, "ta_new", "kakin.jsonl"), encoding="utf-8") if os.path.exists(os.path.join(STATUS, "ta_new", "kakin.jsonl")) else []:
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("yen"):
            add(str(r.get("at"))[:10], "xai_koe", r.get("yen"), "status/ta_new/kakin.jsonl（画面の円表示）")
    xai = next((i for i in (_rj(os.path.join(STATUS, "subsc.json"), {}).get("items") or []) if i.get("id") == "xai"), None)

    hyou = {}
    for (d, s), r in sorted(rows.items()):
        hyou.setdefault(d, {})[s] = {"yen": round(r["yen"], 1), "kaisuu": r["kaisuu"], "moto": sorted(r["moto"])}
    goukei = {}
    week = (_now() - timedelta(days=7)).strftime("%Y-%m-%d")
    for (d, s), r in rows.items():
        g = goukei.setdefault(s, {"30nichi_yen": 0.0, "7nichi_yen": 0.0})
        g["30nichi_yen"] = round(g["30nichi_yen"] + r["yen"], 1)
        if d >= week:
            g["7nichi_yen"] = round(g["7nichi_yen"] + r["yen"], 1)
    out = {
        "kind": "API 従量課金（家計簿の欄）",
        "updatedAt": _now().isoformat(),
        "note": "工場の記録だけで数えた円（推定を含む）。カードから引かれた円は status/okane/kakin.json の harai が正本。",
        "goukei": goukei,
        "hibetsu": hyou,
        "koe_xai_ruikei": (xai or {}).get("gaku_moto"),
        "soto": [
            "xAI 声（Supabase voice-session）…工場の関所を通らない。上限は console.x.ai の Billing で設定",
            "ElevenLabs …工場から叩いた記録なし。請求は elevenlabs.io の Subscription/Usage でしか見られない",
            "OpenAI …使用額APIは管理キー（admin key）が無く読めない。platform.openai.com/usage",
            "Gemini …請求は Google Cloud Billing でしか見られない",
        ],
        "teishi": teishi_chuu()[0],
        "kaisuu_kyou": _rj(KAISUU, {}).get("saifu", {}),
    }
    _wj(NIKKI, out)
    try:
        _wj(NIKKI_PUB, out)
    except Exception:
        pass
    return out


# ---------------------------------------------------------------- 逆テスト
def self_test():
    import shutil
    import tempfile
    global TEISHI, SETTEI, KAISUU, OUTBOX
    keep = (TEISHI, SETTEI, KAISUU, OUTBOX)
    d = tempfile.mkdtemp(prefix="saifu-test-")
    TEISHI, SETTEI, KAISUU, OUTBOX = (os.path.join(d, x) for x in ("t.json", "s.json", "k.json", "o.jsonl"))
    res = []
    try:
        _wj(SETTEI, {"saifu": {"xai": {"nichi_yen": 10, "ikkai_yen": 5, "nichi_kaisuu": 3, "jikan_kaisuu": 2}}})
        res.append(("① 普通の1回は通る", toosu("xai", 1)[0], True))
        res.append(("② 1回上限5円に6円は止まる", toosu("xai", 6)[0], False))
        res.append(("③ 2回目は通る", toosu("xai", 1)[0], True))
        res.append(("④ 1時間2回の上限で3回目は止まる（失敗も数える）", toosu("xai", 1)[0], False))
        kiroku("xai", 9.5)
        k = _rj(KAISUU, {}); k["saifu"]["xai"]["jikan"] = 0; _wj(KAISUU, k)
        res.append(("⑤ 日上限10円・使用9.5円に1円は止まる", toosu("xai", 1)[0], False))
        res.append(("⑥ 知らない財布（上限0）は止まる", toosu("shiranai", 0.01)[0], False))
        teishi("試験")
        res.append(("⑦ 停止札があれば0.01円でも止まる", toosu("gemini", 0.01)[0], False))
        kaijo()
        res.append(("⑧ 解除したら札は消える", teishi_chuu()[0], False))
        io.open(TEISHI, "w").write("こわれた")
        res.append(("⑨ 札が壊れていたら止まる側", teishi_chuu()[0], True))
        res.append(("⑩ 止めたことが Dispatch に1行出ている", "財布の関所" in io.open(OUTBOX, encoding="utf-8").read(), True))
    finally:
        TEISHI, SETTEI, KAISUU, OUTBOX = keep
        shutil.rmtree(d, ignore_errors=True)
    ng = [r for r in res if r[1] != r[2]]
    print("財布の関所 逆テスト：%d件中 %d件 想定どおり" % (len(res), len(res) - len(ng)))
    for n, got, want in res:
        print("  %s %s" % ("◯" if got == want else "✕", n))
    return 1 if ng else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teishi", nargs="?", const="手で止めた")
    ap.add_argument("--kaijo", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--nikki", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.teishi:
        teishi(a.teishi); print("止めました：", teishi_chuu()[1]); return 0
    if a.kaijo:
        kaijo(); print("解除しました。以後は status/saifu_kanmon.json の上限で止まります"); return 0
    if a.nikki:
        o = nikki(); print(json.dumps(o["goukei"], ensure_ascii=False)); return 0
    on, why = teishi_chuu()
    print("停止中" if on else "動いている（上限つき）", why)
    print(json.dumps({"jougen": settei()["saifu"], "kyou": _rj(KAISUU, {}).get("saifu", {})}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
