#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-10-19 追加2便（白飛びの解消／クラウドセッションのクレジット使い切り）。zenkaiKeyで二重に積まない。"""
import io, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import queue_store
from zenkai_1018yu_tsumu import MAMORU, FABLE, JRS, SHIN
NOW = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
X = [
 ("Y8-shirotobi", JRS, "白飛びの解消：ページの切り替えで白い画面を挟まない",
  "たまごさんの言葉（そのまま）：「表示と読み込みは速くなった。でも、触ると白飛びして切り替わるのが多くて残念」。\n"
  "対象：本番 https://joy-relief-station.lovable.app 。トップ→棚→曲ページ→マガジン、戻る、言語の切り替え、のたびに白い画面が挟まる所を全部洗い出して、なくす。\n"
  "直し方の例：背景色をhtml/bodyとindex.htmlの最初の描画から暗い地にそろえる（白が一瞬も出ない）／読み込み中は前の画面か骨組み（skeleton）を見せる（Suspenseのfallbackを白い全面にしない・遷移はstartTransition等で前の画面を保つ）／ページ全体の読み直し（location.href・aタグの全読み込み・reload）をSPAの遷移に変える（外部へ出る所以外）／マガジン（静的HTML）とサイトの行き来も背景色をそろえる。\n"
  "測る：スマホ相当（工場のheadless・4G相当）で、各切り替えの秒数と「白い画面が出たか（フレームの明るさで機械判定）・何ミリ秒」を、直す前と後で status/zenkai_1018yu/Y8-shirotobi/jissoku.json に数字で残す。\n"
  "前の便「Y6-site（サイト全体の見直し・122708番）」の結果（status/zenkai_1018yu/Y6-site/）を最初に読み、重ねない。気に入られている見た目は変えない。後退の関所（koutai_kanmon）を必ず通す。", 2),
 ("Y9-cloud", SHIN, "クラウドセッションのクレジット（$248・11/5 16:59 JST期限）を使い切る計画と起動",
  "1. 前回「クラウドセッションを使い切る」の1本目（バグゼロ）を起動したあとどうなったかを、status/cloud_ledger.json・tools/cloud_launch.py・tools/cloud_prompts/・tools/cloud_credit_henji.py・dispatch_outbox で確かめ、台帳を今の姿に直す。\n"
  "2. 期限までの計画を status/cloud_keikaku_1105.md に：重い便（白飛びY8・「この流れで」のコピー811件＝copy_queue_1018のB-bin便・マガジンの関所の直し便8本・サイトの見直し）のどれをクラウドに回すか、1本の大きさ、日ごとの本数。Macの負荷とMaxの枠を節約するのが目的。\n"
  "3. 起動できる仕組みがあり、許可ポップアップ・ブラウザ・たまごさんの手なしで通るなら、今日中に2〜3本起動して台帳に記録（日時・セッションURL・目的）。クラウドに回した便は queue.json 側を hold にして「クラウドで走行中（URL）」と書く（二重に走らせない）。\n"
  "4. 残高・使用額は取れなければ「未確認」と書く（たまごさんに見てもらわない）。起動が通らなければ、止まった所と理由を1行で。", 3),
]
added = []
with queue_store.queue_lock():
    q = queue_store.load_queue(); snap = queue_store.snapshot_items(q); items = q["items"]
    have = {it.get("zenkaiKey") for it in items}
    n = max(int(it.get("n") or 0) for it in items) + 1
    for key, repo, title, what, order in X:
        if key in have: continue
        items.append({"n": n, "title": "Fable｜" + title, "hyoudai": title, "hyoudaiSrc": "rule",
            "why": "たまごさん指示（10-19）", "what": "【全開便・Fable】%s\n%s%s" % (title, what, MAMORU),
            "status": "waiting", "limitMin": 180, "model": FABLE, "fixedModel": FABLE, "fableLane": True,
            "fableLaneOrder": order, "priority": 1, "urgent": True, "origin": "user", "queuedAt": NOW,
            "repo": repo, "zenkaiKey": key, "costsMoney": False})
        added.append((n, key)); n += 1
    if added and not queue_store.save_queue(q, snapshot=snap):
        print("save_queue 拒否"); sys.exit(2)
print("積んだ", added)
