#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1036番【税金ライン・1区＝拾う】Obsidianの #税金 系タグを1件1行の台帳にする。

━━ なぜ作ったか（2026-09-23・たまごさん原文）━━

  「Obsidianに『税金説明』『税金政治家』『税金無駄』『税金を見直す』『税金透明化』
    みたいなハッシュタグでいっぱい散らばってんのよ。それをピックアップして裏取りして、
    ひたすら裏取りしてまとめてくれるエージェントは誰がいいかね。
    俺、これわざわざアナログでもう調べたくないのよ。」

━━ この区がやること（これだけ。増やさない）━━

  Vault の .md を読んで、**#税金 で始まるタグ**が付いているノートから
  1件＝1行の台帳 status/uratori/dane.jsonl を作る。

  列： note（どのノート） / claim（主張・★原文そのまま） / urls（貼ってあるURL）
       / tag / status（未 / 済 / 取れず）

━━ 絶対に守ること（たまごさんの指示を動作に変換したもの）━━

  ★ Vault を1文字も書き換えない。open() は 'r' しか使わない。書き込み先は repo の中だけ。
  ★ 主張を勝手に要約して歪めない。**ノートの原文の1行をそのまま claim に入れる。**
     （要約はこの区の仕事ではない。歪みはここでしか防げない）
  ★ 台帳は追記。すでにある行の status（裏取りの結果）を上書きしない。
     同じものかどうかは sha1(note + claim) で決める。

━━ サンドボックスからは Vault に届かない ━━

  iCloud の Vault は Mac の上にしか無い。だからこのファイルは **Macの上で走る**。
  呼び方： status/mac_jobs/pending/ に .sh を置く（mac_job_runner.py が15秒で拾う）。
  使い走りは180秒で切られるので --budget で時間を区切り、途中まででも必ず台帳に書く。

━━ 使い方 ━━

    python3 tools/zeikin_hiroi.py                 # 拾って台帳に積む
    python3 tools/zeikin_hiroi.py --budget 120    # 120秒で切り上げる
    python3 tools/zeikin_hiroi.py --tags          # どのタグが何件あるか数えるだけ
    python3 tools/zeikin_hiroi.py --show 10       # 台帳の頭10件を見る

終了コード: 0=正常 / 2=Vaultが見つからない
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUTDIR = os.path.join(REPO, "status", "uratori")
DAICHO = os.path.join(OUTDIR, "dane.jsonl")
LOG = os.path.join(OUTDIR, "hiroi.log")

JST = timezone(timedelta(hours=9))

VAULT = os.path.expanduser(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
)

# ★「#税金」で始まるタグだけ。#税 では広すぎる（#税理士 等を巻き込む）
TAG_RE = re.compile(r"#(税金[0-9A-Za-z_぀-ヿ一-鿿々ー―\-]*)")
URL_RE = re.compile(r"https?://[^\s\)\]\>\"'、。」）]+")

# 拾わない場所（自分たちの作業ログ。たまごさんの主張ではない）
SKIP_DIRS = (
    "/.obsidian/", "/.trash/", "/.git/",
    "/_ルール/hooks/", "/受付台帳_自動記録", "/作業ログ_自動記録",
)

# 主張として拾わない行（見出しだけ・タグだけ・箇条書きの記号だけ）
def _is_noise(line: str) -> bool:
    s = line.strip()
    if len(s) < 8:
        return True
    body = TAG_RE.sub("", s).strip(" #-*>|・:：　")
    return len(body) < 6


def _now() -> str:
    return datetime.now(JST).strftime("%F %T")


def _sha(note: str, claim: str) -> str:
    return hashlib.sha1((note + "\x00" + claim).encode("utf-8")).hexdigest()[:16]


def load_daicho() -> dict:
    """既にある台帳を id -> 行 で返す。status は絶対に壊さない。"""
    rows = {}
    if not os.path.exists(DAICHO):
        return rows
    with open(DAICHO, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("id"):
                rows[r["id"]] = r
    return rows


# ★たまごさんから 2026-09-23 に来た「親のノート」。ここが税金の棚の入口。
#   obsidian://open?vault=tamago_brain&file=世界 社会 グローバル化　政治経済　歴史/
#     税金　年金　社会保険　福利厚生/💰税金　年金　社会保険
#   ★全角スペースが混ざっている。半角に直すと開かない。
HUB_DIR = "世界 社会 グローバル化　政治経済　歴史/税金　年金　社会保険　福利厚生"
# ★実測（2026-09-23 12:48・status/uratori/hub.txt）：たまごさんが貼ってくれたリンクの
#   ファイル名 💰税金　年金　社会保険.md は無く、本当の名前はこちらだった。
#   絵文字の位置が違うだけ。★リンクをそのまま信じず、必ず find で確かめる。
HUB_NOTE = HUB_DIR + "/税金　年金　社会保険💰🔥🔥🔥.md"


def walk_folder(vault: str, sub: str, budget: float):
    """★この棚は丸ごと拾う。タグが付いていないノートも中身は税金の話なので落とさない。"""
    base = os.path.join(vault, sub)
    t0 = time.time()
    if not os.path.isdir(base):
        return
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in sorted(files):
            if not fn.endswith(".md") or time.time() - t0 > budget:
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    yield os.path.relpath(path, vault), f.read()
            except Exception:
                continue


def walk_vault(vault: str, budget: float):
    """Vault を読む。★読むだけ。"""
    t0 = time.time()
    cut = False
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in files:
            if not fn.endswith(".md"):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, vault)
            if any(s in ("/" + rel.replace(os.sep, "/") + "/") for s in SKIP_DIRS):
                continue
            if any(s.strip("/") in rel for s in SKIP_DIRS):
                continue
            if time.time() - t0 > budget:
                cut = True
                return
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception:
                continue
            if "#税金" not in text:
                continue
            yield rel, text
    return


NUM_RE = re.compile(r"[0-9０-９]{2,}|[一二三四五六七八九十百千万億兆]{1,}[万億兆円%％割]")


def pick(text: str, rel: str, relaxed: bool = False, cap: int = 40):
    """1ノートから「主張の行」を取り出す。★原文のまま。要約しない。

    relaxed=True（棚を丸ごと拾うとき）は、タグが無くても
    数字かURLの入っている行を主張として拾う。
    """
    lines = text.splitlines()
    note_urls = URL_RE.findall(text)
    out = []
    for i, line in enumerate(lines):
        tags = TAG_RE.findall(line)
        if not tags:
            if not relaxed or len(out) >= cap:
                continue
            if not (NUM_RE.search(line) or URL_RE.search(line)):
                continue
            if _is_noise(line):
                continue
            tags = ["税金_棚"]
        claim = line.strip()
        if _is_noise(claim):
            # タグだけの行 → 次の中身のある行を主張として拾う（原文のまま）
            for j in range(i + 1, min(i + 6, len(lines))):
                nxt = lines[j].strip()
                if nxt and not _is_noise(nxt):
                    claim = nxt
                    break
            else:
                continue
        # その行と、前後2行に貼ってあるURL
        near = "\n".join(lines[max(0, i - 2): i + 3])
        urls = URL_RE.findall(near) or note_urls[:2]
        for t in dict.fromkeys(tags):
            out.append({
                "note": rel,
                "line": i + 1,
                "tag": "#" + t,
                "claim": claim,          # ★原文。要約しない
                "urls": list(dict.fromkeys(urls))[:5],
            })
            break  # 1行につき1件。タグ違いで重複させない
    return out


def cmd_collect(args) -> int:
    vault = args.vault or VAULT
    if not os.path.isdir(vault):
        print("Vaultが見つかりません: %s" % vault)
        print("★サンドボックスからは届きません。Mac の上で走らせてください。")
        return 2
    os.makedirs(OUTDIR, exist_ok=True)
    have = load_daicho()
    added = 0
    notes = 0
    tagcount = {}
    t0 = time.time()
    # ★親のノートの棚を丸ごと → そのあとタグ検索で残りを拾う
    if args.tana:
        src_iter = walk_folder(vault, HUB_DIR, args.budget)
        relaxed = True
    else:
        src_iter = walk_vault(vault, args.budget)
        relaxed = False
    with open(DAICHO, "a", encoding="utf-8") as out:
        for rel, text in src_iter:
            notes += 1
            for r in pick(text, rel, relaxed=relaxed):
                tagcount[r["tag"]] = tagcount.get(r["tag"], 0) + 1
                rid = _sha(r["note"], r["claim"])
                if rid in have:
                    continue
                r["id"] = rid
                r["status"] = "未"          # 未 / 済 / 取れず
                r["hiroi_at"] = _now()
                r["source"] = []            # 2区が埋める（URL + HTTPコード + 時刻）
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                have[rid] = r
                added += 1
    msg = "%s 拾い: ノート%d件 / 新規%d件 / 台帳合計%d件 / %.1f秒" % (
        _now(), notes, added, len(have), time.time() - t0)
    print(msg)
    for t, n in sorted(tagcount.items(), key=lambda x: -x[1]):
        print("  %-16s %d" % (t, n))
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass
    return 0


def cmd_tags(args) -> int:
    vault = args.vault or VAULT
    if not os.path.isdir(vault):
        print("Vaultが見つかりません: %s" % vault)
        return 2
    c = {}
    for rel, text in walk_vault(vault, args.budget):
        for t in TAG_RE.findall(text):
            c["#" + t] = c.get("#" + t, 0) + 1
    for t, n in sorted(c.items(), key=lambda x: -x[1]):
        print("%-20s %d" % (t, n))
    print("---- タグ%d種" % len(c))
    return 0


def cmd_show(args) -> int:
    rows = list(load_daicho().values())
    print("台帳 %d件（未%d / 済%d / 取れず%d）" % (
        len(rows),
        sum(1 for r in rows if r.get("status") == "未"),
        sum(1 for r in rows if r.get("status") == "済"),
        sum(1 for r in rows if r.get("status") == "取れず"),
    ))
    for r in rows[: args.show]:
        print("- [%s] %s %s" % (r.get("status"), r.get("tag"), r.get("claim", "")[:70]))
        print("    %s:%s  urls=%d" % (r.get("note"), r.get("line"), len(r.get("urls") or [])))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=None)
    ap.add_argument("--budget", type=float, default=120.0, help="秒。使い走りは180秒で切られる")
    ap.add_argument("--tana", action="store_true",
                    help="★親のノートの棚（税金　年金　社会保険　福利厚生）を丸ごと拾う")
    ap.add_argument("--tags", action="store_true", help="タグの数を数えるだけ")
    ap.add_argument("--show", type=int, default=0, help="台帳の頭N件を見る")
    args = ap.parse_args()
    if args.tags:
        return cmd_tags(args)
    if args.show:
        return cmd_show(args)
    return cmd_collect(args)


if __name__ == "__main__":
    sys.exit(main())
