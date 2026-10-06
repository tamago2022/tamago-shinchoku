#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""932番(6/7)：hold 584/586/587/596/598/611/613/614/643/710 を1回見直し、
   生きている案件は再開(waiting)へ戻し、そうでないものは畳んだまま理由を残す。
   直接queue.jsonを書かず、queue_store.py経由(差分マージ・世代バックアップ付き)で書く。
"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(__file__))
import queue_store as qs

now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

# status="waiting"へ戻す（生きている・再開条件を実測で満たした）
REVIVE = {
    584: (
        "932番棚卸し・2026-09-17再確認: 常設の仕入れタスク（列が空いたら走る埋め草）。"
        "584番自身のholdNote(590番棚卸し)でも『継続稼働を確認済み』とある。"
        "止めておく積極的な理由がないため再開(waiting)へ戻す。"
    ),
    596: (
        "932番棚卸し・2026-09-17再確認: 保留理由は『PC保守優先・容量20GB以上に戻ったら再開』(2026-09-07 23:05)。"
        "実測(df -h /)で空き251GB・使用率8%、swap free 1.3GBを確認。条件を満たしたため再開(waiting)へ戻す。"
    ),
    598: (
        "932番棚卸し・2026-09-17再確認: 596番と同じ保留理由（PC保守優先）。"
        "実測で空き251GB(基準20GBを大幅にクリア)のため再開(waiting)へ戻す。"
    ),
    613: (
        "932番棚卸し・2026-09-17再確認: 保留理由はPC保守優先（638番/容量）のみで、"
        "ブラウザ依存の記載なし（既存のdead-youtube.json・videoHealthReport.generated.ts・"
        "videoReplacements.generated.tsの3点セットを使う機械的スイープ）。実測で容量条件を満たし"
        "621番(ブラウザ統合)待ちにも該当しないため再開(waiting)へ戻す。"
    ),
    643: (
        "932番棚卸し・2026-09-17再確認: 保留理由はPC保守優先のみ（たまごさん『全く優先ではない』＝"
        "急がない・列の後ろでよい、の指示であって停止指示ではない）。全ページ機械走査での修正のためブラウザ不要。"
        "容量条件を実測で満たしたため再開(waiting)へ戻す（優先度は最下位のままでよい）。"
    ),
}

# status="hold"のまま・理由だけ更新する（再開条件が未達 or たまごさん本人の明示保留 or 実案件でない）
KEEP_HOLD = {
    586: (
        "932番棚卸し・2026-09-17再確認: タイトル『テストA』・本文(what)は空。実案件ではないテスト項目のため"
        "hold継続。既存資産として削除はしない。"
    ),
    587: (
        "932番棚卸し・2026-09-17再確認: タイトル『テストB』・本文(what)は空。586と同じくテスト項目のため"
        "hold継続。既存資産として削除はしない。"
    ),
    611: (
        "932番棚卸し・2026-09-17再確認: 再開条件『621番(ブラウザ統合)の後に再開』は09-17時点で621自身が"
        "まだstatus=holdのまま未達成（専用ヘッドレスChrome・排他鍵の仕組みもtools/に未実装）。"
        "先に再開するとブラウザ占有事故が再発するリスクがあるため、案件は生きているがhold継続。"
        "621番が片付き次第、最優先で再開する。"
    ),
    614: (
        "932番棚卸し・2026-09-17再確認: 611番と同じく621番(ブラウザ統合)待ちが未達成。加えて前回"
        "AI検品(Verifier)で『22曲読み取り0件・GitHub blob 404』としてはねられた実績あり。"
        "ブラウザ占有事故の再発防止と、前回不合格の原因（ブラウザなしでは読み取れないページ）が"
        "解消していないためhold継続。"
    ),
    710: (
        "932番棚卸し・2026-09-17再確認: たまごさん本人の明示指示『工場を発射しないでください。"
        "後で見るからね』(2026-09-10)が現行方針。ai-brain/kettei.jsonにも解除の決定記録なし。"
        "案件（Måneskin THE FIRST TAKE仕入れ）は生きているが、owner判断待ちのためhold継続。"
        "710がOKになったら711番も連動して再開する。"
    ),
}

q = qs.load_queue()
snap = qs.snapshot_items(q)
items = q["items"]

revived, kept = [], []
for it in items:
    n = it.get("n")
    if n in REVIVE:
        it["status"] = "waiting"
        it["revivedAt"] = now
        it["revivedReason"] = REVIVE[n]
        revived.append(n)
    elif n in KEEP_HOLD:
        it["status"] = "hold"
        it["blockedNote"] = KEEP_HOLD[n]
        it["holdReviewedAt"] = now
        kept.append(n)

ok = qs.save_queue(q, snapshot=snap)
print("save_queue ok:", ok)
print("revived(hold->waiting):", sorted(revived))
print("kept(hold, reason updated):", sorted(kept))
