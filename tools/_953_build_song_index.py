#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案内人が引くための「軽い索引」を作る。

coverGuide.ts は 6.1MB ある。丸ごとブラウザに積んだら、たまごさんのスマホが死ぬ。
だから2段に分ける。

  share/check/assets/953-songs/head.json   … アーティスト名簿＋各人の代表曲（気分で探す用）
  share/check/assets/953-songs/t/NN.json   … 曲名で探す用。**聞かれた語の棚しか読まない**

ページを開いた時点では1バイトも読まない。
お客さんが「なにか無い？」と言って初めて head.json を読み、
曲名を口に出したときだけ、その頭文字の棚を1〜2枚だけ読む。

**索引に入っていない曲は、案内人も口に出せない。**
（存在しない曲名を喋らせないための、唯一の仕掛け）
"""
import json
import pathlib
import re
import sys
import unicodedata

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC = REPO / "status" / "_952" / "recon" / "HIT_src_lib_coverGuide.ts"
OUT_DIR = REPO / "share" / "check" / "assets" / "953-songs"
BASE = "https://joy-relief-station.lovable.app/cover-guide"
NBUCKET = 128
MAX_BYTES = 900 * 1024

# 案内人が出してはいけない「寄せ集め動画」。曲ではないので棚から外す。
JUNK = re.compile(
    r"(greatest hits|top\s*\d+|best of|full album|playlist|non.?stop|"
    r"\d+\s*hits|listen in 20\d\d|collection 20\d\d|mix\s*20\d\d|"
    r"hit parade|a.list hits|groove mix|\bmix\b[^|]*\bhits?\b|"
    r"\bvol\.?\s*\d+\b[^|]*\bmix\b|\bmix\b\s*$|"
    r"メドレー|作業用|睡眠用|\d+\s*時間|【\s*\d+\s*(分|時間)|連続】|"
    r"の名曲(集|selection)|傑作選|詰め合わせ)", re.I)


# ── コメントを消す（文字列の中の // は消さない） ──────────────────
def strip_comments(s: str) -> str:
    out = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in "\"'`":
            q = c
            out.append(c)
            i += 1
            while i < n:
                if s[i] == "\\":
                    out.append(s[i:i + 2])
                    i += 2
                    continue
                out.append(s[i])
                if s[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            j = s.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


# ── 走査（再帰なし・壊れた行があっても隣まで巻き込まない） ─────────
def scan_obj(s: str, i: int) -> int:
    """s[i] が '{' のとき、対応する '}' の位置を返す。見つからなければ -1。"""
    depth, n, j = 0, len(s), i
    while j < n:
        c = s[j]
        if c in "\"'`":
            q = c
            j += 1
            while j < n:
                if s[j] == "\\":
                    j += 2
                    continue
                if s[j] == q:
                    break
                j += 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return -1


RE_ARTIST = re.compile(r'\{\s*id:\s*"([^"]+)",\s*name:\s*"((?:[^"\\]|\\.)*)"')
RE_OBJ_START = re.compile(r'\{\s*id:\s*"')
RE_FIELD_S = {k: re.compile(r'\b%s:\s*"((?:[^"\\]|\\.)*)"' % k)
              for k in ("id", "title", "note", "copy", "youtubeId", "kind", "about")}
RE_YEAR = re.compile(r"\byear:\s*(\d{4})")
RE_PICK = re.compile(r"\bpick:\s*true")
RE_ALT = re.compile(r'\baltYoutubeIds:\s*\[\s*"([^"]+)"')
RE_LIST = {k: re.compile(r"\b%s:\s*\[([^\]]*)\]" % k)
           for k in ("aliases", "tags", "eras")}
RE_STR_ITEM = re.compile(r'"((?:[^"\\]|\\.)*)"')


def unesc(s: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), s)


def field(body: str, key: str):
    m = RE_FIELD_S[key].search(body)
    return unesc(m.group(1)) if m else None


def listfield(body: str, key: str):
    m = RE_LIST[key].search(body)
    return [unesc(x) for x in RE_STR_ITEM.findall(m.group(1))] if m else []


def read_artists(src: str):
    """アーティスト1組ずつを、独立した塊として取り出す。"""
    out, seen, pos = [], set(), 0
    for m in RE_ARTIST.finditer(src):
        if m.start() < pos:
            continue
        end = scan_obj(src, m.start())
        if end < 0:
            continue
        body = src[m.start():end + 1]
        if "songs:" not in body:
            continue
        aid = m.group(1)
        if aid in seen:
            pos = end
            continue
        seen.add(aid)
        head = body[:body.index("songs:")]
        art = {
            "id": aid, "name": unesc(m.group(2)),
            "aliases": listfield(head, "aliases"),
            "tags": listfield(head, "tags"),
            "eras": listfield(head, "eras"),
            "kind": field(head, "kind"),
            "about": field(head, "about"),
            "songs": [],
        }
        sk = body.index("songs:")
        j = sk
        while True:
            sm = RE_OBJ_START.search(body, j)
            if not sm:
                break
            se = scan_obj(body, sm.start())
            if se < 0:
                break
            sb = body[sm.start():se + 1]
            j = se + 1
            title = field(sb, "title")
            sid = field(sb, "id")
            if not title or not sid:
                continue
            ym = RE_YEAR.search(sb)
            am = RE_ALT.search(sb)
            art["songs"].append({
                "id": sid, "title": title,
                "note": field(sb, "note") or "",
                "copy": field(sb, "copy") or "",
                "year": int(ym.group(1)) if ym else None,
                "youtubeId": field(sb, "youtubeId"),
                "altYoutubeIds": [am.group(1)] if am else [],
                "pick": bool(RE_PICK.search(sb)),
            })
        out.append(art)
        pos = end
    return out


# ── 正規化とバケツ（ブラウザ側と一字一句そろえること） ─────────────
def norm(s) -> str:
    s = unicodedata.normalize("NFKC", str(s)).lower()
    return re.sub(r"[\s'’`\-_.,!?/()（）「」『』・:;\"]+", " ", s).strip()


def tokens(s: str):
    """語の頭2文字。ブラウザ側と一字一句そろえること。"""
    out = set()
    for w in norm(s).split(" "):
        if w:
            out.add(w[:2])
    return out


def bucket(pre: str) -> int:
    h = ord(pre[0]) * 131 + (ord(pre[1]) if len(pre) > 1 else 0)
    return h % NBUCKET


def main():
    if not SRC.exists():
        print("元データが無い:", SRC)
        return 1
    src = strip_comments(SRC.read_text(encoding="utf-8", errors="replace"))

    artists = read_artists(src)

    A, picks, all_rows = [], [], []
    seen_song = set()
    dropped_junk = 0
    for a in artists:
        aid = a["id"]
        aname = a.get("name") or aid
        songs = []
        for s in (a.get("songs") or []):
            if not isinstance(s, dict):
                continue
            sid, title = s.get("id"), s.get("title")
            if not sid or not title:
                continue
            vid = s.get("youtubeId") or ((s.get("altYoutubeIds") or [None])[0])
            if not vid:          # 動画が無い＝押しても何も起きない
                continue
            if JUNK.search(title):
                dropped_junk += 1
                continue
            if (aid, sid) in seen_song:
                continue
            seen_song.add((aid, sid))
            songs.append(s)
        if not songs:
            continue

        ai = len(A)
        kw = [aname] + [x for x in (a.get("aliases") or []) if isinstance(x, str)]
        tg = [x for x in (a.get("tags") or []) if isinstance(x, str)]
        er = [x for x in (a.get("eras") or []) if isinstance(x, str)]
        ent = {"i": aid, "n": aname}
        if kw[1:]:
            ent["al"] = kw[1:][:4]
        if tg:
            ent["g"] = tg[:6]
        if er:
            ent["e"] = er
        if a.get("kind") and a["kind"] != "music":
            ent["k"] = a["kind"]
        about = (a.get("about") or "").strip()
        if about:
            ent["ab"] = about[:70]
        ent["c"] = len(songs)
        A.append(ent)

        # 代表曲（pick優先→noteがある曲→先頭）を最大4曲。head.json に入る分。
        ranked = sorted(
            songs,
            key=lambda s: (0 if s.get("pick") else 1,
                           0 if (s.get("copy") or s.get("note")) else 1))
        for s in ranked[:2]:
            row = [ai, s["id"], s["title"],
                   s.get("year") if isinstance(s.get("year"), int) else 0,
                   s.get("youtubeId") or (s.get("altYoutubeIds") or [""])[0]]
            note = (s.get("copy") or s.get("note") or "").strip()
            picks.append(row + ([note[:40]] if note else []))

        for s in songs:
            all_rows.append([ai, s["id"], s["title"],
                             s.get("year") if isinstance(s.get("year"), int) else 0,
                             s.get("youtubeId") or (s.get("altYoutubeIds") or [""])[0],
                             1 if s.get("pick") else 0])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "t").mkdir(exist_ok=True)

    hp = OUT_DIR / "head.json"
    hp.write_text(json.dumps({"base": BASE, "nb": NBUCKET, "A": A,
                              "n": len(all_rows)},
                             ensure_ascii=False, separators=(",", ":")),
                  encoding="utf-8")
    pp = OUT_DIR / "picks.json"
    pp.write_text(json.dumps(picks, ensure_ascii=False, separators=(",", ":")),
                  encoding="utf-8")

    buckets = {i: [] for i in range(NBUCKET)}
    # アーティスト名では引かない（それは head.json の仕事）。曲名の語だけ棚に置く。
    for row in all_rows:
        for pre in sorted(tokens(row[2]))[:4]:
            buckets[bucket(pre)].append(row)

    # アーティスト別の棚。気分・名前で当たった人の曲を、丸ごと引くための棚。
    abuckets = {i: [] for i in range(NBUCKET)}
    for row in all_rows:
        abuckets[row[0] % NBUCKET].append(row)
    (OUT_DIR / "a").mkdir(exist_ok=True)
    amax = 0
    for i, rows in abuckets.items():
        ap = OUT_DIR / "a" / f"{i}.json"
        ap.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
                      encoding="utf-8")
        amax = max(amax, ap.stat().st_size)
    print(f"アーティスト別の棚 {NBUCKET}枚 / いちばん大きい棚 {amax/1024:.0f}KB")

    sizes = []
    for i, rows in buckets.items():
        p = OUT_DIR / "t" / f"{i}.json"
        p.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
                     encoding="utf-8")
        sizes.append((p.stat().st_size, p.name, len(rows)))
    sizes.sort(reverse=True)

    print(f"アーティスト {len(A)}組 / 曲 {len(all_rows)}件 "
          f"（寄せ集め動画を {dropped_junk} 件はじいた）")
    print(f"head.json {hp.stat().st_size/1024:.0f}KB / "
          f"picks.json {pp.stat().st_size/1024:.0f}KB（代表曲 {len(picks)}件）")
    print(f"棚 {NBUCKET}枚 / いちばん大きい棚 {sizes[0][0]/1024:.0f}KB ({sizes[0][1]})")
    over = [s[1] for s in sizes if s[0] > MAX_BYTES]
    over += [f.name for f in (hp, pp) if f.stat().st_size > MAX_BYTES]
    if over:
        print("※ 1MBを超えたファイルがある:", over)
        return 2
    total = sum(s[0] for s in sizes) + hp.stat().st_size + pp.stat().st_size
    print(f"合計 {total/1024/1024:.1f}MB（ただし1回の検索で読むのは head + 棚1〜2枚だけ）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
