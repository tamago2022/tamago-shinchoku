#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1042番【投げ込み箱の一覧】何が入ってきたかを1枚で見られるようにする。

たまごさん（2026-09-23・原文）:
  「今も一個入れたから、何が入ってきたかわかるようにしといてね。
    一応今テストでいくつか入れてみるから、反映されるかどうか見てるからね。」

■ 決め（なぜこの形か）
  ・**進捗表には入れない。**（たまごさん「重くなる」）箱と同じ推測されないURLの1枚にする。
  ・**台帳の原本は公開しない。**status/nagekomi.jsonl は .gitignore のまま。
    ここが**公開してよい列だけを写した写し**を status/public/nagekomi_list.json に吐く。
    ★過去にツイート47,011件を誤公開した事故がある。だから「除くものを選ぶ」のではなく
      **出すものを名指しで選ぶ**（allowlist）。知らない列は絶対に外へ出ない。
  ・**今どうなっているかは3つだけ。**届いた／棚に入った／入れられない（＋理由1行）。
  ・**新しい常駐を増やさない。**心臓(heartbeat.sh)に相乗りする。1秒かからない。

■ 出す列（これ以外は1つも出さない）
    at     時刻
    title  題名
    channel チャンネル名
    shelf  棚
    memo   ひとこと（たまごさんが喋った言葉）
    state  届いた / 棚に入った / 入れられない
    why    入れられないときの理由1行
    kind   youtube / x / web（絵文字の出し分けだけに使う）

■ 使い方
    python3 tools/nagekomi_list.py          … 写しを作り直す
    python3 tools/nagekomi_list.py --show   … 中身を見る
"""
import argparse
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
JST = timezone(timedelta(hours=9))

LEDGER = os.path.join(STATUS, "nagekomi.jsonl")
IRETA = os.path.join(STATUS, "nagekomi_ireta.jsonl")
OUT = os.path.join(STATUS, "public", "nagekomi_list.json")
# ★中継所(relay_server)は status/ 直下しか配らない。家の中・トンネル経由で「押した瞬間」に
#   出すために、同じ中身を status/ 直下にも置く（公開されるのは public/ の方だけ）。
OUT_LIVE = os.path.join(STATUS, "nagekomi_list.json")
LIMIT = 200   # 新しい順に200件まで（スマホで開けなくならない上限）

# ★個人が特定できる形のものは、写す前にここで落とす。
#   memo はたまごさんが喋った言葉なので、うっかり混ざる形だけを潰す。
SCRUB = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "（メール伏せ）"),
    (re.compile(r"0\d{1,4}-?\d{1,4}-?\d{3,4}"), "（電話伏せ）"),
    (re.compile(r"/Users/[^\s\"']+"), "（場所伏せ）"),
    (re.compile(r"https?://\d{1,3}(?:\.\d{1,3}){3}[^\s\"']*"), "（家の中の道 伏せ）"),
    (re.compile(r"https?://[a-z0-9-]+\.(?:loca\.lt|trycloudflare\.com)[^\s\"']*"), "（中継所 伏せ）"),
    (re.compile(r"(?i)(sk-|ghp_|github_pat_|AIza)[A-Za-z0-9_\-]{10,}"), "（鍵 伏せ）"),
]


def scrub(s):
    s = "" if s is None else str(s)
    for pat, rep in SCRUB:
        s = pat.sub(rep, s)
    return s.strip()


def short(s):
    """理由は1行。長い機械の泣き言は先頭だけにする（読んで次の一手が分かる長さ）。"""
    s = scrub(s).split(" ／ ")[0].split("：")[0].strip()
    return s[:56] + "…" if len(s) > 56 else s


def read_jsonl(path):
    rows = []
    try:
        for line in io.open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        pass
    return rows


def build():
    rows = read_jsonl(LEDGER)

    # 棚に入ったもの（戻されたものは除く）
    ireta = {}
    for r in read_jsonl(IRETA):
        if r.get("modoshiAt"):
            continue
        if r.get("id"):
            ireta[r["id"]] = r

    # 棚入れ便が「入れられなかった」と言ったもの（理由つき）
    ng, ran_at = {}, ""
    try:
        d = json.load(io.open(os.path.join(STATUS, "public", "nagekomi_shelf.json"),
                              encoding="utf-8"))
        ran_at = str(d.get("ranAt") or "")
        for r in (d.get("mitei") or []) + (d.get("skip") or []) + (d.get("red") or []):
            if isinstance(r, dict) and r.get("id"):
                ng[r["id"]] = r.get("why") or r.get("reason") or "行き先の棚が決まっていません"
    except Exception:
        pass

    out = []
    for r in rows:
        rid = r.get("id") or ""
        if rid in ireta:
            state, why = "棚に入った", ""
        elif rid in ng and str(r.get("at") or "") <= ran_at:
            # ★棚入れ便より後に入ってきたものに、古い判定を貼らない（「入れられない」の嘘を作らない）
            state, why = "入れられない", short(ng[rid])
        elif str(r.get("status") or "") in ("failed", "error"):
            state = "入れられない"
            why = short(r.get("why") or r.get("error") or "理由が残っていません")
        else:
            state, why = "届いた", ""

        out.append({
            "at": scrub(r.get("at"))[:16],
            "title": scrub(r.get("title"))[:120] or "（題名が取れませんでした）",
            "channel": scrub(r.get("channel"))[:60],
            "shelf": scrub(r.get("shelf"))[:40],
            "memo": scrub(r.get("memo"))[:200],
            "state": state,
            "why": why,
            "kind": str(r.get("kind") or "web")[:12],
        })

    out.reverse()                      # ★新しい順
    out = out[:LIMIT]
    return {
        "builtAt": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
        "total": len(rows),
        "shown": len(out),
        "counts": {
            "届いた": sum(1 for x in out if x["state"] == "届いた"),
            "棚に入った": sum(1 for x in out if x["state"] == "棚に入った"),
            "入れられない": sum(1 for x in out if x["state"] == "入れられない"),
        },
        "items": out,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    d = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    json.dump(d, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    try:
        tmp2 = OUT_LIVE + ".tmp"
        json.dump(d, io.open(tmp2, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp2, OUT_LIVE)
    except Exception:
        pass
    if a.show:
        print(json.dumps(d, ensure_ascii=False, indent=1))
    else:
        print("一覧を作り直しました：%d件（届いた%d／棚に入った%d／入れられない%d）"
              % (d["shown"], d["counts"]["届いた"], d["counts"]["棚に入った"],
                 d["counts"]["入れられない"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
