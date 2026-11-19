#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Googleドライブ「一時保管場所」の3個を元へ戻す（2026-10-14）。status/youryou_gdrive6.go → .json
  ・lost_and_found_data.txt から元の場所を読む
  ・元の場所に同じ大きさのものが既にある → 一時保管場所のものは重複なので消す
  ・無い／違う → 元の場所へ書き戻し、大きさを確かめてから一時保管場所のものを消す
  ・中身が空になれば Googleドライブは通知を出さない
  Googleアカウントの接続・設定には一切触らない。デスクトップには何も置かない。
"""
import json, os, re, shutil, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")
GO = os.path.join(REPO, "status", "youryou_gdrive6.go")
OUT = os.path.join(REPO, "status", "youryou_gdrive6.json")
LAF = HOME + "/Library/Application Support/Google/DriveFS/lost_and_found/105507007224342070482"
MOUNT = HOME + "/Library/CloudStorage/GoogleDrive-eggypop2010@gmail.com"


def main():
    if not os.path.exists(GO):
        return
    os.remove(GO)
    res = {"at": time.strftime("%F %T"), "items": []}
    data_p = os.path.join(LAF, "lost_and_found_data.txt")
    try:
        data = open(data_p, encoding="utf-8", errors="replace").read()
    except Exception as e:
        data = ""
        res["data_err"] = str(e)
    res["data"] = data
    res["mount_exists"] = os.path.isdir(MOUNT)
    for fn in sorted(os.listdir(LAF)) if os.path.isdir(LAF) else []:
        if not fn.lower().endswith((".mp4", ".mov", ".png", ".jpg", ".pdf", ".txt")) or fn == "lost_and_found_data.txt":
            continue
        src = os.path.join(LAF, fn)
        it = {"file": fn, "bytes": os.path.getsize(src)}
        # data.txt の中で、このファイル名を含む行から元の場所（ドライブ内のパス）を拾う
        orig = None
        # 1行＝「元の場所, 一時保管場所」
        for line in data.splitlines():
            first = line.split(", " + LAF, 1)[0].strip()
            if first.endswith("/" + fn) and first.startswith(MOUNT + "/"):
                orig = first
                break
        it["orig"] = orig
        cand = None
        if orig:
            try:
                os.makedirs(os.path.dirname(orig), exist_ok=True)  # 元のフォルダ（ドライブ内）を戻す
                cand = orig
            except Exception as e:
                it["mkdir_err"] = str(e)[:120]
        it["dest"] = cand
        if cand and os.path.exists(cand) and os.path.getsize(cand) == it["bytes"]:
            os.remove(src)
            it["result"] = "元の場所に同じものがあった（重複）→一時保管場所のものを消した"
        elif cand:
            try:
                shutil.copyfile(src, cand)
                if os.path.getsize(cand) == it["bytes"]:
                    os.remove(src)
                    it["result"] = "元の場所へ戻した"
                else:
                    it["result"] = "戻したが大きさが合わない→一時保管場所のものは残した"
            except Exception as e:
                it["result"] = "戻せず（%s）→残した" % str(e)[:120]
        else:
            # 2026-10-14 実測：工場（心臓）からはドライブの中へ書けない（Resource deadlock avoided）。
            #   捨てずに iMac HDD へ写して保管し、確かめてから一時保管場所を空にする（＝通知が止まる）。
            try:
                import sys
                sys.path.insert(0, os.path.join(REPO, "tools"))
                import hdd_okiba
                if hdd_okiba.ok():
                    sub = os.path.basename(os.path.dirname(orig)) if orig else "不明"
                    d = hdd_okiba.dest("Googleドライブ一時保管場所から", sub)
                    q = os.path.join(d, fn)
                    shutil.copyfile(src, q)
                    if os.path.getsize(q) == it["bytes"]:
                        os.remove(src)
                        it["result"] = "ドライブへは書き戻せず→iMac HDDへ保管：%s" % q
                    else:
                        it["result"] = "HDDへの写しの大きさが合わない→残した"
                else:
                    it["result"] = "HDDが無い→残した"
            except Exception as e:
                it["result"] = "保管できず（%s）→残した" % str(e)[:100]
        res["items"].append(it)
    left = [f for f in os.listdir(LAF) if f not in ("lost_and_found_data.txt", ".DS_Store")] if os.path.isdir(LAF) else []
    if not left and os.path.isdir(LAF):
        for f in ("lost_and_found_data.txt", ".DS_Store"):
            try:
                os.remove(os.path.join(LAF, f))
            except Exception:
                pass
        res["laf_empty"] = True
    else:
        res["laf_left"] = left
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
