#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
933番(7/7)：確認待ち40件棚卸しの仕組み化③「7日以上動いていない案件に自動でstale印」。

たまごさんの言葉（2026-09-17）：「進捗を見て8月30日のあれが出てきててさぁ、これ2週間以上前の
ことまだやってるんだと思って結構もうゾッとしたんだよね。治ってない。」

■ 何をするか（0円・AIを呼ばない・既存ログを読んで数えるだけ）
  queue.json の中で「まだ動いているはずの状態」（waiting/hold/awaiting_check/running/
  verifying/touchchecking/stuck）にある項目について、
    - 3日（72時間）以上その状態のまま → staleLevel="yellow"
    - 7日（168時間）以上その状態のまま → staleLevel="red"
  を machine 可読な形で残す。

■ queue.jsonにはcreatedAt/updatedAtが個々のitemに無い問題（shikumi.pyと同じ制約）
  自前の台帳 status/item_status_since.json で「いつからその状態か」を追跡する。
  初めて観測した項目は、item自身が持っている時刻っぽいフィールド
  （finishedAt→checkedAt→startedAt→holdReviewedAt の優先順）があればそれを「since」として
  採用し、無ければ「今」を起点にする（それより前から放置されていた可能性はあるが、
  無いものは測れないため。shikumi.pyのWAITING_SINCEと同じ割り切り）。

■ queue.jsonへの書き込みは「staleLevelが変わった時だけ」
  staleDaysは毎回動くので、もし常に書き込むとqueue_store.save_queue()の差分検出が
  常に「changed」と判定し、他プロセスと衝突する書き込み頻度が上がってしまう
  （過去に3回、queue.json項目が丸ごと消える事故が起きている＝案件#687）。
  ここでは staleLevel（""→"yellow"→"red"、またはその逆）が実際に変わった項目だけを
  queue_store経由で安全に(差分マージ・世代バックアップ付きで)書き戻す。
  staleDays自体はitemに書かず、別ファイル status/stale_summary.json に都度書く
  （表示用・件数の正本はこちら）。

実行:
  python3 tools/stale_marker.py             # 判定して status/stale_summary.json を書く。
                                             # staleLevelが変わった項目だけqueue.jsonへ反映。
  python3 tools/stale_marker.py --no-write  # queue.jsonは書かず、判定結果を表示するだけ。
"""
import datetime
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import queue_store as qs

JST = datetime.timezone(datetime.timedelta(hours=9))
SINCE_LEDGER = os.path.join(ST, "item_status_since.json")
SUMMARY_OUT = os.path.join(ST, "stale_summary.json")

# 「まだ動いているはず」の状態だけを対象にする。done/mergedは完了済みなので古くても正常。
ACTIVE_STATUSES = {"waiting", "hold", "awaiting_check", "running", "verifying", "touchchecking", "stuck"}

YELLOW_DAYS = 3.0
RED_DAYS = 7.0

TS_FIELDS_PRIORITY = ("finishedAt", "checkedAt", "startedAt", "holdReviewedAt")


def now_jst():
    return datetime.datetime.now(JST)


def jread(path, default):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def jwrite(path, data):
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _parse_ts(s):
    if not s:
        return None
    s = str(s)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            # コロン無しタイムゾーン("+0900")／コロンあり("+09:00")の両方を吸収する
            s2 = s
            if len(s2) >= 5 and s2[-5] in "+-" and s2[-3] != ":":
                s2 = s2[:-2] + ":" + s2[-2:]
            return datetime.datetime.strptime(s2, fmt.replace("%z", "%z")) if "%f" not in fmt or "." in s2 else None
        except Exception:
            continue
    # 素朴な fromisoformat フォールバック（Python 3.11+ はコロン無しTZも読めるが、3.9系向けに上のstrptimeを主にする）
    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        return None


def _best_seed_ts(it):
    for f in TS_FIELDS_PRIORITY:
        ts = _parse_ts(it.get(f))
        if ts:
            return ts
    return None


def update_since_ledger(items):
    """『いつからこの状態か』を自前台帳で追跡する（shikumi.pyのupdate_waiting_sinceを一般化）。
    状態が変わった項目・初めて観測した項目はsinceを付け替える。対象外になった項目は消す。"""
    ledger = jread(SINCE_LEDGER, {})
    now_iso = now_jst().isoformat()
    changed = False
    current_keys = set()
    for it in items:
        n = it.get("n")
        if n is None:
            continue
        status = it.get("status")
        if status not in ACTIVE_STATUSES:
            continue
        key = str(n)
        current_keys.add(key)
        entry = ledger.get(key)
        if not entry or entry.get("status") != status:
            seed = _best_seed_ts(it)
            since = seed.isoformat() if seed else now_iso
            ledger[key] = {"status": status, "since": since}
            changed = True
    for key in list(ledger.keys()):
        if key not in current_keys:
            del ledger[key]
            changed = True
    if changed:
        jwrite(SINCE_LEDGER, ledger)
    return ledger


def compute_stale(items, ledger):
    now = now_jst()
    rows = []
    for it in items:
        n = it.get("n")
        status = it.get("status")
        if n is None or status not in ACTIVE_STATUSES:
            continue
        entry = ledger.get(str(n)) or {}
        since_ts = _parse_ts(entry.get("since"))
        if since_ts is None:
            continue
        age_days = (now - since_ts).total_seconds() / 86400.0
        level = "red" if age_days >= RED_DAYS else ("yellow" if age_days >= YELLOW_DAYS else "")
        rows.append({
            "n": n,
            "title": it.get("title") or "",
            "status": status,
            "since": entry.get("since"),
            "ageDays": round(age_days, 1),
            "staleLevel": level,
        })
    return rows


def apply_to_queue(rows):
    """staleLevelが変わった項目だけ、queue_store経由で安全に書き戻す。書いた件数を返す。"""
    by_n = {r["n"]: r for r in rows}
    q = qs.load_queue()
    snap = qs.snapshot_items(q)
    touched = 0
    for it in q.get("items") or []:
        n = it.get("n")
        r = by_n.get(n)
        new_level = r["staleLevel"] if r else ""
        old_level = it.get("staleLevel") or ""
        if new_level != old_level:
            if new_level:
                it["staleLevel"] = new_level
            else:
                it.pop("staleLevel", None)
            touched += 1
    if touched:
        qs.save_queue(q, snapshot=snap)
    return touched


def main():
    no_write = "--no-write" in sys.argv
    q = qs.load_queue()
    items = q.get("items") or []
    ledger = update_since_ledger(items)
    rows = compute_stale(items, ledger)
    yellow = [r for r in rows if r["staleLevel"] == "yellow"]
    red = [r for r in rows if r["staleLevel"] == "red"]
    awaiting_check_n = len([it for it in items if it.get("status") == "awaiting_check"])

    summary = {
        "measuredAt": now_jst().isoformat(timespec="seconds"),
        "totalActive": len(rows),
        "yellowCount": len(yellow),
        "redCount": len(red),
        "yellow": sorted(yellow, key=lambda r: -r["ageDays"]),
        "red": sorted(red, key=lambda r: -r["ageDays"]),
        "awaitingCheckCount": awaiting_check_n,
        "awaitingCheckOverLimit": awaiting_check_n > 10,
    }
    jwrite(SUMMARY_OUT, summary)

    touched = 0 if no_write else apply_to_queue(rows)
    print(json.dumps({"yellowCount": len(yellow), "redCount": len(red),
                      "awaitingCheckCount": awaiting_check_n,
                      "queueItemsTouched": touched}, ensure_ascii=False))
    if red:
        print("🔴 7日以上停滞:", ", ".join("%s(%s日)" % (r["n"], r["ageDays"]) for r in red))
    if yellow:
        print("🟡 3日以上停滞:", ", ".join("%s(%s日)" % (r["n"], r["ageDays"]) for r in yellow))
    return 0


if __name__ == "__main__":
    sys.exit(main())
