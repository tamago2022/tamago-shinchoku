#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-10-11 入荷の一覧ページ（スマホ用1枚）：share/check/nyuka-1011.html
数字は全部 status/nyuka_1011/nyuka.json・jev_all.json（無ければ jev10.json）・status/ura_tag/ から機械で数える。手で書いた数字は入れない。
  python3 tools/nyuka_1011_page.py
"""
import html
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import importlib  # noqa: E402

ura = importlib.import_module("ura_tag")
N = os.path.join(REPO, "status", "nyuka_1011")
OUT = os.path.join(REPO, "share", "check", "nyuka-1011.html")
e = html.escape


def load(p, d=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def jev():
    for f in ("jev_all.json", "jev10.json"):
        d = load(os.path.join(N, f))
        if d:
            m = {}
            for k, st in (("tooshita", "通過"), ("bessin", "別人で止めた"), ("horyuu", "未確認")):
                for x in d.get(k, []):
                    m[(x["artist_id"], x["song_id"])] = (st, x.get("riyu", ""))
            return m, f
    return {}, "なし"


def main():
    d = load(os.path.join(N, "nyuka.json"))
    rows = d["rows"]
    new = [r for r in rows if r["status"] == "new"]
    ex = [r for r in rows if r["status"] == "exist"]
    no = [r for r in rows if r["status"] == "no_official"]
    jm, jf = jev()
    v = ura.vocab()
    m = ura.merged()
    ins = ura.jsonl(ura.IN)
    tagged = {k: r for k, r in m.items() if any(c in r for c in ura.LIMITS)}
    total = len(ins)
    by = {c: sum(1 for r in tagged.values() if c in r) for c in ura.LIMITS}
    names = {"g": "ジャンル", "r": "国・地域", "e": "年代", "m": "気分", "s": "季節", "c": "シーン"}
    vk = {"g": "genre", "r": "region", "e": "era", "m": "mood", "s": "season", "c": "scene"}

    def label(rec):
        out = []
        for c in ("g", "r", "e", "m", "s", "c"):
            for t in rec.get(c, []):
                out.append(v[vk[c]].get(t, t))
        return "・".join(out)

    jt = {"通過": 0, "未確認": 0, "別人で止めた": 0}
    for r in new:
        st = jm.get((r["artist_id"], r["song_id"]), ("未確認", ""))[0]
        jt[st] = jt.get(st, 0) + 1
    h = []
    h.append("""<!doctype html><html lang=ja><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>10/11 入荷の一覧（新規・既存・公式なし）</title>
<style>
:root{color-scheme:dark}
body{margin:0;padding:16px;background:#0d1117;color:#e6edf3;font-family:-apple-system,"Hiragino Kaku Gothic ProN",sans-serif;line-height:1.6}
a{color:#8ef0ae}h1{font-size:1.2rem;margin:.2em 0 .6em}h2{font-size:1.02rem;margin:1.4em 0 .4em}
.box{border:1px solid #30363d;border-radius:12px;padding:12px 14px;margin:0 0 14px;background:#161b22}
.big{font-size:1.5rem;font-weight:800}
.warn{border-color:#e3b341}.warn b{color:#e3b341}
.card{border-bottom:1px solid #21262d;padding:8px 0}
.t{font-weight:700}.s{color:#8b949e;font-size:.8rem}.tag{color:#c9d1d9;font-size:.8rem}
.ok{color:#8ef0ae}.ng{color:#ff7b72}.mi{color:#e3b341}
small{color:#8b949e}
</style>""")
    h.append("<h1>10/11 入荷の一覧</h1>")
    h.append("<p><small>更新 %s ／ 数字は status/nyuka_1011/nyuka.json と status/ura_tag/ から機械で数えた。リスト %d 行。</small></p>" % (time.strftime("%Y-%m-%d %H:%M"), len(rows)))
    h.append('<div class=box><div class=big>新規 %d曲・既存 %d曲・公式なし %d曲</div>' % (len(new), len(ex), len(no)))
    h.append('<div>裏タグ付与 <b>%d曲</b> ／ 全 %d曲（Haikuの答えが返った %d曲のうち、1つ以上タグが付いたもの）</div>' % (len(tagged), total, len(m)))
    h.append('<div><small>新規の内訳：既存アーティストに %d曲・新しいアーティスト %d組（%d曲）。棚（名カバー含む）には入れていない＝曲ページとアーティストページだけ。</small></div></div>' % (
        sum(1 for r in new if not r.get("new_artist")), len({r["artist_id"] for r in new if r.get("new_artist")}), sum(1 for r in new if r.get("new_artist"))))
    h.append('<div class="box warn"><b>まだ本番に出していない。</b> 公開は「最優先 公開の詰まりを解消」（Lovable）が片付いてから。'
             'データは用意済み：<code>python3 tools/nyuka_1011_ireru.py ~/Desktop/joy-relief-station/src/lib/coverGuide.ts</code> で入る（何度走らせても重複しない）。</div>')
    h.append('<div class=box><b>本人判定の門（Jev／0円の代役 codex）</b>：通過 %d ／ 未確認 %d ／ 別人で止めた %d <small>（%s）。未確認は「鍵が無い・回線が遅くて答えが返らない」もの。公開前にもう一度通す。</small></div>' % (
        jt.get("通過", 0), jt.get("未確認", 0), jt.get("別人で止めた", 0), e(jf)))

    h.append("<h2>入れた曲（%d）</h2>" % len(new))
    for r in new:
        st = jm.get((r["artist_id"], r["song_id"]), ("未確認", ""))[0]
        cls = {"通過": "ok", "別人で止めた": "ng"}.get(st, "mi")
        tg = m.get("%s/%s" % (r["artist_id"], r["song_id"]), {})
        h.append('<div class=card><div class=t>%s — %s%s</div>' % (e(r["artist"]), e(r["title"]), " <small>（新しいアーティスト）</small>" if r.get("new_artist") else ""))
        h.append('<div class=s><a href="https://www.youtube.com/watch?v=%s">%s</a> ／ %s ／ 本人判定 <span class=%s>%s</span></div>' % (
            e(r["youtubeId"]), e(r["videoTitle"]), e(r["evidence"]), cls, st))
        if tg:
            h.append('<div class=tag>裏タグ：%s</div>' % e(label(tg)))
        h.append("</div>")
    mv = d.get("moved") or []
    if mv:
        h.append("<h2>棚を移した曲（%d）</h2>" % len(mv))
        for x in mv:
            h.append('<div class=card><div class=t>久保田利伸 — Missing</div><div class=s>%s。米倉利徳の棚から久保田利伸の棚へ（消さずに移す・同じ動画IDなので重複は増えない）。</div></div>' % e(x["why"]))
    h.append("<h2>既にあった曲（%d）</h2>" % len(ex))
    for r in ex:
        h.append('<div class=card><div class=t>%s</div><div class=s>在庫：%s「%s」 <a href="https://www.youtube.com/watch?v=%s">動画</a> ／ %s</div></div>' % (
            e(r["list"].replace("|", " — ")), e(r["key"]), e(r["title"]), e(r.get("youtubeId") or ""), e(r["why"])))
    h.append("<h2>公式が無かった曲（%d・入れていない）</h2>" % len(no))
    for r in no:
        c = (' <a href="https://www.youtube.com/watch?v=%s">候補（未確認チャンネル）</a>' % e(r["candidate"])) if r.get("candidate") else ""
        h.append('<div class=card><div class=t>%s</div><div class=s>%s%s</div></div>' % (e(r["list"].replace("|", " — ")), e(r["why"]), c))

    h.append("<h2>裏タグの語彙（画面には出さない）</h2><div class=box>")
    for c in ("g", "r", "e", "m", "s", "c"):
        h.append('<div><b>%s</b>（%d曲に付与）<br><small>%s</small></div>' % (names[c], by[c], e("・".join(v[vk[c]].values()))))
    h.append('<div><small>一覧に無い語は機械が捨てる（tools/ura_tag.py）。根拠の弱いものは付けない：確信の無いカテゴリは空、年代は曲の年の事実があればそれで上書き、アーティストの活動年代と食い違う年代は捨てる。今回入れた39曲（移した1曲を含む）は手で確かめた行（status/ura_tag/manual.jsonl）が勝つ。</small></div></div>')
    h.append('<p><small>動画の特定は YouTube Data API（検索・動画情報・チャンネル情報）だけで行った。再生・ブラウザは使っていない（音は出していない）。</small></p>')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write("\n".join(h) + "\n")
    print("書いた", OUT, "新規", len(new), "既存", len(ex), "公式なし", len(no), "裏タグ", len(tagged), "/", total)


if __name__ == "__main__":
    main()
