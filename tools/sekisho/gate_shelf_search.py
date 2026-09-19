# -*- coding: utf-8 -*-
"""関門：「検索に出るのに、その人の棚に無い曲」を出させない。

事故：ジャズシンガー akiko の棚に Tristeza / Come Together / Somebody Else's Guy が無い。
検索では出る。棚には無い。初めて来た人には、曲が消えたようにしか見えない。

原因は棚側の絞り込み（cover-guide.tsx の playable）で、検索側（searchSongs）は
全曲をそのまま見ている。同じ元データから作っているのに、片方だけが曲を捨てている。

この関門は両方を同じ式で数え直し、片側にしか無い曲を数える。
--strict を付けると1件でもあれば exit 1（コミットを通さない）。

使い方:
  python3 tools/sekisho/gate_shelf_search.py <coverGuide.ts>
  python3 tools/sekisho/gate_shelf_search.py <coverGuide.ts> --json out.json
  python3 tools/sekisho/gate_shelf_search.py <coverGuide.ts> --strict
  python3 tools/sekisho/gate_shelf_search.py <coverGuide.ts> --allow allow_shelf_gap.txt

終了コード: 0=一致 / 1=ズレあり（--strict時）
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_coverguide_deep import parse_deep, parse_curated_with_video, _strip_for_scan, _match_brace, _unesc  # noqa: E402

STR = r'"((?:[^"\\]|\\.)*)"'


def parse_curated_flag(path, flag):
    """curated の "artistId/songId" のうち <flag>: true が立っているキー集合。"""
    src = open(path, encoding="utf-8").read()
    scan = _strip_for_scan(src)
    out = set()
    pat = re.compile(flag + r'\s*:\s*true')
    for m in re.finditer(r'^\s*' + STR + r'\s*:\s*\{', src, re.M):
        key = _unesc(m.group(1))
        if "/" not in key:
            continue
        b = scan.find("{", m.start())
        e = _match_brace(scan, b)
        if e < 0:
            continue
        if pat.search(scan[b:e + 1]):
            out.add(key)
    return out


def analyze(path):
    artists = parse_deep(path)
    with_video = parse_curated_with_video(path)
    covers_are_originals = parse_curated_flag(path, "coversAreOriginals")
    # 直した後（publicSongs が入った後）は、カバーは棚から外さない。
    # 同じ台本で両方を数えるため、ここも同じ分岐で切り替える。
    keep_covers = "export function publicSongs" in open(path, encoding="utf-8").read()
    if keep_covers:
        covers_are_originals = set()

    rows = []          # 検索にあるが棚に無い
    per_reason = {"hideFromArtistList": 0, "originalRef（カバー）": 0,
                  "coversAreOriginals": 0, "再生できる動画が無い": 0}
    total_songs = 0
    shelf_total = 0

    for a in artists:
        key = a["id"]
        songs = a["songs"]
        drop = {}

        not_discarded = [s for s in songs if not s["hideFromArtistList"]]
        for s in songs:
            if s["hideFromArtistList"]:
                drop[s["id"]] = "hideFromArtistList"

        not_cover = [s for s in not_discarded
                     if keep_covers or (not s["originalRef"]
                                        and f"{key}/{s['id']}" not in covers_are_originals)]
        if not_cover:
            for s in not_discarded:
                if s["originalRef"]:
                    drop[s["id"]] = "originalRef（カバー）"
                elif f"{key}/{s['id']}" in covers_are_originals:
                    drop[s["id"]] = "coversAreOriginals"
            deduped = not_cover
        else:
            deduped = not_discarded

        def playable(s):
            if s["youtubeId"] or s["altYoutubeIds"]:
                return True
            return f"{key}/{s['id']}" in with_video

        filtered = [s for s in deduped if playable(s)]
        if filtered:
            for s in deduped:
                if not playable(s):
                    drop[s["id"]] = "再生できる動画が無い"
            base = filtered
        else:
            base = deduped

        shelf_ids = {s["id"] for s in base}
        shelf_total += len(shelf_ids)
        # 直した後は searchSongs も publicSongs() を通るので、検索側＝棚側になる。
        search_set = base if keep_covers else songs
        total_songs += len(search_set)
        for s in search_set:
            if s["id"] not in shelf_ids:
                why = drop.get(s["id"], "不明")
                per_reason[why] = per_reason.get(why, 0) + 1
                rows.append({"artistId": key, "artistName": a["name"],
                             "songId": s["id"], "title": s["title"],
                             "why": why, "line": s["line"],
                             "hasOriginalRef": s["originalRef"]})

    return {"artists": len(artists), "songs": total_songs,
            "shelf": shelf_total, "gap": rows, "byReason": per_reason}


GUARD_RULES = [
    ("coverGuide.ts", "searchSongs が publicSongs() を通っていない",
     r'export function searchSongs[\s\S]{0,600}?for \(const s of publicSongs\(a\)\)'),
    ("coverGuide.ts", "songIsPublic() が無い（捨てる判断の置き場所が1か所でない）",
     r'export function songIsPublic\s*\('),
    ("coverGuide.ts", "publicSongs() が無い",
     r'export function publicSongs\s*\('),
]


def guard_sources(cg_path, tsx_path):
    """コードの形を見張る。データが今たまたま揃っていても、
    棚側だけが曲を捨てる書き方に戻ったらここで落とす。"""
    ng = []
    cg = open(cg_path, encoding="utf-8").read()
    for _, msg, pat in GUARD_RULES:
        if not re.search(pat, cg):
            ng.append(msg)
    if tsx_path and os.path.exists(tsx_path):
        tsx = open(tsx_path, encoding="utf-8").read()
        m = re.search(r'const playable = useMemo\(\(\) => \{[\s\S]*?\n  \}, \[', tsx)
        body = m.group(0) if m else ""
        if not body:
            ng.append("cover-guide.tsx の playable（棚の曲一覧）が見つからない")
        else:
            if "songIsPublic(" not in body:
                ng.append("棚の曲一覧が songIsPublic() を通っていない")
            if re.search(r'!s\.originalRef|coversAreOriginals\s*!==\s*true', body):
                ng.append("棚の曲一覧がカバー（originalRef）を外している"
                          "（カバーは外さず『★ 原曲：◯◯』の印を付けて並べる）")
            if "useArtistWithAddedSongs" in tsx:
                print("【注意・落とさない】棚は admin_artist_songs（DBに後付けした曲）を"
                      "合流させているが、searchSongs はコード側の artists しか見ない。"
                      "＝『棚にあるが検索に出ない』が構造として残っている。"
                      "数はDB次第でコードからは測れない。仕入れを coverGuide.ts に"
                      "書き戻すか、検索側もDBを見るまで消えない。")
            if "hideFromArtistList" in body:
                ng.append("棚の曲一覧が hideFromArtistList を直接見ている"
                          "（songIsPublic() の中だけで見る）")
    return ng


def load_allow(p):
    if not p or not os.path.exists(p):
        return set()
    out = set()
    for ln in open(p, encoding="utf-8"):
        ln = ln.split("#")[0].strip()
        if ln:
            out.add(ln)
    return out


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    path = args[0]
    strict = "--strict" in args
    jout = None
    allow_path = None
    tsx = None
    for i, a in enumerate(args):
        if a == "--json" and i + 1 < len(args):
            jout = args[i + 1]
        if a == "--allow" and i + 1 < len(args):
            allow_path = args[i + 1]
        if a == "--tsx" and i + 1 < len(args):
            tsx = args[i + 1]

    if tsx is not None:
        ng = guard_sources(path, tsx)
        if ng:
            print("★コードの形が「棚と検索がズレる書き方」に戻っています：")
            for x in ng:
                print("   -", x)
            if strict:
                return 1
        else:
            print("コードの形：棚も検索も publicSongs()／songIsPublic() の1か所を通っています。")

    r = analyze(path)
    allow = load_allow(allow_path)
    gap = [g for g in r["gap"] if f"{g['artistId']}/{g['songId']}" not in allow]

    print(f"アーティスト {r['artists']} / 曲（検索に出る） {r['songs']} / 棚に並ぶ {r['shelf']}")
    print(f"★検索にあるが棚に無い： {len(gap)} 件"
          + (f"（うち {len(r['gap']) - len(gap)} 件は許可リストで除外）" if allow else ""))
    print("★棚にあるが検索に出ない： 0 件（coverGuide.ts に書かれた曲について。"
          "DBに後付けした曲は上の注意を参照）")
    for k, v in sorted(r["byReason"].items(), key=lambda x: -x[1]):
        if v:
            print(f"   - {k}: {v} 件")

    by_artist = {}
    for g in gap:
        by_artist.setdefault(g["artistId"], []).append(g)
    print("\n落ちている数が多い棚 上位20：")
    for aid, gs in sorted(by_artist.items(), key=lambda x: -len(x[1]))[:20]:
        print(f"   {len(gs):4d}  {gs[0]['artistName']}  ({aid})")

    if jout:
        with open(jout, "w", encoding="utf-8") as f:
            json.dump({**r, "gap": gap}, f, ensure_ascii=False, indent=1)
        print(f"\n明細を書き出しました（{len(gap)}件）")

    if strict and gap:
        print("\n★このままでは「検索には出るのに棚に無い曲」が残ります。")
        print("  カバーは棚から消さず、『★原曲：◯◯』の印を付けて棚に並べてください。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
