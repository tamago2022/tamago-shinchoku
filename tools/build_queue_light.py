#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
status/queue.json（正本・1.4MB超）から、進捗表アプリの初回読み込み用に
軽量版 status/queue_light.json を作る。

背景（2026-09-10・店主）：「ブラウザの進捗表、読み込み遅いね。重いよ。軽くして」
実測：queue.json の中身の大半は各タスクの指示文 what（1件2000〜3000字）だが、
画面（index.html）が表に出すのは題名・番号・状態・優先度・モデルだけ。全部運んでいるのが重い。

やること：
  1. 各 items[] から "what" と "result" の2フィールドだけを取り除く（ブラックリスト方式。
     他のフィールドはどこで使われているか把握しきれないため、ホワイトリストで絞らず安全側に倒す）。
  2. status が "done"／"cancelled" の項目は、直近30件（finishedAtがあればそれで降順、
     無ければ n で降順）だけ残す。それ以外の done/cancelled は queue_light.json から間引く
     （queue.json 自体からは消さない。正本はそのまま）。

queue.json 自体は読み取り専用（正本）として扱い、書き換えない。
index.html 側は、開いた行に what/result が無い時だけフルの queue.json を裏で1回fetchして
差し込む（遅延取得）。詳しくは index.html の fetchQueueFull() を参照。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
QUEUE = os.path.join(REPO, "status", "queue.json")
QUEUE_LIGHT = os.path.join(REPO, "status", "queue_light.json")
# 948番（2026-09-19）トップ（index.html）の「次に発車」専用の極小ファイル。
#   実測：queue_light.json は 314KB まで太っていた（コード内のコメントは117KB時代のまま）。
#   トップは最初に top_status.json の nextUp を出してから queue_light.json で上書きしていたので、
#   スマホでは「前の並びが出て、数秒後にパッと切り替わる」＝たまごさんが嫌がっている動きになる。
#   トップが実際に使う7つの項目だけを持つファイルを別に作り、上書きではなく一発で出す。
QUEUE_NEXT = os.path.join(REPO, "status", "queue_next.json")
# 「次に発車」が読むフィールドだけ（index.html の pri/rankCmp/renderNext が使うものが全部）。
NEXT_FIELDS = ("n", "title", "label", "status", "priority", "order", "urgent")

# 軽量版から取り除くフィールド（ブラックリスト）。
STRIP_FIELDS = ("what", "result")

# doneとcancelledは、直近何件だけ軽量版へ残すか
DONE_KEEP = 30
DONE_LIKE_STATUSES = ("done", "cancelled")


def _sort_key(it):
    # finishedAtがあればそれを最優先（新しい順）。無ければnで代用。
    fin = it.get("finishedAt") or ""
    n = it.get("n") or 0
    return (fin, n)


def build(queue_path=QUEUE, out_path=QUEUE_LIGHT, keep=DONE_KEEP):
    with io.open(queue_path, encoding="utf-8") as f:
        q = json.load(f)

    items = q.get("items") or []
    done_like = [it for it in items if it.get("status") in DONE_LIKE_STATUSES]
    others = [it for it in items if it.get("status") not in DONE_LIKE_STATUSES]

    done_like_sorted = sorted(done_like, key=_sort_key, reverse=True)
    kept_done = done_like_sorted[:keep]

    kept = others + kept_done

    def _light_item(it):
        return {k: v for k, v in it.items() if k not in STRIP_FIELDS}

    light_items = [_light_item(it) for it in kept]
    # 表示順は元のqueue.json内の並びに合わせる（n昇順）。renderQueue/renderCheck等が
    # 自前でソート・優先度並べ替えをするので、ここでの並びは決定的であれば良い。
    light_items.sort(key=lambda it: it.get("n") or 0)

    light = {
        "updatedAt": q.get("updatedAt"),
        "note": q.get("note"),
        "repo": q.get("repo"),
        "items": light_items,
    }

    # 2026-09-12（776番）：固定名の .tmp だと、心臓（15秒おき）とmachine_status_push.sh
    #   （260秒ループ）の両方が同時にbuild()を呼んだ時、片方が rename した直後にもう片方が
    #   同じ .tmp を開こうとして [Errno 2] No such file or directory で失敗する競合があった
    #   （心臓が詰まる事故の引き金の1つ）。プロセスIDを名前に入れて衝突しないようにする。
    tmp = "%s.tmp.%d" % (out_path, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(light, f, ensure_ascii=False, indent=1)
    os.replace(tmp, out_path)

    # 948番：トップ専用の極小ファイルも同時に作る（待機列だけ・7項目だけ）。
    #   ここで失敗しても queue_light.json 側は既に書けているので、本体は絶対に止めない。
    try:
        _write_queue_next(q, items)
    except Exception:
        pass

    return light


def _write_queue_next(q, items, out_path=QUEUE_NEXT):
    """トップの「次に発車」が読むぶんだけの極小ファイルを書く。

    待機中（status == "waiting"）の項目だけを、7フィールドに削って出す。
    トップはこれを1回読んで一発で描く（古い並びを先に出して上書きする作りをやめるため）。
    """
    waiting = [it for it in items if it.get("status") == "waiting"]
    slim = []
    for it in waiting:
        row = {}
        for k in NEXT_FIELDS:
            v = it.get(k)
            if v is not None:
                row[k] = v
        slim.append(row)
    slim.sort(key=lambda it: it.get("n") or 0)

    out = {
        "updatedAt": q.get("updatedAt"),
        "note": "トップの「次に発車」専用。待機中のみ・7項目のみ（tools/build_queue_light.py が生成）",
        "items": slim,
    }
    # これは画面が読むだけのファイルなので、改行と空白を入れずに詰めて書く（そのぶん軽い）。
    tmp = "%s.tmp.%d" % (out_path, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, out_path)
    return out


if __name__ == "__main__":
    result = build()
    print("queue_light.json を書きました（items: %d件）" % len(result.get("items") or []))
    try:
        _n = len(json.load(io.open(QUEUE_NEXT, encoding="utf-8")).get("items") or [])
        print("queue_next.json を書きました（待機 %d件・%dバイト）" % (_n, os.path.getsize(QUEUE_NEXT)))
    except Exception as _e:
        print("queue_next.json は書けませんでした: %s" % _e)
