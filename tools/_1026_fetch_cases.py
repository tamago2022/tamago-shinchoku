#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1026番：Wikipedia誤爆の「見本」を、実物のWikipediaから取ってくる（Mac側で走る）。

なぜ要るか：
  たまごさんが挙げた誤爆（TURNSTILE→改札機 / Trueno→車 / IO→木星の衛星 /
  Riddim Saunter→フジロックの記事）を **--selftest の見本に足す** ために、
  その記事の書き出しが要る。★見本の文を記憶から書かない。実物から引く。
  （出典が取れないものは書かない＝skill sekisho-jijitsu-shutten）
出力：tools/sekisho/wiki_cases.json
"""
import io, json, os, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
UA = "tamago-shiire/1.0 (https://github.com/tamago2022/tamago-shinchoku)"

# (探した名前, 言語, 実際に採られた／採られかけた記事, 期待する判定, なぜ)
CASES = [
    # ★たまごさんが名指しした4件（再発したらここで機械が落ちる）
    ("TURNSTILE",            "en", "Turnstile",                      False, "改札機の記事"),
    ("Trueno",               "en", "Toyota Sprinter Trueno",         False, "トヨタの車"),
    ("IO",                   "en", "Io (moon)",                      False, "木星の衛星"),
    ("Riddim Saunter",       "en", "Fuji Rock Festival",             False, "フェスの記事そのもの"),
    # ★(album)を人物より先に採る癖（引き継ぎ1025に明記された未修理）
    ("LOYLE CARNER",         "en", "Hugo (album)",                   False, "アルバムの記事（人物ではない）"),
    ("DONAVON FRANKENREITER","en", "Donavon Frankenreiter (album)",  False, "アルバムの記事（人物ではない）"),
    ("GRAPEVINE",            "en", "Here (GRAPEVINE album)",         False, "アルバムの記事（バンドではない）"),
    # ★名前が違う別人・別物を採っていた（実測で見つけた同じ型）
    ("GRAPEVINE",            "en", "AM Radio (band)",                False, "まったく別のバンド"),
    ("TORO Y MOI",           "ja", "Mabanua",                        False, "別のアーティスト"),
    ("Yo-Sea",               "ja", "LUNA SEA",                       False, "別のバンド"),
    ("TURNSTILE",            "ja", "ロードランナー・レコード",         False, "レコード会社の記事"),
    ("SON ROMPE PERA",       "en", "Tiny Desk Concerts",             False, "番組の記事"),
    ("KOTORI",               "en", "Kotori Koiwai",                  False, "声優（別人）"),
    ("平沢進+会人",           "en", "Susumu Hirasawa discography",    False, "ディスコグラフィ一覧"),
    ("SOFIA ISELLA",         "ja", "The Eras Tour",                  False, "他人のツアーの記事"),
    ("BOHEMIAN BETYARS",     "en", "DMZ Peace Train Music Festival", False, "フェスの記事"),
    ("Kneecap",              "en", "Kneecap (film)",                 False, "映画の記事"),
    # ★通らないといけない側（厳しくしすぎて全部落ちるのを防ぐ）
    ("TURNSTILE",            "en", "Turnstile (band)",               True,  "本人（バンド）"),
    ("LOYLE CARNER",         "en", "Loyle Carner",                   True,  "本人"),
    ("MOGWAI",               "en", "Mogwai",                         True,  "本人（バンド）"),
    ("MOGWAI",               "ja", "モグワイ",                        True,  "本人（日本語表記）"),
    ("GEORDIE GREEP",        "en", "Geordie Greep",                  True,  "本人"),
    ("KNEECAP",              "en", "Kneecap (band)",                 True,  "本人（バンド）"),
    ("平沢進",                "ja", "平沢進",                         True,  "本人"),
    ("Bialystocks",          "ja", "Bialystocks",                    True,  "本人"),
    ("JOEY VALENCE & BRAE",  "en", "Joey Valence & Brae",            True,  "本人（デュオ）"),
    ("TOMORA",               "en", "Tomora (duo)",                   True,  "本人（デュオ）"),
    ("GRAPEVINE",            "ja", "GRAPEVINE",                      True,  "本人（バンド・日本）"),
    ("TORO Y MOI",           "ja", "トロ・イ・モア",                   True,  "本人（日本語表記）"),
]


def extract(lang, title):
    api = "https://%s.wikipedia.org/w/api.php" % lang
    u = api + "?" + urllib.parse.urlencode({
        "action": "query", "prop": "extracts", "explaintext": 1,
        "titles": title, "format": "json", "redirects": 1})
    req = urllib.request.Request(u, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8", "ignore"))
    pg = list(d["query"]["pages"].values())[0]
    return pg.get("title") or title, (pg.get("extract") or "")


def main():
    out = []
    for name, lang, title, want, why in CASES:
        try:
            real, text = extract(lang, title)
        except Exception as e:
            print("NG %-30s %s %r" % (title[:30], lang, e))
            continue
        out.append({"name": name, "lang": lang, "title": real,
                    "askedTitle": title, "expectArtist": want, "why": why,
                    "lead": text[:1400],
                    "src": "https://%s.wikipedia.org/wiki/%s" % (
                        lang, urllib.parse.quote(real.replace(" ", "_")))})
        print("ok %-32s %s %5d字  期待=%s" % (real[:32], lang, len(text), want))
        time.sleep(0.35)
    os.makedirs(os.path.join(REPO, "tools", "sekisho"), exist_ok=True)
    p = os.path.join(REPO, "tools", "sekisho", "wiki_cases.json")
    io.open(p, "w", encoding="utf-8").write(
        json.dumps({"takenAt": time.strftime("%F %T"),
                    "note": "実物のWikipediaから引いた見本。★手で書かない。",
                    "cases": out}, ensure_ascii=False, indent=1))
    print("見本 %d件 → tools/sekisho/wiki_cases.json" % len(out))


if __name__ == "__main__":
    main()
