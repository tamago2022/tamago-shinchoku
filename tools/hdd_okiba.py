#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工場の「溜まるもの」の置き場＝iMac HDD（外付け）。正本はこの1か所。

たまごさんの指示（2026-10-12）：
  「溜まるものはiMacのHDD（外付け）に置き、macOS本体には溜めない」
  「HDDが外れているときは、本体に溜めずに処理を止める」
★HDDは exFAT（実測 2026-10-12：2.0TB・空き753GB）。シンボリックリンクが置けないので、
  node_modules を含む作業場（git worktree）そのものは置けない。作業場は本体で作り、
  終わったら tools/worktree_taihi.py が消す（未保存のものは HDD へ tar.gz で写してから消す）。
"""
import os

HDD = "/Volumes/iMac HDD"
ROOT = os.path.join(HDD, "Mac標準置き場")


def ok():
    """HDDがつながっていて書けるか。"""
    if not os.path.isdir(ROOT):
        return False
    t = os.path.join(ROOT, ".kakikomi_test")
    try:
        with open(t, "w") as f:
            f.write("ok")
        os.remove(t)
        return True
    except Exception:
        return False


def dest(*parts):
    p = os.path.join(ROOT, *parts)
    os.makedirs(p, exist_ok=True)
    return p
