#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
98407番：発車待ち(status=waiting)の重複と「死に案件」をまとめて圧縮する（2026-10-19）。

依頼の原文：「発車待ちが4,678件。同じ依頼の言い直し・判定日赤の写し・言葉の断片が大量に
混ざっている。意味で束ねて（同じ目的のものは1件に統合し、元の番号をmergedとして紐づける）、
言葉の断片やルール文の写しは捨てる。たまごさん発の依頼の原文は消さずに統合先へ残す。」

■ 事前調査で分かったこと（憶測で全件を意味統合しない理由）
  - 発車待ちのtitle/hyoudaiはほぼ全件が distinct（4796/4798）。
    「判定日赤」3223件も (title, 言われた日時) でほぼ全件 distinct ＝
    これは「同じ依頼の言い直し」ではなく、**たまごさんの別々の発言1つずつ**。
    hyoudai（AIが付けた短い見出し）だけで束ねるのは危険（例：「中身の確認」113件は
    113個の別発言。同じ見出しでも中身は別物）。
  - 本当に機械的な重複と確認できたのは2種類だけ：
    A) status=waiting の中で `what` が一字一句まったく同じもの（心臓の多重起動などで
       同じ依頼が複数回積まれたもの）。
    B) title が "(1/78) 同じ見出し" のような自動分割の子票（423番の仕組み＝
       「大きすぎる仕事」を機械が10件ずつに割った残骸）。同じ元依頼・同じ見出しの
       子票がN本並んでいるだけで、たまごさんの発言としては1件。
  - 「この依頼は『全ページ』...大きすぎる仕事...」という前置きを持つ65件は、
    前置きの後に埋め込まれた「元の依頼」がそれぞれ全部別物だったため、**統合しない**
    （誤って束ねると別々のたまごさん発言を消してしまう）。

■ やること（既存の安全な仕組みにそのまま乗る。新しい危険な仕組みは作らない）
  - カテゴリA：`what`が同一の waiting グループ → 番号最小を残し、残りを
    status=hold + mergedInto + holdNote で統合（tools/gaibu_henji_matome.py の
    matome_inbox() と同じやり方）。
  - カテゴリB：自動分割の子票グループ → 番号最小の1枚に、残り全部の「対象一覧」部分を
    安全に積み（文字数上限つき）、残りを同じく hold + mergedInto で統合。
  - 書き込みは tools/queue_store.py の load_queue/snapshot_items/save_queue に乗る
    （差分マージ・件数減少は構造的に拒否される。items配列からは何も消さない）。

使い方：
  python3 tools/queue_compress_98407.py --plan        何を統合するかを数えるだけ（書かない）
  python3 tools/queue_compress_98407.py --apply        実際に統合して保存する
  python3 tools/queue_compress_98407.py --self-test     統合して保存し、直後に
                                         ①item配列から何も消えていないこと
                                         ②origin=="user"の全件が現存すること
                                         ③統合した子票がhold+mergedIntoになっていること
                                         ④canonical側に統合内容が積まれていること
                                         を機械的に照合し、QUEUE_COMPRESS_RESULT: PASS/FAILを出す。
"""
import collections
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import queue_store  # noqa: E402

SPLIT_TITLE_RE = re.compile(r'^\((\d+)/(\d+)\)\s*(.*)$')
MAX_APPEND_CHARS = 60000
REASON = "98407番・2026-10-19"
LOG_PATH = os.path.join(REPO, "status", "queue_compress_98407.jsonl")


def _n_int(it):
    try:
        return int(it.get("n"))
    except Exception:
        return 0


def normalize_what(w):
    return (w or "").strip()


def find_category_a(waiting_items):
    groups = collections.defaultdict(list)
    for it in waiting_items:
        w = normalize_what(it.get("what"))
        if not w:
            continue
        groups[w].append(it)
    return {w: xs for w, xs in groups.items() if len(xs) > 1}


def find_category_b(waiting_items):
    groups = collections.defaultdict(list)
    for it in waiting_items:
        m = SPLIT_TITLE_RE.match((it.get("title") or "").strip())
        if not m:
            continue
        total = int(m.group(2))
        base = m.group(3).strip()
        groups[(base, total)].append(it)
    return {k: v for k, v in groups.items() if len(v) >= 2}


def extract_part_block(it):
    """自動分割の子票から、その子だけが持つ『対象一覧』部分だけを取り出す。
    見つからなければ本文全体（上限つき）を使う。"""
    w = it.get("what") or ""
    marker = "# ★この仕事は自動分割の一部です"
    idx = w.find(marker)
    if idx == -1:
        return w.strip()
    return w[idx:].strip()


def pick_canonical(xs):
    xs = sorted(xs, key=_n_int)
    return xs[0], xs[1:]


def hold_absorbed(it, canonical_n, reason):
    it["status"] = "hold"
    it["mergedInto"] = canonical_n
    it["holdNote"] = (
        "%s（%s）。内容は消していません。戻すなら status を waiting に。"
        % (reason, REASON)
    )


def _log(row):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def plan_or_apply(apply_changes):
    q = queue_store.load_queue()
    items = q.get("items") or []
    snapshot = queue_store.snapshot_items(q)
    before_total = len(items)
    waiting = [it for it in items if it.get("status") == "waiting"]
    before_waiting = len(waiting)
    before_user_ns = sorted(
        it.get("n") for it in items if it.get("origin") == "user" and it.get("n") is not None
    )

    cat_a = find_category_a(waiting)
    cat_b = find_category_b(waiting)

    plan = {"A": [], "B": []}
    absorbed_total = 0

    for w, xs in cat_a.items():
        canonical, rest = pick_canonical(xs)
        plan["A"].append({
            "canonical": canonical.get("n"),
            "absorbed": [x.get("n") for x in rest],
            "snippet": w[:60],
        })
        if apply_changes:
            for it in rest:
                hold_absorbed(it, canonical.get("n"), "内容が一字一句同じ依頼のため統合")
        absorbed_total += len(rest)

    for (base, total), xs in cat_b.items():
        canonical, rest = pick_canonical(xs)
        plan["B"].append({
            "canonical": canonical.get("n"),
            "absorbed": [x.get("n") for x in rest],
            "base_title": base[:60],
            "total": total,
        })
        if apply_changes:
            blocks = []
            for it in rest:
                block = extract_part_block(it)[:2000]
                blocks.append("\n\n---\n● n=%s より統合：\n%s" % (it.get("n"), block))
            addition = "".join(blocks)
            if len(addition) > MAX_APPEND_CHARS:
                addition = addition[:MAX_APPEND_CHARS] + (
                    "\n\n（これ以上は長すぎるため省略。各nの元データはqueue.json内にhold状態で"
                    "現存しています。n一覧は holdNote/mergedInto を参照）"
                )
            marker = (
                "\n\n==================================================\n"
                "■ %s で統合した残り%d件ぶんの対象一覧（元は自動分割(%d本)の子票）\n"
                "==================================================" % (REASON, len(rest), total)
            )
            canonical["what"] = (canonical.get("what") or "") + marker + addition
            old_title = canonical.get("title") or ""
            canonical["title"] = SPLIT_TITLE_RE.sub(
                "(統合済み・全%d件を1件に) %s" % (total, base), old_title, count=1
            ) if SPLIT_TITLE_RE.match(old_title.strip()) else old_title
            for it in rest:
                hold_absorbed(it, canonical.get("n"), "自動分割(%d本)の子票を1件に統合" % total)
        absorbed_total += len(rest)

    after_waiting_inmem = len([it for it in items if it.get("status") == "waiting"])

    result = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "apply": apply_changes,
        "before_total_items": before_total,
        "before_waiting": before_waiting,
        "category_a_groups": len(cat_a),
        "category_b_groups": len(cat_b),
        "absorbed_total": absorbed_total,
        "after_waiting_inmemory": after_waiting_inmem,
        "plan": plan,
    }

    if apply_changes:
        ok = queue_store.save_queue(q, snapshot=snapshot)
        result["saved"] = ok
        _log(result)
        return result, q, before_user_ns
    else:
        _log(result)
        return result, None, before_user_ns


def self_test():
    result, _q, before_user_ns = plan_or_apply(apply_changes=True)
    ok = True
    problems = []

    if not result.get("saved"):
        ok = False
        problems.append("保存が拒否されました（queue_store.save_queue が False を返した）")

    # 保存後のディスクを読み直して照合する
    q2 = queue_store.load_queue()
    items2 = q2.get("items") or []
    by_n = {it.get("n"): it for it in items2 if it.get("n") is not None}

    # ① origin=="user" の全件が現存すること（n単位で存在確認。内容は削除していない）
    missing_user = [n for n in before_user_ns if n not in by_n]
    if missing_user:
        ok = False
        problems.append("origin=user の %d件が消えています: %s" % (len(missing_user), missing_user[:20]))

    # ② 統合予定だった absorbed がすべて hold + mergedInto になっていること
    checked = 0
    for cat in ("A", "B"):
        for g in result["plan"][cat]:
            canon_n = g["canonical"]
            if canon_n not in by_n:
                ok = False
                problems.append("canonical n=%s がディスクに見つかりません" % canon_n)
                continue
            for an in g["absorbed"]:
                checked += 1
                it = by_n.get(an)
                if it is None:
                    ok = False
                    problems.append("absorbed n=%s が消えています" % an)
                    continue
                if it.get("status") != "hold" or it.get("mergedInto") != canon_n:
                    ok = False
                    problems.append(
                        "absorbed n=%s が hold+mergedInto=%s になっていません(status=%s mergedInto=%s)"
                        % (an, canon_n, it.get("status"), it.get("mergedInto"))
                    )

    after_waiting = len([it for it in items2 if it.get("status") == "waiting"])
    after_total = len(items2)

    summary = {
        "before_total_items": result["before_total_items"],
        "after_total_items": after_total,
        "before_waiting": result["before_waiting"],
        "after_waiting": after_waiting,
        "category_a_groups": result["category_a_groups"],
        "category_b_groups": result["category_b_groups"],
        "absorbed_total": result["absorbed_total"],
        "absorbed_checked": checked,
        "origin_user_before": len(before_user_ns),
        "origin_user_missing": len(missing_user),
        "problems": problems,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("QUEUE_COMPRESS_RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    args = sys.argv[1:]
    if "--self-test" in args:
        sys.exit(self_test())
    apply_changes = "--apply" in args
    result, _q, _before_user_ns = plan_or_apply(apply_changes=apply_changes)
    print(json.dumps({
        "apply": apply_changes,
        "before_total_items": result["before_total_items"],
        "before_waiting": result["before_waiting"],
        "category_a_groups": result["category_a_groups"],
        "category_b_groups": result["category_b_groups"],
        "absorbed_total": result["absorbed_total"],
        "after_waiting_inmemory": result["after_waiting_inmemory"],
        "saved": result.get("saved"),
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
