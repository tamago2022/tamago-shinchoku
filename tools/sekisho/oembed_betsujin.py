#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""アーティストページの別人混入を、oEmbed（YouTubeのチャンネル名・題名）で機械的に洗い出す（2026-10-15）。

なぜ要るか（実測 2026-10-15）：
  アダム・ローズ（コメディアン @realadamrose）のページに、同名のゴスペル歌手・WWEレスラー・アニメの Adam が混ざっていた。
  全37,308本を oEmbed で照合したら、94棚・254本の別人／的外れが見つかった（王OKの棚に ONE OK ROCK、
  Rufus の棚に RÜFÜS DU SOL、SPEED の棚に IShowSpeed、U.F.O. の棚にペンタゴンのUFO映像…）。
  原因はいつも同じ：**名前で検索して拾った動画を、チャンネル名を見ずに棚へ入れている。**

何をするか（0円・APIキー不要。oEmbed は無料・鍵なし）：
  1. coverGuide.ts の全動画の oEmbed（チャンネル名・題名）を取る（Macで。サンドボックスからは出られない）
  2. 英字の短い名前（2〜7文字）を持つ棚で、チャンネル名にも題名にも棚の名前が「単語として」出てこない動画を候補に出す
  3. 同じ棚に「棚と同名のチャンネル」が2つ以上ある棚を候補に出す（アダム・ローズ型）
  ★候補は「保留」。外すのは人（またはAI）が1件ずつ見てから。名前の一致は本人の証明にならない（sekisho-artist-song）。

使い方（Macで）：
  python3 tools/sekisho/oembed_betsujin.py --cg <joy-relief-station>/src/lib/coverGuide.ts --work status/_betsujin
  → status/_betsujin/kouho.txt（候補一覧）／oembed.jsonl（取得結果・次回は差分だけ取る）
"""
import argparse, collections, concurrent.futures as cf, json, os, re, subprocess, sys, unicodedata
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from parse_coverguide import parse  # noqa: E402

def oembed(i):
    p = subprocess.run(["curl", "-s", "-m", "20", "-w", "\n%{http_code}",
                        "https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v=" + i],
                       capture_output=True, text=True).stdout
    body, _, code = p.rpartition("\n")
    try: d = json.loads(body)
    except Exception: d = {}
    return {"yt": i, "code": code, "author": d.get("author_name"), "author_url": d.get("author_url"), "title": d.get("title")}

def norm(s): return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", s or "").lower())

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--cg", required=True); ap.add_argument("--work", default="status/_betsujin")
    ap.add_argument("--no-fetch", action="store_true"); a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    rows = []
    for ar in parse(a.cg):
        for s in ar["songs"]:
            m = re.search(r'youtubeId:\s*"([\w-]{11})"', s["raw"])
            if m: rows.append({"artist": ar["id"], "name": ar["name"], "aliases": ar.get("aliases", []), "song": s["id"], "title": s["title"], "yt": m.group(1)})
    out = os.path.join(a.work, "oembed.jsonl"); oe = {}
    if os.path.exists(out):
        for l in open(out, encoding="utf-8"):
            try: d = json.loads(l); oe[d["yt"]] = d
            except Exception: pass
    todo = [y for y in dict.fromkeys(r["yt"] for r in rows) if y not in oe]
    if todo and not a.no_fetch:
        with open(out, "a", encoding="utf-8") as f, cf.ThreadPoolExecutor(12) as ex:
            for d in ex.map(oembed, todo): oe[d["yt"]] = d; f.write(json.dumps(d, ensure_ascii=False) + "\n")
    by = collections.defaultdict(list)
    for r in rows: by[r["artist"]].append(r)
    lines = []; n = 0
    for aid, rs in by.items():
        names = [rs[0]["name"]] + rs[0]["aliases"]; nn = set(norm(x) for x in names if len(norm(x)) >= 3)
        # 型A：同名チャンネルが2つ以上（アダム・ローズ型）
        ch = collections.defaultdict(list)
        for r in rs:
            d = oe.get(r["yt"]) or {}
            if d.get("author_url"): ch[d["author_url"]].append((r, d))
        same = [u for u, l in ch.items() if norm(l[0][1]["author"]) in nn and not re.search(r"topic|vevo|official|公式", l[0][1]["author"] or "", re.I)]
        if len(same) >= 2:
            lines.append("## [同名チャンネル複数] %s %s" % (aid, rs[0]["name"]))
            for u in same: lines.append("    %s %s 本 | %s" % (ch[u][0][1]["author"], len(ch[u]), " / ".join(x[1]["title"][:40] for x in ch[u][:3])))
        # 型B：短い英字名の棚で、名前がどこにも出てこない動画
        if any(re.fullmatch(r"[a-z]{2,7}", norm(x)) for x in names):
            sus = []
            for r in rs:
                d = oe.get(r["yt"]) or {}
                if not d.get("author"): continue
                s = (d["author"] or "") + " " + (d.get("title") or "")
                if not any(len(x) >= 2 and re.search(r"(?<![A-Za-z])" + re.escape(x) + r"(?![A-Za-z])", s, re.I) for x in names):
                    sus.append("    %s ‖ %s ‖ %s" % (r["title"][:35], d["author"][:30], (d.get("title") or "")[:55]))
            if sus:
                n += len(sus); lines.append("## [名前が出てこない] %s %s %d本中%d" % (aid, rs[0]["name"], len(rs), len(sus))); lines += sus
    open(os.path.join(a.work, "kouho.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("動画 %d本 / oEmbed %d件 / 候補の行 %d" % (len(rows), len(oe), len(lines)))

if __name__ == "__main__":
    main()
