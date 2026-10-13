#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1036番【税金ライン・2区＝裏を取る】安い順に叩いて、取れたら次へ行かない。

━━ たまごさん（2026-09-23・原文）━━

  「ひたすら裏取りしてまとめてくれるエージェントは誰がいいかね。
    俺、これわざわざアナログでもう調べたくないのよ。」
  「誰かを悪者にしようっていうんじゃなくて、そういうズルができないような社会にしたい。」

━━ 順番（★これが一番大事。安い順。通ったらそこで止めて次の種へ）━━

  ① 貼ってあるURL   … ノートに既に貼られているURLを叩いて HTTPコードを付ける（0円）
  ② e-Gov法令API     … 条文。キー不要（0円）
  ③ 国会会議録API    … 国会での発言。キー不要（0円）
  ④ 手元のCSV        … 行政事業レビュー／調達ポータル（0円・落としてあれば）
  ⑤ 外部AI           … ★ここまでで取れないものだけ。このファイルは投げない。
                        status を「外部待ち」にして tools/nageru.py に渡す口だけ作る。

  ★取れなかったら「取れず」と書いて次へ進む。止まらない。
  ★`sekisho-jijitsu-shutten` の決まり：**出典の取れない断定は書かない。**

━━ 出典として認める形（kazu_gate.py と同じ。これ以外は出典ではない）━━

  url   叩いたURL ＋ HTTPコード ＋ 時刻

  ★返ってきたURLは必ずこちらで叩く。叩いていないURLを出典に書かない
    （Julesのときに未確認のまま残した。同じ穴を二度掘らない）

━━ サンドボックスからは出られない（2026-09-23 実測）━━

  $ curl -s -o /dev/null -w "%{http_code}" https://laws.e-gov.go.jp/api/2/keyword?keyword=相続税
    → 000（つながらない）
  $ curl -s -o /dev/null -w "%{http_code}" https://kokkai.ndl.go.jp/api/speech?any=税金
    → 000（つながらない）

  ＝ **このファイルは Mac の上で走らせる。**status/mac_jobs/pending/ に .sh を置く。

━━ 使い方 ━━

    python3 tools/zeikin_uratori.py --limit 5        # 未の種を5件ぶん裏取りする
    python3 tools/zeikin_uratori.py --id <id>        # 1件だけ
    python3 tools/zeikin_uratori.py --count          # 3つの数字だけ出す
    python3 tools/zeikin_uratori.py --probe          # APIが生きているかだけ叩く

終了コード: 0=正常 / 1=1件も叩けなかった（★赤。黙って0件で終わらせない）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUTDIR = os.path.join(REPO, "status", "uratori")
DAICHO = os.path.join(OUTDIR, "dane.jsonl")
LOG = os.path.join(OUTDIR, "uratori.log")
COUNTS = os.path.join(OUTDIR, "counts.json")

JST = timezone(timedelta(hours=9))

EGOV = "https://laws.e-gov.go.jp/api/2/keyword?keyword={kw}&limit=3"
KOKKAI = ("https://kokkai.ndl.go.jp/api/speech?any={kw}"
          "&recordPacking=json&maximumRecords=3")

# ★検索語はここから拾う。claim の書き換えではない（claim は原文のまま触らない）。
#   長い語から先に当てる。
KEYWORDS = [
    "国際観光旅客税", "文書通信交通滞在費", "復興特別所得税", "森林環境税",
    "政党交付金", "官房機密費", "特別会計", "予備費", "政治資金",
    "相続税", "贈与税", "消費税", "所得税", "法人税", "住民税", "事業税",
    "揮発油税", "ガソリン税", "たばこ税", "酒税", "印紙税", "固定資産税",
    "自動車税", "軽自動車税", "出国税", "金融所得課税", "給与所得控除",
    "基礎控除", "配偶者控除", "扶養控除", "年末調整", "確定申告", "源泉徴収",
    "インボイス", "定額減税", "補助金", "交付金", "基金", "天下り",
    "社会保険料", "国民年金", "厚生年金", "国民健康保険", "後期高齢者",
    "軽減税率", "益税", "内部留保", "租税特別措置",
]


def _now() -> str:
    return datetime.now(JST).strftime("%F %T")


def hit(url: str, timeout: int = 25):
    """URLを叩いて (HTTPコード, 本文) を返す。★叩いた事実だけを出典にする。"""
    try:
        p = subprocess.run(
            ["curl", "-sL", "-o", "-", "-w", "\n@@CODE@@%{http_code}",
             "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 10)
        out = p.stdout or ""
        if "@@CODE@@" in out:
            body, code = out.rsplit("@@CODE@@", 1)
            return code.strip(), body
        return "000", out
    except Exception:
        return "000", ""


def src(url: str, code: str) -> dict:
    return {"kind": "url", "url": url, "http": code, "at": _now()}


def keywords_of(claim: str):
    found = [k for k in KEYWORDS if k in claim]
    return found[:2]


def load_rows():
    rows = []
    if not os.path.exists(DAICHO):
        return rows
    with open(DAICHO, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows


def save_rows(rows):
    tmp = DAICHO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, DAICHO)


def uratori_one(r: dict) -> dict:
    """1件の裏を取る。★安い順。通ったらそこで止める。"""
    srcs = list(r.get("source") or [])
    tried = []

    # ① ノートに貼ってあるURL
    for u in (r.get("urls") or [])[:3]:
        code, _ = hit(u)
        tried.append("貼ってあるURL %s -> %s" % (u[:60], code))
        srcs.append(src(u, code))
        if code.startswith("2"):
            r["source"] = srcs
            r["status"] = "済"
            r["uratori_at"] = _now()
            r["uratori_by"] = "貼ってあるURL"
            r["tried"] = tried
            return r

    kws = keywords_of(r.get("claim", ""))
    if not kws:
        r["source"] = srcs
        r["status"] = "取れず"
        r["uratori_at"] = _now()
        r["naze"] = "主張の中に、条文・会議録を引ける語が1つも無い（検索語なし）"
        r["tried"] = tried
        return r

    # ② e-Gov法令API（条文）
    for kw in kws:
        url = EGOV.format(kw=urllib.parse.quote(kw))
        code, body = hit(url)
        tried.append("e-Gov %s -> %s (%dB)" % (kw, code, len(body)))
        srcs.append(src(url, code))
        if code.startswith("2") and len(body) > 200 and '"' in body:
            r["source"] = srcs
            r["status"] = "済"
            r["uratori_at"] = _now()
            r["uratori_by"] = "e-Gov法令API"
            r["hiki"] = kw
            r["tried"] = tried
            return r

    # ③ 国会会議録API（発言）
    for kw in kws:
        url = KOKKAI.format(kw=urllib.parse.quote(kw))
        code, body = hit(url)
        n = 0
        try:
            n = int(json.loads(body).get("numberOfRecords") or 0)
        except Exception:
            pass
        tried.append("国会会議録 %s -> %s (%d件)" % (kw, code, n))
        srcs.append(src(url, code))
        if code.startswith("2") and n > 0:
            r["source"] = srcs
            r["status"] = "済"
            r["uratori_at"] = _now()
            r["uratori_by"] = "国会会議録API"
            r["hiki"] = kw
            r["kensuu"] = n
            r["tried"] = tried
            return r

    # ④⑤ ここまでで取れない → 止まらずに「取れず」と書いて次へ
    r["source"] = srcs
    r["status"] = "取れず"
    r["uratori_at"] = _now()
    r["naze"] = "①貼ってあるURL ②e-Gov ③国会会議録 の3つとも空振り。次は外部AI（4区の手前）"
    r["tried"] = tried
    return r


def write_counts(rows):
    c = {
        "machi": sum(1 for r in rows if r.get("status") == "未"),
        "toreta": sum(1 for r in rows if r.get("status") == "済"),
        "torezu": sum(1 for r in rows if r.get("status") == "取れず"),
        "at": _now(),
    }
    os.makedirs(OUTDIR, exist_ok=True)
    with open(COUNTS, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=1)
    return c


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--id", default=None)
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()

    if args.probe:
        for name, url in (("e-Gov", EGOV.format(kw=urllib.parse.quote("相続税"))),
                          ("国会会議録", KOKKAI.format(kw=urllib.parse.quote("税金")))):
            code, body = hit(url)
            print("%s  %s  %s  %dB  %s" % (_now(), name, code, len(body), url[:90]))
        return 0

    rows = load_rows()
    if args.count:
        print(json.dumps(write_counts(rows), ensure_ascii=False))
        return 0
    if not rows:
        print("台帳が空です。先に 1区（tools/zeikin_hiroi.py）を走らせてください。")
        return 1

    target = [r for r in rows
              if (r.get("id") == args.id) if args.id] or \
             [r for r in rows if r.get("status") == "未"][: args.limit]
    if not target:
        print("未の種がありません（台帳%d件）" % len(rows))
        return 0

    done = 0
    for r in target:
        before = r.get("status")
        uratori_one(r)
        done += 1
        print("[%s→%s] %s" % (before, r["status"], (r.get("claim") or "")[:56]))
        for t in r.get("tried", []):
            print("    " + t)

    save_rows(rows)
    c = write_counts(rows)
    msg = "%s 裏取り: 走った%d件 / 裏取り待ち%d・裏が取れた%d・取れなかった%d" % (
        _now(), done, c["machi"], c["toreta"], c["torezu"])
    print(msg)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

    # ★「走った回数>0なのに取れた回数=0」は赤。黙って飲み込まない
    if done > 0 and c["toreta"] == 0:
        print("★赤：走ったのに1件も取れていません。APIの口が閉じている可能性があります。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
