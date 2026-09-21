#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""973番：Devinの「$8.85はいつ・何に消えたか」を、叩いて返ってきたものだけで測る。

なぜ工場側（Mac）で走るか：
  Coworkのサンドボックスは api.devin.ai / app.devin.ai へ回線が出ない
  （プロキシが 403 CONNECT）。Macからは出る。962番の口に相乗りする。

やること（**読むだけ**。何も買わない・何も変更しない）:
  1. GET /v1/sessions を全ページ取る（limit/offset を進めて打ち止めまで）
  2. 各セッションの個票 GET /v1/session/{id} を引いて**生JSONのキー一覧**を残す
     （「消費量のフィールドが無い」と書くなら、その証拠を残すため）
  3. 消費額の口を順に叩いて、返ってきたHTTPコードと本文をそのまま残す
     （403なら403の本文を1文字も変えずに残す）

鍵の値は一切出力しない。保存先 status/_973/ は .gitignore の中（非公開）。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "status", "_973")
API = "https://api.devin.ai"


def load_key():
    p = os.path.join(REPO, ".env")
    if not os.path.exists(p):
        return None
    for line in open(p, encoding="utf-8"):
        if line.startswith("DEVIN_API_KEY="):
            return line.strip().split("=", 1)[1]
    return None


def hit(key, path):
    """叩いて (status, body文字列) を返す。例外も文字列にして必ず返す。"""
    req = urllib.request.Request(API + path,
                                 headers={"Authorization": "Bearer %s" % key})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return 0, "EXC %r" % (e,)


def main():
    os.makedirs(OUT, exist_ok=True)
    key = load_key()
    if not key:
        print("NG: .env に DEVIN_API_KEY がありません")
        return 1

    report = {"ranAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "probes": []}

    # ---- 1. セッション一覧（ページング込み） ----
    sessions = []
    seen = set()
    limit = 100
    for page in range(0, 30):
        st, body = hit(key, "/v1/sessions?limit=%d&offset=%d" % (limit, page * limit))
        report["probes"].append({"path": "/v1/sessions?limit=%d&offset=%d" % (limit, page * limit),
                                 "status": st, "bytes": len(body),
                                 "body_head": body[:300]})
        if st != 200:
            break
        try:
            d = json.loads(body)
        except Exception:
            break
        batch = d.get("sessions") if isinstance(d, dict) else d
        if not batch:
            break
        new = 0
        for s in batch:
            sid = s.get("session_id") or s.get("id")
            if sid and sid not in seen:
                seen.add(sid)
                sessions.append(s)
                new += 1
        if new == 0 or len(batch) < limit:
            break
        time.sleep(0.4)

    report["sessionCount"] = len(sessions)
    report["listKeys"] = sorted({k for s in sessions for k in s.keys()})
    with open(os.path.join(OUT, "sessions_raw.json"), "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=1)

    # ---- 2. 個票（全部。消費量フィールドの有無を生で確かめる） ----
    detail_keys = {}
    details = {}
    for s in sessions:
        sid = s.get("session_id") or s.get("id")
        if not sid:
            continue
        st, body = hit(key, "/v1/session/%s" % sid)
        if st == 200:
            try:
                d = json.loads(body)
            except Exception:
                d = {"_unparsable": body[:200]}
            details[sid] = d
            for k in d.keys():
                detail_keys[k] = detail_keys.get(k, 0) + 1
        else:
            details[sid] = {"_httpStatus": st, "_body": body[:300]}
        time.sleep(0.3)
    report["detailKeyCounts"] = detail_keys
    with open(os.path.join(OUT, "session_details_raw.json"), "w", encoding="utf-8") as f:
        json.dump(details, f, ensure_ascii=False, indent=1)

    # ---- 3. 消費額の口（閉じているかどうかを実測で示す） ----
    for path in ["/v1/enterprise/consumption",
                 "/v1/enterprise/consumption?start_date=2026-09-17&end_date=2026-09-21",
                 "/v1/usage",
                 "/v1/billing",
                 "/v1/organization/usage",
                 "/v1/acu",
                 "/v1/enterprise/usage"]:
        st, body = hit(key, path)
        report["probes"].append({"path": path, "status": st,
                                 "body": body[:600]})
        time.sleep(0.3)

    with open(os.path.join(OUT, "probe_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print("セッション件数: %d" % len(sessions))
    print("一覧のキー: %s" % ", ".join(report["listKeys"]))
    print("個票のキー: %s" % ", ".join(sorted(detail_keys)))
    for p in report["probes"]:
        if not p["path"].startswith("/v1/sessions"):
            print("  %s -> %s : %s" % (p["status"], p["path"],
                                       (p.get("body") or "")[:160].replace("\n", " ")))
    print("OK: status/_973/ に保存しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
