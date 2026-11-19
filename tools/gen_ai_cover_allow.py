#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★2026-10-08 AIカバーの表示を「AIカバー 架空セッション コラボ」棚に入っている物だけに絞る許可名簿を作る。
たまごさん「知らないAIカバーがいっぱい入ってる。確認できていないものは外して、棚に入っているやつだけに絞って」

棚に入っている物＝①棚の静的カード（worlds.ts の ai-covers 棚）②DBの棚の並び（admin_shelf_picks。excluded/unmarked は除く）。
出力：joy-relief-station/src/lib/aiCoverShelfAllow.generated.ts（棚に新しく入れたら、このスクリプトを回して名簿を更新する）
使い方： python3 tools/gen_ai_cover_allow.py [joy-relief-stationのパス]
"""
import io, os, re, sys, importlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
t = importlib.import_module("2210_tanaire")
SHELF = "691ea732-7171-4d24-8030-fba1a9ec285b"
J = sys.argv[1] if len(sys.argv) > 1 else "/Users/mac/Desktop/joy-relief-station"
db = t.DB()
rows = db.q("select s.kind,s.ref from admin_shelf_picks p join admin_stock s on s.id=p.stock_id "
            "where p.shelf_id=%s and p.status not in ('excluded','unmarked') and s.deleted_at is null" % t.lit(SHELF))
songs, yts = set(), set()
for r in rows:
    if r["kind"] == "cover-guide" and r["ref"].startswith("ai-cover-archive/"):
        songs.add(r["ref"].split("/", 1)[1])
    elif r["kind"] == "youtube":
        m = re.search(r"v=([A-Za-z0-9_-]{11})", r["ref"])
        if m: yts.add(m.group(1))
w = io.open(os.path.join(J, "src/lib/worlds.ts"), encoding="utf-8").read()
i = w.index('id: "x-ai-shou-queen"')
j = w.index("\n        ],", i)
for m in re.finditer(r"artist=ai-cover-archive&song=([^\"&]+)", w[i - 200:j]):
    songs.add(m.group(1))
out = os.path.join(J, "src/lib/aiCoverShelfAllow.generated.ts")
io.open(out, "w", encoding="utf-8").write(
    "// 自動生成（tools/gen_ai_cover_allow.py）。手で編集しない。\n"
    "// 「AIカバー 架空セッション コラボ」棚に入っているAIカバーだけを表に出すための許可名簿。\n"
    "// 戻す時は coverGuide.ts の AI_COVER_LIMIT_TO_SHELF を false にする（データは1件も消していない）。\n"
    "export const AI_COVER_LIMIT_TO_SHELF = true;\n"
    "export const AI_COVER_SHELF_SONG_IDS: readonly string[] = %s;\n"
    "export const AI_COVER_SHELF_YOUTUBE_IDS: readonly string[] = %s;\n"
    % (sorted(songs).__repr__().replace("'", '"'), sorted(yts).__repr__().replace("'", '"')))
print("songs", sorted(songs)); print("yt", sorted(yts))
