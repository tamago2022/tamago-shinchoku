#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1044番【Vaultの読み口】Obsidian Vault の中のノートを**読むだけ**。

なぜ要るか（2026-09-24 実測）:
  Cowork/Dispatch のサンドボックスは ~/Library/Mobile Documents/... を
  マウントしていない（Read も bash も届かない。実測 2026-09-24 01:05）。
  たまごさんが「このノートを見て」と言うたびに中身を貼らせるのは水くみ（憲法第3条）。
  → 工場（Mac）側に「読むだけ」の口を1つ置いて、向こうから読ませる。

■ 安全のための縛り（ここを壊さない）
  ・**読むだけ。** 書き込み・削除・移動は一切しない（open は "r" のみ）。
  ・行き先は VAULT 配下だけ＝ALLOW_ROOT で保証。`..` で外へ出ようとしたら弾く。
  ・拡張子は .md / .txt / .json / .csv だけ。
  ・1ファイル 400KB まで（それ以上は切って「切った」と書いて返す）。
  ・**課金0。** 外へ1本も出ない。

使い方（払い出す側＝サンドボックス）:
  enqueue_job("vault", {"op": "read", "path": "grok調べ　motel.md"})
  enqueue_job("vault", {"op": "find", "query": "grok調べ"})   # 名前で探す
  enqueue_job("vault", {"op": "ls",   "path": ""})            # 直下を並べる
"""
import io
import os

VAULT = os.path.expanduser(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain")
ALLOW_EXT = (".md", ".txt", ".json", ".csv")
MAX_BYTES = 400 * 1024
MAX_HITS = 60


def _safe(rel):
    """VAULTの外へ出ようとしたら None を返す。"""
    rel = (rel or "").lstrip("/")
    p = os.path.realpath(os.path.join(VAULT, rel))
    root = os.path.realpath(VAULT)
    if p != root and not p.startswith(root + os.sep):
        return None
    return p


def _read(rel):
    p = _safe(rel)
    if not p:
        return {"ok": False, "error": "Vaultの外は読めません: %s" % rel, "totalYen": 0.0}
    if not os.path.isfile(p):
        return {"ok": False, "error": "ありません: %s" % rel, "totalYen": 0.0}
    if os.path.splitext(p)[1].lower() not in ALLOW_EXT:
        return {"ok": False, "error": "読める形ではありません: %s" % rel, "totalYen": 0.0}
    size = os.path.getsize(p)
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        text = f.read(MAX_BYTES)
    return {"ok": True, "path": os.path.relpath(p, os.path.realpath(VAULT)),
            "bytes": size, "truncated": size > MAX_BYTES,
            "text": text, "totalYen": 0.0}


def _find(query):
    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "探す言葉が空です", "totalYen": 0.0}
    root = os.path.realpath(VAULT)
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() not in ALLOW_EXT:
                continue
            if q in fn:
                full = os.path.join(dirpath, fn)
                hits.append({"path": os.path.relpath(full, root),
                             "bytes": os.path.getsize(full)})
                if len(hits) >= MAX_HITS:
                    return {"ok": True, "query": q, "hits": hits,
                            "more": True, "totalYen": 0.0}
    return {"ok": True, "query": q, "hits": hits, "more": False, "totalYen": 0.0}


def _ls(rel):
    p = _safe(rel)
    if not p or not os.path.isdir(p):
        return {"ok": False, "error": "フォルダがありません: %s" % rel, "totalYen": 0.0}
    names = sorted(n for n in os.listdir(p) if not n.startswith("."))
    return {"ok": True, "path": rel, "names": names[:400], "totalYen": 0.0}


def run_job(payload):
    p = payload or {}
    op = p.get("op") or "read"
    if not os.path.isdir(VAULT):
        return {"ok": False, "error": "Vaultが見つかりません: %s" % VAULT, "totalYen": 0.0}
    if op == "read":
        return _read(p.get("path"))
    if op == "find":
        return _find(p.get("query"))
    if op == "ls":
        return _ls(p.get("path") or "")
    return {"ok": False, "error": "知らないop: %s" % op, "totalYen": 0.0}


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(run_job({"op": sys.argv[1] if len(sys.argv) > 1 else "ls",
                              "path": sys.argv[2] if len(sys.argv) > 2 else "",
                              "query": sys.argv[2] if len(sys.argv) > 2 else ""}),
                     ensure_ascii=False, indent=1))
