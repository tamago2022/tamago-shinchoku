#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""960番【実額】OpenAIの「実際の請求額」を取ってくる読み取り専用の係。

■ なぜ要るか（2026-09-19）
  たまごさんの言葉：「見積もりなのか。あれで本当に金がかかるなら全然実用的じゃない。
  多分、俺の金がどんどん溶けていく。」
  → 単価×トークンの**見積もり**ではなく、OpenAIが自分で計算した**実額**を出す。

■ 使う口（どれも無料・読み取りのみ・新たな課金はしない）
  GET /v1/organization/costs                 … 日ごとの実額(USD)。line_itemで内訳。
  GET /v1/organization/usage/completions     … 時間ごとのトークン数（モデル別）
  GET /v1/organization/usage/audio_speeches  … 音声合成
  GET /v1/organization/usage/audio_transcriptions … 文字起こし
  ※ costs / usage 系は **Admin key**（sk-admin-…）でないと401/403で断られる。
     その場合は「鍵の格が足りない」ことを結果に明記する（値は出さない）。

■ 絶対に守ること
  鍵の**値は絶対に返さない・ログにも書かない**。有無と先頭数文字だけ。
  POSTは一切しない。GETのみ。
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gaibu_kuchi as gkuchi  # noqa: E402

BASE = "https://api.openai.com/v1/organization"
USD_TO_YEN = 150.0  # gaibu_kenpin.USD_TO_YEN と同じ暫定レート（円は参考、USDが実額）
JST = 9 * 3600

# Admin key を先に探す。無ければ通常の OPENAI_API_KEY で試して、断られたことを記録する。
ADMIN_NAMES = ("OPENAI_ADMIN_KEY", "OPENAI_ADMIN_API_KEY", "OPENAI_ORG_ADMIN_KEY",
               "OPENAI_USAGE_KEY")


def _find_admin_key():
    import gaibu_kenpin as gk
    v = gk._find_env_key(ADMIN_NAMES)
    if v:
        return v, "admin"
    for path in gkuchi.EXTRA_KEY_FILES + [os.path.expanduser("~/.env"),
                                          os.path.join(REPO, ".env")]:
        if not os.path.exists(path):
            continue
        try:
            for line in io.open(path, encoding="utf-8", errors="ignore"):
                line = line.strip()
                if line.lower().startswith("export "):
                    line = line[7:].strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                nm, val = line.split("=", 1)
                nm = nm.strip()
                val = val.strip().strip('"').strip("'")
                if nm in ADMIN_NAMES and val:
                    return val, "admin"
        except Exception:
            continue
    v = gkuchi.find_key("openai")
    return (v, "normal") if v else (None, None)


def _get(path, params, key, timeout=40):
    qs = []
    for k, v in params.items():
        if isinstance(v, (list, tuple)):
            for item in v:
                qs.append((k, item))
        else:
            qs.append((k, v))
    url = "%s/%s?%s" % (BASE, path, urllib.parse.urlencode(qs))
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key},
                                 method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _get_all(path, params, key):
    """page送りを全部たどる。"""
    out = []
    p = dict(params)
    for _ in range(20):
        d = _get(path, p, key)
        out.extend(d.get("data") or [])
        if d.get("has_more") and d.get("next_page"):
            p["page"] = d["next_page"]
        else:
            break
    return out


def _jst_midnight(ts=None):
    ts = ts or time.time()
    return int((ts + JST) // 86400 * 86400 - JST)


def _month_start_jst(ts=None):
    lt = time.localtime(ts or time.time())
    return int(time.mktime((lt.tm_year, lt.tm_mon, 1, 0, 0, 0, 0, 0, -1)))


def _jst(ts):
    return time.strftime("%m/%d %H:%M", time.localtime(ts))


def run_job(payload=None):
    payload = payload or {}
    key, grade = _find_admin_key()
    res = {
        "ok": False,
        "keyGrade": grade,
        "keyHead": (key[:7] + "…") if key else "",
        "usdToYen": USD_TO_YEN,
        "totalYen": 0.0,   # ★この調査自体の課金は0（読み取りAPIは無料）
        "notes": [],
    }
    if not key:
        res["error"] = "OpenAIの鍵が見つかりません"
        return res

    today0 = _jst_midnight()
    month0 = _month_start_jst()
    now = int(time.time())

    # ---- 1) 実額（costs）。バケットはUTC日なので、月初から今日までを丸ごと取る ----
    try:
        rows = _get_all("costs", {"start_time": month0, "bucket_width": "1d",
                                  "limit": 40, "group_by[]": ["line_item"]}, key)
        days = []
        month_usd = 0.0
        for b in rows:
            items = []
            s = 0.0
            for r in (b.get("results") or []):
                amt = float(((r.get("amount") or {}).get("value")) or 0)
                if amt <= 0:
                    continue
                items.append({"lineItem": r.get("line_item") or "(不明)",
                              "usd": round(amt, 6), "yen": round(amt * USD_TO_YEN, 2)})
                s += amt
            month_usd += s
            items.sort(key=lambda x: -x["usd"])
            days.append({
                "utcDay": time.strftime("%Y-%m-%d", time.gmtime(b.get("start_time") or 0)),
                "startJst": _jst(b.get("start_time") or 0),
                "usd": round(s, 6), "yen": round(s * USD_TO_YEN, 2), "items": items,
            })
        res["costs"] = {
            "monthUsd": round(month_usd, 6),
            "monthYen": round(month_usd * USD_TO_YEN, 2),
            "days": days,
        }
        res["ok"] = True
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")[:300]
        except Exception:
            pass
        res["costsError"] = "HTTP %s %s" % (e.code, body)
        if e.code in (401, 403):
            res["notes"].append(
                "costs/usage APIは Admin key（sk-admin-…）専用。今の鍵では格が足りない。"
                "platform.openai.com の Settings → API keys → Admin keys で1本作って "
                "OPENAI_ADMIN_KEY として鍵ファイルに足すと実額が取れる。")
    except Exception as e:
        res["costsError"] = "%s: %s" % (type(e).__name__, e)

    # ---- 2) 内訳（usage）。今日のJST 0時から1時間刻み。モデル別 ----
    usage = {}
    for path, gb in (("completions", ["model"]),
                     ("audio_speeches", ["model"]),
                     ("audio_transcriptions", ["model"])):
        try:
            rows = _get_all(path, {"start_time": today0, "end_time": now,
                                   "bucket_width": "1h", "limit": 24,
                                   "group_by[]": gb}, key)
            per_model = {}
            hours = []
            for b in rows:
                hsum = {"in": 0, "out": 0, "req": 0, "sec": 0}
                for r in (b.get("results") or []):
                    m = r.get("model") or "(不明)"
                    d = per_model.setdefault(m, {"in": 0, "out": 0, "req": 0, "sec": 0,
                                                 "characters": 0})
                    d["in"] += int(r.get("input_tokens") or 0)
                    d["out"] += int(r.get("output_tokens") or 0)
                    d["req"] += int(r.get("num_model_requests") or 0)
                    d["sec"] += int(r.get("seconds") or 0)
                    d["characters"] += int(r.get("characters") or 0)
                    hsum["in"] += int(r.get("input_tokens") or 0)
                    hsum["out"] += int(r.get("output_tokens") or 0)
                    hsum["req"] += int(r.get("num_model_requests") or 0)
                    hsum["sec"] += int(r.get("seconds") or 0)
                if hsum["req"] or hsum["in"] or hsum["out"] or hsum["sec"]:
                    hours.append({"hourJst": _jst(b.get("start_time") or 0), **hsum})
            usage[path] = {"byModel": per_model, "hours": hours}
        except urllib.error.HTTPError as e:
            usage[path] = {"error": "HTTP %s" % e.code}
        except Exception as e:
            usage[path] = {"error": "%s: %s" % (type(e).__name__, e)}
    res["usageToday"] = usage
    res["window"] = {"todayJstFrom": _jst(today0), "monthJstFrom": _jst(month0),
                     "nowJst": _jst(now)}

    # ---- 3) 生の答えも残す（後から数え直せるように） ----
    try:
        outdir = os.path.join(REPO, "status")
        os.makedirs(outdir, exist_ok=True)
        with io.open(os.path.join(outdir, "openai_jitsugaku.json"), "w",
                     encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
    return res


if __name__ == "__main__":
    print(json.dumps(run_job({}), ensure_ascii=False, indent=1))
