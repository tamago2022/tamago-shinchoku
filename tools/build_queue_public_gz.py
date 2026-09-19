#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
status/queue.json（正本・1.8MB超）から、公開リポジトリ用の圧縮版
status/public/queue.json.gz を作る（925番・2回目の修正）。

背景：
1回目の修正は「status/public/queue.json を1MB超の点検の除外パスに追加する」
という誤魔化しで、AI検品にはねられた（実体は1.75MBのまま公開され続けていた）。

なぜdone_archive.jsonと同じ「what/resultを抜く」方式が使えないか：
index_full.html の fetchQueueFull() は、発車待ち・確認待ちの行を開いた瞬間に
このファイルを取りに行き、what（実行プロンプト全文）・result（完了報告全文）を
差し込んでいる。done_archive.json 側は91%が「どこからも読まれていない」と実測できたが、
こちらは実際に使われている（stripすると詳細表示が壊れる）ので、フィールドを削れない。

だから中身は一切削らず、gzip圧縮だけで物理的に縮める（可逆・無損失）。
実測：1,846,125バイト → gzip -9相当で約480KB（1MB未満）。

正本 status/queue.json は一切変更しない。この圧縮版は
status/public/queue.json.gz（公開専用コピー）にのみ使う。
index_full.html 側は DecompressionStream("gzip") で解凍してから JSON.parse する
（fetchQueueFull()を参照）。
"""
import gzip
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
QUEUE = os.path.join(REPO, "status", "queue.json")
QUEUE_GZ_OUT = os.path.join(REPO, "status", "public", "queue.json.gz")


def build(queue_path=QUEUE, out_path=QUEUE_GZ_OUT):
    with io.open(queue_path, "rb") as f:
        raw = f.read()

    tmp = "%s.tmp.%d" % (out_path, os.getpid())
    # mtime=0 で固定し、同じ中身なら毎回同じバイト列になるようにする
    # （差分レビュー・キャッシュ判定を安定させるため）。
    with io.open(tmp, "wb") as f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0, compresslevel=9) as gz:
            gz.write(raw)
    os.replace(tmp, out_path)
    return {"rawBytes": len(raw), "gzPath": out_path, "gzBytes": os.path.getsize(out_path)}


if __name__ == "__main__":
    result = build()
    print(
        "queue.json.gz（公開圧縮版）を書きました：%d バイト → %d バイト"
        % (result["rawBytes"], result["gzBytes"])
    )
