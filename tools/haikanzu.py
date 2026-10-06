#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1066番【配管図】どこが繋がっていて、誰が補給所まで手が届くのかを**図1枚**で出す係。

たまごさん（2026-09-24・原文）:
  「図解できますか？こことここは繋がってるって。相関図みたいな。一目で目視したいんだけど、
    テキストでわーって言われてもわかんねぇわ。配管図みたいな。」
  「誰がごきげん補給所（Lovable）に働きかけられるのかとか、何ができて誰に何が向いてるのかも知りたい。」
  「得意分野が違うわけでしょ？苦手なことをやらせるのは全然良くないから。それが得意な人にやってもらう。」

━━ 決まり ━━
  ① ★**叩いて通ったものだけ緑。**状態は status/public/kaitsuu.json（実測）からしか読まない。
     このファイルは1回も外へ出ない・鍵を1つも読まない＝**0円**。
  ② ★実測していない線は描かない。推測で繋げない。空欄は「未測定」と書く。
  ③ ★数字・状態は**出典と同じ行**に持たせる（tools/kazu_gate.py は行単位で見る）。
  ④ ★書くのは OUT_HTML と OUT_JSON だけ。たまごさんのファイルを消さない・動かさない。
  ⑤ ★スマホ縦1画面に収める。図の寸法は外部AI（codex／gpt-5.6-terra）に実際に聞いた答えに従う
     （status/kiku/1066/ に原文。2026-09-24・30.6秒・0円）。

使い方:
  python3 tools/haikanzu.py            … 1日1回に間引いて描き換える
  python3 tools/haikanzu.py --force    … 今すぐ描き換える
  python3 tools/haikanzu.py --self-test
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
OUT_HTML = os.path.join(REPO, "share", "check", "1066-haikanzu.html")
OUT_JSON = os.path.join(PUBLIC, "haikanzu.json")
STAMP = os.path.join(STATUS, ".haikanzu_at")
JST = timezone(timedelta(hours=9))

KAITSUU = os.path.join(PUBLIC, "kaitsuu.json")
TEKIZAI = os.path.join(PUBLIC, "tekizai.json")

GREEN = "#16A34A"
RED = "#DC2626"
AMBER = "#D97706"
GREY = "#94A3B8"
INK = "#0F172A"

# ─────────────────────────────────────────────────────────────────────────
# 口ごとの「1語」。★状態は書かない（状態は kaitsuu.json から毎回読む）。
#   tanto  … 担当を1語。出典つき。実測が無いものは「未測定」。
#   ichite … あと1手で通るときの、その1手を1語。
#   dare   … その1手を押すのは「たまご」か「こちら」か。
#   kaitsuu… kaitsuu.json のどの行を見るか。None は kaitsuu に無い口。
# ─────────────────────────────────────────────────────────────────────────
NODES = [
    dict(id="codex", name="ChatGPT(codex)", kaitsuu=None, tanto="判定",
         tanto_moto="status/kiku_log.jsonl（2026-09-24 08:10 に1問を30.6秒・0円で返した）",
         ichite="", dare=""),
    dict(id="openai", name="ChatGPT(API)", kaitsuu="openai", tanto="検品",
         tanto_moto="1回 0.013円（status/public/gaibu_kenpin_ledger.json:13）",
         ichite="残高を入れる", dare="たまご"),
    dict(id="gemini", name="Gemini", kaitsuu="gemini", tanto="未測定",
         tanto_moto="まだ1回も叩けていない（status/public/kaitsuu.json の gemini）",
         ichite="鍵を置く", dare="たまご"),
    dict(id="xai", name="Grok(文字)", kaitsuu="xai", tanto="未測定",
         tanto_moto="文字の口は403（status/public/kaitsuu.json の xai）",
         ichite="残高を入れる", dare="たまご"),
    dict(id="xai_koe", name="Grok(声)", kaitsuu="xai_koe", tanto="声",
         tanto_moto="200 短命トークンが出た（status/public/kaitsuu.json の xai_koe）",
         ichite="", dare=""),
    dict(id="devin", name="Devin", kaitsuu="devin", tanto="実装",
         tanto_moto="26本投げてPR5本（status/1060_hikitsugi.md:10）",
         ichite="上限が開くのを待つ", dare="こちら"),
    dict(id="fal", name="fal", kaitsuu="fal", tanto="絵",
         tanto_moto="24本のうち20本を採用（status/public/fal_cost_ledger.json:13）",
         ichite="", dare=""),
    dict(id="genspark", name="Genspark", kaitsuu=None, tanto="調べ",
         tanto_moto="deep_research 1本が120秒で出典つき3件（status/1045_hikitsugi.md:14）",
         ichite="gskを入れ直す", dare="こちら"),
    dict(id="jules", name="Jules", kaitsuu=None, tanto="JSON",
         tanto_moto="149件で合格136件＝91.3%（status/1028/jules_kekka.json:6）",
         ichite="GitHubの鍵", dare="たまご"),
    dict(id="copilot", name="Copilot", kaitsuu="copilot", tanto="未測定",
         tanto_moto="まだ1件も返っていない（status/ai_daicho.jsonl:2）",
         ichite="GitHubの鍵", dare="たまご"),
    dict(id="jev", name="Jev", kaitsuu=None, tanto="判定",
         tanto_moto="13問を1本にまとめると12.2倍安い（tools/sekisho/jev_honnin.py:25）",
         ichite="鍵を置く", dare="たまご"),
    dict(id="claude", name="Claude(発車)", kaitsuu="claude", tanto="配管",
         tanto_moto="261本ぶんの実測（status/public/cost_by_task.json:10）",
         ichite="1回ログインし直す", dare="たまご"),
]

# kaitsuu.json に無い口は、**別の実測**から状態を決める。★憶測で ok にしない。
SOTO = {
    # codex は今日この場で1問返ってきた＝叩いて通った。
    "codex": ("ok", "1問が30.6秒で返った（status/kiku_log.jsonl・2026-09-24）"),
    # gsk me が FileNotFound（status/gaibu_jobs/done/20260924-080624-4956.json の cmds）
    "genspark": ("ng", "gsk me がFileNotFound（status/1034_zandaka_jissoku.json の cmds）"),
    # Jules / Jev は GitHubの鍵／鍵そのものが無い。
    "jules": ("ng", "口はGitHub Issueだけ。そのGitHubの鍵が無い（kaitsuu.json の github）"),
    "jev": ("ng", "鍵が無いので1件も聞けていない（status/1054_jev_nanken_nanen.md:33）"),
}

# 補給所（Lovable）まで手が届くか。★tekizai.json の実測（本番に出た本数）だけで決める。
#   honban>0 … 本番に出た＝太い緑 ／ tooshita>0 かつ honban=0 … PRまで＝細い緑 ／ 0本 … 線を引かない
REACH_FROM_TEKIZAI = ("devin", "jules", "fal")

# 仕事の種類 × 誰に渡すか。◯＝渡すべき／△＝渡せるが本命でない／✕＝渡さない／空＝未測定。
# ★出典のある形にだけ印を付ける（tools/tekizai.py の wariate と同じ実測から）。
SHIGOTO = ["草むしり", "塗装", "ネジ", "ガス漏れ", "新規", "調べもの", "判定", "絵", "声"]
HYO_COLS = ["claude", "devin", "jules", "genspark", "codex", "jev", "fal", "xai_koe"]
HYO = {
    #            claude devin jules gensp codex jev  fal  koe
    "草むしり":   ["△", "△", "◯", "",  "",  "",  "",  ""],
    "塗装":       ["△", "◯", "△", "",  "",  "",  "",  ""],
    "ネジ":       ["◯", "△", "△", "",  "",  "",  "",  ""],
    "ガス漏れ":   ["◯", "✕", "",  "",  "△", "",  "",  ""],
    "新規":       ["◯", "△", "",  "",  "",  "",  "",  ""],
    "調べもの":   ["△", "✕", "✕", "◯", "△", "✕", "",  ""],
    "判定":       ["△", "",  "",  "",  "◯", "◯", "",  ""],
    "絵":         ["✕", "",  "",  "",  "",  "",  "◯", ""],
    "声":         ["✕", "",  "",  "",  "",  "",  "",  "◯"],
}
HYO_MOTO = ("◯△✕の根拠＝status/public/tekizai.json の得意・苦手（実測）と "
            "status/1060_hikitsugi.md:9-12（Devin 26本の内訳と本番1本）")

# ★ズレ（得意と、実際に回している仕事が違う相手）。実測で言えるものだけ。
ZURE = {
    "devin": "得意は実装なのに、26本のうち一番多く回したのはガス漏れ11本（status/1060_hikitsugi.md:9）",
    "jules": "91.3%で通る腕があるのに、いま持たせている仕事は0本（status/public/tekizai.json）",
    "genspark": "調べものができるのに0本。10/4にクレジットが消える（status/1049_hikitsugi_irai_gate.md:13）",
}


# ★実測の生データ。関所（tools/sekisho.py の5番）は「px/%の数字を主張するなら
#   実測の跡（<pre>/<code>の生データ）を同じ紙に置け」と決めている。ここがその跡。
#   ★2026-09-24：これを置かずにpushしたら、関所が**push全体を止めた**（紙は404のまま）。
NAMA = """Jules   検品 136/149 = 91.3%   実測（status/1028/jules_kekka.json:6）
Devin   26本 → PRが返った5本 → 本番で開けた1本   実測（status/1060_hikitsugi.md:9-12）
Devin   26本の内訳 ガス漏れ11／ネジ4／草むしり4／塗装3／新規2／投げ事故2   実測（status/1060_hikitsugi.md:9）
自分    本番に出た131本   実測（status/public/uketori_machi.json:4）
fal     24本のうち20本を採用   実測（status/public/fal_cost_ledger.json:13）
codex   1問 30.6秒 0円   実測（status/gaibu_jobs/done/20260924-080950-0929.json）
Vault   直下の一覧 0.2秒 0円   実測（status/gaibu_jobs/done/20260924-081654-4204.json）
YouTube 文字起こし 7本試して0本   実測（tools/yomu.py の yt_transcript）
Notion  こちらのコネクタ 0件   実測（2026-09-24）"""


def _load(p, d=None):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def joutai():
    """口ごとの状態を実測から決める。戻り値 {id: dict(state, moto, word)}"""
    kt = _load(KAITSUU, {}) or {}
    rows = {k.get("id"): k for k in (kt.get("keys") or [])}
    tk = _load(TEKIZAI, {}) or {}
    trow = {r.get("who"): r for r in (tk.get("rows") or [])}

    out = {}
    for n in NODES:
        i = n["id"]
        if n.get("kaitsuu") and n["kaitsuu"] in rows:
            r = rows[n["kaitsuu"]]
            st = r.get("status") or "unknown"
            moto = "status/public/kaitsuu.json の %s：%s" % (n["kaitsuu"], (r.get("detail") or "")[:70])
        elif i in SOTO:
            st, moto = SOTO[i]
        else:
            st, moto = "unknown", "実測が無い"
        # 1語。★状態から機械的に決める（手で書かない）
        if st == "ok":
            word = "通"
        elif st == "unknown":
            word = "未測定"
        else:
            word = _tomari(moto)
        t = trow.get(i) or {}
        out[i] = dict(state=st, moto=moto, word=word,
                      tooshita=t.get("tooshita"), honban=t.get("honban"))
    return out


def _tomari(detail):
    """止まっている理由を1語にする。★detail の文字から機械的に決める。"""
    d = detail or ""
    if "403" in d:
        return "403"
    if "429" in d:
        return "残高0"
    if "鍵" in d and ("無" in d or "置かれていません" in d or "取れません" in d):
        return "鍵なし"
    if "FileNotFound" in d or "入っていません" in d:
        return "未導入"
    if "上限" in d or "quota" in d:
        return "上限"
    if "expired" in d or "無効" in d:
        return "切れ"
    return "止"


# ─────────────────────────────────────────────────────────────────────────
# 図（SVG）。寸法は codex に聞いた答えに従う：viewBox 0 0 360 …／左列x=78・右列x=282／
# 縦の幹線は本数を限る／横線は同じYを共有しない／枠の中に線を入れない。
# ─────────────────────────────────────────────────────────────────────────
NW, NH = 116, 30
LX, RX = 78, 282


def _node_box(x, y, name, word, tanto, color, zure, dare):
    """1個の箱。中は名前だけ。状態の1語と担当は箱のすぐ下に小さく置く。"""
    s = []
    s.append('<rect x="%d" y="%d" width="%d" height="%d" rx="7" fill="#FFFFFF" '
              'stroke="%s" stroke-width="2"/>' % (x - NW // 2, y - NH // 2, NW, NH, color))
    label = name + ("★" if zure else "")
    s.append('<text x="%d" y="%d" text-anchor="middle" font-size="12.5" font-weight="700" '
             'fill="%s">%s</text>' % (x, y + 4, INK, esc(label)))
    shita = "%s ｜ %s" % (word, tanto)
    if dare:
        shita += " 👤"
    s.append('<text x="%d" y="%d" text-anchor="middle" font-size="9.5" fill="%s">%s</text>'
             % (x, y + NH // 2 + 10, color if word != "通" else GREEN, esc(shita)))
    return "".join(s)


def _line(x1, y1, x2, y2, state, word=""):
    if state == "ok":
        st = 'stroke="%s" stroke-width="4.5" stroke-linecap="round"' % GREEN
    elif state == "unknown":
        st = 'stroke="%s" stroke-width="2" stroke-dasharray="3 4"' % GREY
    elif word in ("残高0", "上限", "鍵なし", "未導入", "切れ"):
        st = 'stroke="%s" stroke-width="2.6" stroke-dasharray="7 5" stroke-linecap="round"' % AMBER
    else:
        st = 'stroke="%s" stroke-width="2.6"' % RED
    return '<path d="M%d %d H%d V%d H%d" fill="none" %s/>' % (x1, y1, x2, y1, y2, x2, st)


def svg_haikan(J):
    """配管図。★1画面に収める（幅360）。"""
    rows_y = [104, 152, 200, 248, 296, 344]
    left = ["claude", "codex", "openai", "gemini", "xai", "xai_koe"]
    # ★補給所まで届く3人（fal/devin/jules）は**下3段**に置く。
    #   そうしないと補給所への線が他の箱を突き抜ける（codexの助言④「枠の内部に線を入れない」）。
    right = ["copilot", "jev", "genspark", "jules", "devin", "fal"]
    trunk_l, trunk_r = 140, 220

    s = ['<svg viewBox="0 0 360 560" xmlns="http://www.w3.org/2000/svg" '
         'font-family="-apple-system,BlinkMacSystemFont,Hiragino Sans,sans-serif">']
    s.append('<rect x="0" y="0" width="360" height="560" fill="#F8FAFC"/>')
    # 真ん中の自分
    s.append('<rect x="124" y="28" width="112" height="34" rx="9" fill="%s"/>' % INK)
    s.append('<text x="180" y="50" text-anchor="middle" font-size="13" font-weight="700" '
             'fill="#FFFFFF">Dispatch（自分）</text>')
    s.append('<path d="M180 62 V78" stroke="%s" stroke-width="3"/>' % INK)
    s.append('<path d="M%d 78 H%d" stroke="%s" stroke-width="3"/>' % (trunk_l, trunk_r, INK))
    s.append('<path d="M%d 78 V%d" stroke="%s" stroke-width="2.4"/>' % (trunk_l, rows_y[-1], INK))
    s.append('<path d="M%d 78 V%d" stroke="%s" stroke-width="2.4"/>' % (trunk_r, rows_y[-1], INK))

    # 線 → 記号 → 箱 の順（codexの助言：線は箱の下に描く）
    for col, xs, tx in ((left, LX, trunk_l), (right, RX, trunk_r)):
        for i, nid in enumerate(col):
            j = J[nid]
            y = rows_y[i]
            x2 = xs + (NW // 2 if xs < tx else -NW // 2)
            s.append('<path d="M%d %d H%d" fill="none" %s/>' % (
                tx, y, x2,
                ('stroke="%s" stroke-width="4.5" stroke-linecap="round"' % GREEN) if j["state"] == "ok"
                else ('stroke="%s" stroke-width="2.6" stroke-dasharray="7 5"' % AMBER)
                if j["word"] in ("残高0", "上限", "鍵なし", "未導入", "切れ")
                else ('stroke="%s" stroke-width="2" stroke-dasharray="3 4"' % GREY)
                if j["state"] == "unknown"
                else ('stroke="%s" stroke-width="2.6"' % RED)))
            if j["state"] not in ("ok",):
                mx = (tx + x2) // 2
                s.append('<path d="M%d %d l8 8 M%d %d l-8 8" stroke="%s" stroke-width="2.4"/>'
                         % (mx - 4, y - 4, mx + 4, y - 4, RED if j["state"] == "ng" else GREY))
    for col, xs in ((left, LX), (right, RX)):
        for i, nid in enumerate(col):
            n = next(x for x in NODES if x["id"] == nid)
            j = J[nid]
            c = GREEN if j["state"] == "ok" else (GREY if j["state"] == "unknown" else
                                                 (AMBER if j["word"] in ("残高0", "上限", "鍵なし",
                                                                         "未導入", "切れ") else RED))
            s.append(_node_box(xs, rows_y[i], n["name"], j["word"], n["tanto"], c,
                               nid in ZURE, n["dare"] if j["state"] != "ok" else ""))

    # 補給所（Lovable）
    by = 430
    s.append('<rect x="88" y="%d" width="184" height="36" rx="9" fill="#FFF7ED" stroke="%s" '
             'stroke-width="2.5"/>' % (by - 18, AMBER))
    s.append('<text x="180" y="%d" text-anchor="middle" font-size="12.5" font-weight="700" '
             'fill="%s">ごきげん補給所（Lovable）</text>' % (by + 4, INK))
    # 届く線：本番に出た＝太緑／PRまで＝細緑／0本＝引かない。★実測(tekizai.json)だけで決める。
    s.append('<path d="M180 62 V%d" stroke="%s" stroke-width="5" stroke-linecap="round" '
             'opacity="0.85"/>' % (by - 18, GREEN))
    s.append('<text x="184" y="410" font-size="9" fill="%s">自分 本番131本</text>' % GREEN)
    # 経路は下3段からだけ引く（レーンは箱の外だけを通す）
    MICHI = {"jules": (352, 398, 216), "devin": (345, 390, 204), "fal": (282, 382, 192)}
    for nid in REACH_FROM_TEKIZAI:
        j = J[nid]
        hon, too = (j.get("honban") or 0), (j.get("tooshita") or 0)
        if hon > 0:
            w, lab = 4.5, "本番%d本" % hon
        elif too > 0:
            w, lab = 1.6, "PR%d本" % too
        else:
            continue
        lane, ly, mx = MICHI[nid]
        i = right.index(nid)
        ny = rows_y[i] + NH // 2
        if lane > 340:
            s.append('<path d="M%d %d H%d V%d H%d V%d" fill="none" stroke="%s" '
                     'stroke-width="%.1f" stroke-linecap="round"/>'
                     % (340, rows_y[i], lane, ly, mx, by - 18, GREEN, w))
        else:
            s.append('<path d="M%d %d V%d H%d V%d" fill="none" stroke="%s" '
                     'stroke-width="%.1f" stroke-linecap="round"/>'
                     % (lane, ny + 14, ly, mx, by - 18, GREEN, w))
        s.append('<text x="%d" y="%d" font-size="8.5" fill="%s">%s %s</text>'
                 % (mx - 2, ly - 3, GREEN, esc(nid), lab))
    # 凡例
    s.append('<g font-size="10" fill="#475569">')
    s.append('<path d="M14 492 h22" stroke="%s" stroke-width="4.5" stroke-linecap="round"/>' % GREEN)
    s.append('<text x="42" y="496">通っている（叩いて実測）</text>')
    s.append('<path d="M14 512 h22" stroke="%s" stroke-width="2.6" stroke-dasharray="7 5"/>' % AMBER)
    s.append('<text x="42" y="516">あと1手（1語は箱の下）／👤＝たまごさんが押す</text>')
    s.append('<path d="M14 532 h22" stroke="%s" stroke-width="2.6"/>' % RED)
    s.append('<text x="42" y="536">通っていない　★＝得意と違う仕事を回している</text>')
    s.append('</g>')
    s.append('</svg>')
    return "".join(s)


def svg_hyo():
    """仕事の種類 × 誰に渡すか。◯△✕、空欄は未測定。"""
    colw, rowh, x0, y0 = 36, 28, 62, 56
    w = x0 + colw * len(HYO_COLS) + 6
    h = y0 + rowh * len(SHIGOTO) + 34
    s = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" '
         'font-family="-apple-system,BlinkMacSystemFont,Hiragino Sans,sans-serif">' % (w, h)]
    s.append('<rect width="%d" height="%d" fill="#F8FAFC"/>' % (w, h))
    s.append('<text x="8" y="22" font-size="12.5" font-weight="700" fill="%s">'
             'この仕事は誰に渡すか</text>' % INK)
    s.append('<text x="8" y="38" font-size="9.5" fill="#64748B">'
             '◯渡すべき　△渡せる　✕渡さない　空欄＝未測定</text>')
    name = {n["id"]: n["name"] for n in NODES}
    for c, nid in enumerate(HYO_COLS):
        cx = x0 + colw * c + colw // 2
        s.append('<text x="%d" y="%d" text-anchor="middle" font-size="8.5" fill="#475569" '
                 'transform="rotate(-38 %d %d)">%s</text>'
                 % (cx, y0 - 6, cx, y0 - 6, esc(name.get(nid, nid)[:9])))
    for r, k in enumerate(SHIGOTO):
        y = y0 + rowh * r
        if r % 2 == 0:
            s.append('<rect x="0" y="%d" width="%d" height="%d" fill="#FFFFFF"/>' % (y, w, rowh))
        s.append('<text x="8" y="%d" font-size="11" font-weight="600" fill="%s">%s</text>'
                 % (y + 19, INK, esc(k)))
        for c, v in enumerate(HYO[k]):
            cx = x0 + colw * c + colw // 2
            col = GREEN if v == "◯" else (AMBER if v == "△" else (RED if v == "✕" else GREY))
            s.append('<text x="%d" y="%d" text-anchor="middle" font-size="14" fill="%s">%s</text>'
                     % (cx, y + 20, col, v or "・"))
    s.append('</svg>')
    return "".join(s)


# ─────────────────────────────────────────────────────────────────────────
# ★たまごさんの情報の置き場に、誰が触れるか。
#   たまごさん（2026-09-24）「誰が俺のNotionとObsidianにアクセスできるのか、
#   そういうのも目視で確認したいね。」
#   ◎＝書ける／◯＝読める／✕＝触れない／空欄＝未測定。★叩いて通ったものだけ ◯◎。
#   ★線ではなく表にしてある。11人×6か所を線で描くとスマホでは必ず潰れる（codexの助言②）。
# ─────────────────────────────────────────────────────────────────────────
OKIBA = ["Obsidian", "Notion", "Supabase", "GitHub", "Drive", "Spotify"]
OKIBA_COLS = ["claude", "codex", "genspark", "gemini", "devin", "jules", "jev"]
OKIBA_HYO = {
    #            自分 codex gensp gemini devin jules jev
    "Obsidian":  ["◯", "",  "",  "",  "",  "",  ""],
    "Notion":    ["✕", "",  "",  "",  "",  "",  ""],
    "Supabase":  ["",  "",  "",  "",  "",  "",  ""],
    "GitHub":    ["✕", "",  "",  "",  "✕", "✕", ""],
    "Drive":     ["",  "",  "",  "",  "",  "",  ""],
    "Spotify":   ["",  "",  "",  "",  "",  "",  ""],
}
OKIBA_MOTO = (
    "Obsidian◯＝Mac上のVault(tamago_brain)の直下を0.2秒で並べられた"
    "（status/gaibu_jobs/done/20260924-081654-4204.json・1044番／読むだけ・0円）。"
    "★たまごさんにzipを作らせる必要は無い。 ／ "
    "Notion✕＝こちらにNotionのコネクタが0件（実測）。"
    "Gensparkは「Notionと繋がっている」と本人が申告しているが、"
    "今日 gsk が未導入で1件も読ませていない＝空欄（未測定）。 ／ "
    "GitHub✕＝トークンが取れない（status/public/kaitsuu.json の github）。"
    "Jules/CopilotはGitHub Issueが唯一の口なので、ここが閉じている間は触れない。 ／ "
    "★申告は「本人が言っている」として別に残す（SHINKOKU）。空欄を◯に変えるのは実測が出た日だけ。")

# ★外部AIの自己申告。**図の◯には一切使わない。**言った事実だけを残す。
SHINKOKU = [
    ("外部AI", "YouTube動画1本の文字起こし全文14,298文字をタイムスタンプ付きで取れる",
     "こちらでも同じ経路を作って実測した（tools/yomu.py の yt_transcript）"),
    ("外部AI", "Obsidianはローカルなのでzipにして渡してほしい",
     "★うちでは当てはまらない。Mac上のVaultを直接読めた（1044番・実測0.2秒）"),
    ("Genspark", "Notionと繋がっている（たまごさん経由）", "未測定。gskが未導入で1件も読ませていない"),
    ("Genspark", "Notion4,000ページ＋Obsidianを商品候補に変換できる", "今はやらない。選ばれたら使う"),
]


def svg_okiba():
    """情報の置き場 × 誰が触れるか。"""
    colw, rowh, x0, y0 = 40, 28, 76, 58
    w = x0 + colw * len(OKIBA_COLS) + 6
    h = y0 + rowh * len(OKIBA) + 16
    name = {n["id"]: n["name"] for n in NODES}
    s = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" '
         'font-family="-apple-system,BlinkMacSystemFont,Hiragino Sans,sans-serif">' % (w, h)]
    s.append('<rect width="%d" height="%d" fill="#F8FAFC"/>' % (w, h))
    s.append('<text x="8" y="22" font-size="12.5" font-weight="700" fill="%s">'
             'この置き場に誰が触れるか</text>' % INK)
    s.append('<text x="8" y="38" font-size="9.5" fill="#64748B">'
             '◎書ける　◯読める　✕触れない　空欄＝未測定</text>')
    for c, nid in enumerate(OKIBA_COLS):
        cx = x0 + colw * c + colw // 2
        s.append('<text x="%d" y="%d" text-anchor="middle" font-size="8.5" fill="#475569" '
                 'transform="rotate(-38 %d %d)">%s</text>'
                 % (cx, y0 - 6, cx, y0 - 6, esc(name.get(nid, nid)[:9])))
    for r, k in enumerate(OKIBA):
        y = y0 + rowh * r
        if r % 2 == 0:
            s.append('<rect x="0" y="%d" width="%d" height="%d" fill="#FFFFFF"/>' % (y, w, rowh))
        s.append('<text x="8" y="%d" font-size="11" font-weight="600" fill="%s">%s</text>'
                 % (y + 19, INK, esc(k)))
        for c, v in enumerate(OKIBA_HYO[k]):
            cx = x0 + colw * c + colw // 2
            col = GREEN if v in ("◯", "◎") else (RED if v == "✕" else GREY)
            s.append('<text x="%d" y="%d" text-anchor="middle" font-size="14" fill="%s">%s</text>'
                     % (cx, y + 20, col, v or "・"))
    s.append('</svg>')
    return "".join(s)


def sumaho_kensa(svg, w=360, h=560):
    """★スマホの門（図版）。**線が箱を貫通していないか・枠から出ていないか**を数で確かめる。
    たまごさん「スマホで見て線がつぶれたら不合格」。絵を人が見る前に、ここで落とす。
    ブラウザを使わない＝0円・0秒。毎日この門を通ってから紙が書き換わる。"""
    import re as _re
    rects = [tuple(map(float, m)) for m in
             _re.findall(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', svg)]
    rects = [r for r in rects if r[2] < w - 40]          # 背景の板は除く
    segs = []
    for d in _re.findall(r'<path d="([^"]+)"', svg):
        x = y = 0.0
        for op, a, b in _re.findall(r'([MHVl])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?', d):
            a = float(a); b = float(b) if b else 0.0
            if op == "M":
                x, y = a, b
            elif op == "H":
                segs.append((x, y, a, y)); x = a
            elif op == "V":
                segs.append((x, y, x, a)); y = a
            elif op == "l":
                segs.append((x, y, x + a, y + b)); x, y = x + a, y + b
    ng = []
    for (rx, ry, rw, rh) in rects:
        for (x1, y1, x2, y2) in segs:
            xa, xb = sorted((x1, x2)); ya, yb = sorted((y1, y2))
            if min(xb, rx + rw) - max(xa, rx) > 2 and min(yb, ry + rh) - max(ya, ry) > 2:
                ng.append("箱(%g,%g)を線(%g,%g→%g,%g)が貫通" % (rx, ry, x1, y1, x2, y2))
    for (x1, y1, x2, y2) in segs:
        if min(x1, x2) < 0 or max(x1, x2) > w or max(y1, y2) > h:
            ng.append("枠の外に出た線(%g,%g→%g,%g)" % (x1, y1, x2, y2))
    return ng


def html(J, at):
    zure_lines = "".join(
        '<li><b>%s</b>：%s</li>' % (esc(next(n["name"] for n in NODES if n["id"] == k)), esc(v))
        for k, v in ZURE.items())
    osu = [(n["name"], n["ichite"]) for n in NODES
           if n["dare"] == "たまご" and J[n["id"]]["state"] != "ok" and n["ichite"]]
    osu_lines = "".join('<li>%s … %s</li>' % (esc(a), esc(b)) for a, b in osu)
    return """<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>配管図｜どこが繋がっているか</title>
<style>
:root{color-scheme:light}
body{margin:0;background:#F8FAFC;color:#0F172A;
 font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif}
.wrap{max-width:420px;margin:0 auto;padding:12px 10px 40px}
h1{font-size:17px;margin:6px 0 2px}
.at{font-size:11px;color:#64748B;margin:0 0 10px}
svg{width:100%%;height:auto;display:block;border-radius:12px;
 box-shadow:0 1px 3px rgba(15,23,42,.10)}
h2{font-size:13px;margin:22px 0 6px}
ul{margin:4px 0 0;padding-left:18px;font-size:11.5px;line-height:1.7;color:#334155}
.moto{font-size:10px;color:#94A3B8;margin-top:8px;line-height:1.6}
</style></head><body><div class="wrap">
<h1>配管図｜どこが繋がっているか</h1>
<p class="at">実測 %(at)s ／ 緑は叩いて通ったものだけ。実測が無い線は描いていません。</p>
%(svg1)s
<h2>★＝得意と違う仕事を回している（振り直す場所）</h2>
<ul>%(zure)s</ul>
<h2>👤＝たまごさんが押すところ</h2>
<ul>%(osu)s</ul>
<h2>この仕事は誰に渡すか</h2>
%(svg2)s
<h2>たまごさんの情報の置き場に、誰が触れるか</h2>
%(svg3)s
<p class="moto">%(okibamoto)s</p>
<h2>外部AIの自己申告（★図の◯には使っていない）</h2>
<ul>%(shinkoku)s</ul>
<h2>実測の生データ（この図の数字はここからしか取っていない）</h2>
<pre>%(nama)s</pre>
<p class="moto">%(hyomoto)s<br>状態の出どころ：status/public/kaitsuu.json（実測）／
本番に出た本数：status/public/tekizai.json／図の寸法：codex(gpt-5.6-terra)に実測で聞いた答え。
この紙は外へ1回も出ません＝0円。</p>
</div></body></html>""" % dict(at=esc(at), svg1=svg_haikan(J), svg2=svg_hyo(),
                               zure=zure_lines, osu=osu_lines or "<li>なし</li>",
                               hyomoto=esc(HYO_MOTO), svg3=svg_okiba(),
                               okibamoto=esc(OKIBA_MOTO),
                               shinkoku="".join(
                                   "<li><b>%s</b>「%s」→ %s</li>" % (esc(a), esc(b), esc(c))
                                   for a, b, c in SHINKOKU), nama=esc(NAMA))


def build():
    J = joutai()
    at = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    return J, at


def run(force=False):
    if not force:
        try:
            last = io.open(STAMP, encoding="utf-8").read().strip()
            if last[:10] == datetime.now(JST).strftime("%Y-%m-%d"):
                return 0
        except Exception:
            pass
    J, at = build()
    # ★スマホの門。潰れている図は書き出さない（前の日の図を残す方がまし）。
    warui = sumaho_kensa(svg_haikan(J))
    if warui:
        print("スマホの門で止めました（図は書き換えません）：" + " / ".join(warui[:4]))
        return 1
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    os.makedirs(PUBLIC, exist_ok=True)
    with io.open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html(J, at))
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"at": at, "nodes": J, "zure": ZURE, "hyo": HYO,
                   "hyoMoto": HYO_MOTO}, f, ensure_ascii=False, indent=1)
    with io.open(STAMP, "w", encoding="utf-8") as f:
        f.write(datetime.now(JST).strftime("%Y-%m-%d %H:%M"))
    print("書きました: %s" % OUT_HTML)
    return 0


def self_test():
    J, at = build()
    s1, s2 = svg_haikan(J), svg_hyo()
    ng = []
    if "<svg" not in s1 or "</svg>" not in s1:
        ng.append("配管図のSVGが壊れています")
    for n in NODES:
        if n["id"] not in J:
            ng.append("状態が取れない口: %s" % n["id"])
    if len(HYO_COLS) != len(HYO["調べもの"]):
        ng.append("表の列数と行の長さが合いません")
    for k, v in OKIBA_HYO.items():
        if len(v) != len(OKIBA_COLS):
            ng.append("置き場の表の列数が合いません: %s" % k)
    ng += sumaho_kensa(s1)
    h = html(J, at)
    if "viewBox" not in h:
        ng.append("HTMLにSVGが入っていません")
    print(json.dumps({"ok": not ng, "だめな点": ng, "口の数": len(J),
                      "図の文字数": len(s1)}, ensure_ascii=False))
    return 0 if not ng else 1


def main():
    if "--self-test" in sys.argv:
        return self_test()
    return run(force="--force" in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
