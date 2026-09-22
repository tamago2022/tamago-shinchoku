#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仕入れの下ごしらえ ― アーティスト名から「裏の取れる素材」だけを機械で集める。

たまごさん（2026-09-22）:
  「フジロックをはじめ、有名なフェスに出てるアーティストは全員入れるくらいの勢いで。
   誰が来ても『いや、それはないですね』っていう状態をなくしたい。」

■ なぜこの道具が要るか（実測）
  Cowork/Dispatchのサンドボックスからは musicbrainz.org も wikipedia.org も
  出られない（proxy が CONNECT を 403 で切る・2026-09-22 実測）。Macからは出られる。
  だから **集めるのはMac側、書くのはセッション側** に分ける。

■ 集めるもの（この2つだけ。どちらも識別子か原文が取れる）
  1. MusicBrainz … 同定用。mbid / 地域 / 種別 / 活動開始 / タグ / 曖昧さ回避
     ★名前一致だけで確定しない。取れた候補を全部残し、選ぶのは人間側の工程。
     （akikoの棚に矢野顕子を入れた事故の再発防止＝skill sekisho-artist-song）
  2. Wikipedia（英/日） … 事実の原文。要約と本文をそのまま保存する。
     ★要約しない。あとで「その語がこのページに本当に載っているか」を機械で照合するため。
     （skill sekisho-jijitsu-shutten の「出典が取れない断定は書かない」を機械にする）

■ 置き場所
  status/shiire_raw/<slug>.json   … 集めた原文。ここは素材置き場で、棚ではない。
  ★棚（coverGuide.ts）には1文字も書かない。

■ 使い方（Mac側）
  python3 tools/shiire_fetch.py --names "TURNSTILE" "MOGWAI" ...
  python3 tools/shiire_fetch.py --from-queue 12      # フェス名簿の穴の上から12組
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RAW = os.path.join(REPO, "status", "shiire_raw")
UA = "tamago-shiire/1.0 (https://github.com/tamago2022/tamago-shinchoku)"

# 名簿の取り込みで混ざる「出演者ではない枠」「別形態」。ここでは素材を集めない。
SKIP = ("(DJ)", "(DJ Set)", "(DJ SET)", "DJs", "SOUND CLASH",
        "トーク", "ワークショップ", "ヨガ", "サーカス", "SPECIAL GUEST")


def slug(name):
    s = re.sub(r"[^0-9A-Za-z]+", "-", name.lower()).strip("-")
    return s or re.sub(r"\s+", "-", name)[:40]


def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, "%r" % (e,)


def musicbrainz(name):
    """同定の候補を上位5件そのまま返す。**1件に決め打ちしない。**"""
    u = ("https://musicbrainz.org/ws/2/artist?query=%s&fmt=json&limit=5"
         % urllib.parse.quote(name))
    code, body = get(u)
    if code != 200:
        return {"ok": False, "http": code, "src": u}
    try:
        d = json.loads(body)
    except Exception:
        return {"ok": False, "http": code, "src": u}
    out = []
    for a in (d.get("artists") or [])[:5]:
        out.append({
            "mbid": a.get("id"), "name": a.get("name"),
            "score": a.get("score"), "type": a.get("type"),
            "area": ((a.get("area") or {}).get("name")
                     or (a.get("begin-area") or {}).get("name")),
            "country": a.get("country"),
            "began": (a.get("life-span") or {}).get("begin"),
            "ended": (a.get("life-span") or {}).get("end"),
            "disambiguation": a.get("disambiguation"),
            "tags": [t.get("name") for t in (a.get("tags") or [])][:8],
            "aliases": [x.get("name") for x in (a.get("aliases") or [])][:6],
        })
    return {"ok": True, "src": u, "candidates": out}


# ★検索の1件目をそのまま採ると事故る（2026-09-22 実測）。
#   "TURNSTILE" の1件目は **改札機の記事**、"Trueno" の1件目は **トヨタのスプリンター トレノ**、
#   "IO" の1件目は **木星の衛星イオ**、"Riddim Saunter" の1件目は **フジロックの記事そのもの**。
#
# ★2026-09-23（1026番）にここを作り直した。理由：「音楽の記事らしさ」で選ぶ前の型では
#   まだ穴が残っていた。実測で出た抜け方は2つ。どちらも「音楽の記事ではある」。
#     (a) 本人ではなく**作品**を採る … LOYLE CARNER → "Hugo (album)"、
#         DONAVON FRANKENREITER → "Donavon Frankenreiter (album)"
#     (b) 音楽の記事だが**まったく別人・別物**を採る … GRAPEVINE → "AM Radio (band)"、
#         TORO Y MOI(ja) → "Mabanua"、Yo-Sea(ja) → "LUNA SEA"、TURNSTILE(ja) → "ロードランナー・レコード"、
#         KOTORI → "Kotori Koiwai"(声優)、SON ROMPE PERA → "Tiny Desk Concerts"
#   → 「らしさの点数」をやめ、**2つの関所を両方通ったものだけ**を採る形にした。
#       関所1：その記事は**人（バンド）の記事か**。作品・映画・一覧・会社・衛星は落とす。
#       関所2：その記事は**探している本人か**。題が名前と一致するか、
#               題が別の文字体系のときだけ、書き出しの括弧内に元の名前があるか。
#   どちらかでも通らなければ **found=False**。★一番近いものを当てはめない。

# 記事の題の括弧（人・バンドを指す言葉）
ARTIST_PAREN = ("band", "musician", "rapper", "singer", "duo", "trio",
                "group", "musical group", "musical duo", "musical project",
                "dj", "producer", "songwriter", "rock band", "singer-songwriter",
                "バンド", "歌手", "ミュージシャン", "ラッパー", "音楽家", "アーティスト")
# 記事の題の括弧（作品・その他＝人ではない）
WORK_PAREN = ("album", "song", "ep", "single", "mixtape", "soundtrack",
              "film", "movie", "tv series", "video game", "novel", "book",
              "moon", "disambiguation", "magazine", "company", "record label",
              "アルバム", "曲", "楽曲", "シングル", "映画", "小説", "曖昧さ回避")
# 題そのものが「人の記事ではない」と言っているもの
NOT_ARTICLE_TITLE = ("discography", "list of", "filmography", "一覧", "の作品",
                     "ディスコグラフィ", "(disambiguation)", "（曖昧さ回避）")

# 書き出しが「作品の記事」だと言っている型（★人より先に見る。
#   "is the debut album by X, an English rapper" は rapper を含むので順番が要る）
WORK_LEAD = (
    r"\bis\s+(?:the|a|an|their|his|her|its)\b[^.]{0,90}?\b"
    r"(?:studio\s+)?(?:album|ep|mixtape|single|song|soundtrack|compilation)\b",
    r"\bis\s+(?:the|a|an)\b[^.]{0,90}?\b(?:film|movie|documentary|novel|video game)\b",
    r"\bis\s+(?:a|the)\b[^.]{0,60}\b(?:moon|satellite|festival|concert series|"
    r"record label|railway station|turnstile|gate)\b",
    r"は、?[^。]{0,60}?(?:の)?(?:アルバム|楽曲|シングル|EP|映画|小説|ゲーム)",
    r"は、?[^。]{0,60}?(?:フェスティバル|音楽祭|レコードレーベル|レコード会社|衛星)",
)
# 書き出しが「人・バンドの記事」だと言っている型
ARTIST_LEAD = (
    r"\b(?:is|are|was|were)\b[^.]{0,120}?\b(?:band|singer|rapper|musician|"
    r"duo|trio|group|songwriter|record producer|dj|recording artist|"
    r"hip hop artist|solo artist|music project|musical project|rock group)\b",
    r"\bknown\s+professionally\s+as\b",
    r"は、?[^。]{0,80}?(?:バンド|歌手|ラッパー|ミュージシャン|音楽家|音楽ユニット|"
    r"音楽グループ|シンガー|デュオ|トリオ|アイドルグループ|シンガーソングライター|"
    r"DJ|音楽プロデューサー|アーティスト)",
)


def norm(s):
    """比べるためだけの形。記号・空白・大文字小文字の差を消す。"""
    return re.sub(r"[^0-9a-z぀-ヿ㐀-鿿]+", "", (s or "").lower())


def title_core(title):
    """題の末尾の括弧を外した本体。'Turnstile (band)' → 'Turnstile'"""
    return re.sub(r"\s*[（(][^（()）]*[）)]\s*$", "", title or "").strip()


def title_paren(title):
    m = re.search(r"[（(]([^（()）]*)[）)]\s*$", title or "")
    return (m.group(1) if m else "").strip().lower()


def _is_latin(s):
    return not re.search(r"[぀-ヿ㐀-鿿]", s or "")


def lead_sentences(text, n=2, cap=520):
    """★見るのは**書き出しの1〜2文だけ**。

    ここを広く取ると事故る（2026-09-23 実測）：700字ぶん見ていたときは
    「モグワイ」「平沢進」「Bialystocks」「GRAPEVINE」の**経歴の途中に出てくる
    「デビュー・アルバム『…』をリリース」**を拾って、本人の記事を
    「アルバムの記事」と読み違えて落としていた。記事が何の記事かを名乗るのは書き出しだけ。
    """
    s = re.sub(r"\s+", " ", (text or "")).strip()[:cap * 2]
    if not s:
        return ""
    parts = re.split(r"(?<=。)", s) if "。" in s[:cap] else re.split(r"(?<=[.])\s", s)
    out = ""
    for p in parts:
        if not p.strip():
            continue
        out += p if out == "" else (p if out.endswith(("。", " ")) else " " + p)
        if len(out) >= 40 and out.count("。") + out.count(". ") >= 1:
            n -= 1
            if n <= 0:
                break
        if len(out) >= cap:
            break
    return out[:cap]


def article_kind(title, text):
    """その記事は誰の・何の記事か。'artist' / 'work' / 'other' と、そう決めた証拠を返す。"""
    t = (title or "").lower()
    lead = lead_sentences(text)
    low = lead.lower()
    for w in NOT_ARTICLE_TITLE:
        if w in t:
            return "other", "題に「%s」が入っている（人の記事ではない）" % w
    p = title_paren(title)
    if p:
        if any(p == w or p.endswith(" " + w) or p.startswith(w + " ") for w in WORK_PAREN):
            return "work", "題の括弧が「%s」＝作品・別物の記事" % p
        if any(p == w or p.endswith(" " + w) for w in ARTIST_PAREN):
            return "artist", "題の括弧が「%s」＝人・バンドの記事" % p
    for pat in WORK_LEAD:                      # ★作品を先に見る
        m = re.search(pat, low) or re.search(pat, lead)
        if m:
            return "work", "書き出しが作品・別物：…%s…" % lead[max(0, m.start() - 20):m.end() + 10]
    for pat in ARTIST_LEAD:
        m = re.search(pat, low) or re.search(pat, lead)
        if m:
            return "artist", "書き出しが人・バンド：…%s…" % lead[max(0, m.start() - 20):m.end() + 10]
    return "other", "書き出しから人の記事だと読み取れない"


def name_matches(name, title, text):
    """その記事は**探している本人**か。名前一致の甘い判定で別人を掴まないためのほう。"""
    core = title_core(title)
    if norm(core) and norm(core) == norm(name):
        return True, "題が名前と一致"
    if norm(title) and norm(title) == norm(name):
        return True, "題が名前と一致"
    # 日本語版で題がカタカナ表記のときだけ、書き出しの括弧に元の綴りがあるかを見る。
    # （例：「モグワイ（Mogwai、…）」）★同じ文字体系のときは使わない＝
    #   "KOTORI" で "Kotori Koiwai"（声優）を拾う穴を開けないため。
    if _is_latin(name) != _is_latin(core):
        head = re.sub(r"\s+", " ", (text or "")[:300])
        toks = [t for t in re.split(r"[^0-9A-Za-z]+", name) if len(t) > 1]
        for m in re.finditer(r"[（(]([^（()）]{0,140})[）)]", head):
            inner = m.group(1)
            if norm(name) and norm(name) in norm(inner):
                return True, "書き出しの括弧に元の綴りがある：（%s）" % inner[:60]
            # ミドルネームが挟まる型（実測：ジョーディー・グリープ →「Geordie Wade Greep」）。
            # 名前の語が**順番どおり全部**入っているときだけ通す。
            if len(toks) >= 2:
                pat = r"\b" + r"\b.{0,24}?\b".join(re.escape(t) for t in toks) + r"\b"
                if re.search(pat, inner, re.I):
                    return True, "書き出しの括弧に元の綴りがある：（%s）" % inner[:60]
    return False, "題「%s」が探している名前と別物" % (core or title)


def judge_article(name, title, text):
    """採ってよいか。★2つとも通ったときだけ True。"""
    ok_name, why_name = name_matches(name, title, text)
    kind, why_kind = article_kind(title, text)
    if not ok_name:
        return False, kind, why_name
    if kind != "artist":
        return False, kind, why_kind
    return True, kind, "%s／%s" % (why_name, why_kind)


def _extract(api, title, lang, timeout=40):
    u2 = api + "?" + urllib.parse.urlencode({
        "action": "query", "prop": "extracts", "explaintext": 1,
        "titles": title, "format": "json", "redirects": 1})
    code2, body2 = get(u2, timeout=timeout)
    if code2 != 200:
        return "", u2
    try:
        pages = json.loads(body2)["query"]["pages"]
        return (list(pages.values())[0].get("extract") or ""), u2
    except Exception:
        return "", u2


def wikipedia(name, lang="en"):
    """要約と本文をそのまま。★要約しない・言い換えない（後で機械照合するため）。

    ★1件目を鵜呑みにしない。上位5件を開いて、**2つの関所を両方通った記事**だけを採る。
      関所1＝その記事は人・バンドの記事か（作品・映画・一覧・会社・衛星は落とす）。
      関所2＝その記事は探している本人か（題が名前と一致／別の文字体系なら括弧の綴り）。
      1つも通らなければ `found=False`。
      **見つからないのに一番近いものを当てはめるのが一番いけない**（憲法・推測で埋めない）。
    """
    api = "https://%s.wikipedia.org/w/api.php" % lang
    u = api + "?" + urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": name,
        "srlimit": 6, "format": "json"})
    code, body = get(u)
    if code != 200:
        return {"ok": False, "http": code, "src": u}
    try:
        hits = json.loads(body)["query"]["search"]
    except Exception:
        return {"ok": False, "http": code, "src": u}
    if not hits:
        return {"ok": True, "found": False, "src": u, "why": "検索で1件も出ない"}

    best = None
    tried = []
    for h in hits[:5]:
        title = h["title"]
        text, u2 = _extract(api, title, lang)
        ok, kind, why = judge_article(name, title, text)
        tried.append({"title": title, "kind": kind, "ok": ok,
                      "why": why[:160], "chars": len(text or "")})
        if ok and (best is None or len(text or "") > len(best["text"] or "")):
            best = {"title": title, "text": text, "src": u2, "why": why}
        time.sleep(0.3)
        if best and len(tried) >= 3:
            break
    if not best:
        return {"ok": True, "found": False, "src": u,
                "why": "本人の記事が見つからない（関所1＝人の記事か／関所2＝本人か を通るものが無い）",
                "tried": tried}
    return {"ok": True, "found": True, "title": best["title"],
            "url": "https://%s.wikipedia.org/wiki/%s" % (
                lang, urllib.parse.quote(best["title"].replace(" ", "_"))),
            "tried": tried, "why": best["why"],
            "text": best["text"][:60000], "src": best["src"]}


def selftest(path=None, verbose=False):
    """★再発したら機械が落ちる。見本は実物のWikipediaから引いたもの
    （tools/sekisho/wiki_cases.json ・作ったのは tools/_1026_fetch_cases.py）。
    たまごさんが名指しした4件（TURNSTILE→改札機／Trueno→車／IO→木星の衛星／
    Riddim Saunter→フジロック）が必ず入っている。"""
    p = path or os.path.join(HERE, "sekisho", "wiki_cases.json")
    if not os.path.exists(p):
        print("見本が無い：%s" % p)
        return 2
    d = json.loads(io.open(p, encoding="utf-8").read())
    cases = d["cases"]
    bad = []
    for c in cases:
        got, kind, why = judge_article(c["name"], c["title"], c["lead"])
        want = bool(c["expectArtist"])
        mark = "ok " if got == want else "NG "
        if got != want:
            bad.append((c, got, kind, why))
        if verbose or got != want:
            print("%s %-22s %-34s 期待=%-5s 出た=%-5s [%s] %s" % (
                mark, c["name"][:22], c["title"][:34], want, got, kind, why[:70]))
    print("---")
    print("見本 %d件 ／ 合わない %d件（見本の採取 %s）" % (len(cases), len(bad), d.get("takenAt")))
    if bad:
        print("★落ちた。直すまで仕入れに進まないこと。")
        return 1
    print("★全部通った。")
    return 0


def audit(repair=False):
    """★1件ずつ手で直さない。今ある素材を機械で全部見て、同じ型をまとめて洗い出す（要るなら直す）。

    repair=True のときは、本人でない記事を `rejectedArticle` に移して `found=False` にする。
    ★消さない・上書きしない（何を採っていたかが後から見えないと、直したことが確かめられない）。
    """
    rows = []
    for fn in sorted(os.listdir(RAW)) if os.path.isdir(RAW) else []:
        if not fn.endswith(".json"):
            continue
        p = os.path.join(RAW, fn)
        d = json.loads(io.open(p, encoding="utf-8").read())
        dirty = False
        for lang in ("wikipedia_en", "wikipedia_ja"):
            w = d.get(lang) or {}
            if not w.get("found"):
                continue
            ok, kind, why = judge_article(d["name"], w.get("title") or "",
                                          w.get("text") or "")
            if not ok:
                rows.append({"file": fn, "name": d["name"], "lang": lang[-2:],
                             "title": w.get("title"), "kind": kind, "why": why})
                if repair:
                    w["rejectedArticle"] = {"title": w.get("title"), "url": w.get("url"),
                                            "kind": kind, "why": why,
                                            "rejectedAt": time.strftime("%F %T"),
                                            "by": "shiire_fetch --audit --repair（1026番）"}
                    w["found"] = False
                    w["why"] = "本人の記事ではなかった：%s" % why
                    for k in ("title", "url", "text", "src"):
                        w.pop(k, None)
                    d[lang] = w
                    dirty = True
        if dirty:
            io.open(p, "w", encoding="utf-8").write(
                json.dumps(d, ensure_ascii=False, indent=1))
    print("■ 素材（status/shiire_raw）で本人の記事でないものを採っていた：%d件" % len(rows))
    for r in rows:
        print("  %-26s %s → %-36s [%s] %s" % (
            r["name"][:26], r["lang"], (r["title"] or "")[:36], r["kind"], r["why"][:60]))
    if repair:
        print("★%d件を found=false に落とした（採っていた記事は rejectedArticle に残してある）。" % len(rows))
        names = sorted({r["name"] for r in rows})
        print("★取り直しが要る組（Mac側で走らせる）：")
        print("   python3 tools/shiire_fetch.py --names " +
              " ".join('"%s"' % n for n in names))
    return rows


def identify_ok(cands, need=95, gap=10):
    """★この名前で曲を引いてよいか。**1位が強いだけでは足りない。2位と離れていること。**

    なぜ（2026-09-23 実測）：
      "IO" は MusicBrainz の1位が **ブラジル・ポルトアレグレのアンビエント奏者**（score 100）、
      2位が **カナダの実験音楽家**（95）、3位が **オーストリアのテクノ3人組**（90）。
      フジロック'26 に出る IO が誰なのかを、この並びから決めることはできない。
      それでも1位の mbid で曲を引くと、**別人の曲が99曲そのまま入ってくる。**
      （akiko の棚に矢野顕子 を入れたのと同じ事故。skill sekisho-artist-song）
      "Trueno" も同じで 100（アルゼンチンのラッパー）対 96（豪のEDM）。
    → **1位が95以上、かつ2位と10以上離れているときだけ**曲を引く。
      離れていなければ **曲を1曲も引かない。**「たぶんこの人」で埋めない。
    """
    if not cands:
        return False, "MusicBrainzに候補が1件も無い"
    top = cands[0]
    if not top.get("mbid"):
        return False, "1位に mbid が無い"
    s1 = top.get("score") or 0
    if s1 < need:
        return False, "同定の1位が弱い（score %s < %s）" % (s1, need)
    s2 = (cands[1].get("score") or 0) if len(cands) > 1 else 0
    if s1 - s2 < gap:
        return False, ("同名が並んでいて本人を決められない（1位 %s「%s／%s／%s」 対 "
                       "2位 %s「%s／%s／%s」）。★決められないので曲を引かない。"
                       % (s1, top.get("name"), top.get("area") or "地域不明",
                          top.get("disambiguation") or "説明なし",
                          s2, cands[1].get("name"), cands[1].get("area") or "地域不明",
                          cands[1].get("disambiguation") or "説明なし"))
    return True, "1位 %s・2位 %s（%s差）で本人を決められる" % (s1, s2, s1 - s2)


def artist_urls(mbid):
    """MusicBrainzの「この人の外部リンク」。★ここに本物の橋がある。

    MusicBrainzは artist に Wikipedia / Wikidata / 公式サイト のURLを関係として持っている。
    つまり **mbid と Wikipedia の記事は、こちらが推測しなくても向こうで繋がっている。**
    同名が並んで1位2位が僅差でも、「1位の外部リンクが、いま採った記事と同じ」なら、
    それは別々の2つの出どころが同じ人を指したということ＝同定の裏が取れた、と言ってよい。
    """
    u = "https://musicbrainz.org/ws/2/artist/%s?inc=url-rels&fmt=json" % mbid
    code, body = get(u, timeout=25)
    if code != 200:
        return {"ok": False, "http": code, "src": u}
    try:
        rels = json.loads(body).get("relations") or []
    except Exception:
        return {"ok": False, "http": code, "src": u}
    return {"ok": True, "src": u,
            "urls": [{"type": r.get("type"),
                      "url": ((r.get("url") or {}).get("resource") or "")}
                     for r in rels]}


def _wiki_page_key(url):
    m = re.match(r"https?://([a-z\-]+)\.wikipedia\.org/wiki/(.+)$", url or "")
    if not m:
        return None
    return m.group(1) + ":" + norm(urllib.parse.unquote(m.group(2)).replace("_", " "))


def wikidata_titles(qid):
    """Wikidataの項目が指しているWikipediaの題（en/ja）。

    ★MusicBrainzの外部リンクは、いまはWikipediaを直接持たず **Wikidata だけ**のことが多い
      （2026-09-23 実測：Turnstile も Mogwai も GRAPEVINE も wikipedia の関係が無い）。
      Wikidata を1回引けば、そこから同じ人のWikipediaの題が出る。橋は繋がったまま。
    """
    u = "https://www.wikidata.org/wiki/Special:EntityData/%s.json" % qid
    code, body = get(u, timeout=25)
    if code != 200:
        return {}
    try:
        ent = list(json.loads(body)["entities"].values())[0]
        sl = ent.get("sitelinks") or {}
    except Exception:
        return {}
    out = {}
    for site, lang in (("enwiki", "en"), ("jawiki", "ja")):
        t = (sl.get(site) or {}).get("title")
        if t:
            out[lang] = t
    return out


def cross_check(mbid, wiki_urls):
    """MusicBrainzの1位と、採ったWikipediaの記事が**同じものを指しているか**。

    戻り値: ("confirmed"|"contradicted"|"unknown", 説明, 生のURL一覧)
    """
    got = artist_urls(mbid)
    if not got.get("ok"):
        return "unknown", "MusicBrainzの外部リンクが読めなかった（HTTP %s）" % got.get("http"), got
    mine = {_wiki_page_key(u) for u in wiki_urls if _wiki_page_key(u)}
    theirs = {_wiki_page_key(x["url"]) for x in got["urls"] if _wiki_page_key(x["url"])}
    via = "MusicBrainzのWikipediaリンク"
    if not theirs:
        # Wikidata経由で橋を架け直す（いまのMusicBrainzはこちらしか持っていないことが多い）
        qids = [re.search(r"/(Q\d+)\s*$", x["url"]).group(1)
                for x in got["urls"]
                if "wikidata.org/wiki/Q" in (x["url"] or "")
                and re.search(r"/(Q\d+)\s*$", x["url"])]
        for q in qids[:1]:
            time.sleep(0.3)
            for lang, t in (wikidata_titles(q) or {}).items():
                theirs.add(lang + ":" + norm(t))
            if theirs:
                via = "MusicBrainz→Wikidata（%s）→Wikipedia" % q
    if not theirs:
        return "unknown", "MusicBrainz側にWikipedia／Wikidataのリンクが無い", got
    if not mine:
        return "unknown", "こちらにWikipediaの記事が無い", got
    both = mine & theirs
    if both:
        return "confirmed", ("MusicBrainzの1位とWikipediaの記事が同じものを指している"
                             "（%s／%s）" % (via, "・".join(sorted(both)))), got
    return "contradicted", ("MusicBrainzの1位が指すWikipedia（%s）と、こちらが採った記事（%s）が"
                            "違う。★別人の疑い。" % ("・".join(sorted(theirs))[:80],
                                              "・".join(sorted(mine))[:80])), got


def works(mbid):
    """★曲名を人間の記憶から書かない。**識別子から引く。**

    MusicBrainz の release-group（アルバム）と recording（曲）を、
    そのアーティストの mbid から直接引く。ここで取れた曲名は
    「recording の mbid が付いた曲名」なので、**名前が似た別人の曲ではない**。
    （akiko の棚に矢野顕子 を入れた事故は、ここを名前一致でやったから起きた）
    """
    out = {"releaseGroups": [], "recordings": []}
    u = ("https://musicbrainz.org/ws/2/release-group?artist=%s&type=album|ep|single"
         "&fmt=json&limit=60" % mbid)
    code, body = get(u, timeout=30)
    if code == 200:
        try:
            for rg in json.loads(body).get("release-groups") or []:
                out["releaseGroups"].append({
                    "mbid": rg.get("id"), "title": rg.get("title"),
                    "date": rg.get("first-release-date"),
                    "type": rg.get("primary-type"),
                    "secondary": rg.get("secondary-types") or []})
        except Exception:
            pass
    out["releaseGroups"].sort(key=lambda r: r.get("date") or "")
    out["src_rg"] = u
    time.sleep(1.1)
    u2 = ("https://musicbrainz.org/ws/2/recording?artist=%s&fmt=json&limit=100" % mbid)
    code2, body2 = get(u2, timeout=30)
    if code2 == 200:
        try:
            seen = set()
            for rc in json.loads(body2).get("recordings") or []:
                t = (rc.get("title") or "").strip()
                if not t or t.lower() in seen:
                    continue
                seen.add(t.lower())
                out["recordings"].append({"mbid": rc.get("id"), "title": t,
                                          "first": rc.get("first-release-date"),
                                          "len": rc.get("length")})
        except Exception:
            pass
    out["src_rec"] = u2
    return out


def one(name):
    rec = {"name": name, "takenAt": time.strftime("%F %T"),
           "musicbrainz": musicbrainz(name)}
    time.sleep(1.1)                      # MusicBrainzの作法（1秒に1回まで）
    rec["wikipedia_en"] = wikipedia(name, "en")
    time.sleep(0.4)
    rec["wikipedia_ja"] = wikipedia(name, "ja")
    time.sleep(0.4)
    # 同定の1位が十分に強いときだけ、その mbid で作品を引く（弱いときは引かない＝別人の曲を混ぜない）
    cands = (rec["musicbrainz"].get("candidates") or []) if rec["musicbrainz"].get("ok") else []
    ok_id, why_id = identify_ok(cands)
    # ★同名が並んでいて決められないときでも、諦める前に「橋」を1回だけ見る。
    #   MusicBrainzの1位が持っている外部リンクが、こちらが採ったWikipediaの記事と同じなら、
    #   別々の2つの出どころが同じ人を指したということ＝裏が取れた（推測ではない）。
    wiki_urls = [ (rec.get("wikipedia_en") or {}).get("url"),
                  (rec.get("wikipedia_ja") or {}).get("url") ]
    wiki_urls = [u for u in wiki_urls if u]
    if cands and cands[0].get("mbid") and (cands[0].get("score") or 0) >= 95 and wiki_urls:
        time.sleep(1.1)
        verdict, why_x, _raw = cross_check(cands[0]["mbid"], wiki_urls)
        rec["crossCheck"] = {"verdict": verdict, "why": why_x}
        if verdict == "confirmed" and not ok_id:
            ok_id, why_id = True, "同名が並んでいたが裏が取れた：%s" % why_x
        elif verdict == "contradicted":
            ok_id, why_id = False, why_x
    rec["identifyOk"] = ok_id
    rec["identifyWhy"] = why_id
    if ok_id:
        top = cands[0]
        rec["works"] = works(top["mbid"])
        rec["worksOf"] = {"mbid": top["mbid"], "name": top["name"],
                          "score": top["score"]}
    else:
        rec["works"] = None
        rec["worksWhyNot"] = why_id
    return rec


def queue_names(n):
    sys.path.insert(0, HERE)
    import fes_meibo
    r = fes_meibo.coverage()
    out = []
    for f in r["festivals"]:
        for h in f["queue"]:
            nm = h["name"]
            if any(w in nm for w in SKIP):
                continue
            if os.path.exists(os.path.join(RAW, slug(nm) + ".json")):
                continue
            out.append(nm)
            if len(out) >= n:
                return out
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", nargs="*", default=[])
    ap.add_argument("--from-queue", type=int, default=0)
    ap.add_argument("--selftest", action="store_true",
                    help="見本で関所を試す（通信しない・再発したらここで落ちる）")
    ap.add_argument("--audit", action="store_true",
                    help="今ある素材の誤爆を機械で洗い出す（通信しない）")
    ap.add_argument("--repair", action="store_true",
                    help="--audit と一緒に。洗い出した誤爆をまとめて found=false に落とす")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest(verbose=a.verbose)
    if a.audit:
        if selftest() != 0:
            print("★見本が通らない関所で洗い出しても意味がない。先に関所を直すこと。")
            return 1
        audit(repair=a.repair)
        return 0
    # ★集めに行く前に必ず見本を試す。関所が壊れたまま集めると嘘の素材が増える。
    if selftest() != 0:
        print("★見本が通らないので集めない。関所を直してから。")
        return 1
    names = list(a.names)
    if a.from_queue:
        names += queue_names(a.from_queue)
    if not names:
        print("名前がありません")
        return 1
    os.makedirs(RAW, exist_ok=True)
    done = []
    for nm in names:
        rec = one(nm)
        p = os.path.join(RAW, slug(nm) + ".json")
        io.open(p, "w", encoding="utf-8").write(
            json.dumps(rec, ensure_ascii=False, indent=1))
        mb = rec["musicbrainz"]
        wk = rec["wikipedia_en"]
        done.append(nm)
        print("%-34s MB=%s Wiki=%s(%d字)" % (
            nm[:34],
            (mb.get("candidates") or [{}])[0].get("mbid", "-")[:8] if mb.get("ok") else "NG",
            (wk.get("title") or "-")[:24] if wk.get("ok") else "NG",
            len(wk.get("text") or "")))
    print("集めた %d組 → status/shiire_raw/" % len(done))
    return 0


if __name__ == "__main__":
    sys.exit(main())
