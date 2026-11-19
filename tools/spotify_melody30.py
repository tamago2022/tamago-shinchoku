#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""プレイリスト「ブルーノ・マーズから辿る、メロディーの天才30人」を作る（2026-10-24）。

・曲：Obsidian「ブルーノ・マーズから辿る、メロディーの天才30人」の表Ⅰ〜Ⅲ、30人×3曲＝90曲をノートの順で。
  番外（山下達郎）はノートで「90曲の本編ではなく別枠」とあるので入れない。
・各曲は表に書かれた演奏者の原曲（カバー・カラオケ・ライブ・リミックスは除外。見分けは spotify_takoukan.find）。
  テイラー・スウィフトは原盤を優先（Taylor's Version は原盤が無いときだけ）。
・見つからない曲は飛ばして控える。2回目以降は同じプレイリストを置き換える（増殖しない）。
・鍵：spotify_ninshou.access_token()。ブラウザは使わない。マガジン・棚・サイトには触らない。
使い方（Mac）：python3 tools/spotify_melody30.py [--shirabe]
結果：status/spotify/melody30.json
"""
import json, os, sys, time, urllib.error, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spotify_ninshou as sn
import spotify_takoukan as tk

REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "status", "spotify", "melody30.json")
NAME = "ブルーノ・マーズから辿る、メロディーの天才30人"
DESC = "ブルーノ・マーズから辿るメロディーの天才30人（下書き）"

TS = ["Taylor Swift"]
SONGS = [
    # Ⅰ
    ("Bruno Mars", "Treasure", [], ["Bruno Mars"]),
    ("Bruno Mars", "Locked Out of Heaven", [], ["Bruno Mars"]),
    ("Bruno Mars", "Just the Way You Are", [], ["Bruno Mars"]),
    ("Michael Jackson", "Billie Jean", [], ["Michael Jackson"]),
    ("Michael Jackson", "Beat It", [], ["Michael Jackson"]),
    ("Michael Jackson", "Don't Stop 'Til You Get Enough", [], ["Michael Jackson"]),
    ("Stevie Wonder", "Sir Duke", [], ["Stevie Wonder"]),
    ("Stevie Wonder", "I Wish", [], ["Stevie Wonder"]),
    ("Stevie Wonder", "Isn't She Lovely", [], ["Stevie Wonder"]),
    ("Prince", "Kiss", [], ["Prince"]),
    ("Prince", "When Doves Cry", [], ["Prince"]),
    ("Prince", "1999", [], ["Prince"]),
    ("Bee Gees", "How Deep Is Your Love", [], ["Bee Gees"]),
    ("Bee Gees", "Night Fever", [], ["Bee Gees"]),
    ("Bee Gees", "Stayin' Alive", [], ["Bee Gees"]),
    ("George Michael", "Faith", [], ["George Michael"]),
    ("George Michael", "Freedom! '90", ["Freedom 90", "Freedom! 90"], ["George Michael"]),
    ("Wham!", "Last Christmas", [], ["Wham!"]),
    ("Mariah Carey", "Fantasy", [], ["Mariah Carey"]),
    ("Mariah Carey", "Always Be My Baby", [], ["Mariah Carey"]),
    ("Mariah Carey", "All I Want for Christmas Is You", [], ["Mariah Carey"]),
    ("Lionel Richie", "All Night Long (All Night)", ["All Night Long"], ["Lionel Richie"]),
    ("Lionel Richie", "Hello", [], ["Lionel Richie"]),
    ("Commodores", "Easy", [], ["Commodores"]),
    ("Pharrell Williams", "Happy", [], ["Pharrell Williams", "Pharrell"]),
    ("Pharrell Williams", "Frontin'", ["Frontin"], ["Pharrell Williams", "Pharrell"]),
    ("Daft Punk", "Get Lucky", [], ["Daft Punk"]),
    ("Britney Spears", "...Baby One More Time", ["Baby One More Time"], ["Britney Spears"]),
    ("Backstreet Boys", "I Want It That Way", [], ["Backstreet Boys"]),
    ("Taylor Swift", "Shake It Off", [], TS),
    ("ABBA", "Dancing Queen", [], ["ABBA"]),
    ("ABBA", "Mamma Mia", [], ["ABBA"]),
    ("ABBA", "Gimme! Gimme! Gimme! (A Man After Midnight)", ["Gimme! Gimme! Gimme!", "Gimme Gimme Gimme"], ["ABBA"]),
    ("Babyface", "When Can I See You", [], ["Babyface"]),
    ("Boyz II Men", "I'll Make Love to You", [], ["Boyz II Men"]),
    ("Boyz II Men", "End of the Road", [], ["Boyz II Men"]),
    # Ⅱ
    ("The Beatles", "Hey Jude", [], ["The Beatles"]),
    ("The Beatles", "Yesterday", [], ["The Beatles"]),
    ("Paul McCartney", "Maybe I'm Amazed", [], ["Paul McCartney"]),
    ("John Lennon", "Imagine", [], ["John Lennon"]),
    ("John Lennon", "Woman", [], ["John Lennon"]),
    ("John Lennon", "(Just Like) Starting Over", ["Just Like Starting Over", "Starting Over"], ["John Lennon"]),
    ("The Beach Boys", "God Only Knows", [], ["The Beach Boys"]),
    ("The Beach Boys", "Wouldn't It Be Nice", [], ["The Beach Boys"]),
    ("The Beach Boys", "Good Vibrations", [], ["The Beach Boys"]),
    ("Dionne Warwick", "Walk On By", [], ["Dionne Warwick"]),
    ("Carpenters", "(They Long To Be) Close To You", ["Close To You", "They Long To Be Close To You"], ["Carpenters", "The Carpenters"]),
    ("B.J. Thomas", "Raindrops Keep Fallin' on My Head", ["Raindrops Keep Falling on My Head"], ["B.J. Thomas", "BJ Thomas"]),
    ("Elton John", "Your Song", [], ["Elton John"]),
    ("Elton John", "Rocket Man (I Think It's Going to Be a Long, Long Time)", ["Rocket Man"], ["Elton John"]),
    ("Elton John", "I'm Still Standing", [], ["Elton John"]),
    ("Carole King", "I Feel the Earth Move", [], ["Carole King"]),
    ("Carole King", "It's Too Late", [], ["Carole King"]),
    ("The Shirelles", "Will You Love Me Tomorrow", [], ["The Shirelles", "Shirelles"]),
    ("Billy Joel", "Uptown Girl", [], ["Billy Joel"]),
    ("Billy Joel", "Piano Man", [], ["Billy Joel"]),
    ("Billy Joel", "The Longest Time", [], ["Billy Joel"]),
    ("Paul Simon", "50 Ways to Leave Your Lover", ["Fifty Ways to Leave Your Lover"], ["Paul Simon"]),
    ("Paul Simon", "You Can Call Me Al", [], ["Paul Simon"]),
    ("Simon & Garfunkel", "Bridge Over Troubled Water", [], ["Simon & Garfunkel"]),
    ("Taylor Swift", "Love Story", [], TS),
    ("Taylor Swift", "Blank Space", [], TS),
    ("Taylor Swift", "You Belong With Me", [], TS),
    ("Ed Sheeran", "Shape of You", [], ["Ed Sheeran"]),
    ("Ed Sheeran", "Perfect", [], ["Ed Sheeran"]),
    ("Ed Sheeran", "Thinking Out Loud", [], ["Ed Sheeran"]),
    ("Aerosmith", "I Don't Want to Miss a Thing", [], ["Aerosmith"]),
    ("Toni Braxton", "Un-Break My Heart", ["Unbreak My Heart"], ["Toni Braxton"]),
    ("Celine Dion", "Because You Loved Me", [], ["Celine Dion", "Céline Dion"]),
    ("Electric Light Orchestra", "Mr. Blue Sky", [], ["Electric Light Orchestra"]),
    ("Electric Light Orchestra", "Livin' Thing", [], ["Electric Light Orchestra"]),
    ("Electric Light Orchestra", "Telephone Line", [], ["Electric Light Orchestra"]),
    ("The Temptations", "My Girl", [], ["The Temptations"]),
    ("Smokey Robinson & The Miracles", "The Tracks of My Tears", ["Tracks of My Tears"], ["Smokey Robinson", "The Miracles"]),
    ("Smokey Robinson & The Miracles", "The Tears of a Clown", ["Tears of a Clown"], ["Smokey Robinson", "The Miracles"]),
    # Ⅲ
    ("竹内まりや", "プラスティック・ラブ", ["Plastic Love"], ["竹内まりや", "Mariya Takeuchi"]),
    ("竹内まりや", "元気を出して", ["Genki wo Dashite"], ["竹内まりや", "Mariya Takeuchi"]),
    ("竹内まりや", "駅", ["Eki"], ["竹内まりや", "Mariya Takeuchi"]),
    ("荒井由実", "ルージュの伝言", ["Rouge no Dengon"], ["荒井由実", "Yumi Arai", "松任谷由実", "Yumi Matsutoya"]),
    ("荒井由実", "やさしさに包まれたなら", ["Yasashisa ni Tsutsumareta Nara"], ["荒井由実", "Yumi Arai", "松任谷由実", "Yumi Matsutoya"]),
    ("荒井由実", "中央フリーウェイ", ["Chuo Freeway"], ["荒井由実", "Yumi Arai", "松任谷由実", "Yumi Matsutoya"]),
    ("小田和正", "ラブ・ストーリーは突然に", ["ラブストーリーは突然に", "Love Story wa Totsuzen ni"], ["小田和正", "Kazumasa Oda"]),
    ("小田和正", "たしかなこと", ["Tashikana Koto"], ["小田和正", "Kazumasa Oda"]),
    ("小田和正", "言葉にできない", ["Kotoba ni Dekinai"], ["小田和正", "Kazumasa Oda"]),
    ("KUWATA BAND", "スキップ・ビート", ["SKIPPED BEAT", "スキップビート"], ["KUWATA BAND"]),
    ("桑田佳祐", "波乗りジョニー", ["Naminori Johnny"], ["桑田佳祐", "Keisuke Kuwata"]),
    ("サザンオールスターズ", "希望の轍", ["Kibou no Wadachi"], ["サザンオールスターズ", "Southern All Stars"]),
    ("久保田利伸", "LA・LA・LA LOVE SONG", ["LA LA LA LOVE SONG", "LALALA LOVE SONG"], ["久保田利伸", "Toshinobu Kubota"]),
    ("久保田利伸", "Missing", [], ["久保田利伸", "Toshinobu Kubota"]),
    ("久保田利伸", "流星のサドル", ["Ryusei no Saddle"], ["久保田利伸", "Toshinobu Kubota"]),
]
# ノートにトラックIDが直接書かれていた曲（そのIDのアーティスト・題名を確かめてから使う）
NOTE_TRACK = {"スキップ・ビート": "0x8MBe69cqFHeKtd2aAihH"}


# 下見（--shirabe 2026-10-24）で原曲でない版を拾った曲への個別の指定
#   ng：題名・アルバム名に出たら外す語／pref：アルバム名に入っていたら優先
FIX = {
    "Last Christmas": {"ng": ["pudding mix", "remix", "mix"], "pref": ["Make It Big", "Last Christmas"]},
    "Hey Jude": {"album_ng": ["love"], "pref": ["1 (Remastered)", "1967-1970", "Hey Jude"]},
    "Frontin'": {"ng": ["club mix", "instrumental", "a cappella"]},
    "How Deep Is Your Love": {"pref": ["Saturday Night Fever"]},
    "Night Fever": {"pref": ["Saturday Night Fever"]},
    "Stayin' Alive": {"pref": ["Saturday Night Fever"]},
    "Will You Love Me Tomorrow": {"album_ng": ["remember when"], "pref": ["Tonight's The Night", "Tonight’s The Night"]},
}
# 言葉にできない：原曲はオフコース（1982）。小田和正名義はセルフカバー（LOOKING BACK 2）なのでオフコースを先に探す
FIRST_ARTISTS = {"言葉にできない": ["オフコース", "Off Course", "OFF COURSE"]}


def find2(tok, s):
    """spotify_takoukan.find と同じ見分け方に、FIX の個別指定を足したもの。"""
    disp, title, alts, artists = s[:4]
    fx = FIX.get(title, {})
    titles = [tk.norm(x) for x in [title] + alts]
    arts = [tk.norm(a) for a in artists]
    queries = ["track:%s artist:%s" % (title, a) for a in artists[:2]] + ["%s %s" % (title, artists[0])]
    cands = []
    for q in queries:
        for market in ("JP", "US"):
            try:
                r = tk.call(tok, "/search?" + urllib.parse.urlencode({"q": q, "type": "track", "limit": 10, "market": market}))
            except urllib.error.HTTPError:
                continue
            for it in (r.get("tracks") or {}).get("items") or []:
                if not it or not it.get("id"):
                    continue
                an = [tk.norm(a.get("name")) for a in it.get("artists") or []]
                main_art = an[0] if an else ""
                if not any(a == main_art or (len(a) >= 4 and a in main_art) for a in arts):
                    continue
                nm = tk.norm(it.get("name"))
                base = tk.norm(tk.re.split(r"\s[-–]\s|\(|（", it.get("name") or "")[0])
                if not any(t == nm or t == base or (len(t) >= 4 and nm.startswith(t)) for t in titles):
                    continue
                alb = (it.get("album") or {}).get("name") or ""
                if tk.bad(it.get("name") or "", alb):
                    continue
                low = ((it.get("name") or "") + " / " + alb).lower()
                if any(w in low for w in fx.get("ng", [])):
                    continue
                if any(alb.lower() == w for w in fx.get("album_ng", [])):
                    continue
                atype = (it.get("album") or {}).get("album_type") or ""
                score = (it.get("popularity") or 0) + (15 if atype in ("album", "single") else 0) \
                    - (20 if atype == "compilation" else 0) + (10 if nm == titles[0] or base == titles[0] else 0) \
                    + (60 if any(p.lower() in alb.lower() for p in fx.get("pref", [])) else 0)
                cands.append((score, it))
        if cands and not fx.get("pref"):
            break
    if not cands:
        return None
    cands.sort(key=lambda x: -x[0])
    it = cands[0][1]
    return {"uri": it["uri"], "id": it["id"], "name": it["name"],
            "artists": ", ".join(a["name"] for a in it["artists"]), "album": (it.get("album") or {}).get("name"),
            "url": (it.get("external_urls") or {}).get("spotify")}


def pick(tok, s):
    first = FIRST_ARTISTS.get(s[1])
    if first:
        r = tk.find(tok, (s[0], s[1], s[2], first))
        if r:
            return r
    if s[1] in FIX:
        return find2(tok, s)
    if s[3] is TS:
        return find_ts(tok, s)
    return tk.find(tok, s)


def find_ts(tok, s):
    """テイラーは原盤を先に探し、無ければ Taylor's Version。"""
    tk.NG.append("taylor's version"); tk.NG.append("taylor’s version")
    try:
        r = tk.find(tok, s)
    finally:
        tk.NG.remove("taylor's version"); tk.NG.remove("taylor’s version")
    return r or tk.find(tok, s)


def from_note_id(tok, s):
    tid = NOTE_TRACK.get(s[1])
    if not tid:
        return None
    try:
        it = tk.call(tok, "/tracks/%s?market=JP" % tid)
    except urllib.error.HTTPError:
        return None
    an = [tk.norm(a.get("name")) for a in it.get("artists") or []]
    if not an or not any(tk.norm(a) == an[0] for a in s[3]):
        return None
    nm = tk.norm(it.get("name"))
    if not any(tk.norm(t) == nm or nm.startswith(tk.norm(t)) for t in [s[1]] + s[2]):
        return None
    return {"uri": it["uri"], "id": it["id"], "name": it["name"],
            "artists": ", ".join(a["name"] for a in it["artists"]), "album": (it.get("album") or {}).get("name"),
            "url": (it.get("external_urls") or {}).get("spotify")}


def get_playlist(tok):
    st = sn._load(tk.PL_STORE) or {}
    pid = st.get(NAME)
    body = {"name": NAME, "description": DESC, "public": False}
    if pid:
        try:
            tk.call(tok, "/playlists/%s?fields=id" % pid)
            return pid
        except urllib.error.HTTPError:
            pass
    try:
        p = tk.call(tok, "/me/playlists", "POST", body)
    except urllib.error.HTTPError:
        me = tk.call(tok, "/me")
        p = tk.call(tok, "/users/%s/playlists" % urllib.parse.quote(me["id"]), "POST", body)
    st[NAME] = p["id"]
    sn._save600(tk.PL_STORE, st)
    return p["id"]


def main():
    shirabe = "--shirabe" in sys.argv
    tok = sn.access_token()
    got, miss, seen = [], [], set()
    for i, s in enumerate(SONGS, 1):
        want = "%s「%s」" % (s[0], s[1])
        if "--only" in sys.argv and s[1] not in FIX and s[1] not in FIRST_ARTISTS:
            continue
        r = from_note_id(tok, s) or pick(tok, s)
        if r and r["id"] in seen:
            r = None
        if r:
            seen.add(r["id"]); r["n"] = i; r["want"] = want; got.append(r)
            print("%2d ○ %s → %s / %s（%s）" % (i, want, r["name"], r["artists"], r["album"]), flush=True)
        else:
            miss.append({"n": i, "want": want})
            print("%2d × %s 見つからず" % (i, want), flush=True)
        time.sleep(0.3)
    res = {"at": time.strftime("%F %T"), "name": NAME, "got": len(got), "miss": miss, "tracks": got}
    if not shirabe and got:
        pid = get_playlist(tok)
        uris = [g["uri"] for g in got]
        tk.put_items(tok, pid, uris)  # 100曲以内なので1回で置き換え
        # 読み戻して順番・曲数を確かめる
        back = []
        for ep in ("items", "tracks"):
            try:
                tk.call(tok, "/playlists/%s/%s?limit=1" % (pid, ep)); break
            except urllib.error.HTTPError:
                continue
        url = "/playlists/%s/%s?limit=100" % (pid, ep)
        while url:
            pg = tk.call(tok, url)
            back += [((x.get("track") or x.get("item") or {}) or {}).get("id") for x in pg.get("items") or []]
            url = pg.get("next")
        res.update({"playlist_id": pid, "url": "https://open.spotify.com/playlist/%s" % pid,
                    "total_on_spotify": len(back), "order_ok": back == [g["id"] for g in got]})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("RESULT", json.dumps({k: res.get(k) for k in ("url", "got", "total_on_spotify", "order_ok", "miss")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
