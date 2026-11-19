#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""題名の関所（daimei_kanmon）：外部から入れたカードの題名が「何の動画か」を言えているかを機械で見る。

たまごさん（2026-10-14・要旨）:
  外部から入れた「さつまいもでビスケットサンドのようなものを作る」動画のカードの題名が
  「冷やすではなく癒やす」になっていた。サムネで見ても何の動画か分からず、クリックされない。
  さつまいもの情報も無い。元の投稿の文に引っ張られて、適当に付けた例。
  「これは何の動画なんだろう？」が一目で伝わる題名・コピーを付けられるようにしてほしい。

■ 題名の型（2行コピーの型・取り込み時のルール）
  1行目（title）  … 何の動画か。**主題の名詞＋していること。**
                     例：「さつまいもで作る、ひんやりビスケットサンド」
  2行目（whisper）… 気の利いた言い回しはこちらへ（ボンジョビおじさん構文）。
  ・投稿文の比喩・決め台詞（「AでなくB」など）を題名に使わない。
  ・投稿文の言い回しをそのまま写さない。絵文字・罫線・ハッシュタグ・URLを持ち込まない。
  ・材料（投稿本文・動画の原題・チャンネル名）に無いことは書かない。

■ 落とす条件（どれか1つでも当たれば差し戻し）
  空／投稿の飾り（絵文字・罫線）／投稿の切れ端（URL・@・#・途中切れ「…」）／長すぎ（41文字以上）／
  決め台詞（AでなくB・かぎかっこだけ）／投稿文の写し（投稿本文に8文字以上そのまま入っている）／
  主題の名詞が無い（料理名・食材・曲名・人・場所・動物などの名詞が1つも無い）

使い方:
  python3 tools/daimei_kanmon.py --title "…" [--source "投稿本文"] [--kind x]
  python3 tools/daimei_kanmon.py --tanaoroshi status/daimei/stock_dump.json   # 棚卸し
  python3 tools/daimei_kanmon.py --self-test
  （import して judge(title, source, kind) → 理由のリスト。空なら合格）
"""
from __future__ import annotations

import html
import io
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT_TANA = os.path.join(REPO, "status", "public", "daimei_tanaoroshi.json")

# スマホ（iPhone幅）の棚カードは題名が2行・1行12文字前後で「…」に切られる（2026-10-14 実測：
# 25文字の「さつまいもで作る、チャイ香るアイスビスケットサンド」が「…ビスケットサ…」で切れ、主題の「サンド」が消えた）。
MAX_LEN = 24

# 絵文字・記号・罫線（投稿の飾り）
RE_KAZARI = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿⬀-⯿←-⇿─-╿"
    "■-◿️‍〰〽❣❤♡♥♪-♯"
    "\U00011000-\U0001107F\U00016900-\U00016A3F˚̣͙⸻]")
RE_KIREHASHI = re.compile(r"https?://|pic\.twitter|t\.co/|(?:^|\s)[@＠][A-Za-z0-9_]{2,}|[#＃][^\s#＃]+|…$|\.\.\.$|〜$")
# 決め台詞：「AでなくB」「AじゃなくてB」「AではなくB」
RE_KIMEZERIFU = re.compile(r"(?:で|じゃ|では)なく(?:て)?(?![てもちゃ])|」(?:で|じゃ|では)なく")
RE_KAKKO_ONLY = re.compile(r"^[「『].*[」』]$")

RE_KATA = re.compile(r"[ァ-ヴヵヶ][ァ-ヴヵヶー・]+")
RE_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9'’&.\-]+")
RE_KANJI = re.compile(r"[一-龥々〆ヶ]+")
# 名詞の後ろに来る助詞。「か」「な」「や」は動詞・形容動詞の活用（動か・特別な）と区別できないので入れない
JOSHI = set("はがをにのでともへ")
KUTEN = set("、。，．・ 　「」『』（）()！？!?～〜/／:：")

# ひらがな・混ぜ書きで書かれやすい主題の名詞（食材・料理・動物など）。足すのは自由。
HIRA_MEISHI = [
    "さつまいも", "じゃがいも", "さといも", "おいも", "おにぎり", "おむすび", "おやつ", "ごはん",
    "うどん", "そば", "すし", "おでん", "みそ汁", "みそ", "だんご", "おもち", "もち", "いちご",
    "みかん", "りんご", "ぶどう", "もも", "なす", "かぼちゃ", "きゅうり", "たまご", "ねこ", "いぬ",
    "うさぎ", "くま", "ぱんだ", "ひよこ", "あんこ", "わらび餅", "どら焼き", "たい焼き", "せんべい",
    "からあげ", "しょうが", "にんにく", "ねぎ", "ほうれん草", "とうもろこし", "あずき", "くり",
    "ぎょうざ", "ちくわ", "はんぺん", "こんにゃく", "ところてん", "ようかん", "まんじゅう",
]

# 名詞だが「何の動画か」は言っていない語（これだけでは主題にならない）
CHUSHOU = {
    "瞬間", "全部", "最高", "最強", "気持", "気分", "本当", "自分", "今日", "明日", "毎日", "人生",
    "世界", "時間", "理由", "正解", "意味", "魔法", "奇跡", "幸", "癒", "天才", "神", "秘密", "大人",
    "一番", "普通", "最後", "最初", "必要", "簡単", "手軽", "完成", "体験", "感覚", "心", "体",
    "不思議", "方法", "絶品", "大好", "驚", "感動", "笑顔", "元気", "勇気", "安心", "本気", "全力",
    "毎年", "季節", "朝", "夜", "昼", "今", "日", "人", "私", "僕", "俺", "君", "誰", "何", "皆",
    "部", "愛", "夢", "声", "顔", "目", "手", "事", "物", "時", "所", "方", "中", "上", "下",
    "前", "後", "先日", "実", "冷", "癒", "甘", "香", "味", "感", "話", "気", "家", "日々",
    "毎朝", "毎晩", "最近", "結果", "効果", "状態", "様子", "場合", "一日", "週末",
    # 「動画です」としか言っていない語（2026-10-14 棚卸しで通ってしまった題名から足した）
    "世界中", "映像", "動画", "人物", "表情", "特別", "何度", "公開", "投稿", "演出", "驚", "至福",
    "一瞬", "日常", "紹介", "注目", "登場", "最新", "話題", "衝撃", "感謝", "一言", "一枚", "全員",
}
KATA_CHUSHOU = {
    "レシピ", "アイデア", "ポイント", "パワー", "ハッピー", "ストレス", "リラックス", "テンション",
    "エモ", "レベル", "チェック", "ポスト", "ツイート", "シェア", "リアル", "スゴイ", "ヤバイ",
    "ワクワク", "ドキドキ", "キラキラ", "ニコニコ", "ホッ", "ゴール", "スタート", "ベスト", "マジ",
}
LATIN_CHUSHOU = {"the", "and", "of", "a", "to", "in", "on", "is", "it", "my", "you", "me",
                 "vs", "feat", "ft", "official", "video", "mv", "live", "lyrics", "hd", "ver"}


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", str(s or ""))
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"&mdash;.*$", "", s, flags=re.S)
    return s


def post_text_of(row):
    """カードの行（admin_stock）から投稿本文を取り出す（Xの埋め込みHTML＝note）。無ければ ''。"""
    note = str(row.get("note") or "")
    if "twitter-tweet" in note:
        m = re.search(r"<p[^>]*>([\s\S]*?)</p>", note)
        return strip_html(m.group(1) if m else note).strip()
    if note.startswith("原題:"):
        return note[3:].strip()
    return ""


def meishi(title):
    """題名から主題になりうる名詞を拾う（形態素解析器なしの手堅い近似）。"""
    t = str(title or "")
    out = []
    for w in HIRA_MEISHI:
        if w in t:
            out.append(w)
    for m in RE_KATA.finditer(t):
        w = m.group(0).strip("ー・")
        if len(w) >= 2 and w not in KATA_CHUSHOU:
            out.append(w)
    for m in RE_LATIN.finditer(t):
        w = m.group(0)
        if len(w) >= 2 and w.lower() not in LATIN_CHUSHOU:
            out.append(w)
    for m in RE_KANJI.finditer(t):
        w = m.group(0)
        nxt = t[m.end():m.end() + 1]
        if nxt and ("ぁ" <= nxt <= "ゖ") and nxt not in JOSHI:
            # 送り仮名つき＝動詞・形容詞の語幹。最後の1字を落として残りを見る（手作り→手）
            w = w[:-1]
            if len(w) < 2:
                continue
        if not w or w in CHUSHOU:
            continue
        if len(w) == 1 and w in CHUSHOU:
            continue
        out.append(w)
    return [w for w in out if w not in CHUSHOU]


def _norm(s):
    s = RE_KAZARI.sub("", str(s or ""))
    return re.sub(r"[\s、。，．・「」『』（）()！？!?～〜…ー\-—_:：/／*＊♪♡☆★w]+", "", s)


def judge(title, source="", kind=""):
    """題名を見て、差し戻す理由のリストを返す。空リストなら合格。"""
    t = str(title or "").strip()
    why = []
    if not t:
        return ["題名が空"]
    if RE_KAZARI.search(t):
        why.append("投稿の飾り（絵文字・罫線）が題名に残っている")
    if RE_KIREHASHI.search(t):
        why.append("投稿の切れ端（URL・@・#・途中切れ）が題名に残っている")
    if len(t) > 40 and kind != "youtube":
        # YouTubeの公式題名（曲名 - アーティスト (Official Video)）は長くても「何か」は言えているので対象外
        why.append("長すぎる（41文字以上＝投稿文の貼り付け）")
    elif len(t) > MAX_LEN and not meishi(t[:MAX_LEN - 1]):
        # 長いだけなら落とさない。主題の名詞が「…」の向こうに消えるときだけ落とす
        why.append("主題の名詞がスマホのカードで切れて見えない（%d文字目以降にある）" % MAX_LEN)
    if RE_KIMEZERIFU.search(t) or RE_KAKKO_ONLY.match(RE_KAZARI.sub("", t).strip()):
        why.append("投稿の比喩・決め台詞を題名にしている")
    src = strip_html(source)
    if src and kind != "youtube":
        nt, ns = _norm(t), _norm(src)
        if len(nt) >= 8:
            # 8文字以上の連続一致＝投稿文の言い回しの写し
            for i in range(0, len(nt) - 7):
                if nt[i:i + 8] in ns:
                    why.append("投稿文の言い回しをそのまま写している")
                    break
    if not meishi(t):
        why.append("何の動画か分かる名詞（料理名・食材・曲名・人・場所・動物など）が無い")
    return why


# ---------------------------------------------------------------- 棚卸し
SOTO = ("x", "youtube", "link")   # 外部から入れたカード（cover-guide＝名カバーは触らない）


def tanaoroshi(dump_path, out_path=OUT_TANA):
    rows = json.load(io.open(dump_path, encoding="utf-8"))
    soto = [r for r in rows if r.get("kind") in SOTO and not r.get("deleted_at")]
    hits = []
    reasons = Counter()
    for r in soto:
        src = post_text_of(r)
        w = judge(r.get("title"), src, r.get("kind"))
        if w:
            for x in w:
                reasons[x] += 1
            hits.append({"id": r.get("id"), "kind": r.get("kind"), "ref": r.get("ref"),
                         "title": r.get("title"), "why": w, "created": (r.get("created_at") or "")[:10]})
    hits.sort(key=lambda h: h["created"], reverse=True)
    hit_ids = {h["id"] for h in hits}
    tooshita = [r.get("title") for r in soto if r.get("id") not in hit_ids and r.get("kind") != "youtube"][:40]
    print("通した（x/link）の見本：")
    for t in tooshita:
        print("    ○ " + str(t)[:60])
    out = {"総数": len(soto), "差し戻し": len(hits),
           "理由ごと": dict(reasons.most_common()),
           "種類ごと": dict(Counter(h["kind"] for h in hits)),
           "一覧": hits}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with io.open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("外部カード %d件中 差し戻し %d件" % (len(soto), len(hits)))
    for k, v in reasons.most_common():
        print("  %4d  %s" % (v, k))
    for h in hits[:15]:
        print("  - [%s] %s ／ %s" % (h["kind"], h["title"][:50], "・".join(h["why"])))
    return out


# ---------------------------------------------------------------- 自己試験
def self_test():
    src = ("⛱ 「冷やす」でなく「癒す」\n365日アイス部\n冷たいのに、香りはまるでチャイ\n"
           "先日ポストした、さつまいも掘り 実はコレ、甘さが足りない、ちょっと微妙なさつまいもを集めて")
    ng = [
        ("⛱ 「冷やす」でなく「癒す」", src, "x"),
        ("冷やすではなく癒やす", "", "x"),
        ("これからの季節に作ってほしい。 甘くてとろ〜り簡単、さつまいものポタージュ🍠 さつまいもと玉ねぎは薄切りに。", "", "x"),
        ("@3105_369 のポスト", "", "x"),
        ("ちょっと微妙なさつまいもを集めて", src, "x"),
        ("抱っこされた瞬間、全部あずけた", "", "x"),
        ("何度も繰り返し見たくなるような心を動かす特別な映像", "", "x"),
    ]
    ok = [
        ("さつまいもで作る、ひんやりビスケットサンド", src, "x"),
        ("チャイ香る、さつまいもアイスのビスケットサンド", src, "x"),
        ("白菜と肉を重ねるだけで、鍋がまるごと花になる", "", "x"),
        ("褒めたのに、柴犬に怒られた", "", "youtube"),
        ("ミキサーを出す前に、ビシソワーズができてしまった", "", "x"),
        ("Something / Josh Turner", "", "youtube"),
        ("雨あがりの夜空に", "", "youtube"),
    ]
    bad = 0
    for t, s, k in ng:
        w = judge(t, s, k)
        print(("OK  落とした " if w else "NG  通してしまった ") + t[:30], w)
        bad += 0 if w else 1
    for t, s, k in ok:
        w = judge(t, s, k)
        print(("OK  通した   " if not w else "NG  落としてしまった ") + t[:30], w)
        bad += 1 if w else 0
    print("SELF_TEST:", "PASS" if bad == 0 else "FAIL %d" % bad)
    return bad == 0


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        return 0 if self_test() else 1
    if "--tanaoroshi" in a:
        tanaoroshi(a[a.index("--tanaoroshi") + 1])
        return 0
    if "--title" in a:
        t = a[a.index("--title") + 1]
        s = a[a.index("--source") + 1] if "--source" in a else ""
        k = a[a.index("--kind") + 1] if "--kind" in a else ""
        w = judge(t, s, k)
        print("DAIMEI_RESULT: " + ("PASS" if not w else "FAIL - " + " ／ ".join(w)))
        return 0 if not w else 1
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
