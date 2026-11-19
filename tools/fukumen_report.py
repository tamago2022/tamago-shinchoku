#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1029番【覆面調査員の報告】tools/fukumen.py が取った数字を、1枚のページにする。

■ たまごさんの指定（そのまま）
  ・表の中身は「症状 ／ 数字 ／ どのページで ／ 直すとどうなるか」の4列だけ。
    原因の講釈・経緯・試したことは書かない。
  ・重い順・ひどい順に並べる。上位5件だけ大きく、あとは小さく。
  ・スクリーンショットを証拠として貼る（ずれた瞬間の前後2枚）。
  ・自己採点は書かない。

■ 「ひどさ」の決め方（憶測を入れない）
  ひどさ ＝ 実測値 ÷ 合格ライン。1.0でちょうど合格ライン、2.0なら倍ひどい。
  合格ラインは全部よそが決めた公式の数字（Web Vitals）か、たまごさんが言った条件。

■ 走らせ方
  python3 tools/fukumen_report.py            # status/fukumen/latest.json から作る
  python3 tools/fukumen_report.py --day 2026-09-23
"""
import argparse
import html
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "status", "fukumen")
PAGE = os.path.join(ROOT, "share", "check", "1029-fukumen.html")
PUBURL = "https://tamago2022.github.io/tamago-shinchoku/share/check/1029-fukumen.html"

CLS_GOOD, CLS_BAD = 0.10, 0.25
LCP_GOOD, LCP_BAD = 2500, 4000
INP_GOOD = 200


def e(s):
    return html.escape(str(s if s is not None else ""))


def short(url):
    u = str(url).replace("https://joy-relief-station.lovable.app", "")
    return u if u else "/"


def shot_rel(p):
    """result.json に入っているのはリポジトリからの相対パス。ここでは触らず、
    公開用に運ぶのは publish_shot()（報告に貼る数枚だけ）。"""
    return p or None


PUBDIR = os.path.join(ROOT, "share", "check", "assets", "1029-fukumen")


def publish_shot(relpath):
    """報告に貼る数枚だけを、軽いJPEGにして公開の場所へ移す。
    ★撮った全部を share/ に置くと毎日6MBがgitに積み上がる（実測）。貼るものだけ運ぶ。"""
    if not relpath:
        return None
    src = os.path.join(ROOT, relpath)
    if not os.path.exists(src):
        return None
    os.makedirs(PUBDIR, exist_ok=True)
    base = os.path.basename(src).rsplit(".", 1)[0]
    try:
        from PIL import Image
        im = Image.open(src).convert("RGB")
        if im.width > 1100:
            im = im.resize((1100, int(im.height * 1100.0 / im.width)), Image.LANCZOS)
        im.save(os.path.join(PUBDIR, base + ".jpg"), "JPEG", quality=72, optimize=True)
        return "assets/1029-fukumen/" + base + ".jpg"
    except Exception:
        shutil.copy2(src, os.path.join(PUBDIR, os.path.basename(src)))
        return "assets/1029-fukumen/" + os.path.basename(src)


def sweep_unused(keep):
    """報告が使わなくなった画像を公開の場所から片付ける（毎回撮り直せるものだけ）。"""
    if not os.path.isdir(PUBDIR):
        return 0
    n = 0
    for f in os.listdir(PUBDIR):
        if f not in keep and (f.endswith(".png") or f.endswith(".jpg")):
            try:
                os.unlink(os.path.join(PUBDIR, f))
                n += 1
            except Exception:
                pass
    return n


def load(day=None):
    if day:
        p = os.path.join(OUTDIR, day, "result.json")
    else:
        p = os.path.join(OUTDIR, "latest.json")
    with open(p) as f:
        return json.load(f)


def load_prev(cur_day):
    days = sorted(d for d in os.listdir(OUTDIR)
                  if os.path.isdir(os.path.join(OUTDIR, d)) and d < str(cur_day))
    for d in reversed(days):
        p = os.path.join(OUTDIR, d, "result.json")
        if os.path.exists(p):
            try:
                with open(p) as f:
                    return d, json.load(f)
            except Exception:
                pass
    return None, None


def metrics(res):
    """前回との比較に使う代表値。少数に絞る（増やすと見る気が失せる）。"""
    pages = [p for p in res.get("pages", []) if "cls" in p]
    typ = res.get("typing", [])
    con = res.get("concierge", [])
    m = {}
    if pages:
        m["CLSの最悪値"] = max(p["cls"] for p in pages)
        m["CLSが悪いページ数"] = len([p for p in pages if p["cls"] > CLS_BAD])
        m["LCPの最悪値(ms)"] = max(p.get("lcp_ms", 0) for p in pages)
        m["console errorが出たページ数"] = len([p for p in pages if p.get("console_errors")])
    if typ:
        m["入力欄の作り直し(最悪・1文字あたり)"] = round(max(
            (float(t.get("入力欄が作り直された回数") or 0) / max(1, t.get("chars") or 1)) for t in typ), 3)
        m["打った字が消えた回数(合計)"] = sum(int(t.get("打った字が消えた回数") or 0) for t in typ)
    if con:
        m["案内人の不合格率"] = round(len([c for c in con if c.get("ng")]) / float(len(con)), 3)
    return m


def findings(res):
    """症状ごとにまとめる。1症状＝1行。ページごとに40行出すと読めない。"""
    out = []
    pages = [p for p in res.get("pages", []) if "cls" in p]
    broke = [p for p in res.get("pages", []) if p.get("error")]

    def group(items, width):
        return [p for p in items if p.get("width") == width]

    # ⓪ ページが落ちた・開けなかった（たまごさんの言う「落ちる」そのもの）
    if broke:
        crashed = [p for p in broke if "crash" in p["error"].lower()]
        allp = len(res.get("pages", []))
        out.append({
            "症状": "ページが落ちる・開けない",
            "数字": "%d枚見て %d枚が最後まで開けなかった（うちブラウザのタブごと落ちたのが %d枚）"
                    % (allp, len(broke), len(crashed)),
            "どこで": "／".join(short(p["url"]) for p in broke[:3])
                      + ("（ほか%d枚）" % (len(broke) - 3) if len(broke) > 3 else ""),
            "直すとどうなるか": "お客さんが曲ページで放り出されなくなる",
            "ひどさ": 8.0 + len(crashed),
            "metric": None,
            "raw": [{"url": p["url"], "error": p["error"][:220]} for p in broke],
        })

    # ① 読んでいる途中で画面がずれる（CLS）
    for w, wname in ((375, "スマホ375px"), (1280, "パソコン1280px")):
        gs = [p for p in group(pages, w) if p["cls"] > CLS_GOOD]
        if not gs:
            continue
        gs.sort(key=lambda p: -p["cls"])
        worst = gs[0]
        who = []
        for s in worst.get("shifts", [])[:3]:
            for src in s.get("srcs", [])[:1]:
                if src.get("el") and src["el"] not in who:
                    who.append(src["el"])
        big = max(worst.get("shifts") or [{"t": 0, "v": 0}], key=lambda s: s.get("v", 0))
        out.append({
            "症状": "読んでいる途中で画面が動く（%s）" % wname,
            "数字": "CLS 最悪 %.3f（良い＝0.1以下／悪い＝0.25超）。%d枚中%d枚が0.1超。"
                    "一番大きなズレは開いてから %.1f秒後（＝もう読み始めている）"
                    % (worst["cls"], len(group(pages, w)), len(gs), (big.get("t") or 0) / 1000.0),
            "どこで": short(worst["url"]) + ("（ほか%d枚）" % (len(gs) - 1) if len(gs) > 1 else ""),
            "直すとどうなるか": "読んでいる行が飛ばなくなる。押そうとしたカードが逃げなくなる",
            "ひどさ": worst["cls"] / CLS_GOOD,
            "ずれたのは": who[:3],
            "before": shot_rel(worst.get("shot_before")),
            "after": shot_rel(worst.get("shot_after")),
            "metric": "CLSの最悪値",
            "raw": {"url": worst["url"], "cls": worst["cls"],
                    "cls_while_reading": worst.get("cls_while_reading"),
                    "shifts": worst.get("shifts", [])[:4]},
        })

    # ② 入力欄が1文字ごとに作り直される
    for t in res.get("typing", []):
        if t.get("error"):
            out.append({
                "症状": "入力欄にたどり着けない",
                "数字": t["error"], "どこで": short(t["url"]) + "｜" + t.get("label", ""),
                "直すとどうなるか": "お客さんが言葉を打てるようになる",
                "ひどさ": 3.0, "metric": None, "raw": t})
            continue
        chars = max(1, int(t.get("chars") or 1))
        rb = int(t.get("入力欄が作り直された回数") or 0)
        fl = int(t.get("フォーカスが外れた回数") or 0)
        vl = int(t.get("打った字が消えた回数") or 0)
        sw = int(t.get("画面の要素が差し替わった回数") or 0)
        if rb or vl or fl:
            out.append({
                "症状": "入力している途中で入力欄が作り直される（＝たまごさんの言う「落ちる」）",
                "数字": "%d文字打つ間に｜入力欄の作り直し %d回／フォーカスが外れた %d回／打った字が消えた %d回／画面の要素の差し替え %d回"
                        % (chars, rb, fl, vl, sw),
                "どこで": short(t["url"]) + "｜" + t.get("label", ""),
                "直すとどうなるか": "打っている途中で手が止まらなくなる。打った字が消えなくなる",
                "ひどさ": 1.0 + (rb / float(chars)) * 10 + (vl / float(chars)) * 10,
                "before": shot_rel(t.get("shot_after")), "after": None,
                "metric": "入力欄の作り直し(最悪・1文字あたり)",
                "raw": {k: t.get(k) for k in
                        ("url", "label", "chars", "入力欄が作り直された回数", "フォーカスが外れた回数",
                         "打った字が消えた回数", "画面の要素が差し替わった回数", "最後に残っていた文字",
                         "全部残ったか", "消えた例", "cls", "inp_ms")},
            })
        elif sw > chars * 3:
            out.append({
                "症状": "入力のたびに画面を作り直している（まだ字は消えていない）",
                "数字": "%d文字打つ間に 画面の要素の差し替え %d回（1文字あたり %.1f回）"
                        % (chars, sw, sw / float(chars)),
                "どこで": short(t["url"]) + "｜" + t.get("label", ""),
                "直すとどうなるか": "打つ手が引っかからなくなる。弱い端末で落ちなくなる",
                "ひどさ": 1.0 + (sw / float(chars)) / 10.0,
                "metric": None, "raw": t.get("per_char", [])[:5],
            })

    # ②-b 打っても返ってくるのが遅い（INP）
    typ = [t for t in res.get("typing", []) if not t.get("error")]
    if typ:
        wt = max(typ, key=lambda t: t.get("inp_ms") or 0)
        if (wt.get("inp_ms") or 0) > INP_GOOD:
            out.append({
                "症状": "打った手ごたえが返ってくるのが遅い",
                "数字": "1文字打ってから画面が応えるまで 最悪 %dms（良い＝200ms以下／悪い＝500ms超）。測った%d箇所の最悪値"
                        % (wt["inp_ms"], len(typ)),
                "どこで": short(wt["url"]) + "｜" + wt.get("label", ""),
                "直すとどうなるか": "打っている最中に「固まった」と感じなくなる",
                "ひどさ": wt["inp_ms"] / float(INP_GOOD),
                "metric": None,
                "raw": [{"label": t.get("label"), "inp_ms": t.get("inp_ms"),
                         "画面の要素が差し替わった回数": t.get("画面の要素が差し替わった回数")} for t in typ],
            })

    # ③ 表示されるまで遅い（LCP）
    for w, wname in ((375, "スマホ375px"), (1280, "パソコン1280px")):
        gs = [p for p in group(pages, w) if p.get("lcp_ms", 0) > LCP_GOOD]
        if not gs:
            continue
        gs.sort(key=lambda p: -p.get("lcp_ms", 0))
        worst = gs[0]
        out.append({
            "症状": "出てくるまで待たされる（%s）" % wname,
            "数字": "一番大きい絵が出るまで 最悪 %.1f秒（良い＝2.5秒以下／悪い＝4秒超）。%d枚中%d枚が2.5秒超"
                    % (worst["lcp_ms"] / 1000.0, len(group(pages, w)), len(gs)),
            "どこで": short(worst["url"]) + ("（ほか%d枚）" % (len(gs) - 1) if len(gs) > 1 else ""),
            "直すとどうなるか": "開いた瞬間に中身が見える。戻るボタンを押されなくなる",
            "ひどさ": worst["lcp_ms"] / float(LCP_GOOD),
            "before": shot_rel(worst.get("shot_before")), "after": shot_rel(worst.get("shot_after")),
            "metric": "LCPの最悪値(ms)",
            "raw": {"url": worst["url"], "lcp_ms": worst["lcp_ms"],
                    "longtasks_over50": worst.get("longtasks_over50"),
                    "kb": worst.get("kb"), "requests": worst.get("requests")},
        })

    # ④ console error
    errp = [p for p in pages if p.get("console_errors")]
    if errp:
        errp.sort(key=lambda p: -len(p["console_errors"]))
        msgs = []
        for p in errp:
            for m in p["console_errors"]:
                if m not in msgs:
                    msgs.append(m)
        out.append({
            "症状": "画面の裏でエラーが出ている",
            "数字": "%d枚中%d枚でエラー。種類は%d通り。一番多いページで%d件"
                    % (len(pages), len(errp), len(msgs), len(errp[0]["console_errors"])),
            "どこで": short(errp[0]["url"]) + ("（ほか%d枚）" % (len(errp) - 1) if len(errp) > 1 else ""),
            "直すとどうなるか": "出ないはずの空欄・止まるボタンが減る",
            "ひどさ": 1.0 + len(errp) / float(max(1, len(pages))),
            "metric": "console errorが出たページ数",
            "raw": msgs[:8],
        })

    # ⑤ 案内人（卵コンシェルジュ）
    con = res.get("concierge", [])
    if con:
        ng = [c for c in con if c.get("ng")]
        kinds = {}
        for c in ng:
            for x in c["ng"]:
                k = x.split("（")[0]
                kinds[k] = kinds.get(k, 0) + 1
        if ng:
            out.append({
                "症状": "案内人の返事が「おじさん、わかってるね」になっていない",
                "数字": "%d問中%d問が不合格（%s）"
                        % (len(con), len(ng),
                           "／".join("%s %d問" % (k, v) for k, v in
                                     sorted(kinds.items(), key=lambda kv: -kv[1]))),
                "どこで": "/cover-guide（卵コンシェルジュ）",
                "直すとどうなるか": "ひとこと返ってきて、棚が出る。読まずに済む",
                "ひどさ": 1.0 + len(ng) / float(len(con)) * 3,
                "metric": "案内人の不合格率",
                "raw": [{"問": c["q"], "不合格": c.get("ng"),
                         "セリフ": (c.get("セリフ") or "")[:120],
                         "出てきたもの": c.get("出てきたもの")} for c in ng[:8]],
            })

    # ⑥ 重さ（転送量・長いタスク）
    if pages:
        heavy = sorted(pages, key=lambda p: -(p.get("kb") or 0))[0]
        lt = sorted(pages, key=lambda p: -(p.get("longtask_total_ms") or 0))[0]
        if (heavy.get("kb") or 0) > 1500 or (lt.get("longtask_total_ms") or 0) > 500:
            out.append({
                "症状": "1枚が重い",
                "数字": "一番重いページで %.0fKB・%d本の通信。ブラウザが固まっていた時間 最悪 %dms（50ms超の長い処理 %d回）"
                        % (heavy.get("kb") or 0, heavy.get("requests") or 0,
                           lt.get("longtask_total_ms") or 0, lt.get("longtasks_over50") or 0),
                "どこで": short(heavy["url"]),
                "直すとどうなるか": "スクロールが滑らかになる。回線が細い所でも開く",
                "ひどさ": 0.9 + (heavy.get("kb") or 0) / 5000.0,
                "metric": None,
                "raw": {"kb": heavy.get("kb"), "requests": heavy.get("requests"),
                        "longtask_total_ms": lt.get("longtask_total_ms")},
            })

    out.sort(key=lambda f: -f["ひどさ"])
    return out


CSS = """
:root{--ji:#EDE6D6;--sumi:#22304A;--shu:#C1442E;--usu:#8a8172;--sen:#d8cfbb}
*{box-sizing:border-box}
body{margin:0;background:var(--ji);color:var(--sumi);
 font-family:"Hiragino Mincho ProN","Yu Mincho",serif;line-height:1.85;
 -webkit-font-smoothing:antialiased}
.wrap{max-width:980px;margin:0 auto;padding:64px 28px 120px}
.kicker{font-family:"Optima","Palatino",serif;font-size:10.5px;letter-spacing:4.2px;
 color:var(--shu);text-transform:uppercase;margin:0 0 18px}
h1{font-size:40px;font-weight:400;letter-spacing:7px;margin:0 0 6px;line-height:1.35}
.en{font-family:"Optima","Palatino",serif;font-size:9.5px;letter-spacing:4.2px;color:var(--shu);margin:0 0 34px}
.lead{font-size:15.5px;color:#3d4a62;max-width:720px;margin:0 0 10px}
.meta{font-size:11.5px;color:var(--usu);letter-spacing:.6px;margin:26px 0 0;
 border-top:1px solid var(--sen);padding-top:14px}
h2{font-size:12px;letter-spacing:5px;font-weight:400;color:var(--usu);
 margin:78px 0 22px;border-bottom:1px solid var(--sen);padding-bottom:10px}
.card{margin:0 0 56px;padding:0 0 40px;border-bottom:1px solid var(--sen)}
.no{font-family:"Optima",serif;font-size:11px;letter-spacing:3px;color:var(--shu)}
.sym{font-size:25px;font-weight:400;letter-spacing:1.2px;margin:6px 0 16px;line-height:1.45}
.row{display:grid;grid-template-columns:96px 1fr;gap:10px 18px;font-size:14px;margin:0 0 6px}
.lbl{font-size:10.5px;letter-spacing:2.6px;color:var(--usu);padding-top:5px}
.num{font-size:16px;color:var(--sumi)}
.fix{color:#3d4a62}
.worse{display:inline-block;background:var(--shu);color:#fff;font-size:10px;letter-spacing:2px;
 padding:3px 9px;margin-left:10px;vertical-align:middle}
.shots{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:24px 0 0}
.shots figure{margin:0}
.shots img{width:100%;display:block;border:1px solid var(--sen);background:#fff}
figcaption{font-size:10.5px;color:var(--usu);letter-spacing:1.4px;margin-top:8px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{font-size:10px;letter-spacing:2.4px;color:var(--usu);font-weight:400;text-align:left;
 border-bottom:1px solid var(--sen);padding:0 12px 8px 0}
td{padding:12px 12px 12px 0;border-bottom:1px solid var(--sen);vertical-align:top;color:#3d4a62}
td:first-child{color:var(--sumi)}
pre{background:#e5ddcb;border:1px solid var(--sen);padding:16px;overflow:auto;
 font-family:"SF Mono",Menlo,monospace;font-size:10.5px;line-height:1.6;color:#4a5570}
details{margin:14px 0 0}
summary{font-size:11px;letter-spacing:2px;color:var(--usu);cursor:pointer}
.mono{font-family:"SF Mono",Menlo,monospace;font-size:11px}
@media(max-width:640px){.wrap{padding:40px 18px 90px}h1{font-size:27px;letter-spacing:4px}
 .sym{font-size:20px}.row{grid-template-columns:1fr;gap:2px}.lbl{padding-top:10px}
 .shots{grid-template-columns:1fr}}
"""


def render(res, prev_day, prev):
    fs = findings(res)
    cur_m = metrics(res)
    prev_m = metrics(prev) if prev else {}
    worse = set()
    for k, v in cur_m.items():
        if k in prev_m:
            try:
                if float(v) > float(prev_m[k]) * 1.05:
                    worse.add(k)
            except Exception:
                pass

    s = res.get("まとめ", {})
    la = res.get("このMacの混み具合(開始時のload average)")
    top, rest = fs[:5], fs[5:]
    used = set()

    h = []
    h.append('<!doctype html><html lang="ja"><head><meta charset="utf-8">')
    h.append('<meta name="viewport" content="width=device-width,initial-scale=1">')
    h.append("<title>覆面調査員の報告 — ごきげん補給所</title>")
    h.append("<style>%s</style></head><body><div class='wrap'>" % CSS)
    h.append("<p class='kicker'>01 / MYSTERY SHOPPER</p>")
    h.append("<h1>覆面調査員の報告</h1>")
    h.append("<p class='en'>JOY RELIEF STATION &nbsp;/&nbsp; WHAT THE CUSTOMERS FELT</p>")
    h.append("<p class='lead'>架空のお客さん4人が、本番のごきげん補給所を実際に触りました。"
             "ここに出ているのは全部、ブラウザが自分で測った数字です。"
             "人の感想もAIの採点も1つも入っていません。</p>")
    h.append("<p class='meta'>%s に実測　／　見たページ %s枚　／　案内人に %s問　／　本番 %s"
             % (e(res.get("開始")), e(s.get("見たページ数")), e(s.get("案内人の設問数")), e(res.get("本番"))))
    if la:
        h.append("　／　このときのMacの混み具合（load average）%s。"
                 "待ち時間の数字（下の「出てくるまで待たされる」）はこの影響を受けます。"
                 "画面のズレと入力の数字は影響を受けません。" % e(la))
    h.append("</p>")

    # ── 上位5件（大きく） ──
    h.append("<h2>ひどい順 ・ 上から5つ</h2>")
    for i, f in enumerate(top, 1):
        red = (f.get("metric") in worse)
        h.append("<div class='card'>")
        h.append("<div class='no'>%02d</div>" % i)
        h.append("<div class='sym'>%s%s</div>" % (
            e(f["症状"]), "<span class='worse'>前回より悪化</span>" if red else ""))
        h.append("<div class='row'><div class='lbl'>数字</div><div class='num'>%s</div></div>" % e(f["数字"]))
        h.append("<div class='row'><div class='lbl'>どこで</div><div class='mono'>%s</div></div>" % e(f["どこで"]))
        h.append("<div class='row'><div class='lbl'>直すと</div><div class='fix'>%s</div></div>" % e(f["直すとどうなるか"]))
        if f.get("ずれたのは"):
            h.append("<div class='row'><div class='lbl'>ずれたのは</div><div class='mono'>%s</div></div>"
                     % e(" ／ ".join(f["ずれたのは"])))
        b, a = publish_shot(f.get("before")), publish_shot(f.get("after"))
        for x in (b, a):
            if x:
                used.add(os.path.basename(x))
        if b or a:
            h.append("<div class='shots'>")
            if b:
                h.append("<figure><img src='%s' alt=''><figcaption>読み始めた瞬間（0.7秒）</figcaption></figure>" % e(b))
            if a:
                h.append("<figure><img src='%s' alt=''><figcaption>読んでいる途中（この間に画面が動いた）</figcaption></figure>" % e(a))
            h.append("</div>")
        h.append("<details><summary>測った生データ</summary><pre>%s</pre></details>"
                 % e(json.dumps(f.get("raw"), ensure_ascii=False, indent=1)[:2600]))
        h.append("</div>")

    # ── 残り（小さく） ──
    if rest:
        h.append("<h2>そのほか</h2><table><tr><th>症状</th><th>数字</th><th>どこで</th><th>直すとどうなるか</th></tr>")
        for f in rest:
            red = " <span class='worse'>悪化</span>" if f.get("metric") in worse else ""
            h.append("<tr><td>%s%s</td><td>%s</td><td class='mono'>%s</td><td>%s</td></tr>"
                     % (e(f["症状"]), red, e(f["数字"]), e(f["どこで"]), e(f["直すとどうなるか"])))
        h.append("</table>")

    # ── 触ったが数字が出なかったもの（ここを黙ると、直っている所をまた疑うことになる）──
    clean = []
    for t in res.get("typing", []):
        if t.get("error"):
            continue
        if not (t.get("入力欄が作り直された回数") or t.get("打った字が消えた回数")
                or t.get("フォーカスが外れた回数")):
            clean.append("%s：%d文字を1文字ずつ打って、作り直し0回・字の消失0回・フォーカス落ち0回"
                         % (t.get("label"), t.get("chars") or 0))
    if clean:
        h.append("<h2>触ったが、異常が出なかったもの</h2><table><tr><th>触った所</th><th>数字</th></tr>")
        for c in clean:
            a, b = c.split("：", 1)
            h.append("<tr><td>%s</td><td>%s</td></tr>" % (e(a), e(b)))
        h.append("</table>")

    # ── 前回との比べ ──
    h.append("<h2>前回と比べて</h2>")
    if prev:
        h.append("<table><tr><th>見ている数字</th><th>今回</th><th>前回（%s）</th><th></th></tr>" % e(prev_day))
        for k in cur_m:
            pv = prev_m.get(k, "—")
            mark = "<span class='worse'>悪化</span>" if k in worse else ""
            h.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (e(k), e(cur_m[k]), e(pv), mark))
        h.append("</table>")
    else:
        h.append("<p class='lead'>前回がまだありません（今回が1回目）。明日から、悪くなった項目だけ赤で出ます。</p>")

    h.append("<h2>測った生データ（実測）</h2>")
    widths = sorted(set(p.get("width") for p in res.get("pages", []) if p.get("width")))
    h.append("<pre>実測: 見た画面の幅 %s\n実測: %s</pre>"
             % (e(" / ".join("%dpx" % w for w in widths)),
                e(json.dumps(cur_m, ensure_ascii=False, indent=1))))
    h.append("<p class='meta'>この数字を取った道具：tools/fukumen.py（Playwright／Chromium）。"
             "CLS・LCP・INP・長いタスクは PerformanceObserver、入力の作り直しは MutationObserver と "
             "document.contains で数えています。お金は1円もかかっていません。</p>")
    h.append("</div></body></html>")
    sweep_unused(used)
    return "\n".join(h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default="")
    a = ap.parse_args()
    res = load(a.day or None)
    prev_day, prev = load_prev(res.get("日付") or time.strftime("%Y-%m-%d"))
    out = render(res, prev_day, prev)
    # ★関所：share/check/ に書く前に必ず通す（呼び忘れが起きないよう、ここに直接置く）
    try:
        import sekisho
        ok, reasons, _ = sekisho.gate_local(out)
        if not ok:
            sys.stderr.write("SEKISHO FAIL: %s\n" % " ／ ".join(reasons))
            return 1
    except ImportError:
        pass
    with open(PAGE, "w") as f:
        f.write(out)
    print("書きました: %s" % os.path.relpath(PAGE, ROOT))
    print(PUBURL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
