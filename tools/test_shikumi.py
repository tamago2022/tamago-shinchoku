#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""799番（2026-09-14）仕組みの生死表の回帰テスト。

本物のstatus/配下には一切触れず、tools/shikumi.pyの純粋関数（tier・parse_ts・
compute_waiting_escalations）だけを固定する。queue.json書き込み・queue_add()呼び出しを
伴う統合的な逆テスト（本物のdead検知→自動でタスクが積まれる確認）は、実装時に手動で
1回実施済み（作業ログ参照）。

python3 tools/test_shikumi.py で実行できる。
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import shikumi as sk  # noqa: E402


def run():
    failures = []

    # ① tier()：alive/slow/deadの境界。
    if sk.tier(5, 10, 30) != "alive":
        failures.append("tier(5,10,30)はaliveのはず")
    if sk.tier(10, 10, 30) != "alive":
        failures.append("tier(10,10,30)は境界含みでaliveのはず")
    if sk.tier(20, 10, 30) != "slow":
        failures.append("tier(20,10,30)はslowのはず")
    if sk.tier(30.1, 10, 30) != "dead":
        failures.append("tier(30.1,10,30)はdeadのはず")
    if sk.tier(None, 10, 30) != "dead":
        failures.append("tier(None,...)は計測不能なのでdead扱いのはず（でっち上げない）")
    # 二択（alive_max==dead_min）の項目：鬼監督・fal_ledgerで使う形。
    if sk.tier(24, 24, 24) != "alive":
        failures.append("tier(24,24,24)は境界含みでaliveのはず")
    if sk.tier(24.1, 24, 24) != "dead":
        failures.append("tier(24.1,24,24)はslow帯が無くdeadに直行するはず")

    # ② parse_ts()：ISO(tzあり/なし)・'%Y-%m-%d %H:%M[:%S]' どれも読める。
    cases = [
        "2026-09-14T02:24:20+09:00",
        "2026-09-14 02:24:20",
        "2026-09-14 02:24",
    ]
    for c in cases:
        if sk.parse_ts(c) is None:
            failures.append("parse_tsが読めませんでした: %r" % c)
    if sk.parse_ts(None) is not None or sk.parse_ts("") is not None:
        failures.append("parse_ts(None/空)はNoneを返すはず")
    if sk.parse_ts("がらくた") is not None:
        failures.append("parse_tsは読めない文字列に対して勝手な時刻をでっち上げてはいけない")

    # ③ compute_waiting_escalations()：ファイルI/Oなしで純粋にロジックだけ確認。
    now = sk.now_jst()
    old_25h = (now - datetime.timedelta(hours=25)).isoformat()
    old_73h = (now - datetime.timedelta(hours=73)).isoformat()
    fresh_1h = (now - datetime.timedelta(hours=1)).isoformat()

    items = [
        {"n": 901, "status": "waiting", "shikumiCheckKey": "heartbeat", "title": "心臓が死んでいます"},
        {"n": 902, "status": "waiting", "shikumiCheckKey": "deploy", "title": "24時間未満なので昇格しない"},
        {"n": 903, "status": "waiting", "kenpouCheckKey": "oni_kantoku_alive", "title": "3日超だがshikumiKeyは無い"},
        {"n": 904, "status": "running", "shikumiCheckKey": "heartbeat", "title": "waitingでないので対象外"},
    ]
    ledger = {"901": old_73h, "902": fresh_1h, "903": old_73h, "904": old_73h}
    escalations, red_lines, changed = sk.compute_waiting_escalations(items, ledger)

    it901 = next(it for it in items if it["n"] == 901)
    if not it901.get("urgent"):
        failures.append("901番（shikumiCheckKey付き・73時間waiting）はurgentへ自動昇格するはず")
    if "shikumi.pyが自動検知" not in (it901.get("urgentReason") or ""):
        failures.append("901番のurgentReasonに自動検知である旨が明記されていない（透明性の原則違反）")
    if not changed:
        failures.append("901番を書き換えたのでchanged=Trueになるはず")

    it902 = next(it for it in items if it["n"] == 902)
    if it902.get("urgent"):
        failures.append("902番（waiting1時間だけ）は24時間未満なのでurgent昇格してはいけない")

    ns_with_stale_red_line = {901, 903}
    matched_ns = set()
    for line in red_lines:
        for n in ns_with_stale_red_line:
            if ("#%d" % n) in line:
                matched_ns.add(n)
    if matched_ns != ns_with_stale_red_line:
        failures.append(
            "3日超waitingの仕組み系タスク(901,903)が両方とも赤旗行に出るはず：実際%r" % matched_ns
        )
    for line in red_lines:
        if "#902" in line or "#904" in line:
            failures.append("902番(24時間未満)・904番(waitingでない)は赤旗行に出てはいけない: %r" % line)

    escalated_ns = {e["n"] for e in escalations if e["type"] == "urgent_promoted"}
    if escalated_ns != {901}:
        failures.append("urgent_promotedのescalationsは901番だけのはず：実際%r" % escalated_ns)

    # ④ 861番：重複チケット判定の状態集合が、queue.json実測の全status値を
    #    カバーしているか（"touchchecking"・"stuck"が漏れて重複発行された実例の再発防止）。
    observed_statuses = {
        "waiting", "running", "hold", "stuck", "awaiting_check", "touchchecking", "verifying",
    }
    missing = observed_statuses - set(sk.OPEN_QUEUE_STATUSES)
    if missing:
        failures.append(
            "OPEN_QUEUE_STATUSESに実在のstatus値が抜けています（重複発行の再発防止漏れ）: %r" % missing
        )
    if "done" in sk.OPEN_QUEUE_STATUSES or "merged" in sk.OPEN_QUEUE_STATUSES:
        failures.append("done/mergedは終了状態なのでOPEN_QUEUE_STATUSESに含めてはいけない")

    if failures:
        print("FAIL（%d件）" % len(failures))
        for f in failures:
            print(" - " + f)
        return 1
    print(
        "PASS：tier()の境界判定、parse_ts()の複数フォーマット対応、"
        "compute_waiting_escalations()のurgent自動昇格(24時間)と3日超赤旗、"
        "OPEN_QUEUE_STATUSESの網羅性（861番）、"
        "どちらも799番の要求どおりに動いています"
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())
