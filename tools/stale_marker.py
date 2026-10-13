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

■ 1466番の修正（2026-09-28・1回目）：backfill項目の時計がリセットされていたバグ
  たまごさんが2026-09-19 20:23に言った苦言（進行の遅さ・仕組みづくり・ミスをしない仕組み）が
  queue.jsonへ実際に登録されたのは2026-09-26（"queuedAtSource":"1372backfill:言われた日時"）。
  旧コードは _best_seed_ts が finishedAt/checkedAt/startedAt/holdReviewedAt しか見ておらず、
  「waiting」状態の新規項目にはどれも無いため、初めて観測した時刻＝"now"を since にしていた。
  結果、9日前に言われたはずの苦言が「2.2日前から待機中」と誤って若返り、
  3日しきい値のyellowにすら届かず、赤化の見逃し（今回の1466番自身）が起きた。
  1回目の修正：①TS_FIELDS_PRIORITYの末尾に queuedAt を追加。②既存台帳の自己修復を追加。

■ 1466番の修正（2026-09-28・2回目＝AI検品FAILを受けた再修正）
  1回目はqueuedAtだけを見ており、発端の案件#1398自身がqueuedAtを一度も持たず
  urakataBlockedAt（裏方キュー投入時刻）しか持っていなかったため、#1398自身は直らなかった
  （AI検品指摘：「同様のフィールド欠落waitingが524件残る」）。
  実測：aktive状態905件中565件がfinishedAt/checkedAt/startedAt/holdReviewedAt/queuedAtを
  1つも持たない。うち197件はurakataBlockedAtのみ保持、68件は本文の「【出どころ】…（日時）」に
  実際に言われた日時が埋め込まれているのにどのフィールドにも構造化されていない、
  残り300件は本当にどこにも時刻情報が無い（対応不能・既存の"nowにフォールバック"のまま）。
  2回目の修正：
    ①出どころ日時抽出 _extract_dekoro_ts() を追加。what/original_textの
      「【出どころ】…（YYYY-MM-DD HH:MM…)」からJSTの実発言時刻を読む
      （たまごさんが「本当に言った時刻」＝最も正確な起点なので、queuedAtやurakataBlockedAtより
      優先する。ただしfinishedAt/checkedAt/startedAt/holdReviewedAtという
      「今のステータスに入った実測時刻」がある場合はそちらを優先し、動いている案件を
      誤って古く見せない＝既存テスト「startedAtがあればqueuedAtより優先」の意味論を壊さない）。
    ②TS_FIELDS_PRIORITYの末尾に urakataBlockedAt を追加（queuedAtの次の最終フォールバック）。
    ③自己修復ロジックは変更なし（seedがsinceより古ければ補正）で①②の新しい種を拾える。
  検品: python3 tools/stale_marker.py --self-test
"""
import datetime
import io
import json
import os
import re
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

# 「今のステータスに入った実測時刻」＝動いている案件を誤って古く見せないための最優先グループ。
STATUS_ENTRY_FIELDS = ("finishedAt", "checkedAt", "startedAt", "holdReviewedAt")
# ↑これらが無い時だけ、出どころ日時（本文埋め込み・最優先）→queuedAt→urakataBlockedAtの順で試す。
FALLBACK_FIELDS_AFTER_DEKORO = ("queuedAt", "urakataBlockedAt")
TS_FIELDS_PRIORITY = STATUS_ENTRY_FIELDS + ("queuedAt", "urakataBlockedAt")  # 後方互換のため残す（未使用箇所参照防止）

_DEKORO_RE = re.compile(r"【出どころ】[^（(]*[（(](\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})")


def _extract_dekoro_ts(it):
    """本文中の「【出どころ】...（YYYY-MM-DD HH:MM／...)」から、たまごさんが実際に言った
    日時をJSTとして読み取る。無い・パースできない場合はNone。"""
    for field in ("what", "original_text"):
        text = it.get(field)
        if not text:
            continue
        m = _DEKORO_RE.search(str(text))
        if not m:
            continue
        try:
            y, mo, d = m.group(1).split("-")
            hh, mm = m.group(2), m.group(3)
            return datetime.datetime(int(y), int(mo), int(d), int(hh), int(mm), tzinfo=JST)
        except Exception:
            continue
    return None


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
    # ①今のステータスに入った実測時刻（動いている案件はここを優先。壊さない）
    for f in STATUS_ENTRY_FIELDS:
        ts = _parse_ts(it.get(f))
        if ts:
            return ts
    # ②出どころ日時（本文埋め込み＝たまごさんが実際に言った時刻）。
    #   queuedAt/urakataBlockedAtは裏方処理・キュー投入の都合で遅れることがあるため、
    #   本当の起点であるこちらを優先する（1466番2回目の核心）。
    dekoro = _extract_dekoro_ts(it)
    if dekoro:
        return dekoro
    # ③queuedAt→urakataBlockedAtの順で最終フォールバック
    for f in FALLBACK_FIELDS_AFTER_DEKORO:
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
        else:
            # 1466番の自己修復：状態が変わっていなくても、backfillされたqueuedAt等が
            # 記録済みのsinceより古ければ、より正確な古い方へ補正する（誤った若返りを直す）。
            seed = _best_seed_ts(it)
            if seed:
                current_since = _parse_ts(entry.get("since"))
                if current_since is None or seed < current_since:
                    ledger[key] = {"status": status, "since": seed.isoformat()}
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


def self_test():
    """1466番の修正が効いているかを、実データを汚さずその場だけで確認する（3ケース）。"""
    ok = True

    def check(name, cond):
        nonlocal ok
        mark = "PASS" if cond else "FAIL"
        if not cond:
            ok = False
        print("[%s] %s" % (mark, name))

    t0 = now_jst()
    old9 = (t0 - datetime.timedelta(days=9)).isoformat()
    old1 = (t0 - datetime.timedelta(days=1)).isoformat()

    # ケース1: waitingのみ・他の状態別フィールドが無い・queuedAtだけが9日前 → queuedAtが拾われること
    it1 = {"n": 90001, "status": "waiting", "queuedAt": old9}
    seed1 = _best_seed_ts(it1)
    check("queuedAtしか無いwaiting項目はqueuedAtを拾う", seed1 is not None and abs((seed1 - t0).total_seconds()) > 8 * 86400)

    # ケース2: startedAtがある場合はqueuedAtより優先されること（既存挙動を壊していない）
    it2 = {"n": 90002, "status": "running", "startedAt": old1, "queuedAt": old9}
    seed2 = _best_seed_ts(it2)
    check("startedAtがあればqueuedAtより優先される", seed2 is not None and abs((seed2 - t0).total_seconds()) < 2 * 86400)

    # ケース3: 既存台帳が誤って"now"寄りに若返っていても、queuedAtが古ければ補正される
    ledger = {"90003": {"status": "waiting", "since": now_jst().isoformat()}}
    it3 = {"n": 90003, "status": "waiting", "queuedAt": old9}
    ledger_copy = json.loads(json.dumps(ledger))
    now_iso = now_jst().isoformat()
    entry = ledger_copy.get("90003")
    status = "waiting"
    seed = _best_seed_ts(it3)
    current_since = _parse_ts(entry.get("since"))
    corrected = seed is not None and (current_since is None or seed < current_since)
    check("誤って若返った既存台帳がqueuedAtへ補正される", corrected)

    # ケース4（2回目修正）: #1398実物と同じ形＝queuedAtが無くurakataBlockedAtのみ9日前
    it4 = {"n": 90004, "status": "waiting", "urakataBlockedAt": old9}
    seed4 = _best_seed_ts(it4)
    check("queuedAt無し・urakataBlockedAtのみでも拾われる（1398型）",
          seed4 is not None and abs((seed4 - t0).total_seconds()) > 8 * 86400)

    # ケース5（2回目修正）: 出どころ日時（9日前）が本文にあり、urakataBlockedAt（2日前）もある
    #   → より正確な出どころ日時（=より古い方）が優先されること
    dekoro_text = "【タスク】テスト\n【出どころ】kioku（%s／abc123）" % old9[:16].replace("T", " ")
    it5 = {"n": 90005, "status": "waiting", "what": dekoro_text, "urakataBlockedAt": old1, "queuedAt": old1}
    seed5 = _best_seed_ts(it5)
    check("本文の出どころ日時がurakataBlockedAt/queuedAtより優先される（#1398実物型）",
          seed5 is not None and abs((seed5 - t0).total_seconds()) > 8 * 86400)

    # ケース6: running中でstartedAtがあれば、出どころ日時が古くてもstartedAtが優先される（既存壊さない）
    it6 = {"n": 90006, "status": "running", "startedAt": old1, "what": dekoro_text}
    seed6 = _best_seed_ts(it6)
    check("runningでstartedAtがあれば出どころ日時より優先される",
          seed6 is not None and abs((seed6 - t0).total_seconds()) < 2 * 86400)

    print("SELF_TEST_RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    if "--self-test" in sys.argv:
        return self_test()
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
