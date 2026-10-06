#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1075番【突き合わせ】Spotifyの全曲と棚を並べて、**棚に無い曲**を洗い出す。

たまごさん（2026-09-24・原文）:
  「秋の曲、45曲は棚にあるけど、俺のSpotifyにはめちゃくちゃ入ってる。何百曲あるかもしれない。」
  「棚と突き合わせて、棚に無い曲を洗い出す。これが仕入れの元になる。」

★棚の正本はどこか（実測 2026-09-23／tools/tana.py の記述）
  ・曲の名簿 … joy-relief-station の `src/lib/coverGuide.ts`（コード）
      → この控えが status/_1039/src_lib_coverGuide.ts（6.5MB・38,031件の title）
  ・棚の中身 … Supabase の `admin_stock`（DB）
  ★ここでは**controlできる控え（コード側の名簿）**と突き合わせる。
    Supabaseの admin_stock は tools/tana.py の口で別に読める（GETだけ）。

★決まり
  ・外へ1本も出ない。鍵を使わない。課金0。サンドボックスでそのまま走る。
  ・棚に1文字も書かない。洗い出した一覧を status/1075_spotify/ に置くだけ。
  ・★曲名が似ているだけで「同じ」と決めない。曲名＋アーティストの両方で見る。
    片方だけ一致したものは「あやしい」として**別に分ける**（勝手に消さない）。

使い方:
  python3 tools/tana_awase.py                       # zenkyoku*.json を全部見る
  python3 tools/tana_awase.py status/1075_spotify/zenkyoku_秋.json
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SPO_DIR = os.path.join(REPO, "status", "1075_spotify")
TANA_FILES = [
    os.path.join(REPO, "status", "_1039", "src_lib_coverGuide.ts"),
    os.path.join(REPO, "status", "_1039", "src_lib_extraCards.ts"),
]

KAKKO = re.compile(r"\(.*?\)|\[.*?\]|（.*?）|【.*?】")
OMAKE = re.compile(r"\b(feat|ft|featuring|with|remaster(ed)?|remix|live|"
                   r"version|ver|edit|mix|mono|stereo|single|album|"
                   r"original|soundtrack|ost|inst(rumental)?)\b.*", re.I)
ZEN = {ord(c): ord(c) - 0xFEE0 for c in
       "".join(chr(x) for x in range(0xFF01, 0xFF5F))}


def norm(s):
    """突き合わせ用。記号・空白・大小・全半角の違いで別物にしない。"""
    s = (s or "").translate(ZEN).lower()
    s = KAKKO.sub(" ", s)
    s = OMAKE.sub(" ", s)
    s = re.sub(r"[^0-9a-z\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]+", "", s)
    return s


def tana_yomu():
    """棚の名簿から title / artist を拾う。TypeScriptを構文解析はしない
    （壊れやすい）。`title: "..."` の形だけを素直に拾う。"""
    kyoku, artist = set(), set()
    for p in TANA_FILES:
        if not os.path.exists(p):
            continue
        s = io.open(p, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r'\btitle:\s*"((?:[^"\\]|\\.)*)"', s):
            kyoku.add(norm(m.group(1)))
        for key in ("artist", "name", "artistName"):
            for m in re.finditer(r'\b%s:\s*"((?:[^"\\]|\\.)*)"' % key, s):
                artist.add(norm(m.group(1)))
    kyoku.discard("")
    artist.discard("")
    return kyoku, artist


def awaseru(spo_file):
    d = json.load(io.open(spo_file, encoding="utf-8"))
    kyoku_tana, artist_tana = tana_yomu()

    nai, ayashii, aru = [], [], []
    mita = set()
    for t in d.get("kyoku") or []:
        k = norm(t.get("kyoku"))
        a = norm(t.get("artist"))
        key = k + "|" + a
        if key in mita:
            continue
        mita.add(key)
        if k and k in kyoku_tana:
            # 曲名は棚にある。アーティストも棚にあれば「ある」、無ければ「あやしい」
            (aru if (a and a in artist_tana) else ayashii).append(t)
        else:
            nai.append(t)

    base = os.path.splitext(os.path.basename(spo_file))[0]
    out = {"at": time.strftime("%F %T"), "moto": os.path.relpath(spo_file, REPO),
           "tanaNoKyokuSu": len(kyoku_tana), "spotifyKyokuSu": len(mita),
           "tanaNiNai": len(nai), "ayashii": len(ayashii), "tanaNiAru": len(aru),
           "tanaNiNaiKyoku": nai, "ayashiiKyoku": ayashii}
    pj = os.path.join(SPO_DIR, "shiire_%s.json" % base)
    json.dump(out, io.open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    pm = os.path.join(SPO_DIR, "shiire_%s.md" % base)
    with io.open(pm, "w", encoding="utf-8") as f:
        f.write("# 棚に無い曲（仕入れの元）%s\n\n" % time.strftime("%F %T"))
        f.write("Spotify %d曲（重複なし）／棚の名簿 %d件と突き合わせ\n\n"
                % (len(mita), len(kyoku_tana)))
        f.write("- 棚に**無い**：%d曲\n- あやしい（曲名は棚にあるがアーティストが違う）：%d曲\n"
                "- 棚に**ある**：%d曲\n\n" % (len(nai), len(ayashii), len(aru)))
        f.write("## 棚に無い曲\n\n")
        for t in nai:
            f.write("- %s ／ %s ／ %s\n" % (t.get("kyoku"), t.get("artist"), t.get("url")))
        f.write("\n## あやしい（★人が見る。勝手に同じ物にしない）\n\n")
        for t in ayashii:
            f.write("- %s ／ %s ／ %s\n" % (t.get("kyoku"), t.get("artist"), t.get("url")))
    return {"ok": True, "files": [os.path.relpath(pj, REPO), os.path.relpath(pm, REPO)],
            **{k: v for k, v in out.items() if not k.endswith("Kyoku")}}


def main(argv):
    saki = argv[1:] or sorted(glob.glob(os.path.join(SPO_DIR, "zenkyoku*.json")))
    if not saki:
        print(json.dumps({"ok": False,
                          "error": "Spotifyの全曲ファイルがまだありません（status/1075_spotify/zenkyoku*.json）"},
                         ensure_ascii=False))
        return 1
    out = [awaseru(p) for p in saki]
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
