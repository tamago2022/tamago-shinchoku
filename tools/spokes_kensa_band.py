#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【スポークスハブ・バンド版の関所】「誰が、そのバンドの何をカバーしたか」を1曲ずつMusicBrainzで裏取りする。

■ なぜ spokes_hub.py の --atsumeru だけでは足りないか（実測・推測ではない）
  spokes_hub の方向Bは「**バンドのMBIDが work の作者に入っている**」ものだけを拾う。
  ところがビートルズの曲の作者は MusicBrainz では
  John Lennon / Paul McCartney / George Harrison **個人**として入っており、
  "The Beatles" というアーティストMBIDは作者に入らない。
  → そのままだと方向Bがほぼ0件になる。バンドはこの形が普通。

■ この係のやり方（関所を通る形）
  1. バンド本人の録音が繋がっている work の集合を作る（＝**バンドが実際に録った曲**）
  2. 曲名の一致ではなく、その **work のMBID** に繋がっている録音を全部引く
  3. その録音のアーティスト・クレジットに、カバーした人の **MBIDが入っているか**で判定する
     （名前の字面では繋がない。akiko × AKIKO の事故と同じ形を塞ぐ）
  4. work の作者にバンドのメンバーが入っているかを確かめる
     （入っていなければ「バンドが他人の曲をカバーした物」なので方向Bではない）
  5. 通ったものだけを spokes_hub の mb.json の dirB / dirB_clean に書き込む
     → 以後 --kensho / --hyou がそのまま使える

■ 口
  python3 tools/spokes_kensa_band.py --artist "The Beatles" \
      --members 4d5447d7-c61c-4120-ba1b-d7f471d385b9,ba550d0e-adac-4864-b88b-407cab5e76af,42a8f507-8412-4611-854f-926571049fa0,300c4c73-33ac-4255-9d57-4e32627f5e13 \
      --in status/spokes/the-beatles/kouho.json
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import spokes_hub as H  # noqa: E402


def work_set(st):
    """バンド本人の録音が繋がっている work（＝本人が実際に録った曲）＋ browse で拾った work。"""
    ws = {}
    for r in st.get("recs", []):
        for w in r.get("works", []):
            ws.setdefault(w, r["title"])
    for w in st.get("works", []):
        ws.setdefault(w["mbid"], w["title"])
    return ws


def find_work(ws, cache, title):
    """曲名から work を引く。★ここは**候補を絞るだけ**で、判定はこの後の録音のMBIDで取る。"""
    n = H.norm(title)
    hit = [wid for wid, t in ws.items() if H.norm(t) == n]
    if not hit:
        hit = [wid for wid, t in ws.items() if n in H.norm(t) or H.norm(t) in n]
    return hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artist", required=True)
    ap.add_argument("--members", default="", help="メンバーのMBIDをカンマ区切りで")
    ap.add_argument("--in", dest="inp", required=True)
    a = ap.parse_args()

    d = H.base(a.artist)
    st = H.load(os.path.join(d, "mb.json"), {}) or {}
    honnin = H.load(os.path.join(d, "honnin.json")) or {}
    members = set(x for x in a.members.split(",") if x)
    members.add(honnin.get("mbid", ""))

    ws = work_set(st)
    print("本人の棚にある work: %d件" % len(ws))
    kouho = json.load(io.open(a.inp, encoding="utf-8"))

    wcache = st.get("kensa_workcache", {})
    dirB, horyuu = [], []
    for k in kouho:
        kyoku, enja = k["kyoku"], k["enja"]
        wids = find_work(ws, wcache, kyoku)
        if not wids:
            horyuu.append(dict(k, riyuu="本人の棚にその work が無い"))
            print("保留 %-34s / %-26s  workなし" % (kyoku[:34], enja[:26]))
            continue
        got = None
        for wid in wids[:3]:
            if wid not in wcache:
                w = H.mb("work/" + wid, inc="artist-rels")
                wcache[wid] = {"title": w["title"], "sakusha": H.sakusha(w)}
                st["kensa_workcache"] = wcache
                H.save(os.path.join(d, "mb.json"), st)
            c = wcache[wid]
            if not any(s["mbid"] in members for s in c["sakusha"]):
                continue                      # 作者にメンバーが居ない＝本人の曲ではない
            off, found = 0, None
            while off < 500 and not found:
                r = H.mb("recording", work=wid, limit=100, offset=off,
                         inc="artist-credits")
                recs = r.get("recordings", [])
                for rec in recs:
                    cred = rec.get("artist-credit") or []
                    names = [(c2.get("artist") or {}).get("name", "") for c2 in cred]
                    ids = [(c2.get("artist") or {}).get("id", "") for c2 in cred]
                    if any(i in members for i in ids):
                        continue              # 本人／メンバーの録音はカバーではない
                    if not any(H.norm(n) == H.norm(enja) for n in names):
                        continue
                    found = {"rec": rec, "names": names, "ids": ids, "wid": wid,
                             "wtitle": c["title"], "sakusha": c["sakusha"]}
                    break
                if len(recs) < 100:
                    break
                off += 100
            if found:
                got = found
                break
        if not got:
            horyuu.append(dict(k, riyuu="その work に、その人のMBID付きの録音が無い"))
            print("保留 %-34s / %-26s  録音なし" % (kyoku[:34], enja[:26]))
            continue
        dirB.append({
            "houkou": "B", "enja": enja, "kyoku": got["rec"]["title"],
            "moto": a.artist,
            "sakusha": [s["name"] for s in got["sakusha"]],
            "enjaMbid": next(i for i, n in zip(got["ids"], got["names"])
                             if H.norm(n) == H.norm(enja)),
            "workMbid": got["wid"], "workTitle": got["wtitle"],
            "recMbid": got["rec"]["id"]})
        print("通し %-34s / %-26s  work %s" % (kyoku[:34], enja[:26], got["wid"][:8]))

    st["dirB"] = dirB
    st["dirB_clean"] = dirB
    st.setdefault("dirA", [])
    st["kensa_horyuu"] = horyuu
    H.save(os.path.join(d, "mb.json"), st)
    print("\n通った %d件 ／ 保留 %d件" % (len(dirB), len(horyuu)))


if __name__ == "__main__":
    sys.exit(main())
