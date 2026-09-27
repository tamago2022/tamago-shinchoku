#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1785番の再発防止チェック。

事故の実体（2026-09-30に実測で特定）：`tools/prompt_rules/always-15-cache-expires-in-an-hour.md`
8〜9行目の一文「モデルを変えてもキャッシュは作り直しになる。安いモデルに変えても、／
長い会話を読み直す分で損をすることがある。」が改行位置で分断され、1775〜1792番の
**18件**が『たまごさんの新規依頼』としてstatus/queue.jsonへ連続登録された（同時間帯・
2026-09-28 01:29〜02:26）。実体の無いゴーストタスクのため、発車のたびに「本番URLが
出せない」で失敗を繰り返していた（1785番はredoCount2・1783番も同じ症状）。

この再発を防ぐため、queue_add()に`_is_rule_document_fragment()`ガードを追加した
（command_ingest.py）。本テストは①実際に事故になった断片が今のガードで弾けること、
②正当な依頼（対照群）まで誤って弾かないこと、の両方を1本で担保する。
python3 tools/test_rule_fragment_guard.py で実行できる。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import command_ingest as ci  # noqa: E402

# ① 実際に1775〜1792番で誤登録された断片そのもの（queue.jsonの実データから採取）。
#    これらは全部、今のガードで「積まない」判定になるべき。
GHOST_FRAGMENTS = [
    "安いモデルに変えても、",
    "モデルを変えてもキャッシュは作り直しになる。",
    "どうしても動かすなら、同じURLで開けるようにしてから動かす。",
    "会話の流れで出た「やってみて」を、そのまま実行に移さない。",
    "誰も測っていなかった。",
    "AppleScript / osascript / System Events は全面禁止。",
    "「直したページを1つだけ貼る」のは禁止です。",
]

# ② 対照群：実際にたまごさんが依頼しそうな、具体的で正当な新規依頼。
#    これらは誤ってガードに弾かれてはいけない（弾かれたら依頼が消えてしまう事故になる）。
REAL_REQUESTS = [
    "アーティストページのカバー動画が再生できないのを直してください",
    "トップページの読み込みが遅いので調査してほしい",
    "新しい棚『秋の癒しソング』を作ってください。曲は10曲くらい",
    "サムネイルが表示されないアーティストが3件あるので直して",
]


def run():
    failures = []

    # ① 実際の事故断片は弾かれること
    for frag in GHOST_FRAGMENTS:
        got = ci._is_rule_document_fragment(frag)
        if not got:
            failures.append(
                "回帰：実際に事故になった断片 %r がガードで弾かれませんでした" % frag
            )

    # ② 対照群（正当な依頼）は弾かれないこと
    for req in REAL_REQUESTS:
        got = ci._is_rule_document_fragment(req)
        if got:
            failures.append(
                "誤検知：正当な依頼 %r が誤ってルール文書断片として弾かれました" % req
            )

    # ③ queue_add()自体がGHOST_FRAGMENTSを"skipped"で返すこと（force_dup無し）
    for frag in GHOST_FRAGMENTS[:2]:
        status, msg = ci.queue_add(frag, priority=None, label=None, origin="user")
        if status != "skipped":
            failures.append(
                "回帰：queue_add(%r) が積まれてしまいました（status=%r, msg=%r）"
                % (frag, status, msg)
            )

    if failures:
        print("FAIL（%d件）" % len(failures))
        for f in failures:
            print(" - " + f)
        return 1
    print(
        "PASS：ルール文書断片（%d件）は全て弾かれ、正当な依頼（%d件）は誤検知されていません"
        % (len(GHOST_FRAGMENTS), len(REAL_REQUESTS))
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())
