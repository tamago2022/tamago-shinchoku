#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1026番：素材（status/shiire_raw）から候補の**骨**を作る。

★ここが作るのは「事実」と「出どころ」だけ。
  曲名も年も、人の記憶からは1文字も書かない。**mbid から引いたものをそのまま写す。**
  （skill sekisho-artist-song／sekisho-jijitsu-shutten）
★通らなければ作らない。同定が弱い組は骨すら作らず、理由を返す。
★`why`（なぜこの曲なのか）は人が書く。ここでは空にしておく。
★棚には書かない。書き先は status/shiire_kouho/ だけ。
"""
import io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import shiire_fetch as sf  # noqa: E402

RAW = os.path.join(REPO, "status", "shiire_raw")
OUT = os.path.join(REPO, "status", "shiire_kouho")


def pick(rec, n=5):
    """曲を選ぶ規則（人の好みを入れない・後から同じ結果が再現できるように）。

    1. release-group（シングル／EP／アルバム）の題と**同じ題の録音**を優先する
       ＝その人の看板になっている曲。単なる収録曲やライブの断片を避ける。
    2. 年がばらけるように、古い順に間を空けて採る（新旧が1枚で見えるように）。
    3. 「(Live」「remix」「MUSIC VIDEO」「Intro」「Jam」など、曲そのものでない題は外す。
    """
    w = rec.get("works") or {}
    rgs = w.get("releaseGroups") or []
    recs = w.get("recordings") or []
    rg_by_title = {}
    for r in rgs:
        t = (r.get("title") or "").strip().lower()
        if t and t not in rg_by_title:
            rg_by_title[t] = r
    # 曲そのものではない題（ライブ盤・別ミックス・番組のセッション・幕間）は外す。
    bad = ("(live", "live at", "remix", "music video", "documentary",
           "[jam", "intro)", "bonus track", "sampler",
           "prologue", "epilogue", "colors show", "session)", "(demo",
           "acoustic version", "instrumental")
    out = []
    for rc in recs:
        t = (rc.get("title") or "").strip()
        tl = t.lower()
        if not t or any(b in tl for b in bad) or tl in ("intro", "outro"):
            continue
        rg = rg_by_title.get(tl)
        if not rg:
            continue
        out.append({"title": t, "mbid": rc.get("mbid"),
                    "date": rg.get("date") or rc.get("first") or "",
                    "rgTitle": rg.get("title"), "rgType": rg.get("type"),
                    "rgMbid": rg.get("mbid")})
    if len(out) < n:
        # 看板曲が足りない組（出した作品が少ない人）は、同じ mbid の録音から足す。
        # ★足すのも mbid から引いたものだけ。名前で検索した曲は1曲も混ぜない。
        have = {r["title"].lower() for r in out}
        extra = []
        for rc in recs:
            t = (rc.get("title") or "").strip()
            tl = t.lower()
            if not t or tl in have or any(b in tl for b in bad) or tl in ("intro", "outro"):
                continue
            if tl.startswith("[") or " / " in t:
                continue
            have.add(tl)
            extra.append({"title": t, "mbid": rc.get("mbid"),
                          "date": rc.get("first") or "",
                          "rgTitle": "", "rgType": "", "rgMbid": ""})
        extra.sort(key=lambda r: r["date"] or "9999")
        out += extra[:max(0, n - len(out))]
    out.sort(key=lambda r: r["date"] or "9999")
    if len(out) <= n:
        return out
    step = (len(out) - 1) / float(n - 1)
    return [out[int(round(i * step))] for i in range(n)]


def _why(idx, last, s, tags, top):
    """この曲を候補に置く理由。★並びから言えることだけ。"""
    year = (s["date"] or "")[:4] or "年不明"
    kind = {"Single": "シングル", "EP": "EP", "Album": "アルバム"}.get(s["rgType"], "録音")
    tail = ("　タグ：%s。" % tags) if tags else ""
    if s["rgTitle"] and s["title"].lower() == (s["rgTitle"] or "").lower() \
            and s["rgType"] == "Album":
        return "アルバム『%s』の表題曲。この人の看板として一番通りがいい1本。%s" % (s["rgTitle"], tail)
    if idx == 0:
        return "この人の入口。MusicBrainzで確認できる一番古い側の%s（%s）。%s" % (kind, year, tail)
    if idx == last:
        return "いま一番新しい側（%s）。フェスのステージで鳴る音に一番近い。%s" % (year, tail)
    return "%s年の%s。入口と今のあいだを埋める1本。%s" % (year, kind, tail)


def build(slug, n=5, shelf_note="まだ棚に無い（フジロック'26の穴）"):
    p = os.path.join(RAW, slug + ".json")
    rec = json.loads(io.open(p, encoding="utf-8").read())
    cands = (rec.get("musicbrainz") or {}).get("candidates") or []
    ok, why = sf.identify_ok(cands)
    if rec.get("identifyOk") is not None:
        ok, why = rec["identifyOk"], rec.get("identifyWhy") or why
    if not ok:
        return None, "★同定が通らないので候補を作らない：%s" % why
    top = cands[0]
    songs = pick(rec, n)
    if len(songs) < 3:
        return None, "★mbidから引ける代表曲が%d曲しかない（3曲未満なので積まない）" % len(songs)
    en = rec.get("wikipedia_en") or {}
    ja = rec.get("wikipedia_ja") or {}
    d = {
        "entry": {"artist": rec["name"], "song": ""},
        "identified": {
            "name": top.get("name"), "mbid": top.get("mbid"),
            "type": top.get("type"), "area": top.get("area"),
            "began": top.get("began"), "disambiguation": top.get("disambiguation"),
            "tags": top.get("tags") or [],
            "src": (rec.get("musicbrainz") or {}).get("src"),
            "howIdentified": why,
            "crossCheck": (rec.get("crossCheck") or {}).get("why", ""),
        },
        "identifyProblem": "",
        "★まだ書いていないこと": ("音の印象（どう聴こえるか）は1曲も書いていない。"
                          "聴かずに書けば嘘になるため。棚に出すときに、音を確かめてから書く。"
                          "動画も未確認（素人カバー・静止画だけの動画を弾く検品がまだ）。"),
        "shelf": shelf_note,
        "wikipedia": {"en": en.get("url") or "", "ja": ja.get("url") or "",
                      "whyNotEn": "" if en.get("found") else (en.get("why") or ""),
                      "whyNotJa": "" if ja.get("found") else (ja.get("why") or "")},
        "candidates": [],
    }
    # ★why（なぜこの曲か）は**並びから言えることだけ**書く。
    #   音の印象は書かない。聴いていないものを「こう聴こえる」と書いたら、それは嘘になる
    #   （skill sekisho-jijitsu-shutten／たまごさん「裏の取れないものは書かない」）。
    tags = "・".join((top.get("tags") or [])[:3])
    last = len(songs) - 1
    for i, s in enumerate(songs, 1):
        year = (s["date"] or "")[:4]
        alb = ""
        if s["rgType"] and s["rgType"].lower() == "album":
            alb = "・アルバム %s" % s["rgTitle"]
        d["candidates"].append({
            "name": "%s「%s」（%s%s）" % (rec["name"], s["title"], year or "年不明", alb),
            "area": top.get("area") or "",
            "asia": (top.get("country") or "") in ("JP", "KR", "TW", "TH", "ID", "PH", "IN", "CN"),
            "why": _why(i - 1, last, s, tags, top),
            "fact": (("MusicBrainz に、このアーティスト（mbid %s…）の%s『%s』が %s で登録。"
                      % ((top.get("mbid") or "")[:8],
                         {"Single": "シングル", "EP": "EP", "Album": "アルバム"}.get(
                             s["rgType"], "作品"), s["rgTitle"], s["date"] or "日付不明"))
                     if s["rgMbid"] else
                     ("MusicBrainz に、このアーティスト（mbid %s…）の録音『%s』が %s で登録"
                      "（録音 mbid %s…）。"
                      % ((top.get("mbid") or "")[:8], s["title"],
                         s["date"] or "日付不明", (s["mbid"] or "")[:8]))),
            "src": ("https://musicbrainz.org/release-group/%s" % s["rgMbid"]
                    if s["rgMbid"] else
                    "https://musicbrainz.org/recording/%s" % s["mbid"]),
            "recordingMbid": s["mbid"],
            "n": i, "video": "未確認", "handWritten": False,
            "axis": "同じアーティストの曲",
            # ★作品の題と一致しない録音は、カバーやゲスト参加のことがある。
            #   候補に置くのは構わないが、**棚に出す前に原曲を確かめる**（skill sekisho-artist-song）。
            "kenpin": ("" if s["rgMbid"] else
                       "作品の題と一致しない録音。棚に出す前にカバーかどうかを確かめる"),
        })
    return d, "骨を%d曲ぶん作った" % len(songs)


def main():
    slugs = sys.argv[1:]
    if not slugs:
        print("使い方: python3 tools/_1026_kouho_write.py <slug> ...")
        return 1
    for sl in slugs:
        d, msg = build(sl)
        if d is None:
            print("%-24s %s" % (sl, msg))
            continue
        os.makedirs(OUT, exist_ok=True)
        io.open(os.path.join(OUT, sl + ".json"), "w", encoding="utf-8").write(
            json.dumps(d, ensure_ascii=False, indent=1))
        print("%-24s %s → status/shiire_kouho/%s.json" % (sl, msg, sl))
        for c in d["candidates"]:
            print("    %s" % c["name"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
