#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完了の検証置き場 status/verify_log.jsonl を作る。

なぜ作るか:
  「完了」と書いてあるだけでは、たまごさんは確かめられない。
  緑にしてよいのは **記録されたURLが、その項目の実物URLと一致したときだけ**。
  一致の条件は次の3つを全部満たすこと:
    ① URLが記録されている
    ② そのURLの中身（share/... 配下のファイル）がこのリポジトリに実在する
    ③ ファイル名の先頭番号が、その項目の番号と一致する（他番の確認ページの流用でない）

判定は3つだけ:
  verified  … 上の3条件を満たす → 緑
  recheck   … URLはあるが実物が無い／番号が違う → 要再確認
  unverified… URLがそもそも無い → 未検証（「完了」とは呼ばない）

出力:
  status/verify_log.jsonl   1行1件（あとから差分を見るための置き場）
  status/verify_summary.json 件数だけの要約（進捗表が読む。top_status.py が取り込む）
"""
import io
import json
import os
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
DONE = os.path.join(ST, "done_archive.json")
OUT_LOG = os.path.join(ST, "verify_log.jsonl")
OUT_SUM = os.path.join(ST, "verify_summary.json")

JST = datetime.timezone(datetime.timedelta(hours=9))
SITE = "https://tamago2022.github.io/tamago-shinchoku/"


def jread(p, d=None):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d if d is not None else {}


def to_relpath(url):
    """本番URLをリポジトリ内の相対パスに直す。repo外（lovable等）は None。"""
    if not url:
        return None
    u = str(url).split("#", 1)[0].split("?", 1)[0]
    if u.startswith(SITE):
        return u[len(SITE):]
    if u.startswith("share/") or u.startswith("./share/"):
        return u.lstrip("./")
    return None


def head_number(path):
    base = os.path.basename(path)
    head = base.split("-", 1)[0]
    return int(head) if head.isdigit() else None


def judge(item):
    n = item.get("n")
    urls = item.get("urls") or ([item["url"]] if item.get("url") else [])
    urls = [u for u in urls if u]
    if not urls:
        return "unverified", None, "URLが記録されていない"

    external = []
    for u in urls:
        rel = to_relpath(u)
        if rel is None:
            external.append(u)
            continue
        full = os.path.join(REPO, rel)
        if not os.path.exists(full):
            continue
        if head_number(rel) != n:
            continue
        return "verified", u, "実物あり・番号一致"

    if external:
        return "recheck", external[0], "リポジトリ外のURL（この場では実物を確かめられない）"
    return "recheck", urls[0], "URLはあるが実物が無いか番号が違う"


def build():
    now = datetime.datetime.now(JST)
    items = (jread(DONE, {}).get("items")) or []
    counts = {"verified": 0, "recheck": 0, "unverified": 0}
    rows = []
    for it in items:
        state, url, why = judge(it)
        counts[state] += 1
        rows.append({
            "n": it.get("n"),
            "title": (it.get("title") or "")[:60],
            "state": state,
            "url": url,
            "why": why,
            "checkedAt": now.isoformat(timespec="seconds"),
        })

    tmp = OUT_LOG + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, OUT_LOG)

    summary = {
        "updatedAt": now.isoformat(timespec="seconds"),
        "total": len(rows),
        "verified": counts["verified"],
        "recheck": counts["recheck"],
        "unverified": counts["unverified"],
        "rule": "記録されたURLの実物がリポジトリにあり、ファイル名の先頭番号が項目の番号と一致したときだけ緑",
    }
    tmp = OUT_SUM + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT_SUM)
    return summary


if __name__ == "__main__":
    s = build()
    print("verify_log.jsonl %d件（緑%d／要再確認%d／未検証%d）"
          % (s["total"], s["verified"], s["recheck"], s["unverified"]))
