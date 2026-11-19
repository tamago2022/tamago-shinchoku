#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""カードの形の関所（2026-10-10・たまごさん「これ全般的に。バラバラなのが気持ち悪い」）。

公開（Lovable の公開ボタン＝tools/kohyou_osu.py）の**前に必ず通る**。1つでも違反があれば押さない。

止めるもの：
  ① DB：本番の棚に出ているカード（admin_shelf_picks の candidate/fixed）で、説明（whisper）が
     空・年だけ（"1980" など）のもの。ただし「行き先のページから説明を借りるカード」
     （曲ページ・部屋カード）は借り先があるので除外し、借り先の無い X・YouTube・外部リンクだけを見る。
     ★芋の棚の satoko369 さんのカードがこれ（説明が空で背が低く、列がガタガタになった）。
  ② コード：公開しようとしている版（Lovable が持つコミット）の
     scripts/patrol/check-card-face.mjs（見出しの形式違い・説明が空/年だけ・高さの固定がない部品）。

使い方:
  python3 tools/card_face_kanmon.py            … いまの main（origin/main）を点検
  python3 tools/card_face_kanmon.py <sha>      … その版を点検
  python3 tools/card_face_kanmon.py --db-only  … DBだけ
  python3 tools/card_face_kanmon.py --self-test
結果: status/public/card_face_kanmon.json（verdict: ok / ng / inconclusive）
終了コード: 0=違反0 / 1=違反あり（公開しない）/ 2=測れなかった（関所の故障。止めずに記録だけ）
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SITE = "/Users/mac/Desktop/joy-relief-station"
OUT = os.path.join(REPO, "status", "public", "card_face_kanmon.json")
WEAK = re.compile(r"^\s*(?:\d{4}\s*(?:年)?\s*[。.]?)?\s*$")
ENV_PATH = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")

SQL = r"""
select distinct s.id::text sid, s.kind, s.ref, s.title, s.whisper, sh.title shelf, sh.world
from admin_shelf_picks p join admin_stock s on s.id = p.stock_id join admin_shelves sh on sh.id = p.shelf_id
where p.status in ('candidate','fixed') and s.deleted_at is null
  and s.thumbnail_url is not null
  and (s.whisper is null or s.whisper ~ '^\s*([0-9]{4}\s*(年)?\s*[。.]?)?\s*$')
"""


def borrowable(kind, ref):
    """行き先のページから説明を借りられるカード（publicShelves.functions.ts borrowedCopyFor と同じ道）。"""
    ref = str(ref or "")
    if kind == "cover-guide":
        return True
    path = ref
    m = re.match(r"^https://joy-relief-station\.lovable\.app(/.*)$", ref)
    if m:
        path = m.group(1)
    return bool(re.match(r"^/(room/(card|food|dance|summer)/|cover-guide)", path))


def db_check():
    sys.path.insert(0, HERE)
    import importlib
    t = importlib.import_module("2210_tanaire")
    rows = t.DB().q(SQL) or []
    bad = [r for r in rows if not borrowable(r.get("kind"), r.get("ref"))]
    return [{"type": "db-desc-weak", "file": "admin_stock:" + r["sid"],
             "detail": "棚「%s」のカードの説明が%s：%s" % (r.get("shelf"), "空" if not (r.get("whisper") or "").strip() else "年だけ", (r.get("title") or "")[:40])}
            for r in bad]


def code_check(sha):
    """その版のファイルだけ取り出して、リポジトリの静的点検を走らせる（作業中の手元は触らない）。"""
    # realpath：macOS の /var → /private/var の付け替えで、node 側の「自分が本体か」判定が外れるのを防ぐ
    tmp = os.path.realpath(tempfile.mkdtemp(prefix="cardface_"))
    try:
        paths = ["src/components", "src/routes", "src/lib/worlds.ts", "src/lib/shelfCardTitles.generated.ts",
                 "src/lib/cardFace.ts", "src/styles.css", "scripts/patrol/check-card-face.mjs",
                 "scripts/patrol/card-face-allow.json"]
        ar = subprocess.run("git archive %s %s | tar -x -C %s" % (sha, " ".join(paths), tmp), shell=True,
                            cwd=SITE, capture_output=True, text=True, timeout=120)
        script = os.path.join(tmp, "scripts/patrol/check-card-face.mjs")
        if not os.path.exists(script):
            return None, "その版に check-card-face.mjs が無い（%s）" % (ar.stderr or "")[:120]
        out = os.path.join(tmp, "res.json")
        p = subprocess.run(["node", script, tmp, "--json", out], capture_output=True, text=True, timeout=120,
                           env=dict(os.environ, PATH=ENV_PATH))
        try:
            return json.load(open(out, encoding="utf-8")).get("violations", []), p.stdout[-400:]
        except Exception:
            return None, (p.stdout + p.stderr)[-300:]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def write(doc):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc["at"] = time.strftime("%F %T")
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)


def run(sha=None, db_only=False):
    v, notes = [], []
    try:
        v += db_check()
    except Exception as e:  # noqa: BLE001
        notes.append("DBを読めない：%r" % (e,))
    if not db_only:
        if not sha:
            subprocess.run(["git", "fetch", "-q", "origin"], cwd=SITE, capture_output=True, timeout=60)
            sha = "origin/main"
        cv, note = code_check(sha)
        if cv is None:
            notes.append("コードを点検できない：%s" % note)
        else:
            v += cv
    verdict = "ng" if v else ("inconclusive" if notes else "ok")
    write({"verdict": verdict, "sha": sha, "count": len(v), "violations": v[:200], "notes": notes})
    return verdict, v, notes


def self_test():
    ok = borrowable("cover-guide", "a/b") and borrowable("link", "/room/card/x") \
        and borrowable("link", "https://joy-relief-station.lovable.app/room/food/y") \
        and not borrowable("x", "https://x.com/a/status/1") and not borrowable("youtube", "https://youtu.be/x") \
        and WEAK.match("1980") and WEAK.match("") and WEAK.match("1980年。") and not WEAK.match("1980。いい曲")
    print("SELF-TEST", "OK" if ok else "NG")
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(self_test())
    sha = next((x for x in a if not x.startswith("--")), None)
    verdict, v, notes = run(sha, db_only="--db-only" in a)
    for x in v[:60]:
        print("✗", x.get("type"), x.get("file"), x.get("detail"))
    for n in notes:
        print("！", n)
    print("RESULT", verdict, len(v))
    sys.exit({"ok": 0, "ng": 1}.get(verdict, 2))
