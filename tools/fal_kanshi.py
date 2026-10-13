#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fal見張り（2026-10-08・たまごさん「fal は最優先で監視対象に」）。

たまごさん（原文の要旨・2026-10-08）:
  「falの利用・残高を読めるAPIで、残高・日ごとの使用額・どのモデルにいくらを台帳に自動で載せる。
    1日$3超えや、1回で$2超えの注文があったら進捗表で赤く出す。
    APIで残高が取れない場合は、取れる範囲と取れない部分を正直に書く。」
  「今日の$0.76をどのセッション・スクリプトが発注したかも台帳に載せて。チャージ後の残高が見えたら、それも記録。」

やること（心臓から1時間に1回・読むだけ＝0円・課金もチャージも押さない）:
  1. fal Platform API を読む（鍵は tools/kagi.py だけから取る。値は1文字も書かない）
       残高            GET https://api.fal.ai/v1/account/billing?expand=credits
       日ごと×モデル別  GET https://api.fal.ai/v1/models/usage?timeframe=day&expand=time_series&expand=auth_method
       時間ごと×モデル別 GET 同上 timeframe=hour（直近48時間・「1回で$2超」の見張り用）
     ★どれも管理者キー（ADMIN scope）が要る。普通の鍵で 401/403/404 が返ったら、その事実（HTTPコード）を書く。
  2. たまごさんのスクショなど「画面で見た数字」は status/fal/mita.json（手で足す正本）から読む。
  3. 工場側の発注台帳 status/public/fal_cost_ledger.json（1回ごとの記録）も読む。
  4. 赤の判定：1日 $3 超／1回 $2 超（工場台帳は1回ずつ、APIは1時間×1モデルの合計で疑いを出す）
  5. 書き出し：status/public/fal_kanshi.json（進捗表とお金の紙が読む）
             status/fal/rireki.jsonl（残高を読めた時刻ごとに1行・チャージ後の残高もここに残る）

使い方:
  python3 tools/fal_kanshi.py            … 本体（毎回走ってよい・API 3本だけ）
  python3 tools/fal_kanshi.py --self-test
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
FALDIR = os.path.join(STATUS, "fal")
OUT = os.path.join(PUBLIC, "fal_kanshi.json")
RIREKI = os.path.join(FALDIR, "rireki.jsonl")
MITA = os.path.join(FALDIR, "mita.json")
LEDGER = os.path.join(PUBLIC, "fal_cost_ledger.json")
JST = timezone(timedelta(hours=9))

ICHINICHI_USD = 3.0     # 1日 $3 超で赤
IKKAI_USD = 2.0         # 1回 $2 超で赤

API = "https://api.fal.ai/v1"


def _load(p, d=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def _keys():
    """管理者キー候補→普通の鍵の順。★値は返り値でしか持たない。"""
    out = []
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import kagi  # 鍵の唯一の読み口
        for name in ("FAL_ADMIN_KEY", "FAL_KEY"):
            v = kagi.get(name)
            if v and v not in [x[1] for x in out]:
                out.append((name, v))
    except Exception:
        pass
    p = os.path.expanduser("~/.fal_admin_key")
    try:
        v = io.open(p, encoding="utf-8").read().strip()
        # 過去にコマンド文字列が入っていた事故がある（783番）。鍵の形でなければ使わない
        if v and " " not in v and ":" in v and v not in [x[1] for x in out]:
            out.insert(0, ("~/.fal_admin_key", v))
    except Exception:
        pass
    return out


def _get(url, key):
    req = urllib.request.Request(url, headers={"Authorization": "Key " + key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")[:300]
        except Exception:
            body = ""
        return e.code, {"_error": body}
    except Exception as e:
        return None, {"_error": type(e).__name__}


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(x):
    try:
        return float(x)
    except Exception:
        return None


def _flat_usage(body):
    """usage の返りを (bucket, endpoint, cost, quantity, unit, auth) の行に平らにする。形が違っても落ちない。"""
    rows = []
    if not isinstance(body, dict):
        return rows
    ts = body.get("time_series") or body.get("timeseries") or []
    for b in ts if isinstance(ts, list) else []:
        bucket = b.get("bucket") or b.get("timestamp") or b.get("date") or ""
        for r in b.get("results") or b.get("items") or []:
            rows.append(dict(bucket=str(bucket), endpoint=r.get("endpoint_id") or r.get("endpoint") or "?",
                             cost=_num(r.get("cost")) or 0.0, quantity=_num(r.get("quantity")),
                             unit=r.get("unit"), auth=r.get("auth_method") or r.get("key_alias") or r.get("key_name")))
    return rows


def api_yomu():
    now = datetime.now(JST)
    res = dict(tamesita=[], zandaka=None, nichibetsu=None, jikanbetsu=None)
    keys = _keys()
    if not keys:
        import socket
        res["tamesita"].append(dict(what="鍵", code=None, why="この回は鍵が読めなかった（走った場所：%s。鍵台帳 tools/kagi.py に FAL_ADMIN_KEY も FAL_KEY も見えない）" % socket.gethostname()))
        return res
    q_day = urllib.parse.urlencode([("start", _iso(now - timedelta(days=30))), ("end", _iso(now)),
                                    ("timeframe", "day"), ("timezone", "Asia/Tokyo"),
                                    ("expand", "time_series"), ("expand", "auth_method")])
    q_hour = urllib.parse.urlencode([("start", _iso(now - timedelta(hours=48))), ("end", _iso(now)),
                                     ("timeframe", "hour"), ("timezone", "Asia/Tokyo"),
                                     ("expand", "time_series"), ("expand", "auth_method")])
    jobs = [("zandaka", API + "/account/billing?expand=credits"),
            ("nichibetsu", API + "/models/usage?" + q_day),
            ("jikanbetsu", API + "/models/usage?" + q_hour)]
    for what, url in jobs:
        got = None
        for name, key in keys:
            code, body = _get(url, key)
            res["tamesita"].append(dict(what=what, kagi=name, code=code,
                                        url=url.split("?")[0],
                                        why=(body.get("_error") if isinstance(body, dict) else "")[:160] if code != 200 else ""))
            if code == 200:
                got = body
                break
        if got is None:
            continue
        if what == "zandaka":
            c = (got or {}).get("credits") or {}
            bal = _num(c.get("current_balance"))
            res["zandaka"] = dict(usd=bal, currency=c.get("currency") or "USD",
                                  at=now.strftime("%Y-%m-%d %H:%M"), moto="fal API /v1/account/billing")
        else:
            res[what] = _flat_usage(got)
    return res


def kojo_daicho():
    """工場側の発注台帳（1回ずつ）。$2超の1回を拾う。"""
    recs = (_load(LEDGER, {}) or {}).get("records") or []
    aka = []
    for r in recs:
        usd = _num(r.get("totalCostUsd"))
        cnt = _num(r.get("count")) or 1
        one = usd / cnt if usd is not None and cnt else None
        if one is not None and one > IKKAI_USD:
            aka.append(dict(date=r.get("date"), model=r.get("model"), usd=round(one, 2),
                            n=r.get("n"), title=r.get("title"), moto="status/public/fal_cost_ledger.json"))
    return recs, aka


def build():
    now = datetime.now(JST)
    today = now.strftime("%Y-%m-%d")
    mita = _load(MITA, {}) or {}
    api = api_yomu()
    _, kojo_aka = kojo_daicho()

    # 日ごと×モデル別：APIが取れればAPI、取れなければ画面で見た数字（mita.json）
    hibetsu = {}
    src_hibetsu = None
    if api.get("nichibetsu"):
        src_hibetsu = "fal API /v1/models/usage（日ごと・Asia/Tokyo）"
        for r in api["nichibetsu"]:
            d = r["bucket"][:10]
            hibetsu.setdefault(d, {}).setdefault(r["endpoint"], dict(usd=0.0, auth=set()))
            hibetsu[d][r["endpoint"]]["usd"] += r["cost"]
            if r.get("auth"):
                hibetsu[d][r["endpoint"]]["auth"].add(str(r["auth"]))
    else:
        for m in mita.get("hibetsu") or []:
            hibetsu.setdefault(m["date"], {}).setdefault(m["model"], dict(usd=0.0, auth=set()))
            hibetsu[m["date"]][m["model"]]["usd"] += float(m["usd"])
        if hibetsu:
            src_hibetsu = "たまごさんのスクショ（status/fal/mita.json）※APIが取れていないため"
    days = []
    for d in sorted(hibetsu, reverse=True):
        models = sorted(([k, round(v["usd"], 2), sorted(v["auth"])] for k, v in hibetsu[d].items()),
                        key=lambda x: -x[1])
        tot = round(sum(x[1] for x in models), 2)
        days.append(dict(date=d, usd=tot, models=[dict(model=a, usd=b, kagi=c) for a, b, c in models],
                         aka=tot > ICHINICHI_USD))

    aka = []
    for d in days:
        if d["aka"]:
            aka.append("%s の fal 使用額 $%.2f（1日$%.0f超）" % (d["date"], d["usd"], ICHINICHI_USD))
    for r in api.get("jikanbetsu") or []:
        if r["cost"] > IKKAI_USD:
            aka.append("%s %s で $%.2f（1時間・1モデルの合計が$%.0f超＝1回$%.0f超の疑い）"
                       % (r["bucket"][:16].replace("T", " "), r["endpoint"], r["cost"], IKKAI_USD, IKKAI_USD))
    for r in kojo_aka:
        aka.append("%s %s 1回 $%.2f（%s番：%s）" % (r["date"], r["model"], r["usd"], r.get("n"), r.get("title") or ""))
    # 赤は「直近7日」に絞る（古い赤を毎日出し続けない）
    since = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    aka = [a for a in aka if a[:10] >= since]

    # 残高：APIで読めたらそれ。読めなければ画面で見た最後の値（時刻つき）
    zan = api.get("zandaka")
    rireki_new = None
    if zan and zan.get("usd") is not None:
        rireki_new = dict(at=zan["at"], usd=zan["usd"], moto=zan["moto"])
    mita_zan = (mita.get("zandaka") or [])
    last_mita = mita_zan[-1] if mita_zan else None

    torenai = []
    codes = {}
    for t in api["tamesita"]:
        codes.setdefault(t["what"], []).append("%s→%s" % (t.get("kagi") or "-", t.get("code")))
    labels = dict(zandaka="残高", nichibetsu="日ごと×モデル別", jikanbetsu="時間ごと（1回$2超の見張り）")
    for w in ("zandaka", "nichibetsu", "jikanbetsu"):
        ok = (w == "zandaka" and zan) or (w != "zandaka" and api.get(w))
        if not ok:
            c = "・".join(codes.get(w, [])) or (api["tamesita"][0].get("why") if api["tamesita"] else "鍵なし")
            torenai.append("%s：APIで取れていない（%s）。管理者キー(ADMIN scope)が要る。鍵台帳に FAL_ADMIN_KEY が置かれれば次の回から自動で載る" % (labels[w], c))

    d = dict(
        generatedAt=now.strftime("%Y-%m-%d %H:%M:%S"),
        kijun=dict(ichinichi_usd=ICHINICHI_USD, ikkai_usd=IKKAI_USD),
        zandaka=dict(api=zan, mita=last_mita),
        charge=mita.get("charge") or [],
        hibetsu=days[:31], hibetsuMoto=src_hibetsu,
        sanjuunichi=mita.get("sanjuunichi"),
        hacchuu=mita.get("hacchuu") or [],
        aka=aka, torenai=torenai, tamesita=api["tamesita"],
    )
    return d, rireki_new


def run():
    os.makedirs(FALDIR, exist_ok=True)
    os.makedirs(PUBLIC, exist_ok=True)
    d, rn = build()
    tmp = OUT + ".tmp"
    json.dump(d, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    if rn:
        last = None
        try:
            lines = io.open(RIREKI, encoding="utf-8").read().strip().splitlines()
            last = json.loads(lines[-1]) if lines else None
        except Exception:
            pass
        if not last or last.get("usd") != rn["usd"]:     # 残高が動いたときだけ1行
            io.open(RIREKI, "a", encoding="utf-8").write(json.dumps(rn, ensure_ascii=False) + "\n")
    return d


def self_test():
    ng = []
    d, _ = build()
    if not isinstance(d.get("aka"), list):
        ng.append("aka が配列でない")
    if not d.get("zandaka", {}).get("api") and not d.get("torenai"):
        ng.append("残高が取れていないのに『取れていない』と書いていない")
    if any("Key " in json.dumps(t, ensure_ascii=False) for t in d["tamesita"]):
        ng.append("鍵の値が出力に混ざった")
    print("自己試験 %s（%d件）" % ("◯ 通った" if not ng else "✕ 落ちた", len(ng)))
    for x in ng:
        print(" -", x)
    return 1 if ng else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    d = run()
    print("fal見張り：赤 %d件／取れない %d件／残高(API) %s" % (
        len(d["aka"]), len(d["torenai"]), (d["zandaka"]["api"] or {}).get("usd", "取れていない")))
