#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1076番【覆面客】Gensparkを「厳しいお客さん役」として常設する1本。

━━ なぜ作ったか（2026-09-24・たまごさん原文）━━

  「覆面カスタマーみたいなやつを誰にやらせた方がいいと思う。まずクラウドコードじゃないよね。
    Gensparkにやってみようか。厳しいお客さん役として。もっとこういうの置いてあった方がいいな、みたいな。
    あなたじゃない方がいいと思うね。なんかコピーがいまいちだなとか、
    ちょっと何が気になってクリックしたのかなとか、そういう擬似的のお客さんもやってもらおう。」
  「Xで見つけて『なんだろう』って入ってきた人が、これも見たい、これも見たい、
    これも気になるって作りにしましょう。」

★なぜClaudeにやらせないか：作った本人が客のふりをしても客にならない。**別の口**に言わせる。

━━ 既にある tools/fukumen.py との線引き（二重管理を作らない）━━
  tools/fukumen.py      … **機械の目**。CLS・LCP・console error を数える。AIを1回も呼ばない。0円。
  このファイル           … **客の目**。コピーが刺さるか、次を押したくなるか。Gensparkに1回1クレジット。
  数字は fukumen.py、感想はこちら。**混ぜない。**

━━ 決まり ━━
  ① ★台本は tools/prompts/fukumen_kyaku.md。中身をこのファイルに書かない（型と配管を分ける）。
  ② ★**叩く前と後の残クレジットを必ず記録する**（status/gsk_daicho.jsonl）。1回でいくつ減ったかを毎回書く。
     ★2026-09-24 実測：`gsk search` は**問いが2048字までしか通らない**（serper_http_400）。
       それでも**1クレジット引かれる**。だからこの道具は `crawl-and-answer` を使う。
       こちらは客が**自分でそのページを開いて**、問いごとに原文を引いて答える（引用が本物になる）。
  ③ ★Gensparkの答えは**要約せずそのまま**残す。status/fukumen_kyaku/<時刻>.txt が正本。
  ④ ★**客の言うことを事実として扱わない。**
     2026-09-24、前に「秋の棚0枚」を鵜呑みにして間違えた。**感想は感想。事実の主張は別に裏を取る。**
     出力の頭に必ずこの但し書きを付けて公開する。
  ⑤ ★公開先は公開リポ tamago2022/ai-kaigi（Gensparkは非公開リポを読めない）。鍵の値は1文字も書かない。
  ⑥ ★サンドボックスからは gsk に届かない。**必ずMac（心臓）側で走らせる。**

━━ 使い方（Mac側）━━

    # ① 1本通す（★1クレジット使う）
    python3 tools/fukumen_kyaku.py --url "https://joy-relief-station.lovable.app/cover-guide?artist=..&song=.." \\
        --x "Xに出す投稿文（そのまま貼る）"

    # ② 通してあるかの関所（0円）。**Xに出す前・本番に出す前にこれを通す。**
    python3 tools/fukumen_kyaku.py --kanmon "<曲ページのURL>"
    #   終了コード 0=通っている / 2=まだ覆面客に見せていない（＝出してはいけない）

    # ③ 今までの結果を並べる（0円）
    python3 tools/fukumen_kyaku.py --ichiran

  --no-koukai を付けると ai-kaigi へ出さずに手元だけに残す。
  --dry を付けるとクレジットを使わずに、投げる台本だけを表示する。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

STATUS = os.path.join(REPO, "status")
OUT_DIR = os.path.join(STATUS, "fukumen_kyaku")
DAICHO = os.path.join(STATUS, "gsk_daicho.jsonl")
LEDGER = os.path.join(OUT_DIR, "daicho.jsonl")     # URLごとの「通した」記録＝関所の正本
DAIHON = os.path.join(HERE, "prompts", "fukumen_kyaku.md")
KOUKAI_REPO = "tamago2022/ai-kaigi"
HONBUN_MAX = 6000                                   # 台本に差し込む本文の上限（問いが長すぎると通らない）

DANMARI = ("★これはお客さんの**感想**です。事実の主張（枚数・年号・有無）は裏を取っていません。"
           "鵜呑みにしないでください。")


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _append(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _rows(path):
    out = []
    try:
        for ln in io.open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
    except Exception:
        pass
    return out


# ───────────────────────── 台本を組む ─────────────────────────

def _daihon(url, xpost):
    """台本を『役（すべての問いの頭に付ける前置き）』と『問い（1行1問）』に切る。"""
    t = io.open(DAIHON, encoding="utf-8").read()
    t = (t.replace("{{URL}}", url)
          .replace("{{XPOST}}", (xpost or "（投稿文は渡されていません。URLだけを見て答えてください）").strip()))
    m = re.search(r"\n##\s*役\s*\n(.*?)\n##\s*問い\s*\n(.*)$", t, re.S)
    if not m:
        raise RuntimeError("台本に `## 役` と `## 問い` が見つかりません: %s" % DAIHON)
    yaku = m.group(1).strip()
    toi = [re.sub(r"^-\s*", "", ln).strip()
           for ln in m.group(2).splitlines() if ln.strip().startswith("- ")]
    if not toi:
        raise RuntimeError("台本の `## 問い` に1問もありません")
    return yaku, toi


def toi_wo_tsukuru(url, xpost):
    """crawl-and-answer に渡す jobs を作る。前置きは問いごとに付ける（別々に答えられるため）。"""
    yaku, toi = _daihon(url, xpost)
    return [{"url": url,
             "questions_to_answer": ["%s\n\n----\nこの前置きの役になりきって答えてください。\n%s"
                                     % (yaku, q) for q in toi]}], yaku, toi


# ───────────────────────── 点数を拾う ─────────────────────────

def tensuu(kotae):
    """答えから 軽さ／楽しさ／美しさ を拾う。拾えなければ None（勝手に埋めない）。"""
    out = {}
    for key, name in (("karusa", "軽さ"), ("tanoshisa", "楽しさ"), ("utsukushisa", "美しさ")):
        m = re.search(name + r"\s*[:：]?\s*\**\s*(\d{1,2})\s*(?:/|／|点)\s*(?:10)?", kotae)
        out[key] = int(m.group(1)) if m and 0 <= int(m.group(1)) <= 10 else None
    return out


def gouhi(kotae):
    """忖度だけの回答を落とす。辛口が1行も無いものは不合格。"""
    riyuu = []
    if len(kotae.strip()) < 200:
        riyuu.append("短すぎる（200字未満）")
    if "【⑤点数】" not in kotae and "点数" not in kotae:
        riyuu.append("点数が無い")
    t = tensuu(kotae)
    if all(v is None for v in t.values()):
        riyuu.append("3つの点数が1つも読めない")
    m = re.search(r"スベっている[^\n]{0,20}\n+(.{0,120})", kotae, re.S)
    if m and re.match(r"^\s*(なし|特になし|ありません|該当なし)", m.group(1)):
        riyuu.append("スベっている一文が『なし』（辛口が出ていない）")
    return (len(riyuu) == 0), riyuu


# ───────────────────────── 答えを取り出す ─────────────────────────

def _kotae_toridasu(stdout, toilist):
    """crawl-and-answer の返事から、読める形の答えを作る。
    ★形が想像と違っても**生のまま残す**（勝手に切り捨てない）。"""
    if not stdout:
        return ""
    if not stdout.lstrip().startswith("{"):
        return stdout
    try:
        d = json.loads(stdout)
    except Exception:
        return stdout
    if isinstance(d, dict) and d.get("status") == "error":
        return stdout

    hiroi = []

    def walk(o):
        if isinstance(o, dict):
            q = o.get("question") or o.get("question_to_answer") or o.get("q")
            a = o.get("answer") or o.get("result") or o.get("a")
            if isinstance(a, str) and a.strip():
                hiroi.append((q if isinstance(q, str) else "", a.strip()))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    if not hiroi:
        return stdout
    out, mita = [], set()
    for q, a in hiroi:
        if a in mita:
            continue
        mita.add(a)
        midashi = ""
        for t in toilist:
            m = re.match(r"^【(.+?)】", t)
            if m and q and m.group(1) in q:
                midashi = "【%s】" % m.group(1)
                break
        out.append(((midashi + "\n") if midashi else "") + a)
    return "\n\n".join(out).strip()


# ───────────────────────── 1本通す ─────────────────────────

def toosu(url, xpost="", koukai=True, dry=False, timeout=300):
    import genspark_nagashi as gn

    jobs, yaku, toilist = toi_wo_tsukuru(url, xpost)

    if dry:
        return {"ok": True, "dry": True, "yaku": yaku, "toi": toilist,
                "jobsBytes": len(json.dumps(jobs, ensure_ascii=False)), "使ったクレジット": 0.0}

    os.makedirs(OUT_DIR, exist_ok=True)
    args_file = os.path.join(OUT_DIR, "_jobs.json")
    json.dump({"jobs": jobs}, io.open(args_file, "w", encoding="utf-8"), ensure_ascii=False)

    zen = gn.zandaka(record=False).get("zan")
    t0 = time.time()
    r = gn.gsk_run(["crawl-and-answer", "--args-file", args_file], timeout=timeout)
    byou = round(time.time() - t0, 1)
    ato = gn.zandaka(record=True).get("zan")
    tsukatta = (round(zen - ato, 3) if (zen is not None and ato is not None) else None)

    kotae = _kotae_toridasu((r.get("stdout") or "").strip(), toilist)

    ok, riyuu = (gouhi(kotae) if r.get("ok") and kotae else (False, ["Gensparkが答えを返さなかった"]))
    ten = tensuu(kotae) if kotae else {"karusa": None, "tanoshisa": None, "utsukushisa": None}

    stamp = time.strftime("%Y%m%d-%H%M%S")
    os.makedirs(OUT_DIR, exist_ok=True)
    raw = os.path.join(OUT_DIR, "%s.txt" % stamp)
    io.open(raw, "w", encoding="utf-8").write(kotae or (r.get("error") or r.get("stderr") or ""))

    rec = {"at": _now(), "url": url, "xpost": xpost, "ok": ok, "gskOk": bool(r.get("ok")),
           "fugoukakuRiyuu": riyuu, "ten": ten, "秒": byou,
           "残クレジット前": zen, "残クレジット後": ato, "使ったクレジット": tsukatta,
           "kuchi": "crawl-and-answer", "kotaeFile": raw}
    _append(LEDGER, rec)
    _append(DAICHO, {"at": rec["at"], "nani": "覆面客", "url": url, "ok": ok,
                     "残クレジット": ato, "使ったクレジット": tsukatta, "答え": raw})

    rec["kotae"] = kotae
    if koukai and kotae:
        rec["koukaiUrl"] = koukai_suru(rec)
    return rec


# ───────────────────────── 公開（ai-kaigi） ─────────────────────────

def koukai_suru(rec):
    try:
        import _965_keijiban as kj
    except Exception:
        try:
            import importlib
            kj = importlib.import_module("_965_keijiban")
        except Exception as e:
            return "（公開できませんでした：%s）" % str(e)[:120]

    t = rec.get("ten") or {}
    midashi = "覆面客｜%s｜軽さ%s／楽しさ%s／美しさ%s" % (
        rec["url"].split("song=")[-1] or rec["url"],
        t.get("karusa"), t.get("tanoshisa"), t.get("utsukushisa"))
    body = "\n".join([
        DANMARI, "",
        "- 見たページ: %s" % rec["url"],
        "- 役: Xでこの投稿を見て初めて来た人（1ページだけ／サイトの事情を知らない）",
        "- 日時: %s" % rec["at"],
        "- 使ったクレジット: %s（前 %s → 後 %s）" % (rec.get("使ったクレジット"),
                                                  rec.get("残クレジット前"), rec.get("残クレジット後")),
        "- 合格判定: %s%s" % ("合格" if rec.get("ok") else "不合格",
                             ("／" + "、".join(rec.get("fugoukakuRiyuu") or [])) if not rec.get("ok") else ""),
        "", "## Xの投稿（客が見たもの）", "", "```", (rec.get("xpost") or "（なし）"), "```",
        "", "## Gensparkの答え（★要約していません。生のまま）", "",
        (rec.get("kotae") or "（空）"),
    ])
    try:
        r = kj.run_job({"repo": KOUKAI_REPO, "action": "issue", "title": midashi, "body": body})
        return r.get("url") or ("（公開できませんでした：%s）" % r.get("error"))
    except Exception as e:
        return "（公開できませんでした：%s）" % str(e)[:160]


# ───────────────────────── 関所 ─────────────────────────

def kanmon(url):
    """このURLは覆面客を通してあるか。★Xに出す前・本番に出す前に必ずここを通す。"""
    base = url.split("#")[0].strip()
    for r in reversed(_rows(LEDGER)):
        if (r.get("url") or "").split("#")[0].strip() == base:
            return r
    return None


# ───────────────────────── 入口 ─────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url")
    p.add_argument("--x", default="", help="Xに出す投稿文")
    p.add_argument("--x-file", default="")
    p.add_argument("--kanmon")
    p.add_argument("--ichiran", action="store_true")
    p.add_argument("--no-koukai", action="store_true")
    p.add_argument("--dry", action="store_true")
    a = p.parse_args()

    if a.ichiran:
        for r in _rows(LEDGER):
            t = r.get("ten") or {}
            print("%s  %s  軽%s/楽%s/美%s  %s" % (r.get("at"), "○" if r.get("ok") else "×",
                  t.get("karusa"), t.get("tanoshisa"), t.get("utsukushisa"), r.get("url")))
        return 0

    if a.kanmon:
        r = kanmon(a.kanmon)
        if not r:
            print("× まだ覆面客に見せていません。出す前に通してください：\n"
                  "  python3 tools/fukumen_kyaku.py --url \"%s\" --x \"<投稿文>\"" % a.kanmon)
            return 2
        t = r.get("ten") or {}
        print("○ %s に通してあります（軽さ%s／楽しさ%s／美しさ%s）%s"
              % (r.get("at"), t.get("karusa"), t.get("tanoshisa"), t.get("utsukushisa"),
                 "" if r.get("ok") else " ※不合格：" + "、".join(r.get("fugoukakuRiyuu") or [])))
        return 0

    if not a.url:
        p.print_help()
        return 1

    xpost = a.x
    if a.x_file:
        xpost = io.open(a.x_file, encoding="utf-8").read()

    rec = toosu(a.url, xpost, koukai=not a.no_koukai, dry=a.dry)
    if rec.get("dry"):
        print(rec["toi"])
        return 0
    print(json.dumps({k: v for k, v in rec.items() if k != "kotae"}, ensure_ascii=False, indent=1))
    print("\n--- Gensparkの答え（生）---\n")
    print(rec.get("kotae") or "（空）")
    return 0 if rec.get("ok") else 3


if __name__ == "__main__":
    sys.exit(main())
