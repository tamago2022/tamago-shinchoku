# -*- coding: utf-8 -*-
"""coverGuide.ts から アーティスト名／曲名 の読み（カタカナ）を機械で起こす。
   お金0・外部API0。読めないものは推測で埋めず「要確認」に落とす。
   使い方: python3 build_yomi.py <coverGuide.ts ...> --out <dir>
"""
import re, sys, json, os, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from romaji import romaji_to_kana

KATA = re.compile(r'^[゠-ヿーー・\s]+$')
HIRA = re.compile(r'^[぀-ゟー・\s]+$')
LATIN = re.compile(r'^[\x00-\x7F]+$')
HAS_JA = re.compile(r'[぀-ヿ一-鿿]')
ROMAJI_ID = re.compile(r'^[a-z][a-z\- ]*$')

def hira2kata(s):
    return "".join(chr(ord(c)+0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)

# ── 日本の英字名アーティスト：機械では絶対に読めない。ここは人の知識で持つ ──
# 出典＝各アーティストの公式表記／日本語版Wikipedia の読み。
KNOWN = {
 "King Gnu":"キングヌー","YOASOBI":"ヨアソビ","RADWIMPS":"ラッドウィンプス",
 "BUMP OF CHICKEN":"バンプ・オブ・チキン","ONE OK ROCK":"ワンオクロック",
 "Official髭男dism":"オフィシャルヒゲダンディズム","SEKAI NO OWARI":"セカイノオワリ",
 "Mrs. GREEN APPLE":"ミセスグリーンアップル","back number":"バックナンバー",
 "SPITZ":"スピッツ","GLAY":"グレイ","L'Arc～en～Ciel":"ラルク・アン・シエル",
 "UVERworld":"ウーバーワールド","SUPER BEAVER":"スーパービーバー",
 "WANIMA":"ワニマ","Vaundy":"バウンディ","ado":"アド","Ado":"アド",
 "yama":"ヤマ","Eve":"イヴ","milet":"ミレイ","Aimer":"エメ",
 "LiSA":"リサ","AKB48":"エーケービーフォーティーエイト",
 "Perfume":"パフューム","BABYMETAL":"ベビーメタル","X JAPAN":"エックスジャパン",
 "B'z":"ビーズ","TM NETWORK":"ティーエムネットワーク","CHAGE and ASKA":"チャゲアンドアスカ",
 "DREAMS COME TRUE":"ドリームズカムトゥルー","ZARD":"ザード",
 "THE BLUE HEARTS":"ザ・ブルーハーツ","THE YELLOW MONKEY":"ザ・イエローモンキー",
 "ゆず":"ユズ","ずっと真夜中でいいのに。":"ズットマヨナカデイイノニ",
 "ヨルシカ":"ヨルシカ","米津玄師":"ヨネヅケンシ","星野源":"ホシノゲン",
 "あいみょん":"アイミョン","藤井風":"フジイカゼ","宇多田ヒカル":"ウタダヒカル",
 "椎名林檎":"シイナリンゴ","東京事変":"トウキョウジヘン","サカナクション":"サカナクション",
 "くるり":"クルリ","フジファブリック":"フジファブリック","凛として時雨":"リントシテシグレ",
 "Superfly":"スーパーフライ","SHISHAMO":"シシャモ","SEKAI":"セカイ",
 "androp":"アンドロップ","indigo la End":"インディゴ・ラ・エンド",
 "amazarashi":"アマザラシ","tacica":"タシカ","the pillows":"ザ・ピロウズ",
 "ELLEGARDEN":"エルレガーデン","ASIAN KUNG-FU GENERATION":"アジアン・カンフー・ジェネレーション",
 "Nulbarich":"ヌルバリッチ","cero":"セロ","never young beach":"ネバーヤングビーチ",
 "SIRUP":"シラップ","iri":"イリ","KIRINJI":"キリンジ","Suchmos":"サチモス",
 "D.A.N.":"ディーエーエヌ","group_inou":"グループイノウ","PUNPEE":"パンピー",
 "Creepy Nuts":"クリーピーナッツ","chelmico":"チェルミコ","DAOKO":"ダヲコ",
 "tofubeats":"トーフビーツ","Base Ball Bear":"ベースボールベアー",
 "Awesome City Club":"オーサム・シティ・クラブ","Chara":"チャラ",
 "UA":"ウーア","MISIA":"ミーシャ","Sheena Ringo":"シイナリンゴ",
 "Cocco":"コッコ","Original Love":"オリジナル・ラブ","Fishmans":"フィッシュマンズ",
 "Yellow Magic Orchestra":"イエロー・マジック・オーケストラ","YMO":"ワイエムオー",
 "Hi-STANDARD":"ハイスタンダード","Dragon Ash":"ドラゴンアッシュ",
 "RIP SLYME":"リップスライム","m-flo":"エムフロウ","Ken Hirai":"ヒライケン",
 "flumpool":"フランプール","Sambomaster":"サンボマスター","サンボマスター":"サンボマスター",
 "怒髪天":"ドハツテン","打首獄門同好会":"ウチクビゴクモンドウコウカイ",
 "四星球":"スーシンチュウ","フレデリック":"フレデリック","ペトロールズ":"ペトロールズ",
}

# ── 形態素解析（任意）。入っていれば漢字の読みを起こす。無ければ静かに諦める ──
_TOK = None
def sudachi(text):
    global _TOK
    if _TOK is False: return None
    if _TOK is None:
        try:
            from sudachipy import Dictionary, SplitMode
            _TOK = (Dictionary().create(), SplitMode.C)
        except Exception:
            _TOK = False; return None
    tk, mode = _TOK
    try:
        out = "".join(m.reading_form() for m in tk.tokenize(text, mode))
    except Exception:
        return None
    return out if out and KATA.match(out) else None

def norm(s):
    return unicodedata.normalize("NFKC", s).strip()

def parse(path):
    s = open(path, encoding="utf-8").read()
    arts = []
    art_re = re.compile(r'\{\s*id:\s*"((?:[^"\\]|\\.)*)",\s*name:\s*"((?:[^"\\]|\\.)*)"')
    song_re = re.compile(r'\{\s*id:\s*"((?:[^"\\]|\\.)*)",\s*title:\s*"((?:[^"\\]|\\.)*)"')
    marks = [(m.start(), m.end(), m.group(1), m.group(2)) for m in art_re.finditer(s)]
    for i, (st, en, aid, name) in enumerate(marks):
        nxt = marks[i+1][0] if i+1 < len(marks) else len(s)
        blk = s[en:nxt]
        if 'songs:' not in blk[:6000]:
            continue
        am = re.search(r'aliases:\s*\[(.*?)\]', blk[:6000], re.S)
        al = re.findall(r'"((?:[^"\\]|\\.)*)"', am.group(1)) if am else []
        ab = re.search(r'about:\s*"((?:[^"\\]|\\.)*)"', blk[:6000])
        songs = [{"id": g1, "title": g2} for g1, g2 in
                 ((m.group(1), m.group(2)) for m in song_re.finditer(blk))]
        arts.append({"id": aid, "name": name, "aliases": al,
                     "about": (ab.group(1)[:120] if ab else ""), "songs": songs})
    return arts

# 外部AI2社が一致した答え／人が直したもの。ここが最優先。
_MANUAL = None
def manual():
    global _MANUAL
    if _MANUAL is None:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manual.json")
        try:
            _MANUAL = json.load(open(p, encoding="utf-8"))
        except Exception:
            _MANUAL = {}
    return _MANUAL

def derive(name, aid, aliases):
    """(読み, 根拠, 自信) を返す。読めなければ (None, 理由, 'none')"""
    n = norm(name)
    m = manual()
    if name in m: return m[name], "外部AI2社が一致（manual.json）", "high"
    if n in m: return m[n], "外部AI2社が一致（manual.json）", "high"
    if n in KNOWN: return KNOWN[n], "既知辞書（公式表記）", "high"
    if name in KNOWN: return KNOWN[name], "既知辞書（公式表記）", "high"
    for a in aliases:
        if KATA.match(a) and len(a) >= 2:
            return a.strip(), "既存データ aliases のカタカナ", "high"
    if KATA.match(n): return n, "名前がすでにカタカナ", "high"
    if HIRA.match(n): return hira2kata(n), "名前がひらがな", "high"
    for a in aliases:
        if HIRA.match(a) and len(a) >= 2:
            return hira2kata(a.strip()), "既存データ aliases のひらがな", "high"
    if HAS_JA.search(name):
        rk = romaji_to_kana(aid)
        if not rk:
            for a in aliases:
                if ROMAJI_ID.match(a):
                    rk = romaji_to_kana(a)
                    if rk: break
        sk = sudachi(re.sub(r'[\s・]', '', name))
        if rk and sk:
            if re.sub(r'[・ー\s]', '', rk) == re.sub(r'[・ー\s]', '', sk):
                return rk, "idのローマ字と形態素解析が一致", "high"
            return rk, f"idのローマ字={rk}／形態素解析={sk}（不一致）", "conflict"
        if rk: return rk, f"id のローマ字（{aid}）", "mid"
        if sk: return sk, "形態素解析（読みの裏取り無し）", "mid"
    return None, "読みの元データ無し", "none"

DANGER_SYM = re.compile(r'[0-90-9&+*#@/\\_~^|]')
JP_ABOUT = re.compile(r'日本の|日本を代表|日本人|邦楽|J-POP|Jポップ|日本のロック|日本のポップ|日本のバンド')

def load_abouts(paths):
    ab = {}
    for p in paths:
        if not os.path.exists(p): continue
        s = open(p, encoding="utf-8").read()
        if "generatedAbouts" not in s: continue
        body = s.split("generatedAbouts")[1].split("export const")[0]
        for k, v in re.findall(r'"((?:[^"\\]|\\.)*)":\s*"((?:[^"\\]|\\.)*)"', body):
            ab.setdefault(k, v)
    return ab

def classify(x, y, conf):
    """緑=そのまま使える / 黄=推定・要確認 / 赤=危ない / 外=外国名で案内人が読める"""
    name, al, about = x["name"], x["aliases"], x["about"]
    latin = LATIN.match(name) is not None
    reasons = []
    kataset = {a.strip() for a in al if KATA.match(a) and len(a) >= 2}
    if y: kataset.add(y)
    # 読みが2つ以上に割れている（先頭2文字が違うものだけを「割れ」と見る）
    if len({k[:2] for k in kataset}) >= 2:
        reasons.append("読みが割れている：" + " / ".join(sorted(kataset)))
    if conf == "none":
        if latin and JP_ABOUT.search(about):
            reasons.append("英字名だが日本のアーティスト（機械では読めない）")
            return "red", reasons
        if latin and DANGER_SYM.search(name) and JP_ABOUT.search(about):
            reasons.append("数字・記号入りの英字名")
            return "red", reasons
        if latin:
            return "foreign", reasons          # 外国名。案内人がそのまま読める
        reasons.append("読みの元データ無し")
        return "red", reasons
    if conf == "conflict":
        reasons.append("読みの候補が2つに割れている：" + x.get("_why", ""))
        return "red", reasons
    if conf == "mid":
        reasons.append("推定（当て字なら外れる）")
        return "yellow", reasons
    if reasons:
        return "yellow", reasons
    return "green", reasons

def main():
    outdir = "."; srcs = []; profiles = []
    it = iter(sys.argv[1:])
    for a in it:
        if a == "--out": outdir = next(it)
        elif a == "--profiles": profiles.append(next(it))
        else: srcs.append(a)
    merged = {}
    for p in srcs:
        for x in parse(p):
            if x["id"] in merged:
                d = {s["id"]: s for s in merged[x["id"]]["songs"]}
                d.update({s["id"]: s for s in x["songs"]})
                merged[x["id"]]["songs"] = list(d.values())
            else:
                merged[x["id"]] = x
    arts = list(merged.values())
    ab = load_abouts(profiles)
    for x in arts:
        if not x["about"]: x["about"] = ab.get(x["id"], "")

    dic, detail, review, buckets = {}, [], [], {"green":0,"yellow":0,"red":0,"foreign":0}
    for x in arts:
        y, why, conf = derive(x["name"], x["id"], x["aliases"])
        x["_why"] = why
        band, reasons = classify(x, y, conf)
        buckets[band] += 1
        e = {"type":"artist","id":x["id"],"name":x["name"],"yomi":y,
             "src":why,"conf":conf,"band":band}
        detail.append(e)
        if y and band in ("green","yellow"): dic[x["name"]] = y
        if band in ("yellow","red"): review.append({**e,"reasons":reasons})

    sdic, sreview, sn = {}, [], 0
    seen = set()
    for x in arts:
        for s in x["songs"]:
            k = (x["id"], s["id"])
            if k in seen: continue
            seen.add(k)
            t = s["title"]
            if not HAS_JA.search(t): continue
            sn += 1
            n = norm(t)
            if KATA.match(n): y, why, conf = n, "曲名がカタカナ", "high"
            elif HIRA.match(n): y, why, conf = hira2kata(n), "曲名がひらがな", "high"
            else:
                rk = romaji_to_kana(s["id"])
                sk = sudachi(re.sub(r'[\s・]', '', n)) if len(n) <= 40 else None
                if rk and sk and re.sub(r'[・ー\s]', '', rk) == re.sub(r'[・ー\s]', '', sk):
                    y, why, conf = rk, "曲idのローマ字と形態素解析が一致", "high"
                elif rk and sk:
                    y, why, conf = rk, f"曲idのローマ字={rk}／形態素解析={sk}（不一致）", "conflict"
                elif rk:
                    y, why, conf = rk, "曲idのローマ字（%s）" % s["id"], "mid"
                elif sk:
                    y, why, conf = sk, "形態素解析（裏取り無し）", "mid"
                else:
                    y, why, conf = None, "読みの元データ無し", "none"
            if y and conf != "conflict":
                sdic.setdefault(x["id"], {})[t] = y
            if conf in ("mid", "conflict"):
                sreview.append({"type":"song","artist":x["id"],"id":s["id"],
                                "name":t,"yomi":y,"src":why,"conf":conf,
                                "band":"red" if conf == "conflict" else "yellow",
                                "reasons":[why if conf == "conflict" else "推定（裏取りが1本だけ）"]})

    os.makedirs(outdir, exist_ok=True)
    def w(n, o): json.dump(o, open(os.path.join(outdir, n), "w", encoding="utf-8"),
                           ensure_ascii=False, sort_keys=True)
    w("yomi-artists.json", dic)
    w("yomi-artists.detail.json", detail)
    w("yomi-songs.json", sdic)
    w("yomi-review.json", review + sreview)
    st = {"artists_total": len(arts), "artists_dict": len(dic),
          "green": buckets["green"], "yellow": buckets["yellow"],
          "red": buckets["red"], "foreign_auto": buckets["foreign"],
          "artists_review": len(review),
          "songs_ja": sn, "songs_dict": sum(len(v) for v in sdic.values()),
          "songs_review": len(sreview)}
    w("yomi-stats.json", st)
    print(json.dumps(st, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
