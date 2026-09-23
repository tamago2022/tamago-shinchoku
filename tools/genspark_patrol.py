#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1092番【Gensparkの毎日のパトロール】

━━ たまごさん（2026-09-24・原文）━━
  「Gensparkにパトロールさせて、間違いを見つけて『ここ直した方がいい』って。
    でリサーチ力高いから『こうした方が伸びるよ』ってアイディアももらって。
    でもそれをそのままやらないで、俺が判断するから。一回俺挟んで。」

━━ 線引き（★ここを間違えない）━━
  穴・間違い・壊れている所 … ★黙ってこちらが直す。報告は1行だけ。
  アイディア・改善案       … ★絶対に勝手にやらない。番号を振って出す。
                              たまごさんが番号を言ったものだけ実行する。

━━ 決め ━━
  ・1日1回・1クレジット。残りは status/gsk/zan.json（`gsk me` は0クレジット）。
  ・10/4でプラン終了。日割りで流す（`tools/yosan.py` の栓＋この中の1日1回の栓）。
  ・たまごさんに質問しない。コピペさせない。答えはこちらが受け取る。
  ・選ばれなかった案は消さない（status/genspark_idea.md にずっと残す）。

━━ 使い方 ━━
    python3 tools/genspark_patrol.py            # 今日の分を1回（すでに流していれば何もしない）
    python3 tools/genspark_patrol.py --force    # 今日の分をもう1回（★1クレジット使う）
    python3 tools/genspark_patrol.py --1gyou    # 今日の1行だけ出す（クレジット0）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

STATUS = os.path.join(REPO, "status")
PDIR = os.path.join(STATUS, "gsk", "patrol")
IDEA = os.path.join(STATUS, "genspark_idea.md")
ANA = os.path.join(STATUS, "genspark_ana.jsonl")
ICHIGYOU = os.path.join(STATUS, "patrol_1gyou.md")
BASE = "https://joy-relief-station.lovable.app"

TOI = """あなたは「ごきげん補給所」というサイトの見回り役です。
サイト: {base}
例: {base}/cover-guide?artist=nat-king-cole&song=autumn-leaves-remastered-1987
    {base}/world/music  {base}/shelf/music/dance  {base}/search

今日やること（この2つに必ず分けて、日本語で答えてください）:

【穴】実際に見て見つかった、壊れている所・間違い・表示が崩れている所・リンク切れ・
事実の誤り。1件1行。かならず「URL ＋ 何がおかしいか」を1行で書く。無ければ「なし」。

【案】このサイトが伸びるための提案。1件1行。何をするかだけを短く書く（理由は書かない）。
多くても10個。無ければ「なし」。

形式（この形以外を書かないでください）:
【穴】
- <URL> / <何がおかしいか>
【案】
- <何をするか>
"""


SHIJI = """日本語で答えてください。見たままの事実だけを書き、推測を書かないでください。
出す形は【穴】と【案】の2つだけ。1件1行。【穴】は必ずURLを含めること。
【案】は「何をするか」だけを短く書き、理由や説明を書かないこと。多くても10個。
資料やスライドは作らないでください。文章だけを返してください。"""


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def kyou():
    return time.strftime("%Y-%m-%d")


def wakeru(text: str):
    """答えを【穴】と【案】に割る。見出しが無ければ全部『案』にはしない（勝手に実行しないため）。"""
    ana, an = [], []
    mode = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^[#\*\s]*【?\s*穴", line):
            mode = "ana"
            continue
        if re.match(r"^[#\*\s]*【?\s*(案|アイディア|提案)", line):
            mode = "an"
            continue
        if line in ("なし", "- なし", "・なし"):
            continue
        item = re.sub(r"^[-・\*\d\.\)\s]+", "", line).strip()
        if not item:
            continue
        if mode == "ana":
            ana.append(item)
        elif mode == "an":
            an.append(item)
    return ana, an[:10]


def idea_tsumu(items, hiduke):
    """案を番号つきで積む。既にある案は足さない。消さない。"""
    mochi = []
    if os.path.exists(IDEA):
        mochi = open(IDEA, encoding="utf-8").read().splitlines()
    aru = set()
    saidai = 0
    for l in mochi:
        m = re.match(r"^\|\s*(\d+)\s*\|\s*([^|]+)\|", l)
        if m:
            saidai = max(saidai, int(m.group(1)))
            aru.add(m.group(2).strip())
    atarashii = []
    for it in items:
        if it.strip() in aru:
            continue
        saidai += 1
        atarashii.append((saidai, it.strip()))
    if not os.path.exists(IDEA):
        with open(IDEA, "w", encoding="utf-8") as f:
            f.write("# Gensparkの案（★選ばれるまで実行しない。消さない）\n\n"
                    "たまごさんは番号を言うだけ。選ばれたものだけこちらが実行します。\n\n"
                    "| 番号 | 何をするか | 出た日 | 状態 |\n|---|---|---|---|\n")
    with open(IDEA, "a", encoding="utf-8") as f:
        for n, it in atarashii:
            f.write(f"| {n} | {it} | {hiduke} | まだ |\n")
    return atarashii


def ichigyou_kaku(hiduke, ana_n, naoshita_n, nokori_n, atarashii):
    os.makedirs(os.path.dirname(ICHIGYOU), exist_ok=True)
    body = [f"# 今日の1行（{hiduke}）", "",
            f"Gensparkが見つけた穴：{ana_n}件 → 直した{naoshita_n}件／残り{nokori_n}件", ""]
    if atarashii:
        body.append("アイディア：")
        for n, it in atarashii:
            body.append(f"{n}. {it}")
        body += ["", "番号を言ってもらえれば、その場でやります。"]
    else:
        body.append("アイディア：なし")
    open(ICHIGYOU, "w", encoding="utf-8").write("\n".join(body) + "\n")
    return "\n".join(body)


def sudeni_nagashita(hiduke):
    return os.path.exists(os.path.join(PDIR, hiduke + ".json"))


def _nakami(o):
    """gsk の JSON から、答えの本文らしい文字列をかき集める。"""
    buf = []

    def walk(x, key=""):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, k)
        elif isinstance(x, list):
            for v in x:
                walk(v, key)
        elif isinstance(x, str) and len(x) > 40 and key in (
                "content", "text", "answer", "result", "output", "message", "summary", "markdown"):
            buf.append(x)
    walk(o)
    return "\n".join(buf)


def gsk_task(toi, timeout=1500):
    """super_agent に1件投げて、答えの本文を返す。旗の名前が版で違うので順に試す。"""
    import genspark_nagashi as G
    last = None
    for flag in ("--query", "--prompt", "--message"):
        r = G.gsk_run(["task", "create", "super_agent",
                       "--task_name", "ごきげん補給所パトロール " + kyou(),
                       "--instructions", SHIJI, flag, toi], timeout=timeout)
        last = r
        if r.get("ok"):
            out = r.get("stdout", "")
            try:
                o = json.loads(out)
            except Exception:
                return out, r
            # すぐ返る版：task_url だけ返って中身は後から
            pid = None
            for k in ("project_id", "id", "task_id"):
                pid = (o.get("data") or {}).get(k) or o.get(k)
                if pid:
                    break
            body = _nakami(o)
            for _ in range(30):
                if body.strip() or not pid:
                    break
                time.sleep(20)
                s = G.gsk_run(["task", "status", str(pid)], timeout=120)
                try:
                    body = _nakami(json.loads(s.get("stdout", "{}")))
                except Exception:
                    body = s.get("stdout", "")
            return body or out, r
    return "", last


def hashiru(force=False):
    import genspark_nagashi as G
    hd = kyou()
    os.makedirs(PDIR, exist_ok=True)
    if sudeni_nagashita(hd) and not force:
        return {"ok": True, "skip": "今日の分はもう流しています（クレジット0）"}
    toi = TOI.format(base=BASE)
    mae = G.zandaka(record=False).get("zan")
    kotae, r = gsk_task(toi)
    ato = G.zandaka().get("zan")
    gyou = {"ok": bool(r and r.get("ok")), "残クレジット": ato,
            "使ったクレジット": (round(mae - ato, 3) if isinstance(mae, (int, float))
                          and isinstance(ato, (int, float)) else None),
            "error": None if (r and r.get("ok")) else ((r or {}).get("error")
                                                       or ((r or {}).get("stderr") or "")[:300])}
    if kotae:
        os.makedirs(os.path.join(REPO, "status", "gsk", "kotae"), exist_ok=True)
        fn = os.path.join(REPO, "status", "gsk", "kotae",
                          "patrol_%s.txt" % time.strftime("%Y%m%d-%H%M%S"))
        open(fn, "w", encoding="utf-8").write(kotae)
        gyou["答え"] = os.path.relpath(fn, REPO)
    ana, an = wakeru(kotae)
    rec = {"at": _now(), "hiduke": hd, "ok": gyou.get("ok"), "残": gyou.get("残クレジット"),
           "使った": gyou.get("使ったクレジット"), "穴": ana, "案": an,
           "答え": gyou.get("答え"), "error": gyou.get("error")}
    json.dump(rec, open(os.path.join(PDIR, hd + ".json"), "w"), ensure_ascii=False, indent=1)
    with open(ANA, "a", encoding="utf-8") as f:
        for a in ana:
            f.write(json.dumps({"at": _now(), "hiduke": hd, "moto": "genspark",
                                "ana": a, "状態": "まだ"}, ensure_ascii=False) + "\n")
    atarashii = idea_tsumu(an, hd)
    nokori = sum(1 for l in open(ANA, encoding="utf-8") if '"状態": "まだ"' in l) if os.path.exists(ANA) else 0
    rec["1行"] = ichigyou_kaku(hd, len(ana), 0, nokori, atarashii)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--1gyou", dest="ichi", action="store_true")
    a = ap.parse_args()
    if a.ichi:
        print(open(ICHIGYOU, encoding="utf-8").read() if os.path.exists(ICHIGYOU) else "まだ1回も流していません")
        return
    r = hashiru(force=a.force)
    print(json.dumps(r, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
