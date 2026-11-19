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
    """比較用に潰す：全角半角・大小文字・アクセント・記号の差を消す。"""
    s = unicodedata.normalize("NFKC", s).lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if not unicodedata.combining(c))
    return re.sub(r"[\s'\"’“”・.,\-_/()\[\]]+", "", s)


PAREN = re.compile(r"[（(\[].*?[)）\]]")
SUFFIX = re.compile(r"\b(jr|sr|ii|iii|official|topic)\b", re.I)


def base_name(s: str) -> str:
    """同一人物判定用。括弧書き・Jr.・The を落とした芯の名前。
    「山下達郎」と「山下達郎 (AOR/LP)」は同じ人。別人扱いしない。"""
    s = PAREN.sub("", s)
    s = SUFFIX.sub("", s)
    s = re.sub(r"^the\s+", "", s.strip(), flags=re.I)
    s = re.sub(r"['’]\d{2}$", "", s.strip())   # モーニング娘。'26
    return norm(s)


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
    seen = set()
    for short, sid, sraw in names:
        for long, lid, lraw in names:
            if sid == lid or short == long or short not in long:
                continue
            k = (sid, lid)
            if k in seen:
                continue
            seen.add(k)
            out.append({"short_id": sid, "short": sraw,
                        "long_id": lid, "long": lraw})
    return out


SEG_SPLIT = re.compile(r"[-–—/|｜／:：~〜]|\bfeat\.?\b|\bft\.?\b|\bwith\b", re.I)


def segments(title: str):
    """曲名を「演者が書かれがちな位置」で切る。"""
    return [norm(p) for p in SEG_SPLIT.split(title) if norm(p)]


def check(artists):
    """本体：各アーティストの曲を1曲ずつ関門に通す。

    関門A（=今回の事故）：自分の名前が別アーティストの名前の一部になっている組で、
      曲名にその「長いほうの名前」が入っている。akiko の棚に AKIKO YANO が入る型。
      これは必ず落とす。
    関門B：曲名の「演者が書かれる位置」に別アーティストの名前が丸ごと入っている。
      共演の可能性があるので保留＝載せない側に倒す。
    """
    by_id = {a["id"]: a for a in artists}
    # 正規化名 → id。長い名前を優先して当てるため長さ順に持つ
    name_owner = {}
    for a in artists:
        for nm in [a["name"]] + a.get("aliases", []):
            n = norm(nm)
            if len(n) >= MIN_NAME_LEN:
                name_owner.setdefault(n, {"ids": set(), "raw": nm})
                name_owner[n]["ids"].add(a["id"])

    # 同一人物の重複登録（棚違い）を別人扱いしないための芯の名前
    base_of = {}
    for a in artists:
        parts = []
        for x in [a["name"]] + a.get("aliases", []):
            # 括弧書き（棚の区別）を先に落としてから「/」で割る。
            # 「山下達郎 (AOR/LP)」を AOR と LP で割ってしまわないように。
            parts.extend(p for p in re.split(r"[/／]", PAREN.sub("", x)) if p.strip())
        base_of[a["id"]] = {base_name(p) for p in parts
                            if len(base_name(p)) >= MIN_NAME_LEN}

    def same_person(id1, id2):
        return bool(base_of.get(id1, set()) & base_of.get(id2, set()))

    blocked, hold = [], []
    for a in artists:
        self_names = {norm(x) for x in [a["name"]] + a.get("aliases", [])
                      if len(norm(x)) >= MIN_NAME_LEN}
        # 関門A用：自分の名前を「含んでしまう」別人の長い名前
        traps = {}
        for me in self_names:
            for n, info in name_owner.items():
                if n == me or me not in n:
                    continue
                others = {i for i in info["ids"]
                          if i != a["id"] and not same_person(i, a["id"])}
                if others:
                    traps[n] = (info["raw"], others)

        for s in a["songs"]:
            title_n = norm(s["title"])
            segs = set(segments(s["title"]))
            if COVER_MARK.search(s["raw"]):
                continue                      # カバーは例外＝通す

            # --- 関門A ---
            hitA = {}
            for n, (raw, others) in traps.items():
                if n in title_n:
                    hitA[raw] = others
            if hitA:
                ids = set().union(*hitA.values())
                # 別人名を曲名から取り除いても、まだ本人の名前が残っているなら
                # 本人の曲に相手が客演しているだけかもしれない。落とさず保留にする。
                stripped = title_n
                for raw in hitA:
                    stripped = stripped.replace(norm(raw), "")
                if any(sn in stripped for sn in self_names):
                    hold.append({
                        "gate": "B", "artist_id": a["id"], "artist": a["name"],
                        "song_id": s["id"], "title": s["title"], "line": s["line"],
                        "other": sorted(by_id[i]["name"] for i in ids if i in by_id),
                        "other_ids": sorted(ids),
                        "why": "本人名も曲名に入っている。共演か要確認",
                    })
                    continue
                blocked.append({
                    "gate": "A", "artist_id": a["id"], "artist": a["name"],
                    "song_id": s["id"], "title": s["title"], "line": s["line"],
                    "other": sorted(by_id[i]["name"] for i in ids if i in by_id),
                    "other_ids": sorted(ids),
                    "why": "曲名に「自分の名前を含む別人のフルネーム」が入っている＝本人でない",
                })
                continue

            # --- 関門B ---
            hitB = set()
            for seg in segs:
                info = name_owner.get(seg)
                if info and seg not in self_names:
                    hitB |= {i for i in info["ids"]
                             if i != a["id"] and not same_person(i, a["id"])}
            # --- 関門C：名前が衝突しうるアーティストの「出所不明の曲」 ---
            # note も year も originalRef も無い＝名前で検索して拾っただけの曲。
            # 名前が他人と衝突する棚では、それは別人の疑いがある。
            if traps and 'note: ""' in s["raw"] and "year:" not in s["raw"] \
                    and "originalRef" not in s["raw"]:
                hold.append({
                    "gate": "C", "artist_id": a["id"], "artist": a["name"],
                    "song_id": s["id"], "title": s["title"], "line": s["line"],
                    "other": sorted({r for r, _ in traps.values()}),
                    "other_ids": sorted(set().union(*[o for _, o in traps.values()])),
                    "why": "出所不明（note/year/originalRefなし）＋名前が衝突する棚。名前検索で拾った別人の疑い",
                })
                continue

            if hitB:
                hold.append({
                    "gate": "B", "artist_id": a["id"], "artist": a["name"],
                    "song_id": s["id"], "title": s["title"], "line": s["line"],
                    "other": sorted(by_id[i]["name"] for i in hitB if i in by_id),
                    "other_ids": sorted(hitB),
                    "why": "曲名の演者位置に別アーティスト名が丸ごと入っている。本人名義か要確認",
                })
    return blocked, hold


def main():
    path = sys.argv[1]
    strict = "--strict" in sys.argv
    artists = parse(path)
    blocked, hold = check(artists)
    collisions = find_collisions(artists)

    print(f"# 関門：アーティスト {len(artists)} 組 / "
          f"曲 {sum(len(a['songs']) for a in artists)} 本を点検")
    nb = sum(1 for r in hold if r["gate"] == "B")
    nc = sum(1 for r in hold if r["gate"] == "C")
    print(f"# 関門A 別人混入（載せない）: {len(blocked)} 件")
    print(f"# 関門B 共演・演者位置に別人名（要確認＝載せない側）: {nb} 件")
    print(f"# 関門C 出所不明＋名前衝突（要確認＝載せない側）: {nc} 件")
    print(f"# 同表記の罠（名前が名前に含まれる組）: {len(collisions)} 組")
    print()
    for r in blocked:
        print(f"[NG] {r['artist']}({r['artist_id']}) L{r['line']}  "
              f"「{r['title']}」 ← {'/'.join(r['other'])}")
    print()
    for r in hold:
        print(f"[保留{r['gate']}] {r['artist']}({r['artist_id']}) L{r['line']}  "
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
