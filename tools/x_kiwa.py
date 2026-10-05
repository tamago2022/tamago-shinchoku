#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""34481番【キーワードからX投稿を集めてノートに格納】

たまごさん（2026-08-05・スマホから原文）:
  「キーワードを入力すると、該当するX投稿を集めてきて、
    Obsidian(ノートアプリ、ローカルのMarkdownファイル群)に格納してくれる」

★なぜゼロから作らないか（枷16：オリジナル禁止・下見済み status/original_kinshi/hyo-1791205909.json）
  2026-08-09に一度、ほぼ同じ道具（~/Desktop/x-archive-search/）が実在していた
  （Vault内 AI出力/40_プロジェクト/X過去投稿検索/00_開く.md が設計図として残っている）。
  ディスク整理でDesktop側の実体は失われたが、その後継として
  share/x-archive/（たまごさん本人の過去投稿47,214件・返信/RT除外・5分割でpublicに
  既に公開中）が同じデータを持っている。外部AIに白紙で聞いた結果（数万件規模は
  JSON線形スキャン＋文字列一致が定石、Obsidian側はYAML frontmatter＋1件1Markdownが
  定石で、専用の既製ツール/MCPは見つからない）を踏まえ、ゼロから検索エンジンを書かず、
  このデータと既存の「投げ込み箱」の道（ページ→中継所→command_ingest→ツール→Vault）
  をそのまま流用する。

★お金（憶測で書かない）
  ここで使うのは share/x-archive/tweets_data_*.json（自分の過去投稿アーカイブ）の
  ローカル検索だけ。外部APIを1回も叩かないので **0円・鍵も不要**。
  xAI Live Searchで「X全体」まで広げる拡張余地は残すが、既定の財布(xai)は上限0円
  （tools/yosan.py --show で確認済み）なので、たまごさんが明示的に開けるまでは使わない。

★書き込み先（Obsidian Vault 操作ルール）
  新規ノートの作成のみ（既存ファイルは一切書き換えない）。
  置き場所は既存の「AI出力/40_プロジェクト/X過去投稿検索/」（2026-08-09に既にある箱）。
  1回の呼び出しで作るノートは1本（10件以上の一括書き換えルールには触れない）。

使い方（CLIから直接）:
    python3 tools/x_kiwa.py "キーワード"
    python3 tools/x_kiwa.py --keyword "キーワード" --max 50

command_ingest.py からの呼び方:
    import x_kiwa
    x_kiwa.run_job({"op": "toru", "keyword": "地球", "max": 50})
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

ARCHIVE_GLOB = os.path.join(REPO, "share", "x-archive", "tweets_data_*.json")
VAULT = os.path.expanduser(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain")
NOTE_DIR_REL = os.path.join("AI出力", "40_プロジェクト", "X過去投稿検索")
HANDLE = "eggypop2014"  # share/x-archive の元アーカイブの本人アカウント（00_開く.md記載）
MAX_HITS_DEFAULT = 50
MAX_HITS_CAP = 200


def _load_archive():
    """share/x-archive/tweets_data_*.json（5分割・public）を結合して読む。0円・鍵不要。"""
    files = sorted(glob.glob(ARCHIVE_GLOB))
    rows = []
    for fp in files:
        try:
            with io.open(fp, encoding="utf-8") as f:
                rows.extend(json.load(f))
        except Exception:
            continue
    return rows


def search_archive(keyword, max_hits=MAX_HITS_DEFAULT):
    """キーワードを本文に含む投稿を、反応(score)が多い順で返す。大小文字・全角半角は素の比較のみ
    （既存share/x-archive/index.htmlの検索と同じ単純includes方式に合わせる。独自仕様を増やさない）。"""
    rows = _load_archive()
    kw = (keyword or "").strip()
    if not kw:
        return [], len(rows)
    hits = [r for r in rows if kw in (r.get("text") or "")]
    hits.sort(key=lambda r: -(r.get("score") or 0))
    max_hits = max(1, min(int(max_hits or MAX_HITS_DEFAULT), MAX_HITS_CAP))
    return hits[:max_hits], len(rows)


def _note_path(keyword):
    dir_abs = os.path.join(VAULT, NOTE_DIR_REL)
    os.makedirs(dir_abs, exist_ok=True)
    safe = re.sub(r"[\\/:*?\"<>|]", "_", keyword).strip() or "キーワード"
    safe = safe[:40]
    stamp = time.strftime("%Y%m%d-%H%M")
    base = "%s_%s" % (safe, stamp)
    p = os.path.join(dir_abs, base + ".md")
    i = 2
    # ★既存ファイルは絶対に上書きしない。同じ分(秒未満)で2回押されたら枝番で避ける
    while os.path.exists(p):
        p = os.path.join(dir_abs, "%s-%d.md" % (base, i))
        i += 1
    return p


def _build_markdown(keyword, hits, total_archive, live_note):
    lines = []
    lines.append("---")
    lines.append("created: %s" % time.strftime("%Y-%m-%d %H:%M"))
    lines.append('keyword: "%s"' % keyword.replace('"', "'"))
    lines.append("source: X過去投稿アーカイブ（@%s・全%d件中から検索）" % (HANDLE, total_archive))
    lines.append("tool: tools/x_kiwa.py（34481番）")
    lines.append("tags: [X投稿収集, キーワード検索]")
    lines.append("---")
    lines.append("")
    lines.append("# Xキーワード収集：%s" % keyword)
    lines.append("")
    lines.append("%d件ヒット（%s）" % (len(hits), live_note))
    lines.append("")
    if not hits:
        lines.append("ヒットなし。別の言い方で試してください。")
    for h in hits:
        date = h.get("date") or "(日付不明)"
        text = (h.get("text") or "").strip()
        tid = h.get("id") or ""
        fav = h.get("fav") or 0
        rt = h.get("rt") or 0
        url = "https://x.com/%s/status/%s" % (HANDLE, tid) if tid else ""
        lines.append("- **%s**　♥%s 🔁%s" % (date, fav, rt))
        preview = text.replace("\n", " ")
        if len(preview) > 160:
            preview = preview[:160] + "…"
        lines.append("  %s" % preview)
        if url:
            lines.append("  %s" % url)
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("関連: [[X過去投稿検索]]")
    lines.append("")
    lines.append("検索画面: https://tamago2022.github.io/tamago-shinchoku/share/x-archive/index.html")
    return "\n".join(lines) + "\n"


def run_job(payload):
    payload = payload or {}
    op = payload.get("op") or "shirabe"
    keyword = (payload.get("keyword") or payload.get("target") or "").strip()
    max_hits = payload.get("max") or MAX_HITS_DEFAULT

    if op == "shirabe":
        rows = _load_archive()
        return {"ok": True, "op": op, "archiveKensu": len(rows),
                "vaultAri": os.path.isdir(VAULT), "totalYen": 0.0}

    if op != "toru":
        return {"ok": False, "error": "知らない op です", "totalYen": 0.0}
    if not keyword:
        return {"ok": False, "error": "キーワードが空です", "totalYen": 0.0}
    if not os.path.isdir(VAULT):
        return {"ok": False, "error": "Vaultが見つかりません: %s" % VAULT, "totalYen": 0.0}

    hits, total = search_archive(keyword, max_hits)
    live_note = "自分の過去投稿アーカイブのみ・ライブ検索(xAI)は未使用"
    md = _build_markdown(keyword, hits, total, live_note)
    note_path = _note_path(keyword)
    with io.open(note_path, "w", encoding="utf-8") as f:
        f.write(md)

    rel = os.path.relpath(note_path, VAULT)
    return {"ok": True, "op": op, "keyword": keyword, "kensu": len(hits),
            "archiveKensu": total, "notePath": rel, "totalYen": 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keyword_pos", nargs="?", default=None)
    ap.add_argument("--keyword", default=None)
    ap.add_argument("--max", type=int, default=MAX_HITS_DEFAULT)
    ap.add_argument("--op", default="toru")
    a = ap.parse_args()
    kw = a.keyword or a.keyword_pos
    out = run_job({"op": a.op, "keyword": kw, "max": a.max})
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
