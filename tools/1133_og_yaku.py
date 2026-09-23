#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1133番【焼く係】曲の一覧からOGカードをまとめて焼き、名簿（manifest）を書く。

たまごさん（2026-09-25）:
  「OG画像は1曲ずつ手で作らない。テンプレート1枚＋データで自動生成。
    テンプレートを直せば全曲に効く形。」
  「既存26,421曲にも一括で当てる。終わったぶんから本番に出す。」

■ 名前の付け方（ここが本番の住所になる）
    <artistId>__<songId>-<lang>.png     例: anzen-chitai__natsu-no-owari-ja.png
  本番では /og/<この名前> で出る。名簿に載っている曲だけ、サイトがこの住所を指す。

■ 使い方
    # 焼く（既にあるものは飛ばす。--force で焼き直す）
    python3 tools/1133_og_yaku.py --json songs.json --outdir /path/to/joy-relief-station/public/og
    # 名簿を書く（サイトはこれを見て、カードがある曲だけ住所を切り替える）
    python3 tools/1133_og_yaku.py --manifest /path/to/joy-relief-station/src/lib/ogCards.generated.ts \
        --outdir /path/to/joy-relief-station/public/og

  songs.json の1件:
    {"artistId":"anzen-chitai","songId":"natsu-no-owari","title":"夏の終りのハーモニー",
     "artist":"井上陽水・安全地帯","year":1986,"lang":"ja"}

■ 戻し方（1行）
    名簿ファイルの `export const OG_CARDS = new Set<string>([...])` を
    `new Set<string>([])` にして push すれば、全曲まるごと前の状態に戻る。
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))
IRO = 64          # 色数を64に落とす。155KB → 16KB。見た目は変わらない（実測 2026-09-25）


SAFE = re.compile(r"[^A-Za-z0-9_-]+")


def namae(artist_id, song_id, lang):
    """本番に出す住所（ファイル名）。日本語のidでも安全な形に落とす。
    名簿がキー→ファイル名の対応表を持つので、落としても引ける。"""
    base = "%s__%s" % (artist_id, song_id)
    safe = SAFE.sub("-", base).strip("-")[:70] or "x"
    import hashlib
    h = hashlib.md5(base.encode("utf-8")).hexdigest()[:6]
    return "%s-%s-%s.png" % (safe, h, lang)


def kotoba(title):
    """題が主にラテン文字なら英語の組み、そうでなければ日本語の組み。"""
    latin = sum(1 for c in title if c.isascii() and c.isalpha())
    ja = sum(1 for c in title if "\u3040" <= c <= "\u30ff" or "\u4e00" <= c <= "\u9fff")
    return "en" if latin >= ja else "ja"


def _load(name):
    p = os.path.join(HERE, name)
    spec = importlib.util.spec_from_file_location(name[:-3], p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def yaku(rows, outdir, force=False, quiet=False):
    card = _load("1133_og_card.py")
    kara = _load("1133_og_karappo.py")
    os.makedirs(outdir, exist_ok=True)
    yaita = tobashita = ochita = 0
    ochi = []
    for r in rows:
        lang = r.get("lang") or kotoba(r["title"])
        name = namae(r["artistId"], r["songId"], lang)
        p = os.path.join(outdir, name)
        if os.path.exists(p) and not force:
            tobashita += 1
            continue
        try:
            im = card.card(r["title"], r.get("artist", ""), r.get("year", "") or "", lang)
            buf = io.BytesIO()
            im.quantize(colors=IRO, method=2).save(buf, "PNG", optimize=True)
            raw = buf.getvalue()
            j = kara.judge_bytes(raw)
            if j["karappo"]:
                ochita += 1
                ochi.append([name, j["riyuu"]])
                continue
            with open(p, "wb") as f:
                f.write(raw)
            yaita += 1
        except Exception as e:
            ochita += 1
            ochi.append([name, [repr(e)[:80]]])
    out = {"焼いた": yaita, "元からあった": tobashita, "焼けなかった": ochita,
           "落ちた例": ochi[:10], "outdir": outdir}
    if not quiet:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


def manifest(outdir, path, rows=None):
    """名簿＝「曲のキー → カードのファイル名」の対応表。サイトはこれだけを見る。"""
    aru = set(os.listdir(outdir))
    pairs = []
    for r in (rows or []):
        lang = r.get("lang") or kotoba(r["title"])
        n = namae(r["artistId"], r["songId"], lang)
        if n in aru:
            pairs.append(("%s__%s-%s" % (r["artistId"], r["songId"], lang), n))
    pairs = sorted(set(pairs))
    body = "\n".join('  ["%s", "%s"],' % (k.replace('"', ''), v) for k, v in pairs)
    ts = """// 1133番【OGカードの名簿】tools/1133_og_yaku.py が自動生成する。手で書かない。
// ここに載っている曲だけ、og:image が /og/<ファイル名> を指す。載っていない曲は今まで通り。
// ★戻し方（1行）：下の配列を [] にして push すれば、全曲まるごと前の状態に戻る。
// 生成: %s  枚数: %d
export const OG_CARDS = new Map<string, string>([
%s
]);
""" % (time.strftime("%Y-%m-%d %H:%M"), len(pairs), body)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(ts)
    print("名簿を書きました: %s（%d枚）" % (path, len(pairs)))
    return len(pairs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--manifest")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if a.json:
        rows = json.load(io.open(a.json, encoding="utf-8"))
        if a.limit:
            rows = rows[:a.limit]
        yaku(rows, a.outdir, a.force)
    if a.manifest:
        rows = json.load(io.open(a.json, encoding="utf-8")) if a.json else []
        manifest(a.outdir, a.manifest, rows)


if __name__ == "__main__":
    main()
