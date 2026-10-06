#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""793番（2026-09-14）「すぐ見たい」別枠・自動仕分けの回帰テスト。

たまごさんの言葉：「今のパーソナライズ、コンシェルジュ、LINE申請、デジタル絵本、これはすぐ見たいの。
別枠がいいな」「そんなの1週間後でいいよってのもあれば、もう明日にでも見たいってのもあるから。
これを最初にやるとか、それも自動化したいね」。

ここで固定するのは2つの純粋関数（ファイルI/Oなし＝本物のqueue.jsonに一切触れずに検証できる）：
  ① tools/auto_launcher.queue_rank_key() … urgent:true が priority より必ず先に来ること
  ② tools/command_ingest._auto_demote_priority() … 「急がない」キーワードで自動的にP4へ落ちること、
     ただし「壊れている」系（本番が落ちている・404等）は対象外になること

queue_urgent()（トグル本体）・queue_add()内の自動仕分け結線は、queue_store.py が
lock/history/self-healまで含む重い実装のため、ここでは安全のため本物のqueue.jsonに対して
実施した手動の往復確認（1番をON→OFFで件数・内容が完全に戻ることを確認済み・793番作業ログ参照）
に委ね、ここでは「ロジックそのもの」だけを機械的に固定する。

python3 tools/test_urgent_lane.py で実行できる。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import auto_launcher as al  # noqa: E402
import command_ingest as ci  # noqa: E402


def run():
    failures = []

    # ① urgent:true は priority（数字が小さいほど急ぎ）より必ず先に来る。
    #    「1週間後でいいよ」＝P1（今すぐ）でも、urgentが立っていなければ
    #    「明日にでも見たい」＝P5（いつでも）だがurgent:trueのものより後ろになる。
    items = [
        {"n": 100, "priority": 1},                 # 普通の最優先（P1）
        {"n": 200, "priority": 5, "urgent": True},  # 優先度は最低(P5)でも「すぐ見たい」
        {"n": 300, "priority": 3},
    ]
    ranked = sorted(items, key=lambda it: al.queue_rank_key(it, {}))
    got = [it["n"] for it in ranked]
    if got != [200, 100, 300]:
        failures.append(
            "urgent優先の並びが崩れています：期待[200,100,300]、実際%r"
            "（P5でもurgent:trueならP1より先に出ないと793番の要求を満たさない）" % got
        )

    # ①' urgentが複数あるときは、その中でpriority→order→番号の順（要求どおり）。
    items2 = [
        {"n": 10, "urgent": True, "priority": 3},
        {"n": 20, "urgent": True, "priority": 1},
        {"n": 30, "urgent": True, "priority": 1, "order": 1},
    ]
    ranked2 = sorted(items2, key=lambda it: al.queue_rank_key(it, {}))
    got2 = [it["n"] for it in ranked2]
    if got2 != [30, 20, 10]:
        failures.append(
            "urgent同士の並び（priority→order→番号）が崩れています：期待[30,20,10]、実際%r" % got2
        )

    # ①'' 走行中の扱いはauto_launcher側（statusフィルタ）の仕事なので、ここではランクキー自体が
    #     item自身のpriorityをpriority.json(Qキー)より優先する既存仕様を壊していないことだけ確認。
    it3 = {"n": 400}
    if al.effective_priority(it3, {"Q400": 2}) != 2:
        failures.append("priority.json（Qキー）へのフォールバックが壊れています")
    if al.effective_priority({"n": 401, "priority": 4}, {"Q401": 1}) != 4:
        failures.append("item自身のpriorityがpriority.jsonより優先されていません")

    # ② 「急がないもの」キーワードはP4へ落としてよい。
    demote_cases = [
        "コピーが違ってるよ直して", "誤字を直す", "表記ゆれを直す", "リンク切れを直す",
        "文言を直してほしい", "体裁を整える", "リファクタしてほしい", "ラベルを直す",
    ]
    for text in demote_cases:
        matched, kw = ci._auto_demote_priority(text, text)
        if not matched:
            failures.append("急がない内容のはずが自動仕分け対象になりませんでした：%r" % text)

    # ②' 「壊れている」系は、急がないキーワードを含んでいても対象外（P1のまま）。
    exception_cases = [
        "本番のリンクが404で開けない",       # 「リンク切れ」相当だが実は壊れている
        "本番が落ちている、コピーが違うかも",  # 「コピーが違」を含むが本番停止が本体
        "画面が真っ白で動かない",
    ]
    for text in exception_cases:
        matched, kw = ci._auto_demote_priority(text, text)
        if matched:
            failures.append(
                "壊れている系なのに急がない扱いでP4へ落とされてしまいます：%r（%s）" % (text, kw)
            )

    # ②'' 急ぎの普通の依頼は対象外のまま。
    normal_cases = ["パーソナライズを実装する", "コンシェルジュを作り直す", "LINE申請を自動化する"]
    for text in normal_cases:
        matched, kw = ci._auto_demote_priority(text, text)
        if matched:
            failures.append("急ぎの依頼が誤って急がない扱いにされました：%r（%s）" % (text, kw))

    if failures:
        print("FAIL（%d件）" % len(failures))
        for f in failures:
            print(" - " + f)
        return 1
    print("PASS：urgent別枠の並び替え（queue_rank_key）と急がない自動仕分け"
          "（_auto_demote_priority）、どちらも793番の要求どおりに動いています")
    return 0


if __name__ == "__main__":
    sys.exit(run())
