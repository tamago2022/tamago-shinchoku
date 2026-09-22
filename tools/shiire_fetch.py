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
#   "IO" の1件目は **木星の衛星イオ**。名前が一致しただけの別物を素材にすると、
#   そこから書いた「事実」は全部嘘になる。だから音楽の記事らしさで選び直す。
MUSIC_WORDS = ("band", "singer", "rapper", "musician", "album", "discography",
               "record label", "songwriter", "duo", "group formed",
               "ミュージシャン", "バンド", "歌手", "ラッパー", "アルバム", "音楽")
MUSIC_TITLE = ("(band)", "(musician)", "(rapper)", "(singer)", "(duo)",
               "(group)", "(musical", "(album)", "（バンド）", "（歌手）")


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

    ★1件目を鵜呑みにしない。上位3件の本文を見て、**音楽の記事らしいもの**を採る。
      どれも音楽らしくなければ `found=False, why="音楽の記事が見つからない"` で返す。
      **見つからないのに一番近いものを当てはめるのが一番いけない**（憲法・推測で埋めない）。
    """
    api = "https://%s.wikipedia.org/w/api.php" % lang
    u = api + "?" + urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": name,
        "srlimit": 4, "format": "json"})
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
    for h in hits[:3]:
        title = h["title"]
        text, u2 = _extract(api, title, lang)
        head = (text or "")[:900].lower()
        score = 0
        if any(w in title.lower() for w in MUSIC_TITLE):
            score += 3
        score += sum(1 for w in MUSIC_WORDS if w in head)
        tried.append({"title": title, "score": score, "chars": len(text or "")})
        if score >= 2 and (best is None or score > best["score"]):
            best = {"title": title, "score": score, "text": text, "src": u2}
        time.sleep(0.3)
    if not best:
        return {"ok": True, "found": False, "src": u,
                "why": "音楽の記事が見つからない（名前が別物と一致している）",
                "tried": tried}
    return {"ok": True, "found": True, "title": best["title"],
            "url": "https://%s.wikipedia.org/wiki/%s" % (
                lang, urllib.parse.quote(best["title"].replace(" ", "_"))),
            "tried": tried,
            "text": best["text"][:60000], "src": best["src"]}


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
    top = cands[0] if cands else None
    if top and (top.get("score") or 0) >= 90 and top.get("mbid"):
        rec["works"] = works(top["mbid"])
        rec["worksOf"] = {"mbid": top["mbid"], "name": top["name"],
                          "score": top["score"]}
    else:
        rec["works"] = None
        rec["worksWhyNot"] = "同定の1位が弱い（score<90）ので曲を引いていない"
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
    a = ap.parse_args()
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
