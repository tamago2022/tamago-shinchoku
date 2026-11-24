#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""改善ループ：関所を頼んだ種類は、関所が入るまで次の候補を出さない門（247750番）。

━━ 実際に起きたこと（推測ではなく bin.json / manabu.json の実物）━━
  改善ループ（tools/kaizen_loop.py）が「速さ（hayasa）」の直し便を3回積んだ：
    204010 bruno-mars/24k-magic        → 子が直せずに終わった（stuck・コミット無し）
    204011 kuricorder-quartet/teikoku-no-march → 子が直せずに終わった（hold・コミット無し）
    204012 unicorn/hige-to-boin        → 子が直せずに終わった（verifying・コミット無し）

  manabu_kanmon() は同じ kind の失敗が2回に達した時点（204011）で
  「関所を1つ足して」という便（＝この247750番）を1回だけ積む（manabu.kanmon["hayasa"]）。
  だが、関所がまだ実装されていない間も candidates() は何も知らず、
  204012 は kanmon の便を積んだ後（20:19:11）に発車し、同じ失敗をもう一度出した（20:39）。

  ＝「気づいた」と「止めた」の間に隙間があった。気づいた時点で止めないと、
    関所が実装されるまでの間、同じ失敗がさらに積まれ続ける。

━━ この門がすること ━━
  manabu.json を見て、ある kind が
    ① 失敗回数が limit（既定2）以上 かつ
    ② まだ「関所を1つ足す」便（manabu.kanmon[kind]）が done/merged/awaiting_check になっていない
  なら、その kind を一時停止（paused）にする。
  candidates() はこの一時停止中の kind を候補から外す（他の kind・他のページは残す）。
  関所の便が完了（done/merged/awaiting_check）になった時点で自動的に再開する
  （＝このタスク自身が完了すれば "hayasa" の一時停止は自動解除される）。

使い方：
    python3 tools/kaizen_kind_matsu_kanmon.py --check --kind hayasa
    python3 tools/kaizen_kind_matsu_kanmon.py --list
    python3 tools/kaizen_kind_matsu_kanmon.py --self-test

終了コード: 0=候補に出してよい（止まっていない） / 2=止めた（一時停止中）
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
MANABU = os.path.join(ST, "kaizen", "manabu.json")
QUEUE = os.path.join(ST, "queue.json")
PUB = os.path.join(ST, "public", "kaizen_kind_matsu.json")

RESOLVED_STATUS = ("done", "merged", "awaiting_check")


def load(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def _queue_items_by_n(items=None):
    """list の items を n(str)→件 の辞書にする。items が None なら status/queue.json を直接読む。"""
    if items is None:
        q = load(QUEUE, {})
        items = q.get("items") or []
    out = {}
    for it in items:
        n = it.get("n")
        if n is not None:
            out[str(n)] = it
    return out


def paused_kinds(manabu, items=None, limit=2):
    """今、候補に出してはいけない kind の集合を返す。

    items: load_queue_items() が返す list、または None（その場で status/queue.json を読む）。
    """
    items_by_n = _queue_items_by_n(items)
    cnt = {}
    for r in manabu.get("rows") or []:
        cnt[r.get("kind")] = cnt.get(r.get("kind"), 0) + 1
    out = {}
    for kind, c in cnt.items():
        if not kind or c < limit:
            continue
        kan = (manabu.get("kanmon") or {}).get(kind)
        if kan:
            it = items_by_n.get(str(kan.get("n")))
            st = (it or {}).get("status")
            if st in RESOLVED_STATUS:
                continue  # 関所の便がもう終わっている＝再開してよい
        out[kind] = {"count": c, "kanmon": kan}
    return out


def check(kind, manabu=None, items=None, limit=2):
    manabu = manabu if manabu is not None else load(MANABU, {"rows": [], "kanmon": {}})
    paused = paused_kinds(manabu, items=items, limit=limit)
    return kind in paused, paused.get(kind)


def run_check(kind, limit=2):
    blocked, info = check(kind, limit=limit)
    if not blocked:
        print("KAIZEN_KIND_MATSU: PASS — %s は止まっていません（候補に出してよい）" % kind)
        return 0
    print("🛑 247750番の門が止めました。「%s」は一時停止中です。" % kind)
    print("  失敗回数: %s回／関所の便: %s番（まだ未完了）" % (
        (info or {}).get("count"), (info or {}).get("kanmon", {}).get("n") if info else None))
    print("\n  直し方：関所の便（%s番）を先に完了させる。完了すれば自動で再開します。"
          % ((info or {}).get("kanmon", {}).get("n") if info else "?"))
    return 2


def run_list(limit=2):
    manabu = load(MANABU, {"rows": [], "kanmon": {}})
    paused = paused_kinds(manabu, limit=limit)
    save(PUB, {"paused": paused, "limit": limit})
    if not paused:
        print("今、一時停止中の kind はありません。")
        return 0
    for kind, info in paused.items():
        print("%s：失敗%d回／関所便%s番（未完了）" % (kind, info.get("count"), (info.get("kanmon") or {}).get("n")))
    return 0


# ---------------------------------------------------------------------------
# 自己試験（逆テスト込み）
# ---------------------------------------------------------------------------

def self_test() -> int:
    ok = True

    def expect(label, cond):
        nonlocal ok
        mark = "OK" if cond else "NG"
        if not cond:
            ok = False
        print("[%s] %s" % (mark, label))

    # ① 失敗2回・関所便がまだ無い（kanmon未登録）→ 止める
    manabu1 = {"rows": [{"kind": "hayasa"}, {"kind": "hayasa"}], "kanmon": {}}
    blocked, _ = check("hayasa", manabu1, items=[])
    expect("失敗2回・関所便まだ無し → 止める（逆テスト含む）", blocked is True)

    # ② 失敗1回だけ → まだ止めない
    manabu2 = {"rows": [{"kind": "hayasa"}], "kanmon": {}}
    blocked, _ = check("hayasa", manabu2, items=[])
    expect("失敗1回だけ → 止めない", blocked is False)

    # ③ 失敗2回・関所便を積んだがまだ waiting → 止める
    manabu3 = {"rows": [{"kind": "hayasa"}, {"kind": "hayasa"}], "kanmon": {"hayasa": {"n": "9", "at": "x"}}}
    items3 = [{"n": "9", "status": "waiting"}]
    blocked, _ = check("hayasa", manabu3, items=items3)
    expect("失敗2回・関所便は waiting のまま → まだ止める", blocked is True)

    # ④ 失敗2回・関所便が done になった → 再開してよい（止めない）
    items4 = [{"n": "9", "status": "done"}]
    blocked, _ = check("hayasa", manabu3, items=items4)
    expect("関所便が done になった → 自動で再開（止めない）", blocked is False)

    # ⑤ 無関係な kind（ikidomari）は hayasa の一時停止に影響されない
    blocked, _ = check("ikidomari", manabu1, items=[])
    expect("無関係な kind は止めない", blocked is False)

    # ⑥ items を渡さず status/queue.json 読み込み経路でも落ちない（実行できることだけ確認）
    try:
        check("hayasa", manabu1, items=None)
        expect("items=None でも例外にならない", True)
    except Exception as e:
        expect("items=None でも例外にならない（%r）" % (e,), False)

    print()
    print("SELF_TEST: %s" % ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--kind")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--limit", type=int, default=2)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.list:
        return run_list(limit=args.limit)
    if args.check:
        if not args.kind:
            print("--kind が必要です", file=sys.stderr)
            return 1
        return run_check(args.kind, limit=args.limit)
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
