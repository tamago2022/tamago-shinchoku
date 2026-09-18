# -*- coding: utf-8 -*-
"""関門：アーティストページに「別人の曲」が入るのを止める。

たまごさんの型：
  - そのアーティストページに入るのは本人だけ。
  - カバーは例外（原曲側への originalRef、または「カバー」と明示があるもの）。
  - 関連するだけの別人は「関連」枠へ。本体には入れない。
  - 判定できないものは「載せない」側に倒す。無いほうがマシ、間違ってるより。

使い方:
  python3 tools/sekisho/gate_artist_song.py <coverGuide.ts>            # 点検して一覧を出す
  python3 tools/sekisho/gate_artist_song.py <coverGuide.ts> --strict   # 1件でも見つかったら exit 1（仕入れの入口用）
  python3 tools/sekisho/gate_artist_song.py <coverGuide.ts> --json out.json

終了コード: 0=通過 / 1=別人混入あり（--strict時）
"""
import json
import re
import sys
import unicodedata

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from parse_coverguide import parse  # noqa: E402

# 「カバーだと明示されている」印
COVER_MARK = re.compile(
    r"カバー|カヴァー|cover|tribute|トリビュート|originalRef|covered", re.I)
# 共演の印（本人のページに置いてよい可能性が高い）
FEAT_MARK = re.compile(r"feat\.|featuring|with |\bx\b|×|＆|&|duet", re.I)
# 名前として短すぎて誤爆するもの
MIN_NAME_LEN = 4


def norm(s: str) -> str:
    """比較用に潰す：全角半角・大小文字・記号の差を消す。"""
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[\s'\"’“”・.,\-_/()\[\]]+", "", s)


def build_name_index(artists):
    """正規化した名前 → アーティストid の索引。別名も入れる。"""
    idx = {}
    for a in artists:
        for nm in [a["name"]] + a.get("aliases", []):
            n = norm(nm)
            if len(n) >= MIN_NAME_LEN:
                idx.setdefault(n, set()).add(a["id"])
    return idx


def find_collisions(artists):
    """同表記の罠：ある名前が別の名前の一部に含まれてしまう組み合わせ。"""
    names = []
    for a in artists:
        for nm in [a["name"]] + a.get("aliases", []):
            n = norm(nm)
            if len(n) >= MIN_NAME_LEN:
                names.append((n, a["id"], nm))
    out = []
    for short, sid, sraw in names:
        for long, lid, lraw in names:
            if sid == lid or short == long:
                continue
            if short in long:
                out.append({"short_id": sid, "short": sraw,
                            "long_id": lid, "long": lraw})
    return out


def check(artists):
    """本体：各アーティストの曲を1曲ずつ関門に通す。"""
    idx = build_name_index(artists)
    by_id = {a["id"]: a for a in artists}
    blocked, hold = [], []

    for a in artists:
        self_names = {norm(x) for x in [a["name"]] + a.get("aliases", [])}
        for s in a["songs"]:
            title_n = norm(s["title"])
            raw = s["raw"]
            has_cover_mark = bool(COVER_MARK.search(raw))

            # 曲名の中に「別人の名前」が入っていないか
            hits = set()
            for name_n, ids in idx.items():
                if name_n in self_names:
                    continue
                if name_n in title_n:
                    # 自分の名前を含んでいるだけの長い名前（akiko ⊂ akikoyano）も
                    # 「別人」として扱う。ここが今回の事故の入口。
                    hits |= (ids - {a["id"]})
            if not hits:
                continue

            rec = {
                "artist_id": a["id"], "artist": a["name"],
                "song_id": s["id"], "title": s["title"], "line": s["line"],
                "other": sorted(by_id[i]["name"] for i in hits if i in by_id),
                "other_ids": sorted(hits),
            }
            if has_cover_mark:
                continue                      # カバーは例外＝通す
            if FEAT_MARK.search(s["title"]):
                rec["why"] = "共演表記あり（feat./with/x）。本人名義か要確認"
                hold.append(rec)              # 判定できない＝保留
            else:
                rec["why"] = "曲名が別アーティストの名前を含む。本人の曲でない疑い"
                blocked.append(rec)           # 別人＝載せない
    return blocked, hold


def main():
    path = sys.argv[1]
    strict = "--strict" in sys.argv
    artists = parse(path)
    blocked, hold = check(artists)
    collisions = find_collisions(artists)

    print(f"# 関門：アーティスト {len(artists)} 組 / "
          f"曲 {sum(len(a['songs']) for a in artists)} 本を点検")
    print(f"# 別人混入（載せない）: {len(blocked)} 件")
    print(f"# 判定保留（載せない側に倒す）: {len(hold)} 件")
    print(f"# 同表記の罠（名前が名前に含まれる組）: {len(collisions)} 組")
    print()
    for r in blocked:
        print(f"[NG] {r['artist']}({r['artist_id']}) L{r['line']}  "
              f"「{r['title']}」 ← {'/'.join(r['other'])}")
    print()
    for r in hold:
        print(f"[保留] {r['artist']}({r['artist_id']}) L{r['line']}  "
              f"「{r['title']}」 ← {'/'.join(r['other'])}")

    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"blocked": blocked, "hold": hold,
                       "collisions": collisions}, f,
                      ensure_ascii=False, indent=2)

    if strict and blocked:
        print("\n★関門で止めました。別人の曲をアーティストページ本体に入れてはいけません。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
