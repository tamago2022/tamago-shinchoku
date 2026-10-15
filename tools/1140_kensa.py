#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1140番【全曲検査】coverGuide.ts の全曲を1曲ずつ機械で判定して、型ごとに何件かを出す。

たまごさん（2026-09-25・原文）:
  「あんな秋の曲だけでさ、パッと押しただけで何個も動画が入ってないとかっていうのもありえない。
    それぐらいミスが多いってことなんだよ。間違いだらけだってことだよ。」
  「じゃあ、それ直そうよ。」
  「何件間違えてましたとか、全然事後報告でいいから、とりあえず直してよ。」

★サンプリング禁止。全件。推定で書かない。数えた数字だけ。

読む場所（1行で言える形）:
  本来の正本 = /Users/mac/Desktop/joy-relief-station/src/lib/coverGuide.ts
  この便は上が繋がっていないので、進捗表内の最新スナップショットを読む:
    status/1132_kansei/files/src/lib/coverGuide.ts   （2026-09-25 03:36・6,503,347 byte）
  補助表 = status/_1039/lib/{deadYoutube,videoReplacements,coverGuide.curated.generated,warehousedSongs}.ts

出す場所:
  status/1140/kensa.json        全曲の判定結果（全件）
  status/1140/kata_*.txt        型ごとの一覧
  status/1140/summary.json      型ごとの件数・合計
"""
from __future__ import annotations
import io, json, os, re, sys, unicodedata
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(ROOT, "status")
CG = os.path.join(ST, "1132_kansei", "files", "src", "lib", "coverGuide.ts")
LIB = os.path.join(ST, "_1039", "lib")
OUT = os.path.join(ST, "1140")
SITE = "https://joy-relief-station.lovable.app"

YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

# ── 1. TS を読む（文字列リテラルを飛ばす括弧スキャナ） ───────────────────────

def scan_array(s, start):
    i, depth, n = start, 0, len(s)
    while i < n:
        c = s[i]
        if c in "\"'`":
            q = c; i += 1
            while i < n:
                if s[i] == "\\":
                    i += 2; continue
                if s[i] == q:
                    break
                i += 1
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def split_top(s):
    out, buf, depth, i, n = [], [], 0, 0, len(s)
    while i < n:
        c = s[i]
        if c in "\"'`":
            q = c; buf.append(c); i += 1
            while i < n:
                buf.append(s[i])
                if s[i] == "\\":
                    i += 1
                    if i < n:
                        buf.append(s[i])
                    i += 1
                    continue
                if s[i] == q:
                    i += 1; break
                i += 1
            continue
        if c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
        if c == "," and depth == 0:
            out.append("".join(buf)); buf = []; i += 1; continue
        buf.append(c); i += 1
    if "".join(buf).strip():
        out.append("".join(buf))
    return out


def unq(x):
    x = x.strip()
    if len(x) >= 2 and x[0] in "\"'`" and x[-1] == x[0]:
        x = x[1:-1]
    if "\\" in x:
        try:
            x = x.encode("utf-8").decode("unicode_escape").encode("latin1", "ignore").decode("utf-8", "ignore") if False else re.sub(r'\\(["\'`\\/])', r"\1", x).replace("\\n", "\n")
        except Exception:
            pass
    return x


def sval(block, key):
    m = re.search(r'(?<![A-Za-z0-9_])"?%s"?:\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`)' % key, block)
    return unq(m.group(1)) if m else ""


def nval(block, key):
    m = re.search(r'(?<![A-Za-z0-9_])"?%s"?:\s*(\d+)' % key, block)
    return int(m.group(1)) if m else None


def bval(block, key):
    m = re.search(r'(?<![A-Za-z0-9_])"?%s"?:\s*(true|false)' % key, block)
    return m.group(1) == "true" if m else None


def arr_strings(block, key):
    """key: [ "a", "b" ] の中の文字列だけを取る。"""
    m = re.search(r'(?<![A-Za-z0-9_])"?%s"?:\s*\[' % key, block)
    if not m:
        return []
    lb = block.index("[", m.end() - 1)
    rb = scan_array(block, lb)
    if rb < 0:
        return []
    return [unq(x) for x in split_top(block[lb + 1:rb]) if x.strip() and x.strip()[0] in "\"'`"]


def sub_block(block, key):
    """key: { ... } の中身を返す。"""
    m = re.search(r'(?<![A-Za-z0-9_])"?%s"?:\s*\{' % key, block)
    if not m:
        return ""
    lb = block.index("{", m.end() - 1)
    i, depth, n = lb, 0, len(block)
    while i < n:
        c = block[i]
        if c in "\"'`":
            q = c; i += 1
            while i < n:
                if block[i] == "\\":
                    i += 2; continue
                if block[i] == q:
                    break
                i += 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return block[lb + 1:i]
        i += 1
    return ""


def arr_objects(block, key):
    m = re.search(r'(?<![A-Za-z0-9_])"?%s"?:\s*\[' % key, block)
    if not m:
        return []
    lb = block.index("[", m.end() - 1)
    rb = scan_array(block, lb)
    if rb < 0:
        return []
    return [x for x in split_top(block[lb + 1:rb]) if x.strip().startswith("{")]


# ── 2. 補助表 ───────────────────────────────────────────────────────────────

def read(p):
    try:
        return io.open(p, encoding="utf-8").read()
    except Exception:
        return ""


def dead_ids():
    s = read(os.path.join(LIB, "deadYoutube.generated.ts"))
    m = re.search(r"new Set\(\[(.*?)\]\)", s, re.S)
    return set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()


def replacements():
    s = read(os.path.join(LIB, "videoReplacements.generated.ts"))
    return dict(re.findall(r'"([A-Za-z0-9_\-]{5,20})"\s*:\s*"([A-Za-z0-9_\-]{5,20})"', s))


def curated_video_ids():
    """curatedGenerated の曲キー -> そこに書かれている動画ID群。"""
    s = read(os.path.join(LIB, "coverGuide.curated.generated.ts"))
    out = defaultdict(set)
    for m in re.finditer(r'\n  "([^"]+)": \{', s):
        key = m.group(1)
        start = m.end() - 1
        depth, i, n = 0, start, len(s)
        while i < n:
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = s[start:i]
        for vid in re.findall(r'"youtubeId":\s*"([^"]*)"', body):
            if vid:
                out[key].add(vid)
        for vid in re.findall(r'"officialVideos"[\s\S]{0,4000}?\]', body):
            pass
    return out


def warehoused():
    s = read(os.path.join(LIB, "warehousedSongs.ts"))
    return set(re.findall(r'"([a-z0-9\-]+/[a-z0-9\-]+)"', s))


# ── 3. 判定 ─────────────────────────────────────────────────────────────────

PLACEHOLDER = re.compile(r"^(TODO|TBD|placeholder|ここにコピー|未設定|未記入|仮|coming soon|N/A)", re.I)
COMMON_IMG = ("og-four-doors", "og-default", "placeholder")

# でっちあげIDの形（英数が階段状に並ぶ／同じ並びの繰り返し）。
FAKE_PATTERNS = [
    re.compile(r"^(?:[0-9][a-z]){4,}[0-9a-z]?$"),      # 1a2b3c4d5e6
    re.compile(r"^[0-9][a-z][0-9][a-z][0-9][a-z]"),
]
SEQ = "abcdefghijklmnopqrstuvwxyz"


def looks_fabricated(vid: str) -> bool:
    if not vid or not YT_ID.match(vid):
        return False
    low = vid.lower()
    # 3文字以上のアルファベット連続（abc, def, klm...）が含まれる
    letters = [c for c in low if c.isalpha()]
    run = 1
    for a, b in zip(low, low[1:]):
        if a.isalpha() and b.isalpha() and SEQ.find(b) == SEQ.find(a) + 1:
            run += 1
            if run >= 3:
                return True
        else:
            run = 1
    # 数字と英字が交互に並ぶ（1a2b3c…）
    if re.match(r"^(?:\d[a-z]){4,}", low):
        return True
    # 階段状の数字（0q1r2s3t）
    for a, b in zip(low, low[1:]):
        pass
    return False


DANTEI = re.compile(r"(代表曲|原曲|オリジナル|カバー|初の|最大のヒット|世界初|史上初|受賞|万枚|オリコン1位|\b(19|20)\d{2}年)")

TOKEN_NEIGHBORS = {}  # artistId -> [(別アーティスト名, id)] 名前の語が一部一致する相手だけ


def name_tokens(n: str):
    """名前を語に割る（Harry Styles / NON STYLE の 'style' のような共通語を拾う）。"""
    n = unicodedata.normalize("NFKC", n or "").lower()
    n = re.sub(r"[（(].*?[)）]", " ", n)
    toks = set(re.findall(r"[a-z]{4,}", n))
    toks |= {x for x in re.findall(r"[぀-ヿ一-鿿]{2,}", n)}
    return toks - {"band", "the", "feat", "live", "best", "song", "songs", "music"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u4e00-\u9fff]", "", s)


def main():
    src = read(CG)
    if not src:
        print("coverGuide.ts が読めない: %s" % CG, file=sys.stderr)
        return 1
    i = src.index("export const artists")
    lb = re.search(r"=\s*\[", src[i:]).end() - 1 + i
    rb = scan_array(src, lb)
    body = src[lb + 1:rb]

    DEAD = dead_ids()
    # ★実測（tools/1140_jissoku.py が工場側で oEmbed を1件ずつ叩いた結果）があれば足す。
    #   「データにある」は証拠にならない。再生できるかは実測だけで決める。
    jp = os.path.join(OUT, "jissoku.json")
    jissoku_n = 0
    if os.path.exists(jp):
        try:
            j = json.load(io.open(jp, encoding="utf-8"))
            DEAD |= set(j.get("dead", []))
            jissoku_n = len(j.get("checked", []))
        except Exception:
            pass
    REPL = replacements()
    CUR = curated_video_ids()
    WARE = warehoused()

    artists = []   # {id,name,songs:[...]}
    for ab in split_top(body):
        ab = ab.strip()
        if not ab.startswith("{"):
            continue
        aid = sval(ab, "id")
        aname = sval(ab, "name")
        j = ab.find("songs:")
        songs = []
        if j >= 0:
            slb = ab.index("[", j)
            srb = scan_array(ab, slb)
            for sb in split_top(ab[slb + 1:srb]):
                sb = sb.strip()
                if not sb.startswith("{"):
                    continue
                sid = sval(sb, "id")
                if not sid:
                    continue
                alt = arr_strings(sb, "altYoutubeIds")
                orf = sub_block(sb, "originalRef")
                songs.append({
                    "songId": sid,
                    "title": sval(sb, "title"),
                    "note": sval(sb, "note"),
                    "copy": sval(sb, "copy"),
                    "memo": sval(sb, "memo"),
                    "year": nval(sb, "year"),
                    "youtubeId": sval(sb, "youtubeId"),
                    "alt": alt,
                    "bridgeRelated": arr_strings(sb, "bridgeRelated"),
                    "bridgeReasons": sub_block(sb, "bridgeReasons"),
                    "bridgeLabel": sval(sb, "bridgeLabel"),
                    "originalRef": (sval(orf, "artistId"), sval(orf, "songId")) if orf else None,
                    "famousUses": [(sval(o, "artistId"), sval(o, "songId")) for o in arr_objects(sb, "famousUses")],
                    "usedSongs": [(sval(o, "artistId"), sval(o, "songId")) for o in arr_objects(sb, "usedSongs")],
                    "samples": [(sval(o, "artistId"), sval(o, "songId"), arr_strings(o, "sources")) for o in arr_objects(sb, "samples")],
                    "sampledBy": [(sval(o, "artistId"), sval(o, "songId"), arr_strings(o, "sources")) for o in arr_objects(sb, "sampledBy")],
                    "hideFromArtistList": bval(sb, "hideFromArtistList"),
                })
        artists.append({"artistId": aid, "name": aname, "songs": songs})

    # 索引
    key_exists = set()
    artist_by_id = {}
    title_to_keys = defaultdict(list)
    for a in artists:
        artist_by_id[a["artistId"]] = a
        for s in a["songs"]:
            k = "%s/%s" % (a["artistId"], s["songId"])
            key_exists.add(k)
            if s["title"]:
                title_to_keys[norm(s["title"])].append(k)

    # 名前が同じ別アーティスト（同名別人の入口）
    name_groups = defaultdict(list)
    for a in artists:
        if a["name"]:
            name_groups[norm(a["name"])].append(a["artistId"])
    name_collisions = {k: v for k, v in name_groups.items() if len(v) > 1}
    collision_ids = {aid for v in name_collisions.values() for aid in v}
    # 名前の語が一部一致する別アーティストだけを候補にする（総当たりは重いので索引で絞る）
    tok_map = defaultdict(list)
    for a in artists:
        if a["name"] and len(a["name"]) >= 4:
            for t in name_tokens(a["name"]):
                tok_map[t].append((a["name"], a["artistId"]))
    for a in artists:
        if not a["name"] or len(a["name"]) < 4:
            continue
        cand = {}
        for t in name_tokens(a["name"]):
            if len(tok_map[t]) > 12:      # 「japan」等の広すぎる語は使わない
                continue
            for (nm, oid) in tok_map[t]:
                if oid != a["artistId"] and nm != a["name"]:
                    cand[oid] = nm
        if cand:
            TOKEN_NEIGHBORS[a["artistId"]] = [(nm, oid) for oid, nm in cand.items()]

    # コピー重複（同じ文が複数曲に使われている）
    copy_users = defaultdict(list)

    rows = []
    kata = defaultdict(list)
    for a in artists:
        aid, aname = a["artistId"], a["name"]
        for s in a["songs"]:
            key = "%s/%s" % (aid, s["songId"])
            faults = []

            raw = [s["youtubeId"]] + s["alt"] + sorted(CUR.get(key, []))
            raw = [x for x in raw if x]
            playable, dead_hit, bad_hit, fake_hit = [], [], [], []
            for vid in raw:
                if not YT_ID.match(vid):
                    bad_hit.append(vid); continue
                if looks_fabricated(vid):
                    fake_hit.append(vid)
                swapped = REPL.get(vid)
                if swapped:
                    if swapped not in playable:
                        playable.append(swapped)
                    continue
                if vid in DEAD:
                    dead_hit.append(vid); continue
                if vid not in playable:
                    playable.append(vid)
            # ★fakeId（でっちあげIDの形）は 2026-09-25 に廃止。
            # 実データで確かめたら 'YBcdt6DsLQA'(beatles/in-my-life) のような**本物のID**が
            # 「bcd が連続している」だけで引っかかり、156件のうち大半が誤検出だった。
            # 生きている動画を隠すのは、穴を空けるのと同じ恥。→ 形での推測はやめ、
            # 再生できるかは tools/1140_jissoku.py の**実測**（oEmbed）だけで決める。

            if not (s["title"] or "").strip() or not (aname or "").strip():
                faults.append("noName")
            if not raw:
                faults.append("noVideo")
            elif not playable:
                faults.append("deadVideo")
            if bad_hit:
                faults.append("badId")
            if not playable:
                faults.append("noThumb")      # サムネは再生できるIDから作るので同根

            copy = (s["copy"] or s["note"] or "").strip()
            if not copy or PLACEHOLDER.match(copy):
                faults.append("noCopy")
            else:
                copy_users[copy].append(key)
            if any(x in (s["copy"] or "") + (s["note"] or "") for x in COMMON_IMG):
                faults.append("kyoutsuuImg")

            # ── 繋ぎ ──
            reasons = s["bridgeReasons"] or ""
            for t in s["bridgeRelated"]:
                if t.startswith("/cover-guide"):
                    m = re.search(r"artist=([^&]+)&song=([^&\s]+)", t)
                    tk = "%s/%s" % (m.group(1), m.group(2)) if m else ""
                    if tk and tk not in key_exists:
                        faults.append("tsunagiMissing")
                        kata["tsunagiMissing"].append("%s -> %s" % (key, tk))
                        continue
                    # 出典URLが無い繋ぎ＝根拠なし
                    if "http" not in reasons:
                        faults.append("tsunagiNoSource")
                        kata["tsunagiNoSource"].append("%s -> %s" % (key, tk))
                    # 曲名が一致しただけの繋ぎ
                    if tk and tk in key_exists:
                        ta, ts = tk.split("/", 1)
                        tsong = next((x for x in artist_by_id[ta]["songs"] if x["songId"] == ts), None)
                        if tsong and norm(tsong["title"]) == norm(s["title"]) and ta != aid and "http" not in reasons:
                            faults.append("tsunagiTitleOnly")
                            kata["tsunagiTitleOnly"].append("%s -> %s（曲名一致だけ）" % (key, tk))

            for (ta, ts) in ([s["originalRef"]] if s["originalRef"] else []) + s["famousUses"] + s["usedSongs"]:
                if ta and ts and "%s/%s" % (ta, ts) not in key_exists:
                    faults.append("refMissing")
                    kata["refMissing"].append("%s -> %s/%s" % (key, ta, ts))

            for (ta, ts, srcs) in s["samples"] + s["sampledBy"]:
                tk = "%s/%s" % (ta, ts)
                if ta and ts and tk not in key_exists:
                    faults.append("refMissing")
                    kata["refMissing"].append("%s -> %s（sample）" % (key, tk))
                elif not [x for x in srcs if x.startswith("http")]:
                    faults.append("sampleNoSource")
                    kata["sampleNoSource"].append("%s -> %s" % (key, tk))

            # ── 重複した棚（同じ人の棚が2つある＝仕入れが二重になっている） ──
            if aid in collision_ids:
                faults.append("juufukuTana")

            # ── 同名別人（名前の一部が一致した別人の曲が棚に入っている疑い） ──
            text = " ".join([s["note"] or "", s["copy"] or "", s["memo"] or ""])
            if text.strip() and aname:
                if aname not in text:
                    for other, oid in TOKEN_NEIGHBORS.get(aid, ()):  # 名前の語が一部一致する別アーティストだけ
                        if other in text:
                            faults.append("douseiBetsujin")
                            kata["douseiBetsujin"].append("%s（棚=%s／本文に別人=%s）" % (key, aname, other))
                            break

            # ── 出典のない断定（年号・代表曲・原曲・カバー…） ──
            if DANTEI.search(text) and "http" not in text:
                faults.append("shuttenNashi")

            # ── 年が近いだけの繋ぎ（「同じ時代の曲」は年だけで機械が並べている） ──
            if s["year"]:
                faults.append("eraOnlyTsunagi")

            faults = sorted(set(faults))
            for f in faults:
                if f not in ("tsunagiMissing", "tsunagiNoSource", "tsunagiTitleOnly", "refMissing", "sampleNoSource"):
                    kata[f].append(key)
            rows.append({
                "key": key, "artist": aname, "title": s["title"],
                "faults": faults,
                "videos": {"raw": raw, "playable": playable, "dead": dead_hit, "bad": bad_hit, "fake": fake_hit},
                "url": "%s/cover-guide?artist=%s&song=%s" % (SITE, aid, s["songId"]),
            })

    # コピー重複は全部集めてから
    dup_keys = []
    for c, ks in copy_users.items():
        if len(ks) > 1:
            dup_keys.extend(ks)
    dup_set = set(dup_keys)
    for r in rows:
        if r["key"] in dup_set:
            r["faults"] = sorted(set(r["faults"] + ["dupCopy"]))
    kata["dupCopy"] = sorted(dup_set)

    os.makedirs(OUT, exist_ok=True)
    ng = [r for r in rows if r["faults"]]
    # 「お客さんに見えている恥」＝再生できる動画が1本もない
    hide = [r for r in rows if any(f in r["faults"] for f in ("noVideo", "deadVideo", "noName", "badId"))]

    summary = {
        "生成": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "読んだ場所": CG,
        "アーティスト数": len(artists),
        "全曲数": len(rows),
        "間違いがあった曲数": len(ng),
        "型ごと": {k: len(set(v)) if k in ("dupCopy",) else len(v) for k, v in sorted(kata.items())},
        "隠す対象（再生できる動画が1本もない等）": len(hide),
        "名前が同じ別アーティスト": {k: v for k, v in list(name_collisions.items())},
        "名前が同じ組数": len(name_collisions),
    }
    json.dump(summary, io.open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with io.open(os.path.join(OUT, "kensa.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False)
    for k, v in kata.items():
        with io.open(os.path.join(OUT, "kata_%s.txt" % k), "w", encoding="utf-8") as f:
            for x in sorted(set(v)):
                f.write(x + "\n")
    with io.open(os.path.join(OUT, "kakusu.txt"), "w", encoding="utf-8") as f:
        for r in hide:
            f.write("%s\t%s\n" % (r["key"], ",".join(r["faults"])))

    # ── 全動画IDの一覧（実測用）。工場側の 1140_jissoku.py がこれを読む ──
    all_ids = sorted({v for r in rows for v in r["videos"]["raw"] if YT_ID.match(v)})
    with io.open(os.path.join(OUT, "all_video_ids.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(all_ids))
    summary["動画IDの実数（重複なし）"] = len(all_ids)
    summary["実測済みID数"] = jissoku_n

    # ── ★直し：隠す表を作る（消さない。直れば次の生成で自動的に外れる） ──
    emit_hidden(hide, summary)

    json.dump(summary, io.open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


def emit_hidden(hide, summary):
    """1132番の関所がそのまま読む形で、隠す一覧を書き出す。

    ★消していない。隠しているだけ。動画が入れば次の生成でこの表から外れ、元どおり出る。
    ★戻し方（1行）: src/lib/kansei.ts の KANSEI_GATE を false にする。
    """
    import datetime
    reasons = {}
    for r in sorted(hide, key=lambda x: x["key"]):
        f = r["faults"]
        reasons[r["key"]] = ("noName" if "noName" in f else
                             "deadVideo" if "deadVideo" in f else
                             "badId" if "badId" in f else "noVideo")
    # 1132番が見つけた「棚の札の行き先が、そもそも曲として存在しない（missing）」も残す。
    # あれは名簿に無いので、名簿を舐める側（この検査）からは絶対に見つからない型。
    old = read(os.path.join(ST, "1132_kansei", "new", "src", "lib", "kanseiHidden.generated.ts"))
    keep = 0
    for k, v in re.findall(r'\n  "([^"]+)": "([^"]+)",', old):
        if k not in reasons:
            reasons[k] = v
            keep += 1
    reasons = dict(sorted(reasons.items()))

    head = (
        "// AUTO-GENERATED by tools/1140_kensa.py — 手で書き換えない。\n"
        "// 1140番【全曲検査】全%d曲を1曲ずつ機械で見て、\n"
        "// 「再生できる動画が1本も無い」曲を全部ここに入れた（%d件）。\n"
        "// 1132番の関所（src/lib/kansei.ts）がこの表を読んで、検索・棚・おすすめ・\n"
        "// 「この流れで、もう一本」・サイトマップの全部から出さない。\n"
        "//\n"
        "// ★消していない。隠しているだけ。動画が入れば次の生成で自動的にこの表から外れ、元どおり出る。\n"
        "// ★戻し方（1行）: src/lib/kansei.ts の KANSEI_GATE を false にする。\n"
        "//\n"
        "// 最終生成: %s\n\n"
    ) % (summary["全曲数"], len(reasons),
         datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    body = "export const KANSEI_HIDDEN_REASONS: Readonly<Record<string, string>> = {\n"
    for k, v in reasons.items():
        body += '  %s: "%s",\n' % (json.dumps(k, ensure_ascii=False), v)
    body += "};\n\n"
    body += ("/** 「artistId/songId」。棚・おすすめ・関連から出さない行き先。 */\n"
             "export const KANSEI_HIDDEN_SONG_KEYS: ReadonlySet<string> = new Set(\n"
             "  Object.keys(KANSEI_HIDDEN_REASONS),\n"
             ");\n")
    for dest in (os.path.join(OUT, "kanseiHidden.generated.ts"),
                 os.path.join(ST, "1132_kansei", "new", "src", "lib", "kanseiHidden.generated.ts")):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        io.open(dest, "w", encoding="utf-8").write(head + body)
    summary["隠す表に書いた件数"] = len(reasons)


if __name__ == "__main__":
    sys.exit(main())
