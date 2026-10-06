#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""759番：一度きりの引っ越し作業。

「できたもの」棚（status/dekimono.json）を、①既存18件へ kind:"new" を補い、
②status/queue.json の完了(done)・status/done_archive.json の完了(done)のうち
まだ棚に無いものを record_done() で「新しく作った／直した」に振り分けて積む。

これで「昨日ちらっと出て、今日探せなくなった」を過去分まで一括で解消する
（record_done は kind が付かない純粋な内部配管作業だけは今まで通り載せない）。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import dekimono_lib  # noqa: E402

DEKI_PATH = os.path.join(REPO, "status", "dekimono.json")
QUEUE_PATH = os.path.join(REPO, "status", "queue.json")
ARCHIVE_PATH = os.path.join(REPO, "status", "done_archive.json")


def load(p, default):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return default


def main():
    # ① 既存の18件に kind が無ければ "new" を補う（元々"新しく作った"判定でしか載らなかった棚のため）
    d = load(DEKI_PATH, {"updatedAt": "", "items": []})
    migrated = 0
    for it in d.get("items", []):
        if "kind" not in it:
            it["kind"] = "new"
            migrated += 1
    if migrated:
        tmp = DEKI_PATH + ".tmp"
        json.dump(d, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        os.replace(tmp, DEKI_PATH)
    print("① 既存分に kind:new を補った: %d件" % migrated)

    # ② queue.json の done を取り込む
    q = load(QUEUE_PATH, {"items": []})
    added_new, added_fixed, skipped = 0, 0, 0
    for it in q.get("items", []):
        if it.get("status") != "done":
            continue
        n = it.get("n")
        added_at = it.get("checkedAt") or it.get("finishedAt")
        kind = dekimono_lib.record_done(n, it.get("title"), it.get("result"), it.get("urls"), added_at)
        if kind == "new":
            added_new += 1
        elif kind == "fixed":
            added_fixed += 1
        else:
            skipped += 1

    # ③ done_archive.json の done も同様に取り込む（cancelledは対象外＝重複判定で無効化されたもの）
    arc = load(ARCHIVE_PATH, {"items": []})
    for it in arc.get("items", []):
        if it.get("status") != "done":
            continue
        n = it.get("n")
        added_at = it.get("checkedAt") or it.get("finishedAt")
        kind = dekimono_lib.record_done(n, it.get("title"), it.get("result"), it.get("urls"), added_at)
        if kind == "new":
            added_new += 1
        elif kind == "fixed":
            added_fixed += 1
        else:
            skipped += 1

    print("② queue.json + done_archive.json から取り込み：新しく作った+%d件・直した+%d件・対象外%d件"
          % (added_new, added_fixed, skipped))
    d2 = load(DEKI_PATH, {"items": []})
    print("合計：%d件（うち新しく作った %d件・直した %d件）" % (
        len(d2.get("items", [])),
        len([x for x in d2.get("items", []) if x.get("kind") == "new"]),
        len([x for x in d2.get("items", []) if x.get("kind") == "fixed"]),
    ))


if __name__ == "__main__":
    main()
