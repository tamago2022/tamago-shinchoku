#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案件ごとの家計簿（2026-10-11）

━━ なぜ作ったか（たまごさん原文）━━
  「『テスト1 水彩画バージョンでいくら』みたいに、案件ごとのコストを家計簿みたいに全部つけて。把握したい」

━━ 決めたこと ━━
  ① 外部API（fal／Gemini／xAI ほか）に払った分を、1回＝1行で status/kakeibo.jsonl に書く。
     列：日時・案件名・サービス・モデル・枚数/秒数・ドル・円・確定/推定・出どころ。
  ② **案件名が無い行は書かせない**（AnkenNashi で止まる）。案件名は引数か環境変数 TAMAGO_ANKEN。
     fal・Gemini・xAI を叩く道具は、叩く前に anken_hissu() を通す（tools/yosan.py の mitsumori も通す）。
  ③ 過去の記録（fal の予算台帳・status/ink/*/cost_log.jsonl・yosan.jsonl の「使った」・
     status/ta_new/kakin.jsonl・fal 画面の見た数字）は、ページを作るたびに読み直して同じ表に並べる。
     ★書き写さない（正本を2つにしない）。
  ④ 確定＝請求画面・カード・APIが返した実額。推定＝単価×量で出した額。分からないところは「不明」。
  ⑤ AIを1回も呼ばない。足し算とファイルだけ。課金0。

━━ 使い方 ━━
    python3 tools/kakeibo.py                 # 集めて status/public/kakeibo.json と share/check/kakeibo.html を作る
    python3 tools/kakeibo.py --add 案件 fal fal-ai/flux-2/flash "1枚" --usd 0.005   # 手で1行
    python3 tools/kakeibo.py --check FILE    # このファイルは fal/Gemini/xAI を家計簿なしで叩くか（関所が使う）
    python3 tools/kakeibo.py --self-test

  コードから：
    import kakeibo
    anken = kakeibo.anken_hissu()            # 案件名が無ければここで止まる（TAMAGO_ANKEN="水彩トーン v2" など）
    ...叩く...
    kakeibo.kiroku(anken, "fal", "fal-ai/flux-2/flash/edit", "1枚", usd=0.0096, kakutei="推定")
"""
from __future__ import annotations

import argparse
import glob
import html
import io
import json
import os
import re
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
DAICHO = os.path.join(STATUS, "kakeibo.jsonl")
OUT_JSON = os.path.join(STATUS, "public", "kakeibo.json")
OUT_HTML = os.path.join(REPO, "share", "check", "kakeibo.html")
PAGE_URL = "https://tamago2022.github.io/tamago-shinchoku/share/check/kakeibo.html"
JST = timezone(timedelta(hours=9))
MAX_BYTES = 1_000_000  # 1MBの関所

# 案件名を必須にするサービス（たまごさん指定：fal・Gemini・xAI）
HISSU = {"fal", "gemini", "xai"}
SVC_LABEL = {"fal": "fal", "gemini": "Gemini", "xai": "xAI", "openai": "OpenAI",
             "typesafe": "TypeSafe(Jev)", "devin": "Devin", "genspark": "Genspark",
             "anthropic": "Anthropic API", "eleven": "ElevenLabs"}


class AnkenNashi(Exception):
    """案件名が無い呼び出し。叩いてはいけない。"""


def _now():
    return datetime.now(JST)


def usd_yen():
    try:
        d = json.load(io.open(os.path.join(STATUS, "okane", "kawase.json"), encoding="utf-8"))
        return float(d["jpy"]), "%s（%s）" % (d.get("moto", ""), d.get("date", ""))
    except Exception:
        return 158.23, "既定値（status/okane/kawase.json が読めない）"


def anken_hissu(anken=None, svc=""):
    a = (anken or os.environ.get("TAMAGO_ANKEN") or "").strip()
    if not a:
        raise AnkenNashi(
            "★案件名がありません。止めました（家計簿・2026-10-11）。%s"
            "\n  叩く前に案件名を付けてください：TAMAGO_ANKEN=\"水彩トーン v2\" python3 ...  "
            "／ コードなら kakeibo.anken_hissu(\"水彩トーン v2\")" % ("（%s）" % svc if svc else ""))
    return a


def kiroku(anken, svc, model="", ryou="", usd=None, yen=None, kakutei="推定", moto="", at=None):
    """1回＝1行。案件名が無ければ AnkenNashi。"""
    anken = anken_hissu(anken, svc)
    rate, _ = usd_yen()
    if yen is None and usd is not None:
        yen = float(usd) * rate
    row = {"at": at or _now().isoformat(timespec="seconds"), "anken": anken,
           "svc": SVC_LABEL.get(svc, svc), "model": model or "不明", "ryou": ryou or "不明",
           "usd": None if usd is None else round(float(usd), 5),
           "yen": None if yen is None else round(float(yen), 3),
           "kakutei": kakutei if kakutei in ("確定", "推定") else "推定", "moto": moto}
    os.makedirs(os.path.dirname(DAICHO), exist_ok=True)
    with io.open(DAICHO, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


# ---------------------------------------------------------------------------
# 関所の判定（tools/stop_kanmon/kakeibo_kanmon.mjs が呼ぶ）
# ---------------------------------------------------------------------------
KUCHI_RX = {
    "fal": re.compile(r"queue\.fal\.run|//fal\.run|fal_client"),
    "gemini": re.compile(r"generativelanguage\.googleapis\.com/v1\w*/models/[^\"'\s]*:(generateContent|streamGenerateContent|predict|bidiGenerateContent)|generateContent"),
    "xai": re.compile(r"api\.x\.ai/v1/(chat|images|responses|realtime|audio|video)"),
}
TOORU = re.compile(r"kakeibo|yosan\.mitsumori|#\s*kakeibo:\s*課金なし|//\s*kakeibo:\s*課金なし")


def check_text(text):
    if not text or TOORU.search(text):
        return []
    out = []
    for svc, rx in KUCHI_RX.items():
        if rx.search(text):
            out.append({"svc": svc, "why": "%s を叩くのに家計簿（案件名）を通していない" % SVC_LABEL[svc]})
    return out


# ---------------------------------------------------------------------------
# 集める（正本はそれぞれの台帳。ここは読むだけ）
# ---------------------------------------------------------------------------
def _jl(path):
    out = []
    if not os.path.exists(path):
        return out
    for ln in io.open(path, encoding="utf-8", errors="ignore"):
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def _svc_of(model):
    m = (model or "").lower()
    if m.startswith("gemini") or "imagen" in m:
        return "Gemini"
    if m.startswith("grok") or m.startswith("xai/") and "fal" not in m:
        return "fal"  # xai/grok-imagine-video は fal 経由
    return "fal"


# status/ink/<dir> → 案件名（★名前は、たまごさんの呼び方に寄せる）
INK = {
    "proto": "棒人間 試作",
    "char": "キャラ版 v1",
    "char2": "水彩トーン v2",
    "long8": "水彩 8分テスト",
}

# fal の予算台帳の題 → 案件名（上から順に最初に当たったもの）
FAL_MAP = [
    (r"^キャラ版|^8分テスト", None),  # status/ink の cost_log 側が正本（1枚ずつ載っている）。二重に数えない
    (r"わえちゃん.*顔だけ", "わえちゃん変身 顔だけ差し替え（v3）"),
    (r"わえちゃん変身動画 v2|わえちゃん変身動画 2本目", "わえちゃん変身 v2"),
    (r"わえちゃん変身動画 青い髪", "わえちゃん変身 青い髪・音付き"),
    (r"わえちゃん変身動画", "わえちゃん変身 v1"),
    (r"卵劇場", "卵劇場EP01 松竹梅"),
    (r"アンビエント動画 *・*安いモデル|早見表", "アンビエント 安いモデル早見表"),
    (r"花・湖・山", "花・湖・山のアンビエント動画"),
    (r"日本の風景", "日本の風景60秒動画"),
    (r"ZEN", "ZEN 海辺・茶室の動画"),
    (r"読み聞かせ", "読み聞かせ絵本の声"),
]


def _fal_anken(title):
    for rx, name in FAL_MAP:
        if re.search(rx, title or ""):
            return name, True
    return (title or "不明"), True


def collect():
    rate, rate_src = usd_yen()
    rows = []

    def add(**r):
        if r.get("yen") is None and r.get("usd") is not None:
            r["yen"] = round(float(r["usd"]) * rate, 3)
        r.setdefault("kakutei", "推定")
        r.setdefault("ryou", "不明")
        r.setdefault("model", "不明")
        rows.append(r)

    # ① これからの正本
    for r in _jl(DAICHO):
        r = dict(r)
        r["moto"] = r.get("moto") or "status/kakeibo.jsonl"
        add(**r)

    # ② status/ink/*/cost_log.jsonl（1回ずつの記録）
    for d, name in INK.items():
        for r in _jl(os.path.join(STATUS, "ink", d, "cost_log.jsonl")):
            model = r.get("model") or "不明"
            svc = _svc_of(model)
            if r.get("kind") == "tts" or "tts" in model:
                ryou = "読み上げ %s トークン" % (r.get("output_tokens") or "?")
            else:
                ryou = "画像1枚" + ("（%s）" % r["what"] if r.get("what") else "")
            exact = r.get("usd_exact")
            add(at=str(r.get("at") or "")[:19], anken=name, svc=svc, model=model, ryou=ryou,
                usd=exact if exact is not None else r.get("usd"),
                yen=r.get("yen_exact") if exact is not None else r.get("yen"),
                kakutei="推定", moto="status/ink/%s/cost_log.jsonl%s" % (d, "（%s）" % r["note"] if r.get("note") else ""))

    # ③ fal の予算台帳
    try:
        led = json.load(io.open(os.path.join(STATUS, "fal_cost_ledger.json"), encoding="utf-8"))
    except Exception:
        led = {"records": []}
    for r in led.get("records", []):
        name, _ = _fal_anken(r.get("title"))
        if name is None:
            continue
        cnt = r.get("count")
        fail = r.get("result") == "failed_no_charge"
        add(at=str(r.get("recordedAt") or r.get("date") or "")[:19] or r.get("date"),
            anken=name, svc="fal", model=r.get("model") or "不明",
            ryou=("%s（%s回）" % (r.get("what") or "", cnt)) if r.get("what") else ("%s回" % cnt if cnt else "不明"),
            usd=r.get("totalCostUsd"), yen=r.get("totalCostYen"),
            kakutei="確定" if fail else "推定",
            moto="status/fal_cost_ledger.json（%s）%s" % (r.get("title", "")[:40], "・失敗＝課金なし" if fail else ""))

    # ④ 予算の栓（yosan.jsonl）の「使った」。★kakeibo へ直接書いた行（kakeibo=True）は①と重なるので外す
    for r in _jl(os.path.join(STATUS, "yosan.jsonl")):
        if r.get("kind") != "使った" or r.get("kakeibo"):
            continue
        s = r.get("saifu")
        what = r.get("what") or ""
        if r.get("anken"):
            name = r["anken"]
        elif "外部検品ゲート" in what:
            name = "外部検品ゲート（鬼監督）"
        elif "依頼の門" in what:
            name = "依頼の門（Jev判定）"
        else:
            name = what or "不明"
        add(at=str(r.get("at"))[:19], anken=name, svc=SVC_LABEL.get(s, s), model="不明",
            ryou=r.get("src") or "1回", usd=r.get("usd"), yen=r.get("yen"), kakutei="推定",
            moto="status/yosan.jsonl（%s）" % what[:40])

    # ⑤ トーキングアバターの本番検品（xAI 声）
    for r in _jl(os.path.join(STATUS, "ta_new", "kakin.jsonl")):
        add(at=str(r.get("at"))[:16], anken="トーキングアバター", svc="xAI", model="xAI Voice（Grok）",
            ryou="%s秒" % r.get("sec", "?"), usd=None, yen=r.get("yen"),
            kakutei="確定" if r.get("src") == "画面の円表示" else "推定",
            moto="status/ta_new/kakin.jsonl（%s%s）" % (r.get("what", "")[:30], "・" + r["note"] if r.get("note") else ""))

    # ⑥ fal 画面で見た日別（発注元が分かっていないもの）
    try:
        mita = json.load(io.open(os.path.join(STATUS, "fal", "mita.json"), encoding="utf-8"))
    except Exception:
        mita = {}
    for r in mita.get("hibetsu", []):
        add(at=r.get("date"), anken="不明（fal画面にだけある発注）", svc="fal", model=r.get("model"),
            ryou="不明", usd=r.get("usd"), kakutei="確定", moto="status/fal/mita.json（%s）" % r.get("moto", "")[:40])

    rows.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    return rows, rate, rate_src


def summarize(rows):
    kon = _now().strftime("%Y-%m")
    by = defaultdict(lambda: {"yen": 0.0, "yenKon": 0.0, "n": 0, "kakutei": 0, "svc": set(), "first": "", "last": ""})
    svc_kon = defaultdict(float)
    tot = tot_kon = kakutei_kon = 0.0
    fumei = 0
    for r in rows:
        y = r.get("yen")
        a = by[r["anken"]]
        a["n"] += 1
        a["svc"].add(r["svc"])
        at = str(r.get("at") or "")
        a["first"] = min(a["first"] or at, at)
        a["last"] = max(a["last"], at)
        if y is None:
            fumei += 1
            continue
        a["yen"] += y
        tot += y
        if at.startswith(kon):
            a["yenKon"] += y
            tot_kon += y
            svc_kon[r["svc"]] += y
            if r.get("kakutei") == "確定":
                kakutei_kon += y
        if r.get("kakutei") == "確定":
            a["kakutei"] += 1
    anken = [{"anken": k, "yen": round(v["yen"], 1), "yenKon": round(v["yenKon"], 1), "n": v["n"],
              "kakuteiN": v["kakutei"], "svc": "・".join(sorted(v["svc"])), "first": v["first"][:10], "last": v["last"][:10]}
             for k, v in by.items()]
    anken.sort(key=lambda x: (x["last"], x["yen"]), reverse=True)
    return {"kon": kon, "totalKon": round(tot_kon, 1), "kakuteiKon": round(kakutei_kon, 1),
            "total": round(tot, 1), "fumeiN": fumei, "anken": anken,
            "svcKon": {k: round(v, 1) for k, v in sorted(svc_kon.items(), key=lambda x: -x[1])}}


def subsc():
    """お金の一目台帳（tools/okane_ichimai.py）の結果を読むだけ。Gmail はこちらから開かない。"""
    try:
        d = json.load(io.open(os.path.join(STATUS, "public", "okane_ichimai.json"), encoding="utf-8"))
    except Exception:
        return {"ok": False, "why": "status/public/okane_ichimai.json が読めない（不明）"}
    rows = []
    for r in d.get("rows", []):
        rows.append({"name": r.get("name"), "shurui": r.get("shurui"), "kubun": r.get("kubun"),
                     "kingaku": re.sub(r"<[^>]+>", " ", str(r.get("kingaku") or "不明")).strip(),
                     "yenKon": r.get("yenKon"), "tsugi": r.get("tsugi") or "不明",
                     "tsukau": r.get("tsukau") or "不明", "kouho": bool(r.get("kouho"))})
    return {"ok": True, "generatedAt": d.get("generatedAt"), "gokei": d.get("gokei"),
            "mikomiYen": d.get("mikomiYen"), "rows": rows}


# ---------------------------------------------------------------------------
# ページ
# ---------------------------------------------------------------------------
def _yen(v):
    if v is None:
        return "不明"
    if v < 10:
        return "%.2f円" % v
    return "{:,}円".format(int(round(v)))


def render(data):
    e = html.escape
    s = data["sum"]
    sb = data["subsc"]
    kon_m = int(s["kon"][5:])
    sub_kon = sb.get("gokei") if sb.get("ok") else None
    h = []
    h.append("""<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>案件ごとの家計簿</title>
<style>
body{font-family:-apple-system,"Hiragino Sans",sans-serif;margin:0;background:#faf8f3;color:#222;font-size:15px}
.w{max-width:760px;margin:0 auto;padding:14px}
h1{font-size:20px;margin:6px 0}h2{font-size:16px;margin:22px 0 6px;border-left:4px solid #b33;padding-left:8px}
.big{font-size:30px;font-weight:700}.k{color:#777;font-size:12px}
.card{background:#fff;border:1px solid #e3ddd0;border-radius:10px;padding:12px;margin:8px 0}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #eee;padding:6px 4px;text-align:left;vertical-align:top}
th{background:#f3efe6;position:sticky;top:0}.r{text-align:right;white-space:nowrap}
.tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:8px;background:#eee}
.tag.k1{background:#d9f0dc}.tag.k0{background:#fbe8c8}
details{margin:6px 0}summary{cursor:pointer;font-weight:600}
.scroll{overflow-x:auto}
a{color:#a33}
</style>""")
    h.append('<div class="w"><p class="k"><a href="../../index.html">← 進捗表</a></p>')
    h.append("<h1>案件ごとの家計簿</h1>")
    h.append('<p class="k">作成 %s ／ 1ドル=%.2f円（%s）</p>' % (e(data["generatedAt"]), data["rate"], e(data["rateSrc"])))
    h.append('<div class="card"><div class="k">%d月の外部API（fal・Gemini・xAI ほか）</div><div class="big">%s</div>'
             '<div class="k">うち確定 %s ／ 残りは単価×量の推定%s</div></div>'
             % (kon_m, _yen(s["totalKon"]), _yen(s["kakuteiKon"]),
                "。金額が分からない行 %d件は入っていない" % s["fumeiN"] if s["fumeiN"] else ""))
    if sub_kon is not None:
        h.append('<div class="card"><div class="k">%d月にカードから引かれたサブスク等（お金の一目台帳）</div><div class="big">%s</div>'
                 '<div class="k">月末までに引かれる見込み あと %s ／ 2つを足すと %s</div></div>'
                 % (kon_m, _yen(sub_kon), _yen(sb.get("mikomiYen")), _yen((sub_kon or 0) + s["totalKon"])))
    else:
        h.append('<div class="card">サブスク：不明（%s）</div>' % e(sb.get("why", "")))
    if s["svcKon"]:
        h.append('<p class="k">%d月のサービス別：%s</p>' % (kon_m, "　".join("%s %s" % (e(k), _yen(v)) for k, v in s["svcKon"].items())))

    h.append("<h2>案件ごとの小計</h2><div class='scroll'><table><tr><th>案件</th><th class='r'>%d月</th><th class='r'>全期間</th><th>サービス</th><th>回数</th><th>期間</th></tr>" % kon_m)
    for a in s["anken"]:
        h.append("<tr><td>%s</td><td class='r'>%s</td><td class='r'>%s</td><td>%s</td><td>%d</td><td class='k'>%s〜%s</td></tr>"
                 % (e(a["anken"]), _yen(a["yenKon"]) if a["yenKon"] else "—", _yen(a["yen"]), e(a["svc"]), a["n"], e(a["first"][5:]), e(a["last"][5:])))
    h.append("</table></div>")

    h.append("<h2>1件ずつ（新しい順）</h2>")
    groups = defaultdict(list)
    for r in data["rows"]:
        groups[r["anken"]].append(r)
    for a in s["anken"]:
        rs = groups[a["anken"]]
        h.append("<details><summary>%s　%s（%d件）</summary><div class='scroll'><table>"
                 "<tr><th>日時</th><th>サービス・モデル</th><th>量</th><th class='r'>ドル</th><th class='r'>円</th><th></th></tr>"
                 % (e(a["anken"]), _yen(a["yen"]), len(rs)))
        for r in rs:
            h.append("<tr><td class='k'>%s</td><td>%s<br><span class='k'>%s</span></td><td>%s</td><td class='r'>%s</td><td class='r'>%s</td>"
                     "<td><span class='tag %s'>%s</span><br><span class='k'>%s</span></td></tr>"
                     % (e(str(r.get("at") or "")[:16].replace("T", " ")), e(r["svc"]), e(str(r.get("model"))),
                        e(str(r.get("ryou"))), "$%.4f" % r["usd"] if r.get("usd") is not None else "—",
                        _yen(r.get("yen")), "k1" if r.get("kakutei") == "確定" else "k0", e(r.get("kakutei", "推定")),
                        e(str(r.get("moto", ""))[:90])))
        h.append("</table></div></details>")

    h.append("<h2>サブスク・定額（お金の一目台帳から）</h2>")
    if sb.get("ok"):
        h.append("<p class='k'>出どころ status/public/okane_ichimai.json（%s 作成・Gmailの領収書とカード通知を読んだ結果）。"
                 "★解約・プラン変更はこちらから押さない。</p><div class='scroll'><table><tr><th>名前</th><th>%d月に引かれた額</th><th>次</th><th>使い道</th></tr>"
                 % (e(str(sb.get("generatedAt"))), kon_m))
        for r in sb["rows"]:
            h.append("<tr><td>%s%s<br><span class='k'>%s・%s</span></td><td>%s</td><td class='k'>%s</td><td class='k'>%s</td></tr>"
                     % (e(r["name"] or "不明"), " <span class='tag k0'>解約候補</span>" if r["kouho"] else "",
                        e(r["shurui"] or "不明"), e(r["kubun"] or ""), e(r["kingaku"]), e(r["tsugi"]), e(r["tsukau"])))
        h.append("</table></div>")
    else:
        h.append("<p>不明（%s）</p>" % e(sb.get("why", "")))

    h.append("<h2>分かっていないこと</h2><ul>")
    for t in data["fumei"]:
        h.append("<li>%s</li>" % e(t))
    h.append("</ul>")
    h.append("<p class='k'>これから：fal・Gemini・xAI を叩く道具は、叩く前に案件名（TAMAGO_ANKEN）が無いと止まる。叩いたら status/kakeibo.jsonl に1行。"
             "作る道具 tools/kakeibo.py ／ 止める関所 tools/stop_kanmon/kakeibo_kanmon.mjs ／ 予算の栓 tools/yosan.py</p></div>")
    return "\n".join(h)


FUMEI = [
    "fal の画面では、9/8〜10/8 の30日で $12.46（いちばん大きいのは sync-lipsync $7.33）。工場の台帳に無い分は、どの案件か分かっていない（status/fal/mita.json）。",
    "10/8 の fal 経由 grok-imagine-video $0.76 は、発注元が分かっていない（工場のコードからは0件）。",
    "Gemini の声（読み上げ）と検品は、返ってきたトークン数×公開単価の推定。Google の請求画面とは突き合わせていない（未確認）。",
    "xAI の声（案内所 Grok Voice）は Supabase 側に記録があるが、ここからは読めていない（未確認）。",
    "わえちゃん変身（pixverse swap）は、fal が返した額ではなく単価×本数の推定。",
    "Claude Max の中で使った分（工場の作業ごとのトークン）は定額の中なので、この表の円には入れていない。",
]


def build(write=True):
    rows, rate, rate_src = collect()
    data = {"generatedAt": _now().strftime("%Y-%m-%d %H:%M"), "rate": rate, "rateSrc": rate_src,
            "sum": summarize(rows), "subsc": subsc(), "rows": rows, "fumei": FUMEI, "url": PAGE_URL}
    page = render(data)
    if len(page.encode("utf-8")) > MAX_BYTES:  # 1MBの関所：古い行の明細を削る
        keep = data["rows"]
        while len(page.encode("utf-8")) > MAX_BYTES and len(keep) > 50:
            keep = keep[: int(len(keep) * 0.8)]
            data2 = dict(data, rows=keep)
            page = render(data2)
    if write:
        os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
        os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
        small = {k: v for k, v in data.items() if k != "rows"}
        small["rowsN"] = len(rows)
        for path, body in ((OUT_JSON, json.dumps(small, ensure_ascii=False, indent=1)), (OUT_HTML, page)):
            tmp = "%s.%d.tmp" % (path, os.getpid())
            with io.open(tmp, "w", encoding="utf-8") as f:
                f.write(body)
            os.replace(tmp, path)
    return data, len(page.encode("utf-8"))


def self_test():
    global DAICHO
    keep = DAICHO
    d = tempfile.mkdtemp(prefix="kakeibo-test-")
    DAICHO = os.path.join(d, "k.jsonl")
    old_env = os.environ.pop("TAMAGO_ANKEN", None)
    res = []
    try:
        try:
            kiroku("", "fal", "fal-ai/x", "1枚", usd=0.01)
            res.append(("① 案件名なしは止まる", False))
        except AnkenNashi:
            res.append(("① 案件名なしは止まる", True))
        r = kiroku("テスト案件", "fal", "fal-ai/x", "1枚", usd=0.01)
        res.append(("② 案件名ありは1行書く・円に直す", os.path.exists(DAICHO) and r["yen"] > 0))
        os.environ["TAMAGO_ANKEN"] = "環境変数の案件"
        res.append(("③ TAMAGO_ANKEN を拾う", anken_hissu() == "環境変数の案件"))
        os.environ.pop("TAMAGO_ANKEN")
        res.append(("④ 家計簿なしで fal を叩くコードは引っかかる", bool(check_text('requests.post("https://queue.fal.run/fal-ai/flux")'))))
        res.append(("⑤ kakeibo を通すコードは通る", not check_text('import kakeibo\nrequests.post("https://queue.fal.run/fal-ai/flux")')))
        res.append(("⑥ 課金なしの印があれば通る", not check_text('# kakeibo: 課金なし（モデル一覧だけ）\nurl="https://api.x.ai/v1/chat/completions"')))
        res.append(("⑦ Gemini generateContent も引っかかる", bool(check_text('u="https://generativelanguage.googleapis.com/v1beta/models/gemini-3:generateContent"'))))
        res.append(("⑧ 関係ないコードは通る", not check_text("print('hello')")))
    finally:
        DAICHO = keep
        if old_env is not None:
            os.environ["TAMAGO_ANKEN"] = old_env
    ng = [x for x in res if not x[1]]
    print("家計簿 見本試験: %d件中 %d件 想定どおり" % (len(res), len(res) - len(ng)))
    for n, ok in res:
        print("  %s %s" % ("◯" if ok else "✕", n))
    return 1 if ng else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", nargs=4, metavar=("案件", "サービス", "モデル", "量"))
    ap.add_argument("--usd", type=float)
    ap.add_argument("--yen", type=float)
    ap.add_argument("--kakutei", action="store_true")
    ap.add_argument("--check", metavar="FILE")
    ap.add_argument("--check-stdin", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.check_stdin:
        print(json.dumps(check_text(sys.stdin.read()), ensure_ascii=False))
        return 0
    if a.check:
        hits = check_text(io.open(a.check, encoding="utf-8", errors="ignore").read())
        print(json.dumps(hits, ensure_ascii=False))
        return 1 if hits else 0
    if a.add:
        try:
            r = kiroku(a.add[0], a.add[1], a.add[2], a.add[3], usd=a.usd, yen=a.yen,
                       kakutei="確定" if a.kakutei else "推定", moto="手で入れた（--add）")
        except AnkenNashi as ex:
            print(ex)
            return 1
        print(json.dumps(r, ensure_ascii=False))
    data, size = build()
    s = data["sum"]
    print("家計簿：%s月 外部API %s（うち確定 %s）・行 %d・案件 %d・ページ %d バイト → %s"
          % (s["kon"][5:], _yen(s["totalKon"]), _yen(s["kakuteiKon"]), len(data["rows"]), len(s["anken"]), size, PAGE_URL))
    return 0


if __name__ == "__main__":
    sys.exit(main())
