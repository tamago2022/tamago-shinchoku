#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
失敗台帳の機械可読な正本（案件#813・2026-09-14新設）。

■ 背景（たまごさんの言葉 2026-09-13）
  「失敗はしょうがない。だけど1個1個確実に再発しないように潰していってほしい」
  「これもデータだから、記録に残されて、なんなら共有されるべき」

■ 既にあるもの・新しく作るもの
  `status/failures.md` は既に正本として存在する（症状/原因/直し方/仕掛け/日付/根拠の
  プロース形式・2026-09-05〜）。これを置き換えない・書き換えない。
  本ファイルは、その台帳を**機械で数えられる形**にするための構造化レイヤーを追加する：
    - `status/failures.jsonl`（1行1件、追記専用。過去の失敗も可能な範囲でここへ変換済み）
    - 「潰した(prevented)」と言えるかどうかの厳格な3条件判定
    - 同じrootCauseが2回目に達したときの再発カウント
    - 週次ダイジェスト（新規/再発/潰した の3つの数）

■ 「潰した」と言える条件（厳格化・案件#813）
  次の3つが揃って初めて `preventedBy` を書いてよい（1つでも欠けたら空のままにする）：
   1. 原因が実測で特定されている（推測は書かない。rootCauseEvidenceに根拠を残す）
   2. 同じことが起きたら機械が気づく（テスト・ガード・生死表のいずれか）
   3. それが実際に動くことを、わざと壊して確認した（reverseTestに実行結果を残す）
  `preventedBy` が空の失敗は、まだ生きている失敗として `list-open` で赤に出る。

使い方:
  python3 tools/failures_ledger.py --add-json <file.json>   # 1件追記（idが既にあれば上書きしない）
  python3 tools/failures_ledger.py --list-open              # preventedByが空の一覧（赤）
  python3 tools/failures_ledger.py --weekly                 # 直近7日の新規/再発/潰した件数
  python3 tools/failures_ledger.py --check-recurrence "<rootCauseキーワード>"
                                                              # 既存の似たrootCauseを探す
  python3 tools/failures_ledger.py --summary                 # status/failures_summary.jsonへ書く（index.html用）
"""
import argparse
import io
import json
import os
import re
import time
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
JSONL = os.path.join(REPO, "status", "failures.jsonl")
SUMMARY = os.path.join(REPO, "status", "failures_summary.json")

REQUIRED_FIELDS = ["id", "date", "what", "howFound", "rootCause"]


def load_all():
    if not os.path.exists(JSONL):
        return []
    out = []
    with io.open(JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _dedupe_keep_latest(entries):
    """同じidが複数行あれば、後に書かれたもの（＝最新の状態）を正とする。"""
    by_id = {}
    order = []
    for e in entries:
        eid = e.get("id")
        if eid not in by_id:
            order.append(eid)
        by_id[eid] = e
    return [by_id[i] for i in order]


def is_prevented(entry):
    """3条件が揃っているかを機械的に判定する（厳格化）。"""
    has_root_cause = bool(entry.get("rootCause")) and bool(entry.get("rootCauseEvidence"))
    has_guard = bool(entry.get("preventedBy"))
    has_reverse_test = bool(entry.get("reverseTest"))
    return has_root_cause and has_guard and has_reverse_test


def normalize_keywords(text):
    if not text:
        return set()
    # 日本語はスペース区切りが無いので、英数字トークン＋既知の技術語だけを拾う簡易版。
    tokens = re.findall(r"[A-Za-z0-9_./\-]{3,}", text)
    return set(t.lower() for t in tokens)


def find_similar(entries, root_cause_text, exclude_id=None):
    """rootCauseの語彙が重なる既存エントリを探す（再発検出の簡易版）。"""
    kws = normalize_keywords(root_cause_text)
    matches = []
    if not kws:
        return matches
    for e in entries:
        if e.get("id") == exclude_id:
            continue
        other_kws = normalize_keywords(e.get("rootCause", ""))
        overlap = kws & other_kws
        if len(overlap) >= 2:
            matches.append((e, sorted(overlap)))
    return matches


def append_entry(entry, bump_recurrence_on_match=True):
    """1件追記する。REQUIRED_FIELDSが無ければ拒否する。既存の似たrootCauseがあれば
    recurrenceを+1して知らせる（自動で最優先へ、はqueue側の別の仕組みに委ねる＝ここは検知のみ）。"""
    missing = [k for k in REQUIRED_FIELDS if not entry.get(k)]
    if missing:
        raise ValueError("必須フィールドが空です: %s" % missing)
    entries = load_all()
    existing_ids = {e.get("id") for e in entries}
    if entry["id"] in existing_ids:
        raise ValueError("id %s は既に台帳にあります（差分で追記する。上書きしない）" % entry["id"])

    entry.setdefault("cost", "")
    entry.setdefault("fixedBy", "")
    entry.setdefault("preventedBy", "")
    entry.setdefault("reverseTest", "")
    entry.setdefault("rootCauseEvidence", "")
    entry.setdefault("recurrence", 0)
    entry.setdefault("lesson", "")
    entry.setdefault("recordedAt", datetime.now().isoformat(timespec="seconds"))

    sim = find_similar(entries, entry.get("rootCause", ""), exclude_id=entry["id"])
    if bump_recurrence_on_match and sim:
        entry["recurrence"] = max(entry.get("recurrence", 0), 1)
        entry["relatedIds"] = sorted({m[0].get("id") for m in sim if m[0].get("id")})

    with io.open(JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry, sim


def list_open(entries=None):
    entries = _dedupe_keep_latest(entries if entries is not None else load_all())
    return [e for e in entries if not is_prevented(e)]


def list_recurring(entries=None):
    entries = _dedupe_keep_latest(entries if entries is not None else load_all())
    return [e for e in entries if (e.get("recurrence") or 0) >= 1]


def weekly_digest(entries=None, now=None):
    entries = _dedupe_keep_latest(entries if entries is not None else load_all())
    now = now or datetime.now()
    week_ago = now - timedelta(days=7)
    new_count = 0
    recurring_count = 0
    prevented_count = 0
    for e in entries:
        d = e.get("date", "")
        try:
            dt = datetime.strptime(d[:10], "%Y-%m-%d")
        except Exception:
            continue
        if dt < week_ago:
            continue
        new_count += 1
        if (e.get("recurrence") or 0) >= 1:
            recurring_count += 1
        if is_prevented(e):
            prevented_count += 1
    return {
        "windowStart": week_ago.strftime("%Y-%m-%d"),
        "windowEnd": now.strftime("%Y-%m-%d"),
        "newCount": new_count,
        "recurringCount": recurring_count,
        "preventedCount": prevented_count,
    }


def write_summary():
    entries = _dedupe_keep_latest(load_all())
    open_list = list_open(entries)
    digest = weekly_digest(entries)
    summary = {
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "totalCount": len(entries),
        "openCount": len(open_list),
        "preventedCount": len(entries) - len(open_list),
        "recurringCount": len(list_recurring(entries)),
        "weekly": digest,
        "openTop": [
            {"id": e.get("id"), "what": e.get("what", "")[:80], "date": e.get("date", "")}
            for e in sorted(open_list, key=lambda e: e.get("date", ""), reverse=True)[:10]
        ],
    }
    with io.open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def quick_add(what, root_cause="", how_found="その場でたまごさんに指摘された", n=""):
    """924番【仕組み⑯】失敗が自動で記録に流れる形にする。
    たまごさんの言葉：『怒られた・指摘された内容が、その場で記憶ファイルと引き継ぎ書に
    入るようにする。人が後でまとめる形だと忙しい日に落ちる』（クロ丸は9/14〜16の44時間、
    記録が1本も無かった）。
    `--add-json`はファイルを別途作る手間があり、忙しい時ほど後回しにされる。
    このコマンドは指摘を受けたその場で1行で流せるようにする最短の入口。"""
    today = datetime.now().strftime("%Y-%m-%d")
    now_s = datetime.now().strftime("%Y%m%d%H%M%S")
    entry = {
        "id": "F-%s-quick" % now_s,
        "date": today,
        "what": what,
        "howFound": how_found,
        "rootCause": root_cause or "（未特定・後で埋める）",
        "queueRef": n,
    }
    saved, sim = append_entry(entry)
    return saved, sim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add-json", help="1件分のJSONファイルを追記する")
    ap.add_argument("--quick", help="怒られた・指摘された内容を、その場で1行で記録する（詳細JSON不要）")
    ap.add_argument("--root-cause", default="", help="--quickと併用。分かっていれば原因も添える")
    ap.add_argument("--n", default="", help="--quickと併用。関連する号番号")
    ap.add_argument("--list-open", action="store_true")
    ap.add_argument("--weekly", action="store_true")
    ap.add_argument("--check-recurrence", help="rootCauseのキーワードで既存の似た失敗を探す")
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()

    if args.quick:
        saved, sim = quick_add(args.quick, args.root_cause, n=args.n)
        print("QUICK追記:", saved["id"], "|", saved["what"][:60])
        if sim:
            print("⚠ 似たrootCauseの既存失敗が%d件見つかりました（再発の疑い）:" % len(sim))
            for e, overlap in sim:
                print("  -", e.get("id"), "|", e.get("what", "")[:60], "| 一致語:", overlap)
        return

    if args.add_json:
        entry = json.load(io.open(args.add_json, encoding="utf-8"))
        saved, sim = append_entry(entry)
        print("追記:", saved["id"])
        if sim:
            print("⚠ 似たrootCauseの既存失敗が%d件見つかりました（再発の疑い）:" % len(sim))
            for e, overlap in sim:
                print("  -", e.get("id"), "|", e.get("what", "")[:60], "| 一致語:", overlap)
        return

    if args.list_open:
        entries = load_all()
        open_list = list_open(entries)
        print("まだ潰していない失敗: %d件" % len(open_list))
        for e in sorted(open_list, key=lambda e: e.get("date", ""), reverse=True):
            print("🔴", e.get("id"), "|", e.get("date"), "|", e.get("what", "")[:70])
        return

    if args.weekly:
        d = weekly_digest()
        print("今週の新規失敗: %d件 / 再発: %d件 / 潰した: %d件（%s〜%s）" % (
            d["newCount"], d["recurringCount"], d["preventedCount"], d["windowStart"], d["windowEnd"]))
        return

    if args.check_recurrence:
        entries = load_all()
        sim = find_similar(entries, args.check_recurrence)
        if not sim:
            print("似たrootCauseは見つかりませんでした。")
        for e, overlap in sim:
            print(e.get("id"), "|", e.get("what", "")[:60], "| 一致語:", overlap)
        return

    if args.summary:
        s = write_summary()
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return

    ap.print_help()


if __name__ == "__main__":
    main()
