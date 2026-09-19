#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
status/done_archive.json（正本・フル）から、公開用の軽量版を作る（925番）。

背景：status/public/done_archive.json が1MB超で憲法点検が赤になっていた。
実測：中身の91%（what 385KB + result 40KB／全体1.07MB中）は完了済みタスクの
実行プロンプト全文・実行結果全文で、公開画面（share/done/index.html・進捗表）の
どこからも読まれていない（write_page()が使うのは n/title/checkedAt/checkNote/urlsだけ）。
tools/build_queue_light.py と同じブラックリスト方式（what/resultだけ除く）で軽量化する。

正本 status/done_archive.json はフルのまま一切変更しない（各ツールが
n/title/what等で照合する処理はこれまで通り正本を読む）。
この軽量版は status/public/done_archive.json（公開専用コピー）にのみ使う。
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ARCHIVE = os.path.join(REPO, "status", "done_archive.json")
ARCHIVE_LIGHT_OUT = os.path.join(REPO, "status", "public", "done_archive.json")

STRIP_FIELDS = ("what", "result")


def build(archive_path=ARCHIVE, out_path=ARCHIVE_LIGHT_OUT):
    with io.open(archive_path, encoding="utf-8") as f:
        a = json.load(f)

    items = a.get("items") or []

    def _light_item(it):
        return {k: v for k, v in it.items() if k not in STRIP_FIELDS}

    light = {
        "updatedAt": a.get("updatedAt"),
        "items": [_light_item(it) for it in items],
    }

    tmp = "%s.tmp.%d" % (out_path, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(light, f, ensure_ascii=False, indent=1)
    os.replace(tmp, out_path)
    return light


if __name__ == "__main__":
    result = build()
    print("done_archive.json（公開軽量版）を書きました（items: %d件）" % len(result.get("items") or []))
