#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1036番【税金ライン・4区＝庶民版にする】難しい話を、友達に送れる1枚にする。

━━ たまごさん（2026-09-23・原文）━━

  「それを簡単な庶民レベルに落とすってところまでやってほしいの。まず人が知ることが大事だから。
    こういう難しい情報を集めたところでみんな読まないから、
    まず簡単な漫画なのか分かりやすい形に落としてほしい。」
  「誰かを悪者にしようっていうんじゃなくて、そういうズルができないような社会にしたい。」

━━ 形（決まりごと。ここを外したら庶民版ではない）━━

  ★1枚目は「大きい数字1つ＋一行」だけ。スクロールしないと次が出ない。
  ★単位を身近に換算する（国民1人あたり◯円／給食費◯年分）。★換算の式を必ず見せる。
  ★「確認できたこと」と「確認できていないこと」を必ず分ける。
  ★締めは「いくら／だれに／なぜ」の3つの質問。**告発ではなく質問で終わる。**
  ★スマホ375pxで読める。LINEやXに貼って開く。友達に送るものだから。

━━ 絵について（正直に書く）━━

  こちらは絵が✕（1030番の表：絵・画像の欄でDispatch✕・子セッション✕）。
  だから**人物・キャラクターを図形で描かない**（tamago-tone：棒人間は100点中5点）。
  1枚目は**文字組みだけで持たせる。**Gensparkの絵が入る場所（e）は空けてあり、
  **絵の門を通った絵が来たら差し込む。**通っていない絵はここから出さない。

  色は tamago-tone の実測値：生成り #EDE6D6 ／ 夜の藍 #22304A ／ 朱 #C1442E。
  差し色は朱1点だけ。グラデーションと光沢を使わない（＝AI臭いの typical）。

━━ 門を通らないと出ない ━━

  組み上げたあと **tools/zeikin_gate.py**（＝3区。中で tools/kazu_gate.py も呼ぶ）に
  自分で通す。落ちたらHTMLを書かない。「思い出したときだけ通る門」にしない。

━━ 使い方 ━━

    python3 tools/zeikin_shomin.py status/uratori/kiji/<id>.json
    python3 tools/zeikin_shomin.py --rei          # 原稿JSONの見本を出す

終了コード: 0=出来た / 1=門で落ちた（★出してはいけない）/ 2=原稿が足りない
"""
from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
GATE = os.path.join(HERE, "zeikin_gate.py")
OUT = os.path.join(REPO, "share", "check")
JST = timezone(timedelta(hours=9))

REI = {
    "id": "（台帳 status/uratori/dane.jsonl の id）",
    "slug": "1036-rei",
    "title": "見出し（15字まで）",
    "hitokoto": "1枚目の一行。ここだけで意味が通ること。",
    "ookii": {"kazu": "1,234", "tan": "億円", "nani": "この数字が何か（1行）"},
    "kanzan": [{"nani": "国民1人あたり", "atai": "◯円", "shiki": "1,234億円 ÷ 1億2,300万人"}],
    "kurabe": {
        "midashi": "同じ1億円でも",
        "gyo": [{"dare": "ふつうの人", "ikura": "◯円", "memo": "1行"},
                {"dare": "こっち", "ikura": "0円", "memo": "1行"}],
    },
    "kakunin_ok": [{"koto": "確認できたこと", "src": "https://… 200 12:40"}],
    "kakunin_ng": ["まだ確かめられていないこと"],
    "shitsumon": ["いくら？", "だれに？", "なぜ？"],
    "moto": {"note": "Vaultのどのノートか", "tag": "#税金…", "claim": "原文のまま"},
    "e": None,
}


def _now():
    return datetime.now(JST).strftime("%F %H:%M")


def esc(s):
    return html.escape(str(s or ""))


def build(k: dict) -> str:
    ookii = k.get("ookii") or {}
    e = k.get("e")
    ehtml = ('<img class="e" src="%s" alt="">' % esc(e)) if e else ""

    kanzan = "".join(
        '<div class="kz"><b>%s</b><span class="v">%s</span>'
        '<span class="sk">%s</span></div>'
        % (esc(x.get("nani")), esc(x.get("atai")), esc(x.get("shiki")))
        for x in (k.get("kanzan") or []))

    # ★並べた比較（たまごさん 2026-09-23：「あなたの場合はこうなる」に落とす）
    kb = k.get("kurabe") or {}
    kurabe = ""
    if kb.get("gyo"):
        rows = "".join(
            '<div class="kb%s"><span class="d">%s</span>'
            '<span class="i">%s</span><span class="m">%s</span></div>'
            % (" hi" if n == len(kb["gyo"]) - 1 else "",
               esc(g.get("dare")), esc(g.get("ikura")), esc(g.get("memo")))
            for n, g in enumerate(kb["gyo"]))
        kurabe = '<h2>%s</h2>%s' % (esc(kb.get("midashi") or "くらべてみる"), rows)

    ok = "".join(
        '<li>%s<span class="src">%s</span></li>'
        % (esc(x.get("koto")), esc(x.get("src")))
        for x in (k.get("kakunin_ok") or []))

    ng = "".join("<li>%s</li>" % esc(x) for x in (k.get("kakunin_ng") or []))
    q = "".join('<div class="q">%s</div>' % esc(x) for x in (k.get("shitsumon") or []))
    moto = k.get("moto") or {}

    return """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title>
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(hitokoto)s">
<style>
:root{--ki:#EDE6D6;--ai:#22304A;--syu:#C1442E;--usu:#6b7787}
*{box-sizing:border-box}
body{margin:0;background:var(--ki);color:var(--ai);
 font-family:"Hiragino Mincho ProN","Yu Mincho",serif;line-height:1.9;
 -webkit-text-size-adjust:100%%}
.w{max-width:600px;margin:0 auto;padding:0 22px 70px}
.ichi{min-height:86vh;display:flex;flex-direction:column;justify-content:center}
.e{width:100%%;display:block;margin:0 0 26px}
.kazu{font-size:clamp(54px,17vw,110px);line-height:1;letter-spacing:-.02em;
 color:var(--syu);font-feature-settings:"palt"}
.tan{font-size:22px;margin-left:6px;color:var(--ai)}
.nani{font-size:14px;color:var(--usu);letter-spacing:.14em;margin:16px 0 0}
.hito{font-size:19px;margin:22px 0 0;line-height:1.95}
.sc{font-size:11px;letter-spacing:.3em;color:var(--usu);margin-top:52px}
h2{font-size:13px;letter-spacing:.34em;color:var(--usu);font-weight:400;
 margin:64px 0 14px;padding-bottom:9px;border-bottom:1px solid #cdc3ae}
.kz{margin:0 0 20px}
.kz b{display:block;font-size:12.5px;letter-spacing:.2em;color:var(--usu);font-weight:400}
.kz .v{display:block;font-size:30px;color:var(--syu);line-height:1.4}
.kz .sk{display:block;font-size:11.5px;color:var(--usu);letter-spacing:.06em}
ul{margin:0;padding-left:1.1em}
li{margin:0 0 13px;font-size:15.5px}
.src{display:block;font-size:11px;color:var(--usu);word-break:break-all;letter-spacing:0}
.ng li{color:#7a6a58}
.kb{margin:0 0 14px;padding:14px 16px;background:#e4dbc8;border-left:3px solid #cdc3ae}
.kb.hi{border-left-color:var(--syu)}
.kb .d{display:block;font-size:12.5px;letter-spacing:.2em;color:var(--usu)}
.kb .i{display:block;font-size:34px;line-height:1.3;color:var(--ai)}
.kb.hi .i{color:var(--syu)}
.kb .m{display:block;font-size:12.5px;color:var(--usu)}
.q{font-size:26px;color:var(--syu);margin:0 0 12px;letter-spacing:.06em}
.qn{font-size:13px;color:var(--usu);margin:16px 0 0}
.moto{font-size:11.5px;color:var(--usu);margin-top:56px;border-top:1px solid #cdc3ae;
 padding-top:14px;word-break:break-all;letter-spacing:0;line-height:1.8}
@media(max-width:375px){.w{padding:0 16px 60px}}
</style></head><body><div class="w">

<section class="ichi">
%(ehtml)s
<div><span class="kazu">%(kazu)s</span><span class="tan">%(tan)s</span></div>
<p class="nani">%(nani)s</p>
<p class="hito">%(hitokoto)s</p>
<p class="sc">↓ つづきは下へ</p>
</section>

%(kurabe)s

<h2>どれくらいか</h2>
%(kanzan)s

<h2>確認できたこと</h2>
<ul>%(ok)s</ul>

<h2>確認できていないこと</h2>
<ul class="ng">%(ng)s</ul>

<h2>この3つを聞きたい</h2>
%(q)s
<p class="qn">責める話ではありません。ズルができない形になっていれば、この3つはすぐ答えられます。</p>

<p class="moto">もとのメモ：%(mnote)s ／ %(mtag)s<br>
原文：%(mclaim)s<br>
%(now)s ・ 1036 税金ライン</p>

</div></body></html>
""" % {
        "title": esc(k.get("title")), "hitokoto": esc(k.get("hitokoto")),
        "ehtml": ehtml,
        "kazu": esc(ookii.get("kazu")), "tan": esc(ookii.get("tan")),
        "nani": esc(ookii.get("nani")),
        "kanzan": kanzan, "kurabe": kurabe, "ok": ok, "ng": ng, "q": q,
        "mnote": esc(moto.get("note")), "mtag": esc(moto.get("tag")),
        "mclaim": esc(moto.get("claim")), "now": _now(),
    }


def gate_text(k: dict) -> str:
    """★門に渡す文章。HTMLではなく中身の言葉を渡す（タグで判定を濁らせない）。"""
    parts = [k.get("title", ""), k.get("hitokoto", "")]
    o = k.get("ookii") or {}
    parts.append("%s%s %s" % (o.get("kazu", ""), o.get("tan", ""), o.get("nani", "")))
    for x in k.get("kanzan") or []:
        parts.append("%s %s（%s）" % (x.get("nani"), x.get("atai"), x.get("shiki")))
    kb = k.get("kurabe") or {}
    parts.append(str(kb.get("midashi") or ""))
    for g in kb.get("gyo") or []:
        parts.append("%s %s %s" % (g.get("dare"), g.get("ikura"), g.get("memo")))
    parts.append("## 確認できたこと")
    for x in k.get("kakunin_ok") or []:
        parts.append("- %s %s" % (x.get("koto"), x.get("src")))
    parts.append("## 確認できていないこと")
    for x in k.get("kakunin_ng") or []:
        parts.append("- %s" % x)
    parts += list(k.get("shitsumon") or [])
    return "\n".join(str(p) for p in parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kiji", nargs="?")
    ap.add_argument("--rei", action="store_true")
    a = ap.parse_args()

    if a.rei or not a.kiji:
        print(json.dumps(REI, ensure_ascii=False, indent=1))
        return 0 if a.rei else 2

    k = json.load(open(a.kiji, encoding="utf-8"))
    for need in ("slug", "title", "hitokoto", "ookii", "kakunin_ok",
                 "kakunin_ng", "shitsumon"):
        if not k.get(need):
            print("原稿に %s がありません" % need)
            return 2

    # ★門。落ちたらHTMLを書かない
    p = subprocess.run([sys.executable, GATE, "--text", gate_text(k)],
                       capture_output=True, text=True)
    print(p.stdout.strip()[:3000])
    if p.returncode != 0:
        print("★門で落ちました。HTMLは作っていません。")
        return 1

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "%s.html" % k["slug"])
    with open(path, "w", encoding="utf-8") as f:
        f.write(build(k))
    print("できました: share/check/%s.html （%d bytes）"
          % (k["slug"], os.path.getsize(path)))
    print("次: python3 tools/kohyou.py share/check/%s.html --why \"1036 庶民版\""
          % k["slug"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
