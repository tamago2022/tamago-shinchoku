#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""プレイリスト「怒り」を作る（2026-10-15）。既存の「ロック反体制」には触らない。

順番：
  1) マガジン「怒れる人々 vol.1」（本番 /magazine/ikareru-01.html）の曲を、マガジンと同じ順で。
     ・おとぼけビ〜バー「ジジイ is waiting for my reaction」の直後に、同じくおとぼけビ〜バー
       「anata watashi daita ato yome no meshi」（たまごさん指示 2026-10-15）。
  2) 続けて Obsidian「怒り 「ふざけんじゃねえ！」が名曲になる瞬間…」にあって、まだ入っていない曲（ノートの順）。
・本人の原曲だけ。カバー・カラオケ・ライブ版は入れない（見分け方は spotify_takoukan.find と同じ）。
・2回目以降は同じプレイリストを、この順に置き換える（増殖しない）。
・鍵：spotify_ninshou.access_token()。ブラウザは使わない。
使い方（Mac）：python3 tools/spotify_ikari.py [--shirabe]
結果：status/spotify/ikari.json と Dispatch への1行。
"""
import json, os, sys, time, urllib.error, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spotify_ninshou as sn
import spotify_takoukan as tk

REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "status", "spotify", "ikari.json")
NAME = "怒り"
DESC = "「ふざけんじゃねえ！」が名曲になる瞬間。マガジン「怒れる人々」の曲順から、怒りの錬金術へ。"

LIVE_OK = {"live_ok": True}
OTO = ["おとぼけビ～バー", "おとぼけビ〜バー", "Otoboke Beaver", "OTOBOKE BEAVER"]

MAGAZINE = [
    ("Ado", "うっせぇわ", ["Usseewa"], ["Ado"]),
    ("THE TIMERS", "FM東京", ["FM Tokyo"], ["THE TIMERS", "ザ・タイマーズ"]),
    ("RCサクセション", "サマータイム・ブルース", ["Summertime Blues"], ["RCサクセション", "RC Succession"]),
    ("X-Ray Spex", "Oh Bondage Up Yours!", ["Oh Bondage! Up Yours!", "Oh Bondage Up Yours"], ["X-Ray Spex"]),
    ("吉幾三", "俺ら東京さ行ぐだ", ["Ora Tokyo sa Iguda"], ["吉幾三", "Ikuzo Yoshi"]),
    ("打首獄門同好会", "日本の米は世界一", [], ["打首獄門同好会", "Uchikubigokumon-Doukoukai"]),
    ("打首獄門同好会", "はたらきたくない", [], ["打首獄門同好会", "Uchikubigokumon-Doukoukai"]),
    ("おとぼけビ〜バー", "ジジイ is waiting for my reaction", ["Dirty old fart is waiting for my reaction", "ジジイ is Waiting For My Reaction"], OTO),
    ("おとぼけビ〜バー", "anata watashi daita ato yome no meshi", ["あなたわたし抱いたあと嫁の飯", "Anata Watashi Daita Ato Yome No Meshi"], OTO),
    ("Lenny Kravitz", "Rock and Roll Is Dead", [], ["Lenny Kravitz"]),
    ("Prince", "Rock and Roll Is Alive! (And It Lives in Minneapolis)", ["Rock 'N' Roll Is Alive! (And It Lives In Minneapolis)", "Rock and Roll Is Alive"], ["Prince"]),
]

NOTE = [
    ("X-Ray Spex", "Oh Bondage Up Yours!", [], ["X-Ray Spex"]),
    ("Rina Sawayama", "STFU!", ["STFU"], ["Rina Sawayama"]),
    ("Amyl and the Sniffers", "U Should Not Be Doing That", [], ["Amyl and The Sniffers"]),
    ("Nina Simone", "Mississippi Goddam", ["Mississippi Goddamn"], ["Nina Simone"], LIVE_OK),
    ("Stevie Wonder", "You Haven't Done Nothin'", ["You Haven't Done Nothin"], ["Stevie Wonder"]),
    ("Fela Kuti", "Zombie", [], ["Fela Kuti", "Fela Anikulapo Kuti"]),
    ("Lily Allen", "Fuck You", ["F**k You"], ["Lily Allen"]),
    ("Pulp", "Common People", [], ["Pulp"]),
    ("Kelis", "Caught Out There", [], ["Kelis"]),
    ("The Linda Lindas", "Racist, Sexist Boy", [], ["The Linda Lindas"]),
    ("The Jam", "Town Called Malice", ["A Town Called Malice"], ["The Jam"]),
    ("Ado", "うっせぇわ", [], ["Ado"]),
    ("おとぼけビ〜バー", "サラダ取り分けませんことよ", ["I won't dish out salads", "I won't share my salad"], OTO),
    ("おとぼけビ〜バー", "アイドンビリーブマイ母性", ["I am not maternal", "I Don't Believe My Bosei"], OTO),
    ("BOØWY", "MORAL", [], ["BOØWY", "BOOWY"]),
    ("BOØWY", "IMAGE DOWN", [], ["BOØWY", "BOOWY"]),
    ("THE BLUE HEARTS", "NO NO NO", [], ["THE BLUE HEARTS", "ザ・ブルーハーツ"]),
    ("THE BLUE HEARTS", "青空", ["Aozora"], ["THE BLUE HEARTS", "ザ・ブルーハーツ"]),
    ("RCサクセション", "サマータイム・ブルース", [], ["RCサクセション", "RC Succession"]),
    ("吉幾三", "俺ら東京さ行ぐだ", [], ["吉幾三", "Ikuzo Yoshi"]),
    ("中島みゆき", "ファイト！", ["ファイト!", "Fight!"], ["中島みゆき", "Miyuki Nakajima"]),
    ("尾崎豊", "卒業", ["Sotsugyo"], ["尾崎豊", "Yutaka Ozaki"]),
    ("岡林信康", "くそくらえ節", [], ["岡林信康", "Nobuyasu Okabayashi"]),
    ("THE TIMERS", "原発賛成音頭", [], ["THE TIMERS", "ザ・タイマーズ"]),
    ("ミドリ", "ゆきこさん", [], ["ミドリ", "Midori"]),
    ("女王蜂", "火炎", ["Kaen"], ["女王蜂", "QUEEN BEE"]),
    ("大森靖子", "マジックミラー", ["Magic Mirror"], ["大森靖子", "Seiko Oomori"]),
    ("筋肉少女帯", "踊るダメ人間", [], ["筋肉少女帯", "Kinniku Shōjo Tai", "Kinniku Shojo Tai"]),
    ("打首獄門同好会", "はたらきたくない", [], ["打首獄門同好会", "Uchikubigokumon-Doukoukai"]),
    ("ずっと真夜中でいいのに。", "秒針を噛む", ["Byoushinwo Kamu"], ["ずっと真夜中でいいのに。", "ZUTOMAYO"]),
    ("Ado", "逆光", ["Gyakkou"], ["Ado"]),
    ("椎名林檎", "罪と罰", ["Tsumi to Batsu"], ["椎名林檎", "Sheena Ringo", "Ringo Sheena"]),
    ("岡崎体育", "MUSIC VIDEO", [], ["岡崎体育", "Okazaki Taiiku"]),
    ("amazarashi", "命にふさわしい", [], ["amazarashi"]),
    ("THE STALIN", "ロマンチスト", [], ["THE STALIN", "ザ・スターリン"]),
    ("サンボマスター", "世界はそれを愛と呼ぶんだぜ", [], ["サンボマスター", "Sambomaster"]),
    ("The Clash", "Clampdown", [], ["The Clash"]),
    ("The Clash", "Career Opportunities", [], ["The Clash"]),
    ("Sex Pistols", "God Save the Queen", [], ["Sex Pistols"]),
    ("Bikini Kill", "Rebel Girl", [], ["Bikini Kill"]),
    ("Le Tigre", "Deceptacon", [], ["Le Tigre"]),
    ("Green Day", "American Idiot", [], ["Green Day"]),
    ("Green Day", "Holiday", [], ["Green Day"]),
    ("IDLES", "Danny Nedelko", [], ["IDLES"]),
    ("IDLES", "Never Fight a Man with a Perm", [], ["IDLES"]),
    ("Bad Religion", "21st Century (Digital Boy)", ["21st Century Digital Boy"], ["Bad Religion"]),
    ("Chumbawamba", "Tubthumping", [], ["Chumbawamba"]),
    ("The Specials", "Ghost Town", [], ["The Specials"]),
    ("Rage Against the Machine", "Bulls on Parade", [], ["Rage Against The Machine"]),
    ("Rage Against the Machine", "Sleep Now in the Fire", [], ["Rage Against The Machine"]),
    ("Beastie Boys", "Sabotage", [], ["Beastie Boys"]),
    ("Public Enemy", "Fight the Power", [], ["Public Enemy"]),
    ("Molotov", "Gimme Tha Power", ["Gimme the Power"], ["Molotov"]),
    ("Rina Sawayama", "XS", [], ["Rina Sawayama"]),
    ("Olivia Rodrigo", "all-american bitch", [], ["Olivia Rodrigo"]),
    ("Olivia Rodrigo", "good 4 u", [], ["Olivia Rodrigo"]),
    ("CeeLo Green", "Fuck You", ["F**k You", "Forget You"], ["CeeLo Green", "Cee Lo Green"]),
    ("Dolly Parton", "9 to 5", ["9 To 5"], ["Dolly Parton"]),
    ("Gil Scott-Heron", "The Revolution Will Not Be Televised", [], ["Gil Scott-Heron"]),
    ("Marvin Gaye", "Inner City Blues (Make Me Wanna Holler)", ["Inner City Blues"], ["Marvin Gaye"]),
    # 棚の6曲（Lily Allen／Stevie Wonder／吉幾三／X-Ray Spex／おとぼけビ〜バー／Nina Simone）は上で全部出ている
]


def get_playlist(tok):
    st = sn._load(tk.PL_STORE) or {}
    pid = st.get(NAME)
    if pid:
        try:
            tk.call(tok, "/playlists/%s?fields=id" % pid)
            return pid
        except urllib.error.HTTPError:
            pass
    # 鍵の控えに無くても、同名がすでにあればそれを使う（増殖させない）
    nxt = "/me/playlists?limit=50"
    while nxt:
        r = tk.call(tok, nxt)
        for p in r.get("items") or []:
            if p and p.get("name") == NAME:
                st[NAME] = p["id"]; sn._save600(tk.PL_STORE, st)
                return p["id"]
        nxt = r.get("next")
    body = {"name": NAME, "description": DESC, "public": False}
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
    want_keys = set()
    n = 0
    for part, lst in (("magazine", MAGAZINE), ("note", NOTE)):
        for s in lst:
            key = (tk.norm(s[0]), tk.norm(s[1]))
            if key in want_keys:
                continue  # ノート側の重複（マガジンに既にある曲）
            want_keys.add(key)
            n += 1
            want = "%s「%s」" % (s[0], s[1])
            r = tk.find(tok, s)
            if r and r["id"] in seen:
                print("%2d = %s すでに入っている" % (n, want), flush=True); continue
            if r:
                seen.add(r["id"]); r.update(n=n, want=want, part=part); got.append(r)
                print("%2d ○ %s → %s / %s（%s）" % (n, want, r["name"], r["artists"], r["album"]), flush=True)
            else:
                miss.append({"n": n, "want": want, "part": part})
                print("%2d × %s 見つからず" % (n, want), flush=True)
            time.sleep(0.25)
    res = {"at": time.strftime("%F %T"), "name": NAME, "got": len(got), "miss": miss, "tracks": got}
    if not shirabe and got:
        pid = get_playlist(tok)
        uris = [g["uri"] for g in got]
        tk.put_items(tok, pid, uris[:100])
        pl = tk.call(tok, "/playlists/%s?fields=items.total,tracks.total" % pid)
        total = (pl.get("items") or pl.get("tracks") or {}).get("total")
        res.update({"playlist_id": pid, "url": "https://open.spotify.com/playlist/%s" % pid, "total_on_spotify": total})
        sn.dispatch("Spotify「%s」を作りました %s ／ %d曲入り・入らなかった曲：%s" % (
            NAME, res["url"], len(got), "、".join(m["want"] for m in miss) or "なし"))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("RESULT", json.dumps({k: res.get(k) for k in ("url", "got", "total_on_spotify", "miss")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
