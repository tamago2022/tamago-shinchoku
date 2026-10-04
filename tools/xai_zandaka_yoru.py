#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xAI の残高と日別使用額を毎晩取って台帳(status/subsc.json の xai 行)へ書く。2026-10-05。

公式 Management API（docs.x.ai/developers/rest-api-reference/management/billing）だけを使う読み取り専用：
  GET  /auth/management-keys/validation          … この管理キーがどのチームのものか（teamId＝自動判定）
  GET  /v1/billing/teams/{id}/prepaid/balance    … 前払いの購入履歴と合計（単位 USDセント。マイナス＝購入）
  POST /v1/billing/teams/{id}/usage              … 日別の使用額（読み取りのPOST。課金・変更はしない）
鍵(XAI_MANAGEMENT_KEY)が無ければ何もしない。値は書かない。
残りの目安 ＝ 購入合計 − 使用合計（公式の合計欄は使用額を引かない実例があるため、両方を残す）。

使い方:  python3 tools/xai_zandaka_yoru.py        # 毎晩22時以降に1回（心臓から5分おきに呼ばれても1日1回）
         python3 tools/xai_zandaka_yoru.py --now  # 今すぐ
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import kagi  # noqa: E402

BASE = "https://management-api.x.ai"
OUT = os.path.join(REPO, "status", "xai_zandaka.json")
LEDGER = os.path.join(REPO, "status", "subsc.json")


def call(key, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                                          "User-Agent": "tamago-xai-zandaka/1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.getcode(), json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception:
        return 0, {}


def usd(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def run(now=False):
    today = datetime.date.today().isoformat()
    prev = {}
    try:
        prev = json.load(open(OUT))
    except Exception:
        pass
    if not now and (datetime.datetime.now().hour < 22 or prev.get("date") == today):
        return 0
    key = kagi.get("XAI_MANAGEMENT_KEY")
    if not key:
        return 0   # 受け口に鍵が入るまで待つ
    st = {"date": today, "at": time.strftime("%F %T")}
    code, v = call(key, "GET", "/auth/management-keys/validation")
    team = v.get("teamId") or (v.get("data") or {}).get("teamId")
    if code != 200 or not team:
        st.update(state="管理キーが通らない(HTTP %s)" % code, last_ok=prev.get("last_ok"))
    else:
        st["team_id"] = team
        c2, bal = call(key, "GET", "/v1/billing/teams/%s/prepaid/balance" % team)
        purchased = sum(-usd((c.get("amount") or {}).get("val")) for c in bal.get("changes", [])
                        if (c.get("changeOrigin") == "PURCHASE" and c.get("topupStatus", "SUCCEEDED") == "SUCCEEDED")) / 100.0
        net = -usd((bal.get("total") or {}).get("val")) / 100.0
        start = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        body = {"analyticsRequest": {"timeRange": {"startTime": start + " 00:00:00", "endTime": today + " 23:59:59", "timezone": "Asia/Tokyo"},
                                     "timeUnit": "TIME_UNIT_DAY", "values": [{"name": "usd", "aggregation": "AGGREGATION_SUM"}],
                                     "groupBy": [], "filters": []}}
        c3, us = call(key, "POST", "/v1/billing/teams/%s/usage" % team, body)
        daily = {}
        for ts in us.get("timeSeries", []):
            for p in ts.get("dataPoints", []):
                vals = p.get("values") or []
                amt = usd(vals[0]) if vals and not isinstance(vals[0], dict) else usd((vals[0] or {}).get("val")) if vals else 0.0
                day = str(p.get("timestamp", ""))[:10]
                daily[day] = round(daily.get(day, 0.0) + amt, 4)
        used = round(sum(daily.values()), 4)
        st.update(state="取得OK" if c2 == 200 else "残高の取得に失敗(HTTP %s)" % c2, purchased_usd=round(purchased, 2),
                  official_total_usd=round(net, 2), used_30d_usd=used, remaining_est_usd=round(purchased - used, 2),
                  usage_http=c3, daily_usd=dict(sorted(daily.items())[-14:]),
                  last_ok=st["at"] if c2 == 200 else prev.get("last_ok"))
    tmp = OUT + ".%d.tmp" % os.getpid()
    json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    # 台帳（サブスク）の xai 行へ『管理キーで取った値』を足す（他の項目・他の係の書き込みは触らない）
    try:
        led = json.load(open(LEDGER, encoding="utf-8"))
        for it in led.get("items", []):
            if it.get("id") == "xai":
                it["kanri_key"] = {"team_id": st.get("team_id"), "remaining_est_usd": st.get("remaining_est_usd"),
                                   "purchased_usd": st.get("purchased_usd"), "used_30d_usd": st.get("used_30d_usd"),
                                   "daily_usd": st.get("daily_usd"), "at": st["at"], "state": st["state"],
                                   "note": "xAI Management API（公式）。残りの目安＝購入−使用"}
                if st.get("team_id"):
                    it["harai"] = "10ドルを入れたチーム＝%s（管理キーで自動判定）" % st["team_id"]
                    it["harai_moto"] = "xAI Management API validation（%s）" % st["at"]
        tmp = LEDGER + ".%d.tmp" % os.getpid()
        json.dump(led, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, LEDGER)
    except Exception:
        pass
    print(st.get("state"))
    return 0


if __name__ == "__main__":
    sys.exit(run(now="--now" in sys.argv))
