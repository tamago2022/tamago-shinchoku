#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""マガジンの週1告知（X）を回す仕組み（2026-10-17 たまごさん「もう本格的に始まる」）。

  週1回、マガジンを順番に回す。同じマガジンは次の周で別の切り口（A→B→C→D）。
  1投稿目 ＝ 引きの強い文章（問いで終わる）＋ 15秒の縦型動画（モーションタイポ）
  リプ    ＝ 「フルはこちら→<マガジンURL>」（URLは末尾＝X_TOUKOU_KATA）
  時刻    ＝ 既存の予約枠（3/9/15/21時）のうち 土曜21:00

  ★予約は、たまごさんの「これで」を待ってから（2026-10-17 変更指示）。
    それまでは Googleドライブ「AI制作物/Claude/その他」に非公開で置いて見せるだけ。
    approved が true の週だけ yoyaku が動く。さらに status/buffer_queue/.TOMERU があれば動かない。

  事実は各マガジン本文（出典つき）に書いてあることだけ。書いていないことは足さない。
  たまごさんの指示は音声入力（Typeless）で誤変換が混ざる。指示の言葉はそのまま使わず、
  固有名詞は記事本文の表記に合わせる（例：「おとぼけビ〜バ〜」→記事表記「おとぼけビ〜バー」）。

使い方:
  python3 tools/sns_shuukan.py plan              … status/sns_weekly_plan.json を書く
  python3 tools/sns_shuukan.py moji              … 文章の文字数（X換算）を測る
  python3 tools/sns_shuukan.py tenken            … 投稿先マガジンの点検（80点・関連4曲以上・曲ページリンク）
  python3 tools/sns_shuukan.py douga <週番号|all> … 15秒縦動画（MP4）＋静止画（PNG）を作る
"""
import datetime, io, json, os, re, subprocess, sys, unicodedata, urllib.parse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JRS = os.path.join(os.path.dirname(REPO), "jrs_fix")
SITE = "https://joy-relief-station.lovable.app"
PLAN_OUT = os.path.join(REPO, "status", "sns_weekly_plan.json")
OUTDIR = os.path.join(REPO, "status", "sns_shuukan")
SLOT = "21:00"          # 既存枠 3/9/15/21 のうち夜
START = datetime.date(2026, 10, 24)   # 最初の土曜

# ---------------------------------------------------------------- マガジン
MAGS = [
    {"key": "ikareru", "title": "怒れる人々 〜ロックは死んだのか〜 vol.1",
     "url": SITE + "/magazine/ikareru-01.html", "local": "status/magazine_prod/ikareru-01.html", "tag": "#怒れる人々"},
    {"key": "hoshikatsu", "title": "君は星勝を知っているか",
     "url": SITE + "/magazine/kimi-wa-hoshi-katsu.html", "local": "status/magazine_prod/kimi-wa-hoshi-katsu.html", "tag": "#星勝"},
    {"key": "citypop", "title": "世界が先に見つけた、日本の夜。",
     "url": SITE + "/feature/citypop-sekai", "local": None, "tag": "#シティポップ"},
    {"key": "harakami", "title": "君はレイ・ハラカミを知っているか",
     "url": SITE + "/magazine/rei-harakami.html", "local": "status/magazine_prod/rei-harakami.html", "tag": "#reiharakami"},
]

# ---------------------------------------------------------------- 切り口 A〜D
# text   … 1投稿目（URLなし・問いで終わる）
# cards  … 動画の文字（1枚目＝一番強い一言。最初の1秒で掴む）
# konkyo … 記事のどの章の、どの出典の話か（事実の裏）
CUTS = {
 "ikareru": {
  "A": {"name": "Ado「うっせぇわ」— 何を代弁したか",
        "text": "2020年、高校3年生がキレたら社会現象になった。\n\nAdo「うっせぇわ」。\n本人いわく、怒りの感情は学生にも共通していた。\n\n押しつけられる側が、古い「常識」をそのまま投げ返した。\nあれは、誰の代わりに叫んでいたんだろう。\n\n#怒れる人々 #Ado",
        "cards": ["優等生が、\nキレた。", "2020年\n高校3年生\nAdo「うっせぇわ」", "社会現象に\nなったのは、", "みんな、\nどこかで\n言いたかったから。"],
        "konkyo": "08章（Wikipedia／SCHOOL OF LOCK!）"},
  "B": {"name": "THE TIMERS「FM東京」— 止める時間は、あった",
        "text": "1989年、テレビが事件になった夜。\n\nTHE TIMERS「FM東京」。\n実はあれ、生放送じゃなかった。夕方に撮って、そのまま流した。\n\n「流していいですか」に、返事は「いいんじゃない？」。\n止める時間はあった。なぜ止めなかったんだろう。\n\n#怒れる人々 #THETIMERS",
        "cards": ["生放送じゃ、\nなかった。", "1989年\nTHE TIMERS\n「FM東京」", "止める時間は、\nあった。", "止めなかった。"],
        "konkyo": "05章（文春オンライン／スポニチ／ENCOUNT）"},
  "C": {"name": "1995年、クラヴィッツの問いにプリンスが同じ年に答えた",
        "text": "1995年、ロックスターが「ロックは死んだ」と歌った。\nLenny Kravitz「Rock and Roll Is Dead」。\n\n同じ年の11月、プリンスが返事を出す。\n「Rock and Roll Is Alive! (And It Lives in Minneapolis)」\n\nロックは、本当に死んだのか。\n\n#怒れる人々 #Prince",
        "cards": ["ロックは、\n死んだ。", "1995年\nLenny Kravitz", "同じ年、\nプリンスが\n答えた。", "ミネアポリスで、\n生きてる。"],
        "konkyo": "00章・10章（Wikipedia／Songfacts）"},
  "D": {"name": "おとぼけビ〜バー — 1分半でジジイを片付ける",
        "text": "「なんで？ ごちそうするのに？」\n\nその一言に、京都のバンドが1分半で返事をした。\nおとぼけビ〜バー「ジジイ is Waiting For My Reaction」。\n\nカップ麺より早く、ジジイが片付く。\nあなたの「なんで？」は、誰の声ですか。\n\n#怒れる人々 #おとぼけビーバー",
        "cards": ["1分半で、\nジジイを\n片付ける。", "おとぼけビ〜バー\n京都", "「なんで？\nごちそうするのに？」", "カップ麺より、\n早い。"],
        "konkyo": "09章（Rooftop／Wikipedia）"},
 },
 "hoshikatsu": {
  "A": {"name": "譜面が読めなかった編曲家",
        "text": "名前は知らなくても、音は知っている。\n\n井上陽水「氷の世界」、RCサクセション「スローバラード」、安全地帯「ワインレッドの心」。\nぜんぶに同じひとりの名前がある。星勝。\n\nしかも本人は、のちに「譜面が読めなかった」と明かしている。\nどうやって、あの音を書いたんだろう。\n\n#星勝",
        "cards": ["譜面が、\n読めなかった。", "その人が、\n日本のうたを\n編んだ。", "氷の世界\nスローバラード\nワインレッドの心", "星勝。"],
        "konkyo": "03・04・07・09章（Wikipedia）"},
  "B": {"name": "「月光仮面」を歌っているのは星勝本人",
        "text": "モップスの「月光仮面」。\nあの声、鈴木ヒロミツだと思っていませんか。\n\n歌っているのは、ギターの星勝本人。\nモップスの曲の半分近くで、リード・ヴォーカルを取っていた。\n\nのちに日本のうたを編む人は、最初は歌っていた。\n\n#星勝 #モップス",
        "cards": ["その声、\n別人です。", "ザ・モップス\n「月光仮面」", "歌っているのは\n星勝。", "ギターの人が、\n歌っていた。"],
        "konkyo": "01・02章（ShimaQの今日この頃 ほか）"},
  "C": {"name": "ロサンゼルスで、認められた日",
        "text": "1974年、ロサンゼルス。\n井上陽水『二色の独楽』の録音に、向こうの一流プレイヤーが並んだ。\n\n編曲したのは、ほぼ独学の日本人。\nスタジオの評価は「絶賛」だったと、一緒にいた人が書いている。\n\n独学の譜面は、なぜ海の向こうで通じたのか。\n\n#星勝 #井上陽水",
        "cards": ["独学の譜面が、\nLAで\n絶賛された。", "1974年\nロサンゼルス", "井上陽水\n『二色の独楽』", "編曲\n星勝"],
        "konkyo": "05章（Wikipedia／music-calendar.jp）"},
  "D": {"name": "清志郎が「違う」と言った録音が、名曲になった",
        "text": "忌野清志郎は、その録音が思っていた音と違うと感じていた。\n\nRCサクセション「スローバラード」（1976）。編曲は星勝とRC。\n\n半世紀たったいま、いろんな人に歌い継がれている。\n思いどおりにならなかった録音が、なぜ残ったんだろう。\n\n#星勝 #スローバラード",
        "cards": ["思っていた音と、\n違った。", "RCサクセション\n「スローバラード」\n1976", "半世紀、\n歌い継がれている。", "編曲\n星勝"],
        "konkyo": "07章（Wikipedia／TOWER RECORDS）"},
 },
 "citypop": {
  "A": {"name": "The Weekndの土台に、1983年の東京",
        "text": "2022年、The Weeknd「Out of Time」。\nその土台に、1983年の東京の夜が入っていた。\n\n亜蘭知子「Midnight Pretenders」。\n40年前の東京の夜が、いま世界中のイヤホンで鳴っている。\n\nあなたの知っている街の歌、海の向こうで鳴っているのを知っていましたか。\n\n#シティポップ #CityPop",
        "cards": ["1983年の東京が、\nThe Weekndの\n中にいた。", "亜蘭知子\n「Midnight Pretenders」", "40年後、\n世界のイヤホンで。", "世界が先に見つけた、\n日本の夜。"],
        "konkyo": "01（Yahoo!ニュース／Mikiki／UNIVERSAL MUSIC JAPAN）"},
  "B": {"name": "松原みき「真夜中のドア」世界1位",
        "text": "1979年のデビュー曲が、世界1位になった。\n\n松原みき「真夜中のドア／Stay With Me」。\nSpotifyのグローバルバイラルチャートで世界1位。\n\n日本の若い人が知らない曲が、海外を盛り上げている。\nなぜ、いまこの曲だったんだろう。\n\n#シティポップ #真夜中のドア",
        "cards": ["1979年の曲が、\n世界1位。", "松原みき\n「真夜中のドア」", "Spotify\nグローバルバイラル", "世界が先に見つけた、\n日本の夜。"],
        "konkyo": "02（PONY CANYON NEWS）"},
  "C": {"name": "泰葉「フライディ・チャイナタウン」69位からの再浮上",
        "text": "1981年、オリコン最高69位。\n\n泰葉「フライディ・チャイナタウン」。\n40年後、Night Tempoのリミックスがロサンゼルスの会場で流れた動画から広がり、Spotifyの日本デイリーバイラルで2位に。\n\n売れなかった曲は、どこで眠っていたんだろう。\n\n#シティポップ #泰葉",
        "cards": ["69位の曲が、\n40年後に\n浮上した。", "泰葉\n「フライディ・\nチャイナタウン」", "ロサンゼルスの\n夜から。", "世界が先に見つけた、\n日本の夜。"],
        "konkyo": "03（Wikipedia／リアルサウンド）"},
  "D": {"name": "竹内まりや「Plastic Love」5500万回",
        "text": "2017年、誰かが投稿した8分のリミックス。\n\n竹内まりや「Plastic Love」（1984）。\nYouTubeのおすすめで広がって、2021年2月までに5500万回以上再生された。\n\nおすすめのボタンが、1984年の夜を掘り起こした。\nあなたのおすすめには、何が眠っていますか。\n\n#シティポップ #PlasticLove",
        "cards": ["5500万回。", "竹内まりや\n「Plastic Love」\n1984", "掘り起こしたのは、\nおすすめボタン。", "世界が先に見つけた、\n日本の夜。"],
        "konkyo": "04（Wikipedia）"},
 },
 "harakami": {
  "A": {"name": "サビがないのに、耳から離れない",
        "text": "Aメロも、Bメロも、サビもない。\nそれなのに、一度聴いたら耳から離れない。\n\nrei harakami（レイ・ハラカミ）。\n京都でひとり、小さな機材で鳴らされていた音。\n\n歌もサビもない音楽を、どうして止めたくなくなるんだろう。\n\n#reiharakami #レイハラカミ",
        "cards": ["サビが、\nない。", "なのに、\n耳から離れない。", "rei harakami", "京都で、\nひとりで\n鳴らしていた。"],
        "konkyo": "冒頭・01章（All About／Wikipedia）"},
  "B": {"name": "出したら引退するつもりだった『red curb』",
        "text": "このアルバムを出したら、引退するつもりだった。\n\nrei harakami『red curb』（2001）。\n本人いわく、好きな事しか出来ないなあ、と考えながら作った。\n\n辞める気の人が、いちばん自由な音を出してしまった。\nその音、聴いてみますか。\n\n#reiharakami",
        "cards": ["引退する\nつもりだった。", "rei harakami\n『red curb』\n2001", "好きな事しか、\n出来ない。", "いちばん自由な音。"],
        "konkyo": "02章（rings／ele-king）"},
  "C": {"name": "SC-88Proを買い換えなかった",
        "text": "あの音の源は、DTM用の音源モジュールだった。\n\nrei harakami。使っていたのはローランドのSC-88Pro。\n本人いわく、長年「買い換えてないので、ああなっちゃう」。\n\n買い換えなかった機材の音が、なぜいまも新しく聴こえるんだろう。\n\n#reiharakami #SC88Pro",
        "cards": ["買い換えて\nないので。", "Roland\nSC-88Pro", "ああ、\nなっちゃう。", "rei harakami"],
        "konkyo": "01章（TOWER RECORDS／Red Bull Music Academy）"},
  "D": {"name": "くるり「ばらの花」のリミックスが矢野顕子に届いた",
        "text": "1曲のリミックスが、矢野顕子に届いた。\n\nくるり「ばらの花 ～remixed by Rei Harakami」。\n2003年、これを聴いた矢野顕子が、ハラカミの才能をキャッチした。\nその先に、ふたりのユニットyanokamiが待っている。\n\n最初の数秒で分かる音、聴いてみますか。\n\n#reiharakami #yanokami",
        "cards": ["1曲のリミックスが、\n矢野顕子に\n届いた。", "くるり\n「ばらの花」\nremixed by\nRei Harakami", "そして、\nyanokami。", "rei harakami"],
        "konkyo": "04章（ヤマハミュージックコミュニケーションズ）"},
 },
}

ORDER = ["A", "B", "C", "D"]


def weeks():
    """週ごとの並び：マガジンを順番に回し、周ごとに切り口を進める。"""
    out = []
    n = 0
    for r, cut in enumerate(ORDER):
        for m in MAGS:
            d = START + datetime.timedelta(days=7 * n)
            c = CUTS[m["key"]][cut]
            out.append({
                "week": n + 1, "date": d.isoformat(), "due_jst": "%s %s" % (d.isoformat(), SLOT),
                "magazine": m["key"], "magazine_title": m["title"], "magazine_url": m["url"],
                "cut": cut, "cut_name": c["name"], "konkyo": c["konkyo"],
                "post1_text": c["text"], "video_cards": c["cards"],
                "reply_text": "フルはこちら→ " + m["url"],
            })
            n += 1
    return out


# ---------------------------------------------------------------- 文字数（X換算）
def x_weight(t):
    t = re.sub(r"https?://\S+", "x" * 23, t)
    w = 0
    for ch in t:
        o = ord(ch)
        w += 1 if (o <= 0x10FF or 0x2000 <= o <= 0x200D or 0x2010 <= o <= 0x201F or 0x2032 <= o <= 0x2037) else 2
    return w


def cmd_moji():
    bad = 0
    for w in weeks():
        a, b = x_weight(w["post1_text"]), x_weight(w["reply_text"])
        ok = a <= 280 and b <= 280
        bad += 0 if ok else 1
        print("%2d %s %-10s %s  本文%3d/280  リプ%3d  %s" % (w["week"], w["date"], w["magazine"], w["cut"], a, b, "OK" if ok else "★超過"))
    return bad


# ---------------------------------------------------------------- 点検（来てよかった）
def _song_links_local(path):
    s = io.open(os.path.join(REPO, path), encoding="utf-8").read()
    pairs = re.findall(r'href="[^"]*cover-guide\?artist=([a-z0-9\-]+)&amp;song=([a-z0-9\-]+)"', s)
    return s, sorted(set(pairs))


def _song_links_citypop():
    s = io.open(os.path.join(JRS, "src/lib/cityPopSekaiSongs.ts"), encoding="utf-8").read()
    pairs = re.findall(r'artistId:\s*"([^"]+)",\s*songId:\s*"([^"]+)"', s)
    return s, sorted(set(pairs))


_CG = None


def _cg():
    global _CG
    if _CG is None:
        _CG = io.open(os.path.join(JRS, "src/lib/coverGuide.ts"), encoding="utf-8").read()
    return _CG


def tenken_one(m):
    """100点満点。80点以上で合格。関連（曲ページへのリンク）4曲以上は必須。"""
    if m["local"]:
        s, pairs = _song_links_local(m["local"])
        has_src = "SOURCES" in s or "出典" in s
        has_other = "OTHER MAGAZINES" in s or "ほかの特集" in s
        vids = len(set(re.findall(r'(?:youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=)|ytimg\.com/vi/|data-yt="|data-id=")([A-Za-z0-9_\-]{11})', s)))
        has_og = 'property="og:title"' in s
    else:
        s, pairs = _song_links_citypop()
        r = io.open(os.path.join(JRS, "src/routes/feature.citypop-sekai.tsx"), encoding="utf-8").read()
        has_src = "出典" in r or "SOURCES" in r
        has_other = "ほかの特集" in r
        vids = len(set(re.findall(r'videoId:\s*"([A-Za-z0-9_\-]{11})"', s)))
        has_og = "og:title" in r or "head:" in r
    hb = None
    if os.path.exists(HONBAN):
        hb = json.load(io.open(HONBAN, encoding="utf-8"))["mags"].get(m["key"])
    if hb:
        exist = [p for p in pairs if hb["songs"].get("%s/%s" % p, {}).get("ok")]
        live = hb["http"] == "200"
    else:
        cg = _cg()
        exist = [p for p in pairs if ('"%s"' % p[0]) in cg and ('"%s"' % p[1]) in cg]
        live = None
    miss = [p for p in pairs if p not in exist]
    pt = 0
    pt += 30 if len(exist) >= 4 else int(30 * len(exist) / 4)          # 関連4曲以上（曲ページがある曲）
    pt += 25 if pairs and not miss else int(25 * len(exist) / max(1, len(pairs)))  # リンク先の曲ページが全部ある
    pt += 15 if vids >= 4 else int(15 * vids / 4)                        # ページの中で聴ける
    pt += 10 if has_src else 0                                           # 出典
    pt += 10 if has_other else 0                                         # 次の一歩（ほかの特集）
    pt += 10 if has_og else 0                                            # Xのカード
    return {"magazine": m["key"], "url": m["url"], "score": pt, "pass": pt >= 80 and len(exist) >= 4 and live is not False,
            "measured": "本番（Macでcurl）" if hb else "手元のデータ（本番未測定）", "page_http": hb["http"] if hb else None,
            "song_links": len(pairs), "song_pages_found": len(exist), "missing": ["%s/%s" % p for p in miss],
            "videos_in_page": vids, "sources": has_src, "other_magazines": has_other, "og": has_og}


HONBAN = os.path.join(OUTDIR, "tenken_honban.json")


def song_pairs(m):
    return (_song_links_local(m["local"]) if m["local"] else _song_links_citypop())[1]


def cmd_honban():
    """Macで走らせる（curl）。マガジン本体と、リンク先の曲ページを全部開いて確かめる。"""
    out = {"at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "mags": {}}
    for m in MAGS:
        r = subprocess.run(["curl", "-sL", "-m", "40", "-o", "/dev/null", "-w", "%{http_code} %{size_download}", m["url"]],
                           capture_output=True, text=True).stdout.split()
        songs = {}
        for ar, so in song_pairs(m):
            u = "%s/cover-guide?artist=%s&song=%s" % (SITE, urllib.parse.quote(ar), urllib.parse.quote(so))
            h = subprocess.run(["curl", "-sL", "-m", "40", u], capture_output=True, text=True).stdout
            t = re.search(r'property="og:title" content="([^"]*)"', h)
            t = t.group(1) if t else ""
            songs["%s/%s" % (ar, so)] = {"og_title": t, "ok": bool(t) and not t.startswith("案内所"), "size": len(h)}
        out["mags"][m["key"]] = {"http": r[0] if r else "", "size": int(r[1]) if len(r) > 1 else 0, "songs": songs}
    os.makedirs(OUTDIR, exist_ok=True)
    io.open(HONBAN, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
    for k, v in out["mags"].items():
        print(k, v["http"], sum(1 for x in v["songs"].values() if x["ok"]), "/", len(v["songs"]))


def cmd_tenken():
    res = [tenken_one(m) for m in MAGS]
    for r in res:
        print("%-10s %3d点 %s  曲リンク%d（曲ページあり%d） 動画%d  欠け%s" % (
            r["magazine"], r["score"], "合格" if r["pass"] else "★不合格", r["song_links"], r["song_pages_found"],
            r["videos_in_page"], r["missing"] or "なし"))
    return res


# ---------------------------------------------------------------- 動画
W, H, FPS, DUR = 1080, 1920, 30, 15.0
FS = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
FR = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
AI, KINARI, SHU = (22, 30, 46), (237, 230, 214), (193, 68, 46)
ICON = os.path.join(JRS, "public", "icon-512.png")
BG_IKARERU = os.path.join(JRS, "public", "magazine", "assets", "ikareru")


def _font(path, size):
    from PIL import ImageFont
    return ImageFont.truetype(path, size, index=0)


def _grain(seed):
    from PIL import Image
    import random
    random.seed(seed)
    g = Image.effect_noise((W // 2, H // 2), 22).resize((W, H))
    return g


def _bg_image(key, i):
    """怒れる人々だけは記事の自前画像（扉の『IS ROCK DEAD? NO.』等）を使う。他は紙と夜の色だけ。"""
    from PIL import Image, ImageOps, ImageEnhance
    if key != "ikareru":
        return None
    names = ["door", "billboard", "chalk", "stencil"]
    p = os.path.join(BG_IKARERU, names[i % len(names)] + ".webp")
    if not os.path.exists(p):
        return None
    im = Image.open(p).convert("RGB")
    im = ImageOps.fit(im, (W, H), centering=(0.5, 0.5))
    g = ImageOps.grayscale(im)
    du = ImageOps.colorize(g, black=(10, 14, 24), white=(150, 160, 175))   # 藍のモノトーン
    return ImageEnhance.Brightness(du).enhance(0.6)


def _draw_text(img, text, size, color, y_center, font=FS, spacing=1.25, track=0.04):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    f = _font(font, size)
    lines = text.split("\n")
    # 横幅に収まるまで縮める
    while True:
        widths = [sum(f.getlength(c) for c in ln) + track * size * max(0, len(ln) - 1) for ln in lines]
        if max(widths) <= W * 0.86 or size < 40:
            break
        size = int(size * 0.92)
        f = _font(font, size)
    lh = int(size * spacing)
    y = int(y_center - lh * len(lines) / 2)
    for ln, wd in zip(lines, widths):
        x = (W - wd) / 2
        for c in ln:
            d.text((x, y), c, font=f, fill=color)
            x += f.getlength(c) + track * size
        y += lh


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _layer(text, size, color, y_center, font=FS, track=0.04):
    """文字だけの透明レイヤー（1回だけ描いて使い回す＝速い）。"""
    from PIL import Image
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _draw_text(im, text, size, color + (255,), y_center, font=font, track=track)
    return im


def _shade(img, amt):
    from PIL import ImageEnhance
    return ImageEnhance.Brightness(img).enhance(amt)


def render(week, outdir):
    from PIL import Image, ImageDraw, ImageChops
    w = week
    key = w["magazine"]
    cards = w["video_cards"]
    # 時間割（テンポはゆるめ）。0〜0.5秒＝朱一色に一番強い一言（最初の1秒で掴む・ショック）
    seg = [(0.0, 3.6), (3.6, 7.0), (7.0, 10.4), (10.4, 12.4)]   # 12.4〜15.0 は締め（題名＋ロゴ半分）
    SHOCK = 0.5
    grain = _grain(w["week"]).convert("RGB").point(lambda v: v // 14)
    bgs = [_bg_image(key, i) for i in range(4)]
    icon = Image.open(ICON).convert("RGBA") if os.path.exists(ICON) else None
    os.makedirs(outdir, exist_ok=True)
    base = "%02d_%s_%s" % (w["week"], key, w["cut"])
    mp4 = os.path.join(outdir, base + ".mp4")
    png = os.path.join(outdir, base + "_1koma.png")
    # 文字レイヤーを先に作る
    shock = Image.new("RGB", (W, H), SHU)
    shock.paste(_layer(cards[0], 200, KINARI, H * 0.46), (0, 0), _layer(cards[0], 200, KINARI, H * 0.46))
    L0 = _layer(cards[0], 190, KINARI if bgs[0] is not None else SHU, H * 0.46)
    LS = [None] + [_layer(cards[i], 120 if i < 3 else 130, KINARI, H * 0.47) for i in (1, 2, 3)]
    end = Image.new("RGB", (W, H), KINARI)
    ttl = w["magazine_title"]
    ttl = ttl.replace(" 〜", "\n〜") if "〜" in ttl else ttl
    for lay in (_layer(ttl, 74, AI, H * 0.42, font=FR, track=0.08),
                _layer("フルは、リプのリンクから。", 44, SHU, H * 0.58, font=FR, track=0.12),
                _layer("ご き げ ん 補 給 所", 34, AI, H * 0.80 + 190, font=FR, track=0.05),
                _layer("JOY RELIEF STATION", 22, SHU, H * 0.80 + 240, font=FR, track=0.3)):
        end.paste(lay, (0, 0), lay)
    if icon is not None:
        ic = icon.resize((150, 150))     # ロゴは半分の大きさ・低い位置
        end.paste(ic, (W // 2 - 75, int(H * 0.80)), ic)
    plain = Image.new("RGB", (W, H), AI)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
                           "-f", "lavfi", "-t", str(DUR), "-i", "anullsrc=r=44100:cl=stereo",
                           "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                           "-preset", "medium", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", mp4],
                          stdin=subprocess.PIPE)
    nf = int(DUR * FPS)
    for fi in range(nf):
        t = fi / FPS
        if t < SHOCK:
            frame = shock.copy()
        else:
            idx = next((i for i, (a, b) in enumerate(seg) if a <= t < b), None)
            if idx is not None:
                a, b = seg[idx]
                lt = (t - a) / (b - a)
                bg = bgs[idx]
                if bg is not None:
                    z = 1.0 + 0.12 * lt                      # ゆっくり寄る（見て分かる速度）
                    cw, ch = int(W / z), int(H / z)
                    frame = bg.crop(((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw, (H - ch) // 2 + ch)).resize((W, H))
                    frame = _shade(frame, 0.75)
                else:
                    frame = plain.copy()
                if idx == 0:
                    frame.paste(L0, (0, 0), L0)
                    ImageDraw.Draw(frame).rectangle((W * 0.42, H * 0.66, W * 0.58, H * 0.665), fill=SHU)
                else:
                    al = _ease(lt / 0.22)
                    dy = int(50 * (1 - al))
                    lay = LS[idx]
                    if al < 1:
                        lay = lay.copy()
                        lay.putalpha(lay.getchannel("A").point(lambda v: int(v * al)))
                    frame.paste(lay, (0, dy), lay)
                    if idx == 3:
                        ImageDraw.Draw(frame).ellipse((W / 2 - 14, H * 0.68, W / 2 + 14, H * 0.68 + 28), fill=SHU)
            else:
                lt = (t - seg[-1][1]) / (DUR - seg[-1][1])
                frame = end if lt >= 0.15 else Image.blend(plain, end, _ease(lt / 0.15))
        frame = ImageChops.add(frame, grain, scale=1.0, offset=-6)   # 紙の粒子
        if fi == 0:
            frame.save(png)
        ff.stdin.write(frame.tobytes())
    ff.stdin.close()
    ff.wait()
    return mp4, png


JNAME = {"ikareru": "怒れる人々", "hoshikatsu": "星勝", "citypop": "シティポップ", "harakami": "レイハラカミ"}


def nouhin_name(w, ext):
    return "SNS週1告知_第%d週_%s%s%s" % (w["week"], JNAME[w["magazine"]], w["cut"], ext)


def cmd_junbi(nums, vdir):
    """サンドボックスで：動画・1コマ目・文章を status/sns_shuukan/nouhin/ に並べる（Macが拾う）。"""
    import shutil
    nd = os.path.join(OUTDIR, "nouhin")
    os.makedirs(nd, exist_ok=True)
    for w in [x for x in weeks() if x["week"] in nums]:
        base = "%02d_%s_%s" % (w["week"], w["magazine"], w["cut"])
        shutil.move(os.path.join(vdir, base + ".mp4"), os.path.join(nd, nouhin_name(w, ".mp4")))
        shutil.move(os.path.join(vdir, base + "_1koma.png"), os.path.join(nd, nouhin_name(w, "_1コマ目.png")))
        body = "【第%d週】%s 21:00（予約はまだ。たまごさんの「これで」待ち）\n【マガジン】%s\n【切り口%s】%s\n【事実の出どころ】%s\n\n■1投稿目（文章＋動画）\n%s\n\n■リプ\n%s\n" % (
            w["week"], w["date"], w["magazine_title"], w["cut"], w["cut_name"], w["konkyo"], w["post1_text"], w["reply_text"])
        io.open(os.path.join(nd, nouhin_name(w, "_文章.txt")), "w", encoding="utf-8").write(body)
    print(sorted(os.listdir(nd)))


def cmd_nouhin():
    """Macで：nouhin/ の中身をドライブ「AI制作物/Claude/その他」へ上げ、URLを取って予定表に書く。"""
    import time, glob
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import claude_nouhin as cn
    nd = os.path.join(OUTDIR, "nouhin")
    names = sorted(f for f in os.listdir(nd) if not f.startswith("."))
    for f in names:
        print("put", f, cn.put(os.path.join(nd, f), anken="その他", move=True).get("ok"))
    cn.flush()
    cmd_url()


def cmd_url(nums=(1, 2, 3, 4)):
    """Macで：ドライブ「その他」から各週のファイルを名前の末尾で探し、URLを予定表に書く（150秒まで）。"""
    import time
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import claude_nouhin as cn
    ws = [w for w in weeks() if w["week"] in nums]
    want = {nouhin_name(w, e): (w["week"], k) for w in ws
            for k, e in (("video_drive_url", ".mp4"), ("png_drive_url", "_1コマ目.png"), ("text_drive_url", "_文章.txt"))}
    found = {}
    t0 = time.time()
    while time.time() - t0 < 150:
        cn.flush()
        base, why = cn.drive_alive()
        folder = os.path.join(base, "その他") if base else None
        if folder and os.path.isdir(folder):
            for f in os.listdir(folder):
                for n in want:
                    if unicodedata.normalize("NFC", f).endswith("_" + n) and n not in found:   # Macの名前はNFD
                        u = cn.drive_url(os.path.join(folder, f))
                        if u:
                            found[n] = u
        if len(found) == len(want):
            break
        time.sleep(10)
    plan = json.load(io.open(PLAN_OUT, encoding="utf-8"))
    for w in plan["weeks"]:
        for n, (wk, k) in want.items():
            if w["week"] == wk:
                w[k] = found.get(n)
    io.open(PLAN_OUT, "w", encoding="utf-8").write(json.dumps(plan, ensure_ascii=False, indent=1))
    for n in sorted(want):
        print(n, found.get(n, "★URL未取得"))


def cmd_plan():
    data = {
        "updatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "rule": "週1回・土曜21:00（既存枠3/9/15/21のうち夜）。マガジンを順番に回し、同じマガジンは次の周で別の切り口（A→B→C→D）。",
        "flow": "1投稿目＝文章（問いで終わる）＋15秒縦動画 ／ リプ＝フルはこちら→マガジンURL",
        "gate": "予約はたまごさんの「これで」の後だけ（approved=true の週のみ）。status/buffer_queue/.TOMERU があれば予約しない。",
        "tenken_rule": "投稿前に tools/sns_shuukan.py tenken：80点以上・関連（曲ページのある曲）4曲以上・曲ページへのリンク",
        "weeks": [dict(w, approved=False, video_drive_url=None, buffer_id=None) for w in weeks()],
    }
    old = {}
    if os.path.exists(PLAN_OUT):
        try:
            old = {x["week"]: x for x in json.load(io.open(PLAN_OUT, encoding="utf-8")).get("weeks", [])}
        except Exception:
            old = {}
    for x in data["weeks"]:
        o = old.get(x["week"], {})
        for k in ("approved", "video_drive_url", "png_drive_url", "text_drive_url", "buffer_id", "cost"):
            if o.get(k) is not None:
                x[k] = o[k]
    io.open(PLAN_OUT, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=1))
    print("書いた:", PLAN_OUT, len(data["weeks"]), "週")


def main():
    a = sys.argv[1:] or ["moji"]
    if a[0] == "plan":
        cmd_plan()
    elif a[0] == "moji":
        sys.exit(1 if cmd_moji() else 0)
    elif a[0] == "junbi":
        cmd_junbi([int(x) for x in a[1].split(",")], a[2])
    elif a[0] == "nouhin":
        cmd_nouhin()
    elif a[0] == "url":
        cmd_url()
    elif a[0] == "honban":
        cmd_honban()
    elif a[0] == "tenken":
        res = cmd_tenken()
        sys.exit(0 if all(r["pass"] for r in res) else 1)
    elif a[0] == "douga":
        ws = weeks()
        sel = ws if a[1] == "all" else [w for w in ws if str(w["week"]) in a[1].split(",")]
        for w in sel:
            print(render(w, a[2] if len(a) > 2 else OUTDIR))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
