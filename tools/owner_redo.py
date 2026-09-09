#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
680番：「ここ直ってないよ、やり直して」の一言で自動的に列に戻す。

たまごさんの言葉（そのまま）：
  「画面が変わってる、オッケーみたいな。変わってないんだったらもう一回やり直してって、
   俺が口頭でここ治ってないよ、やり直してつったら、またセッションが自動的に列に並ぶ
   位のノリにしたい。」

Dispatch（たまごさんと会話しているセッション）が、会話の中で
「◯◯が直ってない」「やり直して」を聞いた、その場で呼ぶための道具。
**番号を店主に聞き直さない。** 題名・依頼文の一部から候補を探し、1件に絞れたら
そのままキューの先頭へ戻す。既存の queue_redo（進捗表の「↩︎やり直し」ボタンと同じ処理。
command_ingest.py）へそのまま乗せるので、実装は1本だけ（新設しない）。

使い方:
  # 番号が分かっているとき（一番確実）
  python3 tools/owner_redo.py --n 426 --note "画像がまだ大きいまま"

  # 番号が分からないとき（題名・会話の一部から自動で当てる）
  python3 tools/owner_redo.py --text "さっきのサムネイルの件、直ってないよ" --note "画像がまだ大きいまま"

  # 候補を確かめたいだけのとき（何も変更しない）
  python3 tools/owner_redo.py --text "サムネイル" --dry-run

出力は最後の1行が `OK <n> ...` か `AMBIGUOUS ...` か `NOTFOUND ...` のいずれかになるので、
Dispatch側はこの1行だけを見て次の一言をたまごさんへ返せばよい。
"""
import argparse
import difflib
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import command_ingest  # noqa: E402


def _searchable_items():
    """検索対象は「発車済み・完了済みを含む全部」。たまごさんが『直ってない』と言うのは
    たいてい done / awaiting_check / verifying の直後なので status で絞り込まない。
    deleted.json（一度完了して片付いたもの）も含める（490番の重複照合と同じ発想）。"""
    q = command_ingest._load_queue()
    items = list(q.get("items") or [])
    try:
        d = command_ingest.load_json(command_ingest.DELETED_PATH_FOR_DEDUPE, {"items": []})
        for it in d.get("items") or []:
            if not any(x.get("n") == it.get("n") for x in items):
                items.append(it)
    except Exception:
        pass
    return items


def _score(text, it):
    """題名(title)を最優先、依頼文(what)の先頭も見て、一番近いものを探す。
    完全に方式を作り込まず difflib（標準ライブラリ）の類似度＋部分一致で足りる。"""
    text = (text or "").strip()
    title = str(it.get("title") or "")
    what = str(it.get("what") or "")[:300]
    if not text:
        return 0.0
    best = 0.0
    for field, weight in ((title, 1.0), (what, 0.6)):
        if not field:
            continue
        if text in field or field in text:
            best = max(best, 0.9 * weight)
        ratio = difflib.SequenceMatcher(None, text, field).ratio()
        best = max(best, ratio * weight)
        # 単語（空白・句読点区切り）の重なりも見る。日本語は分かち書きしないので
        # 2文字以上の部分文字列一致で簡易に見る。
        for tok in [t for t in text.replace("　", " ").split() if len(t) >= 2]:
            if tok in field:
                best = max(best, 0.55 * weight)
    return best


def find_candidates(text, top=5):
    items = _searchable_items()
    scored = [(round(_score(text, it), 3), it) for it in items]
    scored = [s for s in scored if s[0] > 0]
    scored.sort(key=lambda s: (-s[0], -(s[1].get("n") or 0)))
    return scored[:top]


def resolve_n(text, threshold=0.5):
    """1件に絞れたら (n, None) を返す。絞れなければ (None, 候補リスト) を返す。"""
    scored = find_candidates(text, top=5)
    if not scored:
        return None, []
    top_score, top_it = scored[0]
    if top_score < threshold:
        return None, scored
    # 2位僅差（0.08以内）で候補が複数あるときは自動で決めず、たまごさんに聞き直さず
    # Dispatch側に候補を渡して選ばせる（番号を店主に聞くのではなく、Dispatchが本文で判断する）。
    if len(scored) > 1 and (top_score - scored[1][0]) < 0.08 and scored[1][0] >= threshold:
        return None, scored
    return top_it.get("n"), scored


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=None, help="番号が分かっているとき")
    ap.add_argument("--text", default=None, help="会話の一部・題名の一部（番号が分からないとき）")
    ap.add_argument("--note", default="", help="何が直っていなかったか（1行・空でもよい）")
    ap.add_argument("--priority", type=int, default=None, help="急がないやり直しのときだけ1-5で指定")
    ap.add_argument("--dry-run", action="store_true", help="候補を出すだけで何も変更しない")
    args = ap.parse_args()

    if not args.n and not args.text:
        print("FAILED 番号(--n)か手がかり(--text)のどちらかが必要です")
        sys.exit(1)

    n = args.n
    candidates = []
    if not n:
        n, candidates = resolve_n(args.text)
        if not n:
            if not candidates:
                print("NOTFOUND 「%s」に近い項目が見つかりませんでした" % args.text)
            else:
                lines = ["AMBIGUOUS 「%s」に近い項目が複数あります。番号で選び直してください:" % args.text]
                for score, it in candidates:
                    lines.append("  #%s (%.2f) %s" % (it.get("n"), score, it.get("title")))
                print("\n".join(lines))
            sys.exit(2)

    if args.dry_run:
        it = command_ingest._find_item(_searchable_items(), n)
        print("DRYRUN #%s %s" % (n, (it or {}).get("title")))
        return

    target = str(n)
    if args.priority:
        target = "%s:%d" % (target, args.priority)

    with command_ingest.queue_lock():
        status, msg = command_ingest.queue_redo(target, args.note)
    if status == "done":
        print("OK #%s %s" % (n, msg))
    else:
        print("FAILED #%s %s" % (n, msg))
        sys.exit(1)


if __name__ == "__main__":
    main()
