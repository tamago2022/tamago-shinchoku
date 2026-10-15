#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1190号【未完了を全部出す。隠さない】2026-09-29

■ たまごさんの言葉（そのまま）
  「まだ完了してないもの、着手してないもの、やりかけのものがたくさんあると思うので、
    1回リストアップして。隠すことなく、進捗が分かるようにシンプルに。」
  「引き継いだ時に『何のことですか？』みたいになって調べながらやってた。あれ自体言いたくない。」

■ 作り方は発明しない（憲法1184番・オリジナル禁止）
  tools/1180_hikitsugi_ima.py と**同じ形**をそのまま使う：
  機械が既に持っている材料だけを読んで、md と スマホ用html を作り直すだけ。
  手で書くところは1つも無い＝腐らない。

■ 状態は4つしか使わない（たまごさん指定）
  本番に出た  … done/merged で、本番URLが付いているもの
  やりかけ    … 走っている／確認待ち／URLの無い完了（＝本番に出ていない）
  未着手      … 発車待ち。★走らせただけで何も変わっていないものはここ（やってるフリを書かない）
  止まっている… hold。理由（holdNote）が必ず付く

■ 出すもの
  status/1190_tanaoroshi.md    棚卸しの正本
  share/1190-tanaoroshi.html   スマホで開ける形（進捗表から飛ぶ）
  status/public/1190_tanaoroshi.json  件数だけ（他の係が読む用）

■ 入れ方
  tools/1180_hikitsugi_ima.py の build() から呼ぶ。
  1180は tools/genzaichi.py から呼ばれ、genzaichi は心臓が毎周回読み直す。
  ＝25分おきに勝手に作り直される。手で貼らない。
"""
import datetime
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")

QUEUE = os.path.join(ST, "queue.json")
SHININ = os.path.join(ST, "1190_shinin.md")

OUT_MD = os.path.join(ST, "1190_tanaoroshi.md")
OUT_HTML = os.path.join(REPO, "share", "1190-tanaoroshi.html")
OUT_JSON = os.path.join(ST, "public", "1190_tanaoroshi.json")

URL_HTML = "https://tamago2022.github.io/tamago-shinchoku/share/1190-tanaoroshi.html"

JST = datetime.timezone(datetime.timedelta(hours=9))

HONBAN = "本番に出た"
YARIKAKE = "やりかけ"
MICHAKUSHU = "未着手"
TOMATTE = "止まっている"
JUNBAN = [HONBAN, YARIKAKE, TOMATTE, MICHAKUSHU]


def _json(p, default):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _read(p):
    try:
        with io.open(p, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def honban_url(it):
    """その票に付いている『本番で開けるURL』を1本だけ返す。無ければ空。"""
    blob = json.dumps(it, ensure_ascii=False)
    out = []
    for u in re.findall(r"https?://[^\s\"\\)）、。]+", blob):
        if "github.com/tamago2022" in u:      # リポジトリのIssueは本番ではない
            continue
        if u.endswith(".md"):                 # .mdはスマホで開けない＝渡さない
            continue
        out.append(u.rstrip(".,"))
    # check ページ＞Lovable本番＞その他、の順で1本
    for key in ("/share/check/", "joy-relief-station.lovable.app", ""):
        for u in out:
            if key in u:
                return u
    return ""


def shiwake(it):
    """4つのうちどれか。★走らせただけで何も変わっていないものは『未着手』。"""
    st = it.get("status")
    u = honban_url(it)
    if st in ("done", "merged"):
        return (HONBAN, u) if u else (YARIKAKE, "")
    if st in ("running", "awaiting_check"):
        return YARIKAKE, u
    if st == "hold":
        return TOMATTE, u
    if st == "waiting":
        return MICHAKUSHU, u
    return None, u


def atsumeru():
    q = _json(QUEUE, {"items": []})
    box = {k: [] for k in JUNBAN}
    for it in (q.get("items") or []):
        k, u = shiwake(it)
        if not k:
            continue
        box[k].append({
            "n": it.get("n"),
            "title": (it.get("title") or "").strip(),
            "tsugi": tsugi_no_itte(it, k),
            "riyu": (it.get("holdNote") or "").strip() if k == TOMATTE else "",
            "url": u,
        })
    for k in box:
        box[k].sort(key=lambda r: -(r["n"] or 0))
    return box, (q.get("updatedAt") or "")


def tsugi_no_itte(it, k):
    if k == HONBAN:
        return "本番で開けるか自分の目で見る"
    if k == TOMATTE:
        return "塞いでいるものを外す"
    if k == YARIKAKE:
        if it.get("status") == "running":
            return "走っている（上限%s分）" % (it.get("limitMin") or "—")
        if it.get("status") == "awaiting_check":
            return "鬼監督で仕分ける"
        return "本番に出す（URLが無い完了は完了ではない）"
    return "着火する"


def hitokoto(box):
    return "／".join("%s %d" % (k, len(box[k])) for k in JUNBAN)


def build():
    now = datetime.datetime.now(JST)
    box, q_at = atsumeru()
    shinin = _read(SHININ)

    L = []
    A = L.append
    A("# 棚卸し（未完了を全部）— %s 時点・自動生成" % now.strftime("%m-%d %H:%M"))
    A("")
    A("**隠していない。発車待ちの台帳(queue.json)に居るもの全部をそのまま4つに分けただけ。**")
    A("走らせただけで何も変わっていないものは「未着手」に入れてある（やってるフリを書かない）。")
    A("")
    A("## 件数")
    A("")
    for k in JUNBAN:
        A("- **%s：%d件**" % (k, len(box[k])))
    A("")
    A("※ 取り消し済みの票はこの数に入れていない。")
    A("")

    for k in JUNBAN:
        rows = box[k]
        A("## %s（%d件）" % (k, len(rows)))
        A("")
        if not rows:
            A("なし。")
            A("")
            continue
        A("`状態｜案件名｜次の一手｜止まっている理由`")
        A("")
        for r in rows:
            riyu = ("｜%s" % r["riyu"][:100]) if r["riyu"] else ""
            url = ("　%s" % r["url"]) if r["url"] else ""
            A("- %s｜#%s %s｜%s%s%s" % (k, r["n"], r["title"][:60], r["tsugi"], riyu, url))
        A("")

    A("---")
    A("")
    A(shinin or "（status/1190_shinin.md が読めませんでした）")
    A("")
    A("*このファイルは tools/1190_tanaoroshi.py が作る。手で書き換えない（25分後に消える）。*")

    md = "\n".join(L) + "\n"
    with io.open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"madeAt": now.isoformat(timespec="seconds"), "url": URL_HTML,
                   "kensu": {k: len(box[k]) for k in JUNBAN},
                   "queueUpdatedAt": q_at}, f, ensure_ascii=False, indent=1)

    write_html(md, now, box)
    return box, md


def write_html(md, now, box):
    """スマホで開ける形。.mdはスマホで開けない（たまごさん指摘）。"""
    body = md
    body = re.sub(r"^# (.+)$", r"<h1>\1</h1>", body, flags=re.M)
    body = re.sub(r"^## (.+)$", r"<h2>\1</h2>", body, flags=re.M)
    body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", body)
    body = re.sub(r"`([^`]+)`", r"<code>\1</code>", body)
    body = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', body)
    body = re.sub(r"^---$", "<hr>", body, flags=re.M)
    body = re.sub(r"^(\s*)- (.+)$", r"\1・\2<br>", body, flags=re.M)
    body = body.replace("\n\n", "</p><p>")
    fuda = "".join(
        '<div class="k"><b>%s</b><span>%d</span></div>' % (k, len(box[k])) for k in JUNBAN)
    html = """<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>棚卸し（未完了を全部）</title>
<style>
:root{color-scheme:light dark}
body{margin:0;padding:16px 14px 64px;font-family:-apple-system,"Hiragino Sans",sans-serif;
line-height:1.75;max-width:760px;margin-inline:auto;font-size:16px}
h1{font-size:20px;line-height:1.4;margin:0 0 4px}
h2{font-size:17px;margin:28px 0 6px;padding:6px 10px;background:#00000010;border-radius:8px}
p{margin:8px 0}code{background:#00000012;padding:1px 5px;border-radius:5px;font-size:14px}
a{word-break:break-all}
hr{border:0;border-top:1px solid #00000022;margin:22px 0}
.kensu{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:14px 0}
.k{border:2px solid currentColor;border-radius:10px;padding:10px;text-align:center}
.k span{display:block;font-size:26px;font-weight:800}
</style>
<h1>棚卸し（未完了を全部）</h1>
<div class="kensu">%(fuda)s</div>
<p>%(body)s</p>
<p style="opacity:.6;font-size:13px">作り直した時刻 %(at)s（25分おき・自動）</p>
</html>
""" % {"fuda": fuda, "body": body, "at": now.strftime("%Y-%m-%d %H:%M")}
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with io.open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    b, _ = build()
    print("wrote", OUT_MD, OUT_HTML, "|", hitokoto(b))
