#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1122番【いま押す】Lovableの公開ボタンを、この場で1回押す。

━━ なぜ要るか（たまごさん 2026-09-24）━━
  「パブリッシュをあなたはいつも押してるのに、なんで俺が押さないといけないの？
   もうこのやりとりやめない？」

  押す道具（tools/kohyou_osu.py）は**前から有る**。押せなかった理由は鍵ではなく**規則**：
  kohyou_osu は「見る係(kohyou_kanshi)が赤を出していて、かつ15分あけて、かつ1日12回まで」
  でしか押さない見張り用の係で、**便が終わる時に自分の意思で1回押す口が無かった。**
  だから毎回「たまごさんが押してください」になっていた。

  ここはその1つだけを足す：**押す。押した事実を書く。判定はしない。**
  規則（赤かどうか・間隔・回数）は見張りの話なので、ここでは見ない。
  代わりに**Lovableが main を取り込んでいるか**だけは必ず確かめる（別の中身を出さない）。

━━ 使い方 ━━
  python3 tools/kohyou_ima.py                      # 取り込みを待って押す（既定10分）
  python3 tools/kohyou_ima.py --sha <押したいsha>   # そのshaが入るまで待って押す
  python3 tools/kohyou_ima.py --nowait             # 待たずに今すぐ押す

  ★呼ぶ道具は get_project と deploy_project の2つだけ（kohyou_osu の白名簿を使う）。
  ★deploy は全プラン無料。金は出ない。
"""
import argparse
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import kohyou_osu as K  # noqa: E402  （鍵の読み方・refresh・白名簿・MATOはそこが正本）

LOG = os.path.join(REPO, "status", "kohyou_ima.log")


def _log(line):
    s = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), line)
    print(s)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(s + "\n")
    except Exception:
        pass


def press(want_sha="", wait_sec=600, name="ごきげん補給所"):
    mato = K.MATO[name]
    lv = K.Lovable()
    if not lv.ok():
        return {"ok": False, "riyuu": "鍵がありません（%s）" % K.TOKEN_PATH}
    lv.hello()

    got = None
    deadline = time.time() + max(0, wait_sec)
    while True:
        o, err = lv.call("get_project", {"project_id": mato["project_id"]})
        if o is None:
            return {"ok": False, "riyuu": "get_project が読めません: %s" % err}
        got = (o.get("latest_commit_sha") or "")
        if not want_sha or got.startswith(want_sha[:8]) or want_sha.startswith(got[:8]):
            break
        if time.time() >= deadline:
            return {"ok": False, "riyuu": "Lovableがまだ %s を取り込んでいません（今 %s）"
                                          % (want_sha[:8], (got or "-")[:8]),
                    "lovableSha": got[:12]}
        _log("取り込み待ち … Lovable=%s / 待っているのは %s" % ((got or "-")[:8], want_sha[:8]))
        time.sleep(20)

    before = K._honban_key(mato["url"]) or ""
    r, err = lv.call("deploy_project", {"project_id": mato["project_id"]})
    if r is None:
        return {"ok": False, "riyuu": "deploy_project の返事が読めません: %s" % err,
                "lovableSha": (got or "")[:12]}
    _log("★押しました（Lovableのコミット %s / 前=%s / status=%s / id=%s）"
         % ((got or "-")[:8], before or "-", r.get("status"),
            (r.get("deployment_id") or "")[:8]))
    return {"ok": True, "riyuu": "押した", "lovableSha": (got or "")[:12],
            "beforeKey": before, "deploymentId": r.get("deployment_id"),
            "status": r.get("status"), "url": mato["url"]}


def verify(before, url="https://joy-relief-station.lovable.app/", wait_sec=420):
    """押したあと、本番の x-deployment-id が変わるまで見る。★判定を書き替えない。"""
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        now = K._honban_key(url) or ""
        if now and now != before:
            _log("★出ました %s → %s" % (before or "-", now))
            return {"deta": True, "before": before, "after": now}
        time.sleep(20)
    _log("10分見ても x-deployment-id が変わりません（%s のまま）" % (before or "-"))
    return {"deta": False, "before": before}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha", default="")
    ap.add_argument("--wait", type=int, default=600)
    ap.add_argument("--nowait", action="store_true")
    a = ap.parse_args()
    out = press(a.sha, 0 if a.nowait else a.wait)
    if out.get("ok"):
        out["kakunin"] = verify(out.get("beforeKey") or "")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
