#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""966番：アーティストの「どこの人か」を、棚のデータから取り出す。

■ なぜ要るか（2026-09-20 たまごさん実測）
  「アジアの曲ありますかって言ったら、4つのうち1個だけキングヌー。
    あとはデビッド・ボウイ、レイ・チャールズ。アジアって言ったらアジアのものを出す。」

  原因を憶測せずに棚のデータを見た結果：
  head.json のアーティストには **地域の情報が1つも入っていない。**
  （i=id / n=名前 / al=別名 / e=年代 / ab=概要 / g=ジャンル / c=曲数 だけ）
  だから959番は「アジア」を mood（気分の言葉）として概要の文字列に当てるしかなく、
  「ソウル」がレイ・チャールズに、「ロック」がボウイに当たっていた。**地域の絞り込みが
  そもそも実装されていなかった。**

■ 出どころ（憲法11・§11-3：裏が取れないものは空欄。推測で埋めない）
  1. coverGuide.ts の about（手書き 482件）
  2. coverGuide.profiles.generated.ts の generatedAbouts（1506件・Wikipedia由来）
  3. 名前の文字づかい。**ひらがなは日本語にしか無い**ので、名前にひらがなが入って
     いれば日本。カタカナだけ／漢字だけの名前は、この名簿では日本の芸名が大半だが
     中国語・韓国語とも見分けが付かないので、about で国が取れないものは
     「漢字だけ＝東アジア」までしか言わない（下の HINT_ONLY）。

  上のどれでも取れなかったら **空のまま**にする。埋めない。

出力: share/check/assets/953-songs/region.json
  {"r": {"<artistId>": "jp", ...}, "src": {"<artistId>": "<根拠の文字列>"}}
"""
import importlib.util
import io
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
COVER = REPO / "status" / "_952" / "recon" / "HIT_src_lib_coverGuide.ts"
PROF = REPO / "status" / "966_seihon" / "coverGuide.profiles.generated.ts"
OUT = REPO / "share" / "check" / "assets" / "953-songs" / "region.json"

# 国コード → どの地域のくくりに入るか（案内人が言う言葉はブラウザ側に持つ）
GROUP = {
    "jp": ["asia", "eastasia"], "kr": ["asia", "eastasia"], "cn": ["asia", "eastasia"],
    "tw": ["asia", "eastasia"], "hk": ["asia", "eastasia"], "mn": ["asia", "eastasia"],
    "th": ["asia", "seasia"], "id": ["asia", "seasia"], "ph": ["asia", "seasia"],
    "vn": ["asia", "seasia"], "sg": ["asia", "seasia"], "my": ["asia", "seasia"],
    "in": ["asia", "southasia"], "pk": ["asia", "southasia"], "bd": ["asia", "southasia"],
    "np": ["asia", "southasia"], "lk": ["asia", "southasia"],
    "il": ["asia", "mideast"], "tr": ["asia", "mideast"], "ir": ["asia", "mideast"],
    "lb": ["asia", "mideast"], "eg": ["africa", "mideast"],
    "us": ["northamerica"], "ca": ["northamerica"],
    "br": ["latin"], "ar": ["latin"], "cl": ["latin"], "mx": ["latin"], "co": ["latin"],
    "pe": ["latin"], "uy": ["latin"], "ve": ["latin"], "cu": ["latin"], "jm": ["latin"],
    "tt": ["latin"], "pr": ["latin"], "do": ["latin"], "pa": ["latin"], "bo": ["latin"],
    "gb": ["europe", "uk"], "ie": ["europe", "uk"],
    "fr": ["europe"], "de": ["europe"], "it": ["europe"], "es": ["europe"],
    "pt": ["europe"], "nl": ["europe"], "be": ["europe"], "ch": ["europe"],
    "at": ["europe"], "pl": ["europe"], "cz": ["europe"], "hu": ["europe"],
    "gr": ["europe"], "ru": ["europe"], "ua": ["europe"], "ro": ["europe"],
    "rs": ["europe"], "hr": ["europe"], "bg": ["europe"],
    "se": ["europe", "nordic"], "no": ["europe", "nordic"], "dk": ["europe", "nordic"],
    "fi": ["europe", "nordic"], "is": ["europe", "nordic"],
    "ng": ["africa"], "za": ["africa"], "sn": ["africa"], "ml": ["africa"],
    "gh": ["africa"], "ke": ["africa"], "et": ["africa"], "cd": ["africa"],
    "ci": ["africa"], "cm": ["africa"], "tz": ["africa"], "bj": ["africa"],
    "cv": ["africa"], "mg": ["africa"], "zw": ["africa"], "ao": ["africa"],
    "au": ["oceania"], "nz": ["oceania"],
}

# 日本の47都道府県。「◯◯県出身」「◯◯府出身」が書いてあれば日本で確定。
KEN = ("北海道 青森 岩手 宮城 秋田 山形 福島 茨城 栃木 群馬 埼玉 千葉 東京 神奈川 "
       "新潟 富山 石川 福井 山梨 長野 岐阜 静岡 愛知 三重 滋賀 京都 大阪 兵庫 奈良 "
       "和歌山 鳥取 島根 岡山 広島 山口 徳島 香川 愛媛 高知 福岡 佐賀 長崎 熊本 大分 "
       "宮崎 鹿児島 沖縄").split()

# about の中に出てきたら、その国だと判る言葉。★ 完全な語として当てる（部分一致で繋がない）
WORD = {
    "jp": ["日本の", "日本人", "邦楽", "日本のロック", "日本のシンガー", "日本を代表",
           "日本で結成", "日本のバンド", "日本のポップ", "日本の音楽", "J-POP", "Jポップ",
           "日本のヒップホップ", "日本のアイドル", "日本のジャズ"],
    "kr": ["韓国の", "韓国人", "大韓民国", "韓国出身", "ソウル特別市出身", "K-POP", "Kポップ"],
    "cn": ["中国の", "中華人民共和国", "中国出身", "北京出身", "上海出身"],
    "tw": ["台湾の", "台湾出身"],
    "hk": ["香港の", "香港出身"],
    "th": ["タイの", "タイ出身", "バンコク出身"],
    "id": ["インドネシアの", "インドネシア出身", "ジャカルタ出身"],
    "ph": ["フィリピンの", "フィリピン出身", "マニラ出身"],
    "vn": ["ベトナムの", "ベトナム出身"],
    "sg": ["シンガポールの", "シンガポール出身"],
    "my": ["マレーシアの", "マレーシア出身"],
    "in": ["インドの", "インド出身", "ムンバイ出身", "ボリウッド"],
    "pk": ["パキスタンの", "パキスタン出身"],
    "bd": ["バングラデシュ"],
    "lk": ["スリランカ"],
    "np": ["ネパール"],
    "il": ["イスラエルの", "イスラエル出身"],
    "tr": ["トルコの", "トルコ出身", "イスタンブール出身"],
    "ir": ["イランの", "イラン出身"],
    "lb": ["レバノン"],
    "eg": ["エジプトの", "エジプト出身"],
    "us": ["アメリカの", "アメリカ合衆国", "米国の", "米国出身", "アメリカ出身",
           "ニューヨーク出身", "ロサンゼルス出身", "シカゴ出身", "デトロイト出身",
           "ニューオーリンズ出身", "ミシガン州", "ニュージャージー州", "カリフォルニア州",
           "テキサス州", "ジョージア州", "テネシー州", "フロリダ州", "オハイオ州",
           "ミシシッピ出身", "ミシシッピ州", "アラバマ州", "ペンシルベニア州",
           "イリノイ州", "ミネソタ州", "ワシントン州", "ノースカロライナ州",
           "サウスカロライナ州", "バージニア州", "インディアナ州", "メリーランド州",
           "マサチューセッツ州", "ミズーリ州", "ケンタッキー州", "ルイジアナ州",
           "オクラホマ州", "アーカンソー州", "ネバダ州", "アリゾナ州", "オレゴン州",
           "コロラド州", "ウィスコンシン州", "ハワイ", "ブルックリン出身",
           "シアトル出身", "アトランタ出身", "ボストン出身", "フィラデルフィア出身",
           "メンフィス出身", "ナッシュビル出身", "サンフランシスコ出身", "マイアミ出身"],
    "ca": ["カナダの", "カナダ出身", "トロント出身", "モントリオール出身",
           "オンタリオ州", "ケベック州", "ブリティッシュコロンビア州"],
    "gb": ["イギリスの", "英国の", "英国出身", "イギリス出身", "イングランド出身",
           "ロンドン出身", "リヴァプール出身", "リバプール出身", "マンチェスター出身",
           "スコットランド", "ウェールズ", "バーミンガム出身", "シェフィールド出身",
           "ブリストル出身", "グラスゴー出身", "UKの", "英国王室属領"],
    "ie": ["アイルランドの", "アイルランド出身", "ダブリン出身"],
    "fr": ["フランスの", "フランス出身", "パリ出身"],
    "de": ["ドイツの", "ドイツ出身", "ベルリン出身", "デュッセルドルフ出身"],
    "it": ["イタリアの", "イタリア出身", "ローマ出身", "ナポリ出身", "ミラノ出身"],
    "es": ["スペインの", "スペイン出身", "マドリード出身", "バルセロナ出身",
           "アンダルシア"],
    "pt": ["ポルトガルの", "ポルトガル出身", "リスボン出身"],
    "nl": ["オランダの", "オランダ出身", "アムステルダム出身"],
    "be": ["ベルギーの", "ベルギー出身"],
    "ch": ["スイスの", "スイス出身"],
    "at": ["オーストリアの", "オーストリア出身", "ウィーン出身"],
    "pl": ["ポーランドの", "ポーランド出身"],
    "cz": ["チェコの", "チェコ出身"],
    "hu": ["ハンガリーの", "ハンガリー出身"],
    "gr": ["ギリシャの", "ギリシャ出身"],
    "ru": ["ロシアの", "ロシア出身", "モスクワ出身", "ソビエト"],
    "ua": ["ウクライナの", "ウクライナ出身"],
    "ro": ["ルーマニア"],
    "rs": ["セルビア"], "hr": ["クロアチア"], "bg": ["ブルガリア"],
    "se": ["スウェーデンの", "スウェーデン出身", "ストックホルム出身", "スウェーデンで結成"],
    "no": ["ノルウェーの", "ノルウェー出身", "ノルウェーで結成", "オスロ出身"],
    "dk": ["デンマークの", "デンマーク出身", "コペンハーゲン出身"],
    "fi": ["フィンランドの", "フィンランド出身", "ヘルシンキ出身"],
    "is": ["アイスランドの", "アイスランド出身", "レイキャヴィク出身"],
    "br": ["ブラジルの", "ブラジル出身", "リオデジャネイロ出身", "サンパウロ出身",
           "バイーア", "ブラジリアン・ポピュラー・ミュージック", "ブラジルで結成"],
    "ar": ["アルゼンチンの", "アルゼンチン出身", "ブエノスアイレス出身"],
    "cl": ["チリの", "チリ出身"],
    "mx": ["メキシコの", "メキシコ出身", "メキシコシティ出身"],
    "co": ["コロンビアの", "コロンビア出身"],
    "pe": ["ペルーの", "ペルー出身"],
    "uy": ["ウルグアイ"],
    "ve": ["ベネズエラ"],
    "cu": ["キューバの", "キューバ出身", "ハバナ出身"],
    "jm": ["ジャマイカの", "ジャマイカ出身", "キングストン出身"],
    "tt": ["トリニダード"],
    "pr": ["プエルトリコ"],
    "do": ["ドミニカ共和国"],
    "bo": ["ボリビア"],
    "pa": ["パナマ"],
    "ng": ["ナイジェリアの", "ナイジェリア出身", "ラゴス出身"],
    "za": ["南アフリカの", "南アフリカ出身", "ヨハネスブルグ出身"],
    "sn": ["セネガルの", "セネガル出身", "ダカール出身"],
    "ml": ["マリの", "マリ共和国", "マリ出身"],
    "gh": ["ガーナの", "ガーナ出身"],
    "ke": ["ケニアの", "ケニア出身"],
    "et": ["エチオピアの", "エチオピア出身"],
    "cd": ["コンゴの", "コンゴ出身", "コンゴ民主共和国"],
    "ci": ["コートジボワール"],
    "cm": ["カメルーンの", "カメルーン出身"],
    "tz": ["タンザニア"], "bj": ["ベナン"], "cv": ["カーボヴェルデ"],
    "mg": ["マダガスカル"], "zw": ["ジンバブエ"], "ao": ["アンゴラ"],
    "au": ["オーストラリアの", "オーストラリア出身", "シドニー出身", "メルボルン出身"],
    # ★1023：「オークランド出身」を外した。オークランドは2つある——
    #   Oakland（アメリカ・カリフォルニア州）と Auckland（ニュージーランド）。
    #   日本語ではどちらも「オークランド」。実測：Tony! Toni! Toné! の概要は
    #   「アメリカ・オークランド出身のR&Bトリオ」なのに、ニュージーランドが付いていた。
    #   見分けが付かない語は使わない（関所：迷ったら落とす側に倒す）。
    "nz": ["ニュージーランドの", "ニュージーランド出身"],
}

# ★1023：語ではなく形で当てるぶん。「アメリカ・オークランド出身」のような中黒つなぎを拾う。
#   ★ただの「アメリカ・」では拾わない。實測：當山ひとみの概要は
#     「アメリカ・沖縄育ちの背景を持つ**日本の**歌手」で、日本の人がアメリカにされた。
#     **出身までを1つの形として見る。**育ち・ゆかり・ツアーでは国を決めない。
WORD_RE = {
    "us": [r"アメリカ・[^。、]{0,12}出身"],
}
for k in KEN:
    WORD["jp"].append(k + "県出身")
    WORD["jp"].append(k + "県")
WORD["jp"] += ["東京都出身", "京都府出身", "大阪府出身", "北海道出身", "東京都",
               "大阪府", "京都府"]

HIRA = re.compile(r"[ぁ-ゖ]")
KANJI = re.compile(r"[一-鿿]")
KANA = re.compile(r"[ァ-ヺ]")
HANGUL = re.compile(r"[가-힣]")

# ★ 名前の文字づかいだけでは間違う人。名前に併記されている本人の表記を根拠に直す。
#   （2026-09-20 実測：漢字名だけで日本と決めていたので、台湾・香港の人が日本になっていた）
NAOSU = {
    "sunset-rollercoaster": ("tw", "名前が「落日飛車 (Sunset Rollercoaster)」＝台湾のバンド表記"),
    "a-mei": ("tw", "名前が「A-Mei (張惠妹)」＝台湾の歌手表記"),
    "sodagreen": ("tw", "名前が「Sodagreen (蘇打綠)」＝台湾のバンド表記"),
    "leslie-cheung": ("hk", "名前が「張國榮 (レスリー・チャン)」＝香港の俳優・歌手表記"),
    "tvxq": ("kr", "名前が「東方神起」＝韓国のグループ（TVXQ）"),
    "wu-bai": ("tw", "名前が「伍佰」＝台湾の歌手（Wu Bai）"),
}


# ★1023：概要が「その人の記事」ではなく「その名前そのものの記事（曖昧さ回避）」
#   になっているもの。中身が別人の話なので、そこから国を取ると必ず間違える。
#   実測：Simon & Garfunkel の概要は人名「シモン」の語源の記事で、本文に出てくる
#   シモン・ボリバルのせいで **ベネズエラ** が付いていた。
#   ★いま棚の1,506件を当てて、引っかかるのはこの1件だけ（誤って落とすものは無い）。
AB_BETSUMONO = re.compile(
    r"に由来する名前|この名を冠する|曖昧さ回避|同名の人物|に由来する姓|名前である。|姓である。")


def region_of(name, about, aid=None):
    """(国コード, 根拠の文字列) を返す。取れなければ (None, None)。"""
    if aid in NAOSU:
        return NAOSU[aid]
    ab = about or ""
    # ★1023：別人の記事から国を取らない。取れないなら空欄のまま（推測で埋めない）。
    if ab and AB_BETSUMONO.search(ab[:200]):
        return None, None
    # ① about に国・地方・州・都道府県が書いてあるか（先に当たったものを採る）
    best = None
    for code, words in WORD.items():
        for w in words:
            i = ab.find(w)
            if i >= 0 and (best is None or i < best[2]):
                best = (code, w, i)
    # ★1023：形で当てるぶんも、同じ土俵（いちばん先に出てきたものを採る）で混ぜる。
    for code, pats in WORD_RE.items():
        for p in pats:
            mo = re.search(p, ab)
            if mo and (best is None or mo.start() < best[2]):
                best = (code, mo.group(0), mo.start())
    if best:
        return best[0], "概要に「%s」" % best[1]
    # ② 名前の文字づかい。ひらがなは日本語にしか無い
    if HANGUL.search(name):
        return "kr", "名前がハングル"
    if HIRA.search(name):
        return "jp", "名前にひらがな"
    # ★ カタカナだけの名前では決めない（2026-09-20 実測で捨てたルール）。
    #   「日本の芸名が大半」と思って jp を付けたら、77組のうち20組ほどが海外だった
    #   （キャメル＝英／カン＝独／シック＝米／ジャミロクワイ＝英／ムーミン＝芬…）。
    #   4組に1組間違えるルールは使わない。about で取れないものは空欄のままにする。
    if KANJI.search(name):
        return "jp", "名前が漢字"
    return None, None


def main():
    spec = importlib.util.spec_from_file_location("b", str(REPO / "tools" / "_953_build_song_index.py"))
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)

    src = b.strip_comments(io.open(COVER, encoding="utf-8", errors="replace").read())
    arts = b.read_artists(src)

    gab = {}
    if PROF.exists():
        s = io.open(PROF, encoding="utf-8", errors="replace").read()
        m = re.search(r"export const generatedAbouts: Record<string, string> = \{(.*?)\n\};", s, re.S)
        if m:
            for mm in re.finditer(r'\n  "([^"]+)": "((?:[^"\\]|\\.)*)",?', m.group(1)):
                gab[mm.group(1)] = re.sub(r"\\(.)", r"\1", mm.group(2))

    r, srcmap = {}, {}
    for a in arts:
        # ★ 会社・映画・ジャンル・お笑い等（kind が music 以外）には地域を付けない。
        #   付けると「日本の曲」で JR東海 や 花王 が出る（2026-09-20 自己検査で実際に出た）。
        if a.get("kind") not in (None, "music"):
            continue
        ab = a.get("about") or gab.get(a["id"]) or ""
        code, why = region_of(a["name"], ab, a["id"])
        if code:
            r[a["id"]] = code
            srcmap[a["id"]] = why

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"r": r, "src": srcmap, "group": GROUP},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    from collections import Counter
    c = Counter(r.values())
    g = Counter()
    for code in r.values():
        for gg in GROUP.get(code, []):
            g[gg] += 1
    print("アーティスト %d組中 %d組に地域が付いた（%.0f%%）"
          % (len(arts), len(r), 100.0 * len(r) / max(1, len(arts))))
    print("国別:", dict(c.most_common()))
    print("くくり:", dict(g.most_common()))
    print("→", OUT, "%.0fKB" % (OUT.stat().st_size / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
