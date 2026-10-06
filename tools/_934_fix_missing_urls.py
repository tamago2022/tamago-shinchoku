#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""934番：憲法点検「URL無しで完了(done)になった仕事」の赤(#431/#712/#924/#929)を直す。

原因は2種類：
  - #924/#929: result本文には実在する本番URLがすでに書かれていたが、queue.json側の
    urls配列へ転記されていなかっただけの記録漏れ（=データ整合性の修正）。
  - #431/#712: joy-relief-station本体が非公開リポジトリのため公開URLが張れない。
    代わりに share/check/934-done-missing-url-431-712.html に実際のコード差分・
    レポート本文を埋め込んだ確認ページを作り、それを証拠URLとして使う。
    #712はさらに実際にShareButtonが載っている本番ページも併記する。

直接queue.jsonを書かず、queue_store.py経由（差分マージ・世代バックアップ付き）で書く
（案件#687の事故対策・_934_batch4of7_triage.py等の既存precedentと同じ形）。
"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(__file__))
import queue_store as qs

now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
NOTE_PREFIX = "【934番・2026-09-17・憲法点検「URL無しで完了」赤4件の是正】"

CHECK_PAGE_431_712 = "https://tamago2022.github.io/tamago-shinchoku/share/check/934-done-missing-url-431-712.html"

URLS = {
    431: [CHECK_PAGE_431_712],
    712: [
        CHECK_PAGE_431_712,
        "https://joy-relief-station.lovable.app/room/card/maru-cat",
    ],
    924: [
        "https://tamago2022.github.io/tamago-shinchoku/share/check/924-hikitsugi-oni-daidai.html",
    ],
    929: [
        "https://tamago2022.github.io/tamago-shinchoku/share/check/929-awaiting-check-triage-batch3.html",
        # 旧本番リンクは925番のgzip圧縮対応でqueue.jsonがqueue.json.gzへ切り替わり404化した
        # ため、生きている公開データへ差し替える。
        "https://tamago2022.github.io/tamago-shinchoku/status/public/queue_light.json",
    ],
}

NOTES = {
    431: "joy-relief-stationは非公開リポジトリのため公開URLが無く、確認ページへコード差分・"
         "レポート本文を直接埋め込んで証拠とした（本人の929番棚卸し時点の申告どおり）。",
    712: "確認ページに加え、実際にShareButtonが載っている本番ページ(room/card/maru-cat)を"
         "併記した。",
    924: "result本文にあった本番URLをurlsへ転記しただけ（新規変更なし）。",
    929: "result本文にあった確認ページURLをurlsへ転記。本番queue.jsonリンクは925番の"
         "gzip化で404のためqueue_light.jsonに差し替えた。",
}

q = qs.load_queue()
snap = qs.snapshot_items(q)
items = q["items"]

changed = []
for it in items:
    n = it.get("n")
    if n in URLS:
        it["urls"] = URLS[n]
        prev = it.get("urlBackfillNote") or ""
        it["urlBackfillNote"] = (prev + "\n\n" if prev else "") + NOTE_PREFIX + NOTES[n]
        it["urlBackfilledAt"] = now
        changed.append(n)

ok = qs.save_queue(q, snapshot=snap)
print("save_queue ok:", ok)
for n in changed:
    print("n=%s -> urls backfilled: %s" % (n, URLS[n]))
