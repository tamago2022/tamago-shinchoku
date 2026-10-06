#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【スポークスハブ】1人のアーティストを軸に、両方向のカバーを集めてSpotifyのプレイリストに積む係。

  方向A ＝ そのアーティストが**他人の曲をカバー**したもの
  方向B ＝ **他人がそのアーティストの曲をカバー**したもの

★アーティスト名を差し替えるだけで、次の人でそのまま回る。それがこの係の存在理由。

━━ なぜ MusicBrainz を軸にするか（推測ではない）━━
  Spotifyは「これはカバーか」を答えない（作詞作曲クレジットをAPIで返さない）。
  曲名が同じだけで繋ぐのは憲法第22条違反（akiko × AKIKO の事故と同じ形）。
  MusicBrainz は **work（楽曲）** と **recording（録音）** を別物として持ち、
  work に composer/lyricist/writer の関係が付く。
    ・そのアーティストの録音の work に、本人が作者として入っていない → **方向A**
    ・そのアーティストが作者の work に、別人の録音がある → **方向B**
  ＝「名前が同じ」ではなく「同じworkに繋がっている」で判定する。これが関所を通る形。
  出典は work のURL（作者と全録音がそこに載っている）。1曲ずつ控える。

  ★MusicBrainz は投稿型なので、**これ1本では断定しない**（関所：事実と出典）。
    最後の20曲は2本目の出典（公式/報道/Wikipedia）を人手で `shutten2` に入れて初めて通す。

━━ 鍵 ━━
  Spotifyの access_token は次の順で探す。無ければ何もしないで終わる（勝手に課金しない）。
    1) 環境変数 SPOKES_SPOTIFY_TOKEN
    2) ~/.tamago/spotify_token.txt（1行・access_token だけ・1時間で切れる）
    3) tools/spotify_ninshou.py の refresh_token（＝一度同意すれば以後ゼロ。こちらが本命）

━━ 口 ━━
  python3 tools/spokes_hub.py --artist "Ed Sheeran" --tameshi
  python3 tools/spokes_hub.py --artist "Ed Sheeran" --atsumeru          # MusicBrainzで候補を集める
  python3 tools/spokes_hub.py --artist "Ed Sheeran" --awaseru           # Spotifyに実在する物だけ残す
  python3 tools/spokes_hub.py --artist "Ed Sheeran" --playlist "エドシーラン" --shirabe
  python3 tools/spokes_hub.py --artist "Ed Sheeran" --playlist "エドシーラン" --ireru --hoshii 20
  python3 tools/spokes_hub.py --artist "Ed Sheeran" --playlist "エドシーラン" --modoshi
  python3 tools/spokes_hub.py --artist "Ed Sheeran" --hyou              # 1枚のHTMLにする
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

MB = "https://musicbrainz.org/ws/2"
API = "https://api.spotify.com/v1"
UA = "tamago-spokes-hub/1.0 ( eggypop2010@gmail.com )"
MB_MACHI = 1.1          # MusicBrainzの決まり：1秒に1本まで
SAKUSHA_REL = ("composer", "writer", "lyricist", "arranger")

# ★素人カバー／カラオケ／量産物を入口で落とす（憲法：棚出しの判断はたまごさん、仕入れで濁らせない）
NG_NAME = ("karaoke", "tribute", "made famous by", "made popular by", "cover band",
           "backing track", "instrumental version", "playback", "ameritz", "the hit crew",
           "hit co", "starlite", "sing along", "cover guru", "lullaby", "rockabye baby",
           "8-bit", "8 bit", "piano tribute", "midi", "workout", "meditation", "study music",
           "kidz bop", "the cover", "cover versions", "guitar backing")
MIN_FOLLOWERS = 20000   # ★これ未満は「素人かもしれない」側に倒して入れない


# ───────────────────────── 下ごしらえ ─────────────────────────

def base(artist):
    slug = re.sub(r"[^a-z0-9]+", "-", artist.lower()).strip("-") or "artist"
    d = os.path.join(REPO, "status", "spokes", slug)
    os.makedirs(d, exist_ok=True)
    return d


def save(path, obj):
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load(path, default=None):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"\((?:feat|with|featuring)[^)]*\)", " ", s)
    s = re.sub(r"\s-\s(?:live|remix|acoustic|radio edit|remaster(?:ed)?).*$", " ", s)
    keep = [c for c in s if c.isalnum() or c == " "]
    return " ".join("".join(keep).split())


_last = [0.0]


def mb(path, **q):
    q["fmt"] = "json"
    url = "%s/%s?%s" % (MB, path, urllib.parse.urlencode(q))
    wait = MB_MACHI - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                _last[0] = time.time()
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            _last[0] = time.time()
            if e.code in (503, 429):
                time.sleep(2 + i * 2)
                continue
            raise
        except Exception:
            _last[0] = time.time()
            time.sleep(2 + i * 2)
    raise SystemExit("MusicBrainzが返してくれませんでした: " + url)


def token():
    t = os.environ.get("SPOKES_SPOTIFY_TOKEN")
    if t:
        return t.strip()
    p = os.path.expanduser("~/.tamago/spotify_token.txt")
    if os.path.exists(p):
        t = io.open(p, encoding="utf-8").read().strip()
        if t:
            return t
    import spotify_ninshou
    return spotify_ninshou.access_token()


def sp(tok, path, method="GET", payload=None):
    url = path if path.startswith("http") else API + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": "Bearer " + tok,
                                          "Content-Type": "application/json"})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(int(e.headers.get("Retry-After", "2")) + 1)
                continue
            if e.code in (500, 502, 503):
                time.sleep(2 + i)
                continue
            raise SystemExit("Spotifyが %d を返しました: %s %s\n%s"
                             % (e.code, method, path, e.read().decode()[:300]))
    raise SystemExit("Spotifyが混んでいて通りませんでした: " + path)


# ───────────────────────── ① 本人を識別子で決める ─────────────────────────

def dousei(artist, tok):
    """★名前の字面で繋がない。SpotifyのartistidとMusicBrainzのMBIDを、
    お互いのリンクで突き合わせてから先へ進む（憲法第22条）。"""
    d = sp(tok, "/search?q=%s&type=artist&limit=10" % urllib.parse.quote(artist))
    cands = (d.get("artists") or {}).get("items") or []
    spa = None
    for a in cands:
        if norm(a["name"]) == norm(artist):
            spa = a
            break
    if not spa:
        raise SystemExit("Spotifyに「%s」ちょうどの名前のアーティストが居ません" % artist)

    m = mb("artist", query='artist:"%s"' % artist, limit=10)
    best = None
    for a in m.get("artists", []):
        if norm(a["name"]) == norm(artist):
            best = a
            break
    if not best:
        raise SystemExit("MusicBrainzに「%s」が見つかりません" % artist)

    rel = mb("artist/" + best["id"], inc="url-rels")
    spotify_urls = [r["url"]["resource"] for r in rel.get("relations", [])
                    if "open.spotify.com/artist/" in r.get("url", {}).get("resource", "")]
    ura = any(spa["id"] in u for u in spotify_urls)
    return {"name": spa["name"], "spotifyId": spa["id"],
            "spotifyUrl": spa["external_urls"]["spotify"],
            "mbid": best["id"], "mbUrl": "https://musicbrainz.org/artist/" + best["id"],
            "mbSpotifyLinks": spotify_urls,
            "uradori": "MBの公式リンクがSpotifyのartist idと一致" if ura
                       else "★MB側にSpotifyリンクが無い（名前一致のみ）"}


# ───────────────────────── ② MusicBrainzで両方向の候補を集める ─────────────────────────

def mb_only(artist):
    """★鍵が無いときの同定。MusicBrainz側だけで決め、Spotifyのartist idは
    MBが持っている公式リンクから取る（名前の字面では決めない）。"""
    m = mb("artist", query='artist:"%s"' % artist, limit=10)
    best = next((a for a in m.get("artists", []) if norm(a["name"]) == norm(artist)), None)
    if not best:
        raise SystemExit("MusicBrainzに「%s」が見つかりません" % artist)
    rel = mb("artist/" + best["id"], inc="url-rels")
    links = [r["url"]["resource"] for r in rel.get("relations", [])
             if "open.spotify.com/artist/" in r.get("url", {}).get("resource", "")]
    sid = links[0].rstrip("/").split("/")[-1].split("?")[0] if links else ""
    return {"name": best["name"], "spotifyId": sid,
            "spotifyUrl": links[0] if links else "",
            "mbid": best["id"], "mbUrl": "https://musicbrainz.org/artist/" + best["id"],
            "mbSpotifyLinks": links,
            "uradori": "MBの公式リンクからSpotifyのartist idを取った" if links
                       else "★MBにSpotifyリンクが無い"}


def sakusha(work):
    out = []
    for r in work.get("relations", []):
        if r.get("type") in SAKUSHA_REL and r.get("artist"):
            out.append({"name": r["artist"]["name"], "mbid": r["artist"]["id"],
                        "yaku": r["type"]})
    return out


def atsumeru(artist, honnin, limit_works=400, limit_recs=600):
    d = base(artist)
    st = load(os.path.join(d, "mb.json"), {}) or {}
    mbid = honnin["mbid"]

    # ── 方向B：本人が作者の work → 別人の録音
    if "works" not in st:
        works, off = [], 0
        while off < limit_works:
            r = mb("work", artist=mbid, limit=100, offset=off, inc="artist-rels")
            got = r.get("works", [])
            works += got
            print("  work %d件" % len(works), flush=True)
            if len(got) < 100:
                break
            off += 100
        st["works"] = [{"mbid": w["id"], "title": w["title"],
                        "sakusha": sakusha(w)} for w in works]
        save(os.path.join(d, "mb.json"), st)

    if "dirB" not in st:
        dirB, seen = [], set()
        mine = [w for w in st["works"]
                if any(s["mbid"] == mbid for s in w["sakusha"])]
        print("  本人が作者のwork: %d件" % len(mine), flush=True)
        for i, w in enumerate(mine):
            r = mb("recording", work=w["mbid"], limit=100, inc="artist-credits")
            for rec in r.get("recordings", []):
                cred = rec.get("artist-credit") or []
                ids = [c["artist"]["id"] for c in cred if c.get("artist")]
                if mbid in ids or not ids:
                    continue
                who = " ".join((c.get("name") or "") + (c.get("joinphrase") or "")
                               for c in cred).strip()
                k = (norm(who), norm(rec["title"]))
                if k in seen:
                    continue
                seen.add(k)
                dirB.append({"houkou": "B", "enja": who, "kyoku": rec["title"],
                             "moto": honnin["name"],
                             "sakusha": [s["name"] for s in w["sakusha"]],
                             "workMbid": w["mbid"], "workTitle": w["title"],
                             "recMbid": rec["id"]})
            if i % 20 == 19:
                print("  B: %d/%d work、候補 %d" % (i + 1, len(mine), len(dirB)), flush=True)
                st["dirB"] = dirB
                save(os.path.join(d, "mb.json"), st)
        st["dirB"] = dirB
        save(os.path.join(d, "mb.json"), st)

    # ── 方向A：本人の録音 → その work の作者に本人が居ない
    if "recs" not in st:
        recs, off = [], 0
        while off < limit_recs:
            r = mb("recording", artist=mbid, limit=100, offset=off, inc="work-rels")
            got = r.get("recordings", [])
            for rec in got:
                ws = [x["work"]["id"] for x in rec.get("relations", [])
                      if x.get("work")]
                recs.append({"mbid": rec["id"], "title": rec["title"], "works": ws})
            print("  recording %d件" % len(recs), flush=True)
            if len(got) < 100:
                break
            off += 100
        st["recs"] = recs
        save(os.path.join(d, "mb.json"), st)

    if "dirA" not in st:
        cache = st.get("workcache", {})
        dirA, seen = [], set()
        todo = sorted({w for r in st["recs"] for w in r["works"]})
        print("  本人の録音が繋がるwork: %d件" % len(todo), flush=True)
        for i, wid in enumerate(todo):
            if wid not in cache:
                w = mb("work/" + wid, inc="artist-rels")
                cache[wid] = {"title": w["title"], "sakusha": sakusha(w)}
                if i % 20 == 19:
                    st["workcache"] = cache
                    save(os.path.join(d, "mb.json"), st)
                    print("  A: %d/%d work" % (i + 1, len(todo)), flush=True)
            c = cache[wid]
            if not c["sakusha"] or any(s["mbid"] == mbid for s in c["sakusha"]):
                continue                                  # 自作 → 方向Aではない
            rec = next(r for r in st["recs"] if wid in r["works"])
            k = norm(rec["title"])
            if k in seen:
                continue
            seen.add(k)
            dirA.append({"houkou": "A", "enja": honnin["name"], "kyoku": rec["title"],
                         "moto": "／".join(s["name"] for s in c["sakusha"]),
                         "sakusha": [s["name"] for s in c["sakusha"]],
                         "workMbid": wid, "workTitle": c["title"],
                         "recMbid": rec["mbid"]})
        st["workcache"] = cache
        st["dirA"] = dirA
        save(os.path.join(d, "mb.json"), st)

    st["dirB_clean"] = dirB_shiboru(st)
    save(os.path.join(d, "mb.json"), st)
    print("集まりました： 方向A %d件 ／ 方向B %d件（生 %d件）"
          % (len(st.get("dirA", [])), len(st["dirB_clean"]), len(st.get("dirB", []))))
    return st


NG_TITLE = ("remix", "instrumental", "karaoke", "extended", "edit)", "mashup",
            "acapella", "a cappella", "medley", "demo", "live", "version)")


def dirB_shiboru(st):
    """★ここが肝。本人が作者というだけでは「本人の曲」ではない。

    Ed Sheeran は Cold Water（Major Lazer）や Little Things（One Direction）のように
    **他人のために書いた曲**が大量にある。それを他人が歌っているのは「カバー」ではなく
    元の持ち主が歌っているだけ。曲名の一致で繋がないのと同じ理屈で、ここも落とす。
    → 本人自身がその work を録音している物だけを「本人の曲」として残す。
    """
    mine = {w for r in st.get("recs", []) for w in r["works"]}
    out = []
    for x in st.get("dirB", []):
        if x["workMbid"] not in mine:
            continue
        t = x["kyoku"].lower()
        if any(g in t for g in NG_TITLE):
            continue
        out.append(x)
    return out


# ───────────────────────── ③ Spotifyに実在する物だけ残す ─────────────────────────

def hazure(name):
    n = norm(name)
    return any(g in n for g in NG_NAME)


def awaseru(artist, honnin, tok, kagiri=0):
    d = base(artist)
    st = load(os.path.join(d, "mb.json"), {}) or {}
    ok = load(os.path.join(d, "spotify.json"), {"atari": [], "hazure": [], "nashi": []})
    sumi = set((x["houkou"], x["kyoku"], x["enja"]) for x in ok["atari"]) | \
           set(tuple(x) for x in ok.get("sumi", []))
    afoll = {}

    kouho = st.get("dirA", []) + (st.get("dirB_clean") or dirB_shiboru(st))
    for n, k in enumerate(kouho):
        key = (k["houkou"], k["kyoku"], k["enja"])
        if key in sumi:
            continue
        sumi.add(key)
        if hazure(k["enja"]):
            ok["hazure"].append(dict(k, riyuu="カラオケ／量産物の名前"))
            continue
        q = urllib.parse.quote('track:"%s" artist:"%s"' % (k["kyoku"], k["enja"]))
        r = sp(tok, "/search?q=%s&type=track&limit=20" % q)
        hits = (r.get("tracks") or {}).get("items") or []
        if not hits:
            r = sp(tok, "/search?q=%s&type=track&limit=20"
                   % urllib.parse.quote("%s %s" % (k["enja"], k["kyoku"])))
            hits = (r.get("tracks") or {}).get("items") or []
        atari = None
        for t in hits:
            if norm(t["name"]) != norm(k["kyoku"]):
                continue
            # ★ artist id で照合する。方向Aは本人のidそのもの、方向Bは名前ちょうど一致
            if k["houkou"] == "A":
                if not any(a["id"] == honnin["spotifyId"] for a in t["artists"]):
                    continue
            else:
                if not any(norm(a["name"]) == norm(k["enja"]) for a in t["artists"]):
                    continue
                if any(a["id"] == honnin["spotifyId"] for a in t["artists"]):
                    continue                     # 本人が入っているのはカバーではない
            atari = t
            break
        if not atari:
            ok["nashi"].append(k)
            continue
        aid = next((a["id"] for a in atari["artists"]
                    if k["houkou"] == "A" or norm(a["name"]) == norm(k["enja"])),
                   atari["artists"][0]["id"])
        if aid not in afoll:
            a = sp(tok, "/artists/" + aid)
            afoll[aid] = a.get("followers", {}).get("total", 0)
        if k["houkou"] == "B" and afoll[aid] < MIN_FOLLOWERS:
            ok["hazure"].append(dict(k, riyuu="Spotifyの聴き手が%d人＝素人側に倒した"
                                     % afoll[aid]))
            continue
        ok["atari"].append(dict(k, spotifyId=atari["id"], spotifyUri=atari["uri"],
                                spotifyUrl=atari["external_urls"]["spotify"],
                                spotifyName=atari["name"],
                                spotifyArtists=[a["name"] for a in atari["artists"]],
                                spotifyArtistId=aid, followers=afoll[aid],
                                album=atari["album"]["name"],
                                hatsubai=atari["album"].get("release_date", ""),
                                workUrl="https://musicbrainz.org/work/" + k["workMbid"],
                                recUrl="https://musicbrainz.org/recording/" + k["recMbid"]))
        ok["sumi"] = [list(x) for x in sumi]
        save(os.path.join(d, "spotify.json"), ok)
        if kagiri and len(ok["atari"]) >= kagiri:
            break
    ok["sumi"] = [list(x) for x in sumi]
    save(os.path.join(d, "spotify.json"), ok)
    a = [x for x in ok["atari"] if x["houkou"] == "A"]
    b = [x for x in ok["atari"] if x["houkou"] == "B"]
    print("Spotifyに在った： 方向A %d曲 ／ 方向B %d曲 ／ 無かった %d件 ／ 落とした %d件"
          % (len(a), len(b), len(ok["nashi"]), len(ok["hazure"])))
    return ok


# ───────────────────────── ④ プレイリストに積む ─────────────────────────

def playlist(tok, name):
    url = "/me/playlists?limit=50"
    while url:
        d = sp(tok, url)
        for p in d.get("items", []):
            if norm(p["name"]) == norm(name):
                return p
        url = d.get("next")
    raise SystemExit("プレイリスト「%s」が見つかりません" % name)


def nakami(tok, pid):
    out, url = [], ("/playlists/%s/tracks?limit=100"
                    "&fields=next,items(track(id,uri,name,artists(name)))" % pid)
    while url:
        d = sp(tok, url)
        for it in d.get("items", []):
            t = it.get("track") or {}
            if t.get("id"):
                out.append(t)
        url = d.get("next")
    return out


def erabu(ok, hoshii):
    """★両方向とも5曲以上。人気順ではなく「両方向が並ぶ」を先に満たす。"""
    a = sorted([x for x in ok["atari"] if x["houkou"] == "A"],
               key=lambda x: -x["followers"])
    b = sorted([x for x in ok["atari"] if x["houkou"] == "B"],
               key=lambda x: -x["followers"])
    take, i, j = [], 0, 0
    while len(take) < hoshii and (i < len(a) or j < len(b)):
        if i < len(a) and (len(take) % 2 == 0 or j >= len(b)):
            take.append(a[i]); i += 1
        elif j < len(b):
            take.append(b[j]); j += 1
    return take


def ireru(artist, name, tok, hoshii, honto):
    d = base(artist)
    ok = load(os.path.join(d, "spotify.json"), {"atari": []})
    pl = playlist(tok, name)
    mae = nakami(tok, pl["id"])
    have = set(t["id"] for t in mae)
    print("入れる前： %d曲（Spotifyから取り直した実測）" % len(mae))

    take = [x for x in erabu(ok, hoshii + 10) if x["spotifyId"] not in have][:hoshii]
    na = len([x for x in take if x["houkou"] == "A"])
    print("積むもの %d曲（方向A %d／方向B %d）" % (len(take), na, len(take) - na))
    for x in take:
        print("  %s %s ／ %s  ←%s" % (x["houkou"], x["spotifyName"],
                                      "・".join(x["spotifyArtists"]), x["moto"]))
    if not honto:
        return
    if len(take) < hoshii:
        raise SystemExit("★%d曲そろっていません（%d曲）。足りないまま入れません。"
                         % (hoshii, len(take)))
    for i in range(0, len(take), 100):
        sp(tok, "/playlists/%s/tracks" % pl["id"], "POST",
           {"uris": [x["spotifyUri"] for x in take[i:i + 100]]})
    ato = nakami(tok, pl["id"])
    save(os.path.join(d, "ireta.json"),
         {"at": time.strftime("%F %T"), "playlistId": pl["id"],
          "playlistName": pl["name"],
          "playlistUrl": "https://open.spotify.com/playlist/" + pl["id"],
          "maeTotal": len(mae), "atoTotal": len(ato), "ireta": take})
    print("\n入れました。Spotifyから取り直した曲数： %d → %d" % (len(mae), len(ato)))
    print("戻すとき: python3 tools/spokes_hub.py --artist \"%s\" --playlist \"%s\" --modoshi"
          % (artist, name))


def modoshi(artist, name, tok):
    d = base(artist)
    rec = load(os.path.join(d, "ireta.json"))
    if not rec:
        raise SystemExit("控えがありません")
    pl = playlist(tok, name)
    sp(tok, "/playlists/%s/tracks" % pl["id"], "DELETE",
       {"tracks": [{"uri": x["spotifyUri"]} for x in rec["ireta"]]})
    print("戻しました: %d曲 ／ いま %d曲" % (len(rec["ireta"]), len(nakami(tok, pl["id"]))))


# ──────────── ④' 鍵ゼロで取り直す（公開プレイリスト・embedページ） ────────────

BROWSER_UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                             "AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/126 Safari/537.36")}


def _embed(kind, sid):
    url = "https://open.spotify.com/embed/%s/%s" % (kind, sid)
    html = urllib.request.urlopen(
        urllib.request.Request(url, headers=BROWSER_UA), timeout=30).read().decode(
            "utf-8", "replace")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                  html, re.S)
    return json.loads(m.group(1))["props"]["pageProps"]["state"]["data"]["entity"]


def _moto(t):
    """Spotifyの曲名から『- Live at ...』『(2018 Version)』などの尻尾を落とす。"""
    s = re.split(r"\s-\s", t)[0]
    return norm(s)


def kensho(artist, playlist_id):
    """★Spotifyから取り直す。鍵を使わない＝たまごさんのログインに一切触らない。
    1曲ずつ artist id まで取って、どちら向きかを機械で決める。"""
    d = base(artist)
    honnin = load(os.path.join(d, "honnin.json")) or {}
    st = load(os.path.join(d, "mb.json"), {}) or {}
    sh = load(os.path.join(d, "shutten2.json"), {}) or {}
    me = honnin.get("spotifyId", "")

    ent = _embed("playlist", playlist_id)
    rows = []
    for i, t in enumerate(ent.get("trackList", []), 1):
        tid = (t.get("uri") or "").split(":")[-1]
        te = _embed("track", tid)
        arts = [{"name": a.get("name"),
                 "id": (a.get("uri") or "").split(":")[-1]}
                for a in (te.get("artists") or [])]
        honnin_iru = any(a["id"] == me for a in arts)
        title = t.get("title") or ""
        key = _moto(title)

        hit, houkou = None, None
        for x in st.get("dirA", []):
            if honnin_iru and (_moto(x["kyoku"]) == key or key in norm(x["kyoku"])
                               or norm(x["kyoku"]) in key):
                hit, houkou = x, "A"
                break
        if not hit:
            for x in st.get("dirB_clean", []):
                if honnin_iru:
                    break
                if _moto(x["kyoku"]) != key:
                    continue
                if any(norm(a["name"]) in norm(x["enja"])
                       or norm(x["enja"]) in norm(a["name"]) for a in arts):
                    hit, houkou = x, "B"
                    break
        if not houkou:
            houkou = "本人のオリジナル（元から入っていた）" if honnin_iru else "？"

        shn = {norm(k): v for k, v in sh.items() if not k.startswith("_")}
        src = sh.get(title) or shn.get(norm(title)) or shn.get(key) or {}
        rows.append({"no": i, "title": title,
                     "artists": arts, "houkou": houkou,
                     "spotifyUrl": "https://open.spotify.com/track/" + tid,
                     "moto": src.get("moto") or (hit or {}).get("moto", ""),
                     "shutten2": src.get("url", ""), "shutten2iu": src.get("iu", ""),
                     "workUrl": ("https://musicbrainz.org/work/" + hit["workMbid"]) if hit else "",
                     "recUrl": ("https://musicbrainz.org/recording/" + hit["recMbid"]) if hit else ""})
    out = {"at": time.strftime("%F %T"), "playlist": ent.get("name"),
           "playlistId": playlist_id,
           "playlistUrl": "https://open.spotify.com/playlist/" + playlist_id,
           "total": len(rows), "tracks": rows}
    save(os.path.join(d, "kensho.json"), out)
    print("%s ／ Spotifyから取り直した曲数 %d" % (ent.get("name"), len(rows)))
    for r in rows:
        print(" %2d %-6s %-46s | %-30s | 出典2 %s"
              % (r["no"], r["houkou"][:6], r["title"][:46],
                 "・".join(a["name"] for a in r["artists"])[:30],
                 "有" if r["shutten2"] else "★無"))
    return out


# ───────────────────────── ⑤ 1枚のHTML ─────────────────────────

def hyou(artist, mae=None):
    d = base(artist)
    rec = load(os.path.join(d, "kensho.json")) or {}
    rows = rec.get("tracks", [])
    if not rows:
        raise SystemExit("まだ --kensho を走らせていません")
    tr = []
    for x in rows:
        h = x["houkou"]
        cls = h if h in ("A", "B") else "O"
        muki = {"A": "%s が他人の曲をカバー" % artist,
                "B": "%s の曲を他人がカバー" % artist}.get(h, h)
        shu = []
        if x.get("shutten2"):
            shu.append(("2本目の出典", x["shutten2"]))
        if x.get("workUrl"):
            shu.append(("MusicBrainz 楽曲", x["workUrl"]))
        if x.get("recUrl"):
            shu.append(("MusicBrainz 録音", x["recUrl"]))
        tr.append(
            "<tr><td class=n>%d</td><td class=k><a href='%s' target=_blank>%s</a></td>"
            "<td>%s</td><td class='h %s'>%s</td><td>%s</td><td class=s>%s</td></tr>"
            % (x["no"], x["spotifyUrl"], x["title"],
               "・".join(a["name"] for a in x["artists"]),
               cls, muki, x.get("moto") or "—",
               " ".join("<a href='%s' target=_blank>%s</a>" % (u, t) for t, u in shu)
               or "<span class=nashi>取れなかった</span>"))
    maeN = mae if mae is not None else 0
    html = """<!doctype html><html lang=ja><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>スポークスハブ 1本目：%(artist)s</title>
<style>
:root{--ink:#14110f;--sub:#6b625b;--line:#e3ddd6;--paper:#faf7f2;--a:#8c3b2e;--b:#2e5a8c}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
font:16px/1.75 -apple-system,"Hiragino Sans","Noto Sans JP",sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:56px 22px 90px}
.kicker{font-size:12px;letter-spacing:.32em;color:var(--sub);text-transform:uppercase}
h1{font-size:clamp(28px,4.4vw,44px);line-height:1.25;margin:.25em 0 .1em;letter-spacing:.01em}
.lead{color:var(--sub);font-size:15px;margin:0 0 30px}
.kpi{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 34px}
.kpi div{border:1px solid var(--line);background:#fff;padding:10px 16px;border-radius:2px}
.kpi b{font-size:22px;font-variant-numeric:tabular-nums}
.kpi span{display:block;font-size:11px;letter-spacing:.18em;color:var(--sub)}
table{width:100%%;border-collapse:collapse;background:#fff;border:1px solid var(--line)}
th,td{padding:11px 12px;border-bottom:1px solid var(--line);text-align:left;
vertical-align:top;font-size:14px}
th{font-size:11px;letter-spacing:.16em;color:var(--sub);background:#f4efe8;font-weight:600}
td.n{color:var(--sub);font-variant-numeric:tabular-nums;width:34px}
td.k a{color:var(--ink);font-weight:600;text-decoration:none;border-bottom:1px solid var(--line)}
td.h{font-size:12.5px;white-space:nowrap}
td.h.A{color:var(--a)}td.h.B{color:var(--b)}td.h.O{color:var(--sub)}
.nashi{color:#a33}
td.s{font-size:11.5px}td.s a{color:var(--sub);margin-right:8px}
tr:last-child td{border-bottom:0}
.note{margin-top:26px;font-size:12.5px;color:var(--sub);border-top:1px solid var(--line);
padding-top:14px}
</style><div class=wrap>
<p class=kicker>Spokes Hub ／ 実験1本目</p>
<h1>%(artist)s を軸に、カバーが両方向で並んだ</h1>
<p class=lead>プレイリスト「%(pl)s」／ Spotifyから取り直した曲数 %(mae)d → %(ato)d ／ %(at)s</p>
<div class=kpi>
<div><b>%(ato)d</b><span>SPOTIFY実測</span></div>
<div><b>%(na)d</b><span>%(artist)s がカバー</span></div>
<div><b>%(nb)d</b><span>%(artist)s をカバー</span></div>
</div>
<table><tr><th></th><th>曲（Spotifyへ）</th><th>演っている人</th><th>どちら向きか</th>
<th>誰の曲か（作者）</th><th>出典</th></tr>
%(rows)s</table>
<p class=note>判定は曲名の一致ではなく、MusicBrainzの<b>同じ楽曲(work)</b>に繋がっているかで取った。
作者に本人が入っていなければ「本人が他人の曲をカバー」、本人が作者で別人の録音があれば「他人が本人の曲をカバー」。
出典のリンクに、作者と全録音がそのまま載っている。<br>
<a href="%(plurl)s" target=_blank>プレイリストを開く</a></p>
</div>""" % {"artist": artist, "pl": rec.get("playlist", ""),
             "mae": maeN, "ato": rec.get("total", 0),
             "at": rec.get("at", ""), "rows": "\n".join(tr),
             "na": len([x for x in rows if x["houkou"] == "A"]),
             "nb": len([x for x in rows if x["houkou"] == "B"]),
             "_": 0,
             "plurl": rec.get("playlistUrl", "#")}

    out = os.path.join(REPO, "share", "check",
                       "spokes-hub-%s.html" % re.sub(r"[^a-z0-9]+", "-", artist.lower()))
    with io.open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(out)


# ───────────────────────── 口 ─────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artist", required=True)
    ap.add_argument("--playlist")
    ap.add_argument("--hoshii", type=int, default=20)
    ap.add_argument("--kagiri", type=int, default=0, help="Spotify照合を何曲当たったら止めるか")
    ap.add_argument("--tameshi", action="store_true", help="鍵と同定だけ確かめる")
    ap.add_argument("--atsumeru", action="store_true")
    ap.add_argument("--awaseru", action="store_true")
    ap.add_argument("--shirabe", action="store_true", help="積む物を見るだけ")
    ap.add_argument("--ireru", action="store_true")
    ap.add_argument("--modoshi", action="store_true")
    ap.add_argument("--hyou", action="store_true")
    ap.add_argument("--kensho", help="公開プレイリストのIDを渡すと、鍵ゼロで取り直す")
    ap.add_argument("--mae", type=int, help="入れる前の曲数（表に出す）")
    a = ap.parse_args()

    if a.kensho:
        kensho(a.artist, a.kensho)
        return hyou(a.artist, a.mae) if a.hyou else 0
    if a.hyou:
        return hyou(a.artist, a.mae)

    # ★鍵が要るのは「Spotifyに触るとき」だけ。MusicBrainzで集めるだけなら鍵ゼロで回る。
    kagi_iru = a.awaseru or a.shirabe or a.ireru or a.modoshi or a.tameshi
    tok = token() if kagi_iru else None
    d = base(a.artist)
    honnin = load(os.path.join(d, "honnin.json"))
    if not honnin:
        honnin = dousei(a.artist, tok) if tok else mb_only(a.artist)
        save(os.path.join(d, "honnin.json"), honnin)
    print("本人： %s ／ Spotify %s ／ MB %s ／ 裏取り: %s"
          % (honnin["name"], honnin["spotifyId"], honnin["mbid"], honnin["uradori"]))
    if a.tameshi:
        return 0
    if a.atsumeru:
        atsumeru(a.artist, honnin)
    if a.awaseru:
        awaseru(a.artist, honnin, tok, a.kagiri)
    if a.modoshi:
        return modoshi(a.artist, a.playlist, tok)
    if a.shirabe or a.ireru:
        if not a.playlist:
            raise SystemExit("--playlist が要ります")
        ireru(a.artist, a.playlist, tok, a.hoshii, a.ireru)
    return 0


if __name__ == "__main__":
    sys.exit(main())
