#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""プレイリスト「多幸感ポップス」を、決めた30曲の順で作る（2026-10-14）。

・各曲は本人の原曲だけ（カバー・カラオケ・インスト・ライブ・リミックス・〜風は入れない）。
  見分け方：検索結果の「アーティスト」に本人（日本語名・英語名どちらでも）が入っていること＋題名の一致＋除外語。
・見つからない曲は飛ばして控える。
・2回目以降は同じプレイリストの中身を、この順に置き換える（増殖しない）。
・鍵：tools/spotify_ninshou.py の access_token()（鍵帳の refresh_token から自動）。ブラウザは使わない。
結果：status/spotify/takoukan.json と Dispatch への1行。
使い方（Mac）：python3 tools/spotify_takoukan.py [--shirabe]   # --shirabe は探すだけで書き込まない
"""
import json, os, re, sys, time, unicodedata, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spotify_ninshou as sn

REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "status", "spotify", "takoukan.json")
PL_STORE = os.path.join(sn.TDIR, "spotify_playlists.json")
API = "https://api.spotify.com/v1"
NAME = "多幸感ポップス"
DESC = "聴くだけで顔がゆるむ、日本と海外の多幸感ポップス30曲。"

# (表示名, 曲名, [曲名の別表記], [アーティスト名の候補])
SONGS = [
    ("EPO", "う、ふ、ふ、ふ、", ["うふふふ", "U.FU.FU.FU"], ["EPO"]),
    ("山下達郎", "LOVELAND, ISLAND", ["LOVELAND ISLAND"], ["山下達郎", "Tatsuro Yamashita"]),
    ("山下達郎", "高気圧ガール", ["Koukiatsu Girl"], ["山下達郎", "Tatsuro Yamashita"]),
    ("竹内まりや", "不思議なピーチパイ", ["Fushigina Peach Pie"], ["竹内まりや", "Mariya Takeuchi"]),
    ("大滝詠一", "君は天然色", ["Kimi wa Tennenshoku"], ["大滝詠一", "Eiichi Ohtaki", "Eiichi Ootaki"]),
    ("ORIGINAL LOVE", "サンシャイン ロマンス", ["サンシャインロマンス", "Sunshine Romance"], ["ORIGINAL LOVE", "オリジナル・ラブ"]),
    ("小沢健二", "ラブリー", ["Lovely"], ["小沢健二", "Kenji Ozawa"]),
    ("ピチカート・ファイヴ", "東京は夜の七時", ["Twiggy Twiggy", "Tokyo wa Yoru no Shichiji", "The Night Is Still Young"], ["PIZZICATO FIVE", "ピチカート・ファイヴ"]),
    ("星野源", "SUN", [], ["星野源", "Gen Hoshino"]),
    ("スガ シカオ", "午後のパレード", ["Gogo no Parade"], ["スガ シカオ", "Shikao Suga", "スガシカオ"]),
    ("斉藤和義", "歩いて帰ろう", ["Aruite Kaerou"], ["斉藤和義", "Kazuyoshi Saito"]),
    ("桑田佳祐", "波乗りジョニー", ["Naminori Johnny"], ["桑田佳祐", "Keisuke Kuwata"]),
    ("フリッパーズ・ギター", "恋とマシンガン", ["Young, Alive, In Love", "Koi to Machine Gun"], ["フリッパーズ・ギター", "Flipper's Guitar", "The Flipper's Guitar"]),
    ("藤井 風", "きらり", ["Kirari"], ["藤井 風", "Fujii Kaze", "藤井風"]),
    ("ウルフルズ", "バンザイ〜好きでよかった〜", ["バンザイ ~好きでよかった~", "バンザイ", "Banzai"], ["ウルフルズ", "Ulfuls"]),
    ("Stevie Wonder", "Sir Duke", [], ["Stevie Wonder"]),
    ("Earth, Wind & Fire", "September", [], ["Earth, Wind & Fire"]),
    ("Bill Withers", "Lovely Day", [], ["Bill Withers"]),
    ("Daryl Hall & John Oates", "You Make My Dreams (Come True)", ["You Make My Dreams"], ["Daryl Hall & John Oates", "Hall & Oates"]),
    ("The Jackson 5", "I Want You Back", [], ["The Jackson 5", "Jackson 5"]),
    ("Michael Jackson", "Don't Stop 'Til You Get Enough", [], ["Michael Jackson"]),
    ("George Benson", "Give Me the Night", [], ["George Benson"]),
    ("Curtis Mayfield", "Move On Up", [], ["Curtis Mayfield"]),
    ("Daft Punk feat. Pharrell Williams", "Get Lucky", [], ["Daft Punk"]),
    ("Bruno Mars", "Treasure", [], ["Bruno Mars"]),
    ("Vulfpeck", "Back Pocket", [], ["Vulfpeck"]),
    ("Cory Wong feat. Cody Fry", "Golden", [], ["Cory Wong"]),
    ("Jamiroquai", "Canned Heat", [], ["Jamiroquai"]),
    ("Corinne Bailey Rae", "Put Your Records On", [], ["Corinne Bailey Rae"]),
    ("Katrina and the Waves", "Walking on Sunshine", [], ["Katrina and the Waves", "Katrina & The Waves"]),
]

# 原曲でないものに付く語（題名・アルバム名に出たら外す）
NG = ["karaoke", "カラオケ", "cover", "カバー", "instrumental", "インスト", "originally performed", "in the style of",
      "tribute", "トリビュート", "remix", "リミックス", "live", "ライブ", "ライヴ", "acoustic", "piano version",
      "lullaby", "オルゴール", "music box", "8-bit", "made famous", "a cappella", "demo", "version by"]
# Get Lucky の Radio Edit や Remaster は原曲として許す
OK_WORDS = ["radio edit", "remaster", "リマスター", "single version", "album version", "mono", "stereo"]


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = s.replace("’", "'").replace("‘", "'").replace("〜", "~").replace("～", "~")
    return re.sub(r"[\s、,.・!！?？'\"~\-()（）\[\]&]+", "", s)


def call(tok, path, method="GET", payload=None):
    url = path if path.startswith("http") else API + path
    data = json.dumps(payload).encode() if payload is not None else None
    for _ in range(5):
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(int(e.headers.get("Retry-After", "3")) + 1); continue
            raise
    raise SystemExit("Spotifyが混んでいて通りませんでした: " + path)


def bad(name, album):
    t2 = (name + " / " + album).lower()
    for w in OK_WORDS:
        t2 = t2.replace(w, "")
    for w in NG:
        if re.match(r"^[a-z0-9 \-']+$", w):  # 英語は単語として（Alive の live・Demon の demo を誤って外さない）
            if re.search(r"(?<![a-z])%s(?![a-z])" % re.escape(w), t2):
                return True
        elif w in t2:
            return True
    return False


def find(tok, song):
    disp, title, alts, artists = song
    titles = [norm(x) for x in [title] + alts]
    arts = [norm(a) for a in artists]
    queries = []
    for a in artists[:2]:
        queries.append("track:%s artist:%s" % (title, a))
    queries.append("%s %s" % (title, artists[0]))
    for alt in alts[:1]:
        queries.append("%s %s" % (alt, artists[-1]))
    cands = []
    for q in queries:
        for market in ("JP", "US"):
            try:
                r = call(tok, "/search?" + urllib.parse.urlencode({"q": q, "type": "track", "limit": 10, "market": market}))
            except urllib.error.HTTPError:
                continue
            for it in (r.get("tracks") or {}).get("items") or []:
                if not it or not it.get("id"):
                    continue
                an = [norm(a.get("name")) for a in it.get("artists") or []]
                main_art = an[0] if an else ""
                if not any(a == main_art or (len(a) >= 4 and a in main_art) for a in arts):
                    continue  # 一人目のアーティストが本人でなければ外す（カバー・別人）
                nm = norm(it.get("name"))
                base = norm(re.split(r"\s[-–]\s|\(|（", it.get("name") or "")[0])
                if not any(t == nm or t == base or (len(t) >= 4 and nm.startswith(t)) for t in titles):
                    continue
                alb = (it.get("album") or {}).get("name") or ""
                if bad(it.get("name") or "", alb):
                    continue
                atype = (it.get("album") or {}).get("album_type") or ""
                score = (it.get("popularity") or 0) + (15 if atype in ("album", "single") else 0) \
                    - (20 if atype == "compilation" else 0) + (10 if nm == titles[0] or base == titles[0] else 0)
                cands.append((score, it))
            if cands:
                break
        if cands:
            break
    if not cands:
        return None
    cands.sort(key=lambda x: -x[0])
    it = cands[0][1]
    return {"uri": it["uri"], "id": it["id"], "name": it["name"],
            "artists": ", ".join(a["name"] for a in it["artists"]), "album": (it.get("album") or {}).get("name"),
            "url": (it.get("external_urls") or {}).get("spotify")}


def get_playlist(tok):
    st = sn._load(PL_STORE) or {}
    pid = st.get(NAME)
    if pid:
        try:
            call(tok, "/playlists/%s?fields=id" % pid)
            return pid
        except urllib.error.HTTPError:
            pass
    body = {"name": NAME, "description": DESC, "public": False}
    try:
        p = call(tok, "/me/playlists", "POST", body)
    except urllib.error.HTTPError:  # 旧エンドポイント
        me = call(tok, "/me")
        p = call(tok, "/users/%s/playlists" % urllib.parse.quote(me["id"]), "POST", body)
    st[NAME] = p["id"]
    sn._save600(PL_STORE, st)
    return p["id"]


def put_items(tok, pid, uris):
    for path in ("/playlists/%s/items" % pid, "/playlists/%s/tracks" % pid):
        try:
            call(tok, path, "PUT", {"uris": uris[:100]})  # 置き換え（順番どおり・ダブらない）
            return path
        except urllib.error.HTTPError as e:
            last = e
    raise last


def main():
    shirabe = "--shirabe" in sys.argv
    tok = sn.access_token()
    got, miss = [], []
    for i, s in enumerate(SONGS, 1):
        r = find(tok, s)
        if r:
            r["n"] = i; r["want"] = "%s「%s」" % (s[0], s[1]); got.append(r)
            print("%2d ○ %s → %s / %s（%s）" % (i, r["want"], r["name"], r["artists"], r["album"]), flush=True)
        else:
            miss.append({"n": i, "want": "%s「%s」" % (s[0], s[1])})
            print("%2d × %s 見つからず" % (i, "%s「%s」" % (s[0], s[1])), flush=True)
        time.sleep(0.3)
    res = {"at": time.strftime("%F %T"), "name": NAME, "got": len(got), "miss": miss, "tracks": got}
    if not shirabe and got:
        pid = get_playlist(tok)
        put_items(tok, pid, [g["uri"] for g in got])
        pl = call(tok, "/playlists/%s?fields=external_urls,items.total,tracks.total" % pid)
        total = ((pl.get("items") or pl.get("tracks") or {}).get("total"))
        res.update({"playlist_id": pid, "url": "https://open.spotify.com/playlist/%s" % pid, "total_on_spotify": total})
        sn.dispatch("Spotify「%s」を作りました %s ／ %d曲入り・入らなかった曲：%s" % (
            NAME, res["url"], len(got), "、".join(m["want"] for m in miss) or "なし"))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("RESULT", json.dumps({k: res.get(k) for k in ("url", "got", "total_on_spotify", "miss")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
