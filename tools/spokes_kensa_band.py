#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【スポークスハブ・バンド版の関所】「誰が、そのバンドの何をカバーしたか」を1曲ずつMusicBrainzで裏取りする。

■ なぜ spokes_hub.py の --atsumeru だけでは足りないか（2026-09-27 実測）
  spokes_hub の方向Bは「**バンドのMBIDが work の作者に入っている**」ものだけを拾う。
  ビートルズで走らせた実測：

      本人が作者のwork: 0件 ／ 方向B 0件

  MusicBrainz では、ビートルズの曲の作者は John Lennon / Paul McCartney /
  George Harrison **個人**として入っており、"The Beatles" というアーティストMBIDは
  作者に入らない。バンドはこの形が普通なので、そのままでは方向Bが常に0件になる。

■ この係のやり方（関所を通る形。曲名の一致では繋がない）
  1. **メンバー個人のMBID**で work を browse する（＝メンバーが書いた曲）
  2. 曲名で work の候補を絞る（★絞るだけ。ここは判定ではない）
  3. その work に繋がっている録音を全部引き、アーティスト・クレジットの**MBID**を見る
     ・バンド本人のMBIDの録音があるか → 無ければ「バンドが録っていない曲」なので落とす
     ・カバーした人のMBIDの録音があるか → 無ければ落とす
  4. 通ったものだけを spokes_hub の mb.json の dirB / dirB_clean に書く
     → 以後 --kensho / --hyou がそのまま使える

  ＝「名前が同じ」ではなく「**同じ work に、両方のMBIDの録音がぶら下がっている**」で判定する。

■ 口
  python3 tools/spokes_kensa_band.py --artist "The Beatles" \
      --members "John Lennon,Paul McCartney,George Harrison,Ringo Starr" \
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


def member_mbids(names):
    out = {}
    for nm in names:
        r = H.mb("artist", query='artist:"%s"' % nm, limit=5)
        hit = next((a for a in r.get("artists", []) if H.norm(a["name"]) == H.norm(nm)), None)
        if not hit:
            print("★メンバーが引けません: %s" % nm)
            continue
        out[hit["id"]] = hit["name"]
        print("メンバー %s = %s" % (hit["name"], hit["id"]))
    return out


def member_works(mbids):
    """メンバーが作者として繋がっている work を全部引く。"""
    ws = {}
    for mid, nm in mbids.items():
        off = 0
        while off < 1200:
            r = H.mb("work", artist=mid, limit=100, offset=off, inc="artist-rels")
            got = r.get("works", [])
            for w in got:
                ws[w["id"]] = {"title": w["title"], "sakusha": H.sakusha(w)}
            if len(got) < 100:
                break
            off += 100
        print("  %s の work 累計 %d件" % (nm, len(ws)))
    return ws


def recordings_of(wid):
    out, off = [], 0
    while off < 800:
        r = H.mb("recording", work=wid, limit=100, offset=off, inc="artist-credits")
        got = r.get("recordings", [])
        out += got
        if len(got) < 100:
            break
        off += 100
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artist", required=True)
    ap.add_argument("--members", required=True, help="メンバー名をカンマ区切りで")
    ap.add_argument("--in", dest="inp", required=True)
    a = ap.parse_args()

    d = H.base(a.artist)
    st = H.load(os.path.join(d, "mb.json"), {}) or {}
    honnin = H.load(os.path.join(d, "honnin.json")) or {}
    band = honnin.get("mbid", "")
    if not band:
        raise SystemExit("honnin.json がありません。先に spokes_hub --atsumeru を1回")

    mem = st.get("kensa_members")
    if not mem:
        mem = member_mbids([x.strip() for x in a.members.split(",") if x.strip()])
        st["kensa_members"] = mem
        H.save(os.path.join(d, "mb.json"), st)
    else:
        print("メンバー（控えから）: %s" % "、".join(mem.values()))

    ws = st.get("kensa_works")
    if not ws:
        ws = member_works(mem)
        st["kensa_works"] = ws
        H.save(os.path.join(d, "mb.json"), st)
    print("メンバーが作者の work: %d件" % len(ws))

    kouho = json.load(io.open(a.inp, encoding="utf-8"))
    dirB, horyuu = [], []
    for k in kouho:
        kyoku, enja = k["kyoku"], k["enja"]
        n = H.norm(kyoku)
        cands = [w for w, v in ws.items() if H.norm(v["title"]) == n]
        if not cands:
            cands = [w for w, v in ws.items()
                     if n and (n in H.norm(v["title"]) or H.norm(v["title"]) in n)]
        if not cands:
            horyuu.append(dict(k, riyuu="メンバーが作者の work にその曲名が無い"))
            print("保留 %-38s / %-24s  work無し" % (kyoku[:38], enja[:24]))
            continue
        got = None
        for wid in cands[:2]:
            recs = recordings_of(wid)
            band_rec = [r for r in recs
                        if any((c.get("artist") or {}).get("id") == band
                               for c in (r.get("artist-credit") or []))]
            if not band_rec:
                continue                       # バンドが録っていない＝バンドの曲ではない
            for r in recs:
                cred = r.get("artist-credit") or []
                ids = [(c.get("artist") or {}).get("id", "") for c in cred]
                names = [(c.get("artist") or {}).get("name", "") for c in cred]
                if band in ids or any(i in mem for i in ids):
                    continue                   # 本人・メンバーの録音はカバーではない
                if not any(H.norm(x) == H.norm(enja) for x in names):
                    continue
                got = {"rec": r, "ids": ids, "names": names, "wid": wid,
                       "wtitle": ws[wid]["title"], "sakusha": ws[wid]["sakusha"],
                       "bandRec": band_rec[0]["id"]}
                break
            if got:
                break
        if not got:
            horyuu.append(dict(k, riyuu="その work に、その人のMBID付きの録音が無い"
                                        "／またはバンド本人の録音が無い"))
            print("保留 %-38s / %-24s  録音無し" % (kyoku[:38], enja[:24]))
            continue
        dirB.append({
            "houkou": "B", "enja": enja, "kyoku": got["rec"]["title"],
            "moto": a.artist,
            "sakusha": [s["name"] for s in got["sakusha"]],
            "enjaMbid": next(i for i, x in zip(got["ids"], got["names"])
                             if H.norm(x) == H.norm(enja)),
            "workMbid": got["wid"], "workTitle": got["wtitle"],
            "recMbid": got["rec"]["id"], "bandRecMbid": got["bandRec"]})
        print("通し %-38s / %-24s  work %s" % (kyoku[:38], enja[:24], got["wid"][:8]))
        st["dirB"] = dirB
        st["dirB_clean"] = dirB
        st["kensa_horyuu"] = horyuu
        H.save(os.path.join(d, "mb.json"), st)

    st["dirB"] = dirB
    st["dirB_clean"] = dirB
    st["kensa_horyuu"] = horyuu
    st.setdefault("dirA", [])
    H.save(os.path.join(d, "mb.json"), st)
    print("\n通った %d件 ／ 保留 %d件" % (len(dirB), len(horyuu)))


if __name__ == "__main__":
    sys.exit(main())
