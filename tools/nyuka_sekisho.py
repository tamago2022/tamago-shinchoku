#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""入荷の関所 — 曲が1曲入った瞬間に、事実・文脈・コピーを80点で決める。

たまごさんの言葉（2026-09-19・依頼原文は status/nyuka/original.md）：
  「デビューアルバム『GIRL TALK』のタイトル曲を入れてみたら、見た目の情報だけで
    書いてるのがバレバレ。まだ適当な感じで、事実は一切調べてない。
    1発目でそこの情報を調べて入れてほしいんだよ。できないの？」
  「『編み込まれた髪と横顔。その静かな視線の先に、夜の会話の続きが聴こえてくる。』
    適当だよな。60点。80点まで頑張ってほしい。」
  「入荷したときにバチっと決まる仕組みを作ってください。
    30,000曲を巡回するのは大変でしょう。」

だからこれは「後から直す道具」ではない。**入口で決める関所**である。
巡回はしない。URLが1本入った瞬間に、この5つの門を順に通る。通らなければ出さない。

■ 門の並び（1本でも落ちたら先へ進まない）
  門1 素性を割る   … 誰が歌っているか／年／アルバム／原曲／作詞作曲。
                      **外部AIの言い分は採用しない。** AIが出した出典URLを
                      こちらが実際に取得し、そのページに主張の語が載っているかを
                      機械で照合する（load_and_match）。載っていなければ事実を落とす。
                      投稿型ドメイン（Wikipedia/Discogs/SecondHandSongs等）は
                      1本では採用せず、独立したもう1本との一致を要求する。
                      ＝ skill sekisho-jijitsu-shutten の「通し方」をそのまま機械にした門。
  門2 別人を止める … skill sekisho-artist-song の判定。名前が一致しただけの別人を
                      本人の棚に入れない（akikoの棚に矢野顕子を入れた事故の再発防止）。
  門3 文脈を決める … 「女性ジャズシンガー」「ジャズボーカル」等の棚の文脈を、
                      **裏の取れた事実からしか**決めない。当てずっぽうで付けない。
  門4 コピーを書く … skill bonjovi-ojisan-kobun の型。
                      ★ここが今回の本題：**画像に写っているものだけで書いた語を落とす。**
                      髪・横顔・視線・瞳……は、裏取り済み事実で支えられていなければ失格。
                      裏取り済み事実を1つ必ず含むこと。水道水コピーは機械で落とす。
  門5 採点        … 0〜100点を**外部AI（OpenAI）**に付けさせる。
                      **こちら側の自己採点は使わない**（たまごさん指示）。
                      80点未満は通さない。書き直して最大3回まで再挑戦。
                      それでも通らなければ **保留**。たまごさんには出さない。

■ 鍵とネットワークの置き場所（ここが回りくどい理由）
  Cowork/Dispatchのサンドボックスからは api.openai.com に出られない（実測 HTTP 000）。
  鍵も届かない（~/.tamago/keys/api_keys.env はマウント外）。
  そこで **セッション側は積むだけ**にする：

     python3 tools/nyuka_sekisho.py --submit --json intake.json
       → status/nyuka/pending/<id>.json を置いて終わり。APIは呼ばない。

  実際に外部AIへ投げて採点を持ち帰るのは、鍵とネットワークがあるMac側：

     python3 tools/nyuka_sekisho.py --run-pending

  これは既存の5分おきのlaunchd便（tools/machine_status_push.sh）に相乗りする。
  **新しいlaunchd便は増やさない**（この工場の決まり）。
  たまごさんが画面から画面へ文章を運ぶ必要は無い＝伝書鳩ゼロ。

■ 結果の置き場所
  status/nyuka/done/<id>.json   … 通った（copy が確定。棚と検索に同時に載せる材料）
  status/nyuka/hold/<id>.json   … 保留（80点に届かなかった。たまごさんには出さない）
  最後に必ず1行：
     NYUKA_RESULT: PASS <点> - <copy>
     NYUKA_RESULT: HOLD <点> - <理由>
     NYUKA_RESULT: SKIP - <理由>      … 鍵無し・上限超過（ゲートを塞がない）
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
if HERE not in sys.path:
    sys.path.insert(0, HERE)

NYUKA_DIR = os.path.join(REPO, "status", "nyuka")
PENDING_DIR = os.path.join(NYUKA_DIR, "pending")
DONE_DIR = os.path.join(NYUKA_DIR, "done")
HOLD_DIR = os.path.join(NYUKA_DIR, "hold")

PASS_SCORE = 80          # たまごさん指定の合格点
MAX_REWRITES = 3         # 落ちたら書き直す。3回で保留に倒す
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) nyuka-sekisho/1.0"


# ===========================================================================
# 門0：棚に出せるか（動画idが無いものを「通った」にしない）
# ===========================================================================
#
# 足した理由（2026-09-22・1024番の申し送りにあった穴）:
#   友川カズキ10曲・特撮3曲・akiko1曲の**14曲が門1〜門5を全部通って done/ に入った。
#   なのに棚に1曲も出ていない。**理由は youtubeId が無いから。押しても何も鳴らない。
#   関所が「PASS」と言ったのに棚に出せない＝**通ったのか通っていないのか分からない状態**で
#   3日間止まっていた。しかも done/ の中なので、誰も気づかない（進捗表にも出ない）。
#
#   これは1曲ずつ拾う話ではなく、**関所に門が1つ足りなかった**という話。
#   札は「押したら鳴る」までが1枚。鳴らない札は札ではない。
#   だから入口で落とす。落ちれば hold/ に理由つきで残り、進捗表から見える。
#
# ★ここで動画を探しには行かない。探した結果が正しい保証が無いから（関所の掟）。
#   「動画idを人が確かめて入れる」までが仕入れ、と決める。

YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
YT_URL = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:[^&]*&)*v=|embed/|shorts/|live/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})")


def gate0_shelf(item):
    """棚に出せるか。出せないなら理由を返す（空文字なら出せる）。

    youtubeUrl しか無い入荷票は、URLから11文字のidを機械で取り出して埋める。
    取り出せない／形が違うものは通さない。**探しには行かない。**
    """
    yid = (item.get("youtubeId") or "").strip()
    if not yid:
        for k in ("youtubeUrl", "youtube", "movieUrl", "url"):
            m = YT_URL.search(str(item.get(k) or ""))
            if m:
                yid = m.group(1)
                item["youtubeId"] = yid
                item["youtubeIdFrom"] = k
                break
    if not yid:
        return ("動画idが無い（押しても何も鳴らないので札にできない）。"
                "入荷票に \"youtubeId\": \"<11文字>\" を入れてから積み直してください")
    if not YT_ID.match(yid):
        return "動画idの形が違う（11文字の英数字・_・- のはず）: %r" % yid[:40]
    item["youtubeId"] = yid
    return ""


# ===========================================================================
# 門1の心臓部：出典の機械照合
# ===========================================================================

# 投稿型（誰でも書ける）ドメイン。**1本では採用しない。**
# skill sekisho-jijitsu-shutten:「投稿型のデータベースは、それ1本では採用しない。
#   独立したもう1本と一致したときだけ採用する」
USER_SUBMITTED = (
    "wikipedia.org", "wikiwand.com", "fandom.com", "discogs.com",
    "secondhandsongs.com", "genius.com", "utaten.com", "uta-net.com",
    "j-lyric.net", "last.fm", "rateyourmusic.com", "musicbrainz.org",
    "note.com", "ameblo.jp", "hatenablog.com", "blog.livedoor.jp",
)
# 検索結果の要約は出典にしない（要約はAIが作っている）。
# 検索エンジンのURLが出典欄に入っていたら、その時点で無効にする。
NOT_A_SOURCE = ("google.com/search", "bing.com/search", "duckduckgo.com",
                "search.yahoo", "perplexity.ai")

_TAG_RE = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>|<[^>]+>")
_WS_RE = re.compile(r"[\s　]+")


def fetch_text(url, timeout=25):
    """ページを実際に取得して、タグを落とした本文を返す。取れなければ None。

    2026-09-19：SecondHandSongs が素のurllibを 403 で弾き、**裏の取れている事実
    （「Girl Talk」の作者 Neal Hefti / Bobby Troup・原曲1965年）が
    「独立したもう1本が取れない」で落ちた**。門が厳しいのは正しいが、
    取りに行き方が下手で落とすのは関所の失点なので、ブラウザと同じ頭で2回叩く。
    """
    heads = (
        {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/127.0.0.0 Safari/537.36"),
         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
         "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
         "Cache-Control": "no-cache"},
        {"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"},
    )
    raw = None
    for h in heads:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                        timeout=timeout) as resp:
                raw = resp.read(3_000_000)
            break
        except Exception:
            continue
    if raw is None:
        return None
    try:
        enc = "utf-8"
        m = re.search(rb'charset=["\']?([A-Za-z0-9_\-]+)', raw[:4000])
        if m:
            enc = m.group(1).decode("ascii", "ignore")
        html = raw.decode(enc, "ignore")
    except Exception:
        return None
    text = _TAG_RE.sub(" ", html)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&quot;", '"').replace("&#39;", "'")
                .replace("&lt;", "<").replace("&gt;", ">"))
    return _WS_RE.sub(" ", text)


def _norm(s):
    """照合用に丸める。全角/半角・大小文字・中黒・記号の揺れで落とさないため。"""
    s = (s or "").lower()
    s = s.replace("・", "").replace("･", "").replace("’", "'").replace("”", '"')
    return _WS_RE.sub("", re.sub(r"[‐-‒–—―ー\-_/,.、。！!？?()（）\[\]「」『』:：;；]", "", s))


def probes_of(fact):
    """その事実が「ページに載っている」と言えるための語。
    value は必須。needles は補助（曲名・人名など、どれか1つ当たればよい）。"""
    val = str(fact.get("value") or "").strip()
    needles = [str(x) for x in (fact.get("needles") or []) if str(x).strip()]
    return val, needles


def verify_fact(fact, cache):
    """事実1件を、出典URLを実際に取得して照合する。
    戻り値: (ok: bool, evidence: list, why: str)

    通す条件（どちらか）:
      A) 投稿型でない出典が1本、照合できた
      B) 独立した（ドメインの異なる）出典が2本、照合できた
    """
    val, needles = probes_of(fact)
    srcs = [s for s in (fact.get("src") or []) if isinstance(s, str) and s.startswith("http")]
    if not val:
        return False, [], "値が空"
    if not srcs:
        return False, [], "出典URLが無い"

    evidence, seen_domains, editorial_hit = [], set(), False
    for url in srcs[:6]:
        low = url.lower()
        if any(bad in low for bad in NOT_A_SOURCE):
            evidence.append({"src": url, "matched": False,
                             "why": "検索結果は出典にしない"})
            continue
        if url not in cache:
            cache[url] = fetch_text(url)
        body = cache[url]
        if body is None:
            evidence.append({"src": url, "matched": False, "why": "取得できなかった"})
            continue
        nb = _norm(body)
        hit_val = _norm(val) in nb
        hit_needle = (not needles) or any(_norm(x) in nb for x in needles)
        matched = bool(hit_val and hit_needle)
        host = urllib.parse.urlparse(url).netloc.lower()
        submitted = any(host.endswith(d) or ("." + d) in host for d in USER_SUBMITTED)
        evidence.append({"src": url, "matched": matched, "submitted": submitted,
                         "why": "" if matched else
                                ("値がページに無い" if not hit_val else "手がかり語がページに無い")})
        if matched:
            seen_domains.add(host)
            if not submitted:
                editorial_hit = True

    if editorial_hit:
        return True, evidence, "投稿型でない出典で照合"
    if len(seen_domains) >= 2:
        return True, evidence, "独立した2本の一致で照合"
    if seen_domains:
        return False, evidence, "投稿型1本だけ。独立したもう1本が必要"
    return False, evidence, "どの出典でも照合できなかった"


def gate1_facts(facts):
    """門1。裏の取れた事実だけを通す。取れなかったものは落として記録する。"""
    cache, kept, dropped = {}, [], []
    for f in facts or []:
        ok, ev, why = verify_fact(f, cache)
        row = dict(f)
        row["evidence"] = ev
        row["why"] = why
        (kept if ok else dropped).append(row)
    return kept, dropped


# ===========================================================================
# 門2：別人を止める（skill sekisho-artist-song）
# ===========================================================================

def gate2_not_someone_else(artist, title, kept_facts):
    """曲名に「自分の名前を含む別人のフルネーム」が入っていないか等。
    判定Aは落とす、B・Cは保留に倒す（載せない側に倒す＝掟4）。"""
    ng = []
    a = _norm(artist)
    t = title or ""
    # 判定A/B：演者位置に別アーティスト名が丸ごと入っている
    for sep in (" - ", "/", "／", "feat.", "feat ", "with ", "×", " x "):
        if sep in t.lower():
            for part in re.split(re.escape(sep), t, flags=re.IGNORECASE):
                p = _norm(part)
                if p and a and a in p and p != a and len(p) > len(a):
                    ng.append("曲名の演者位置に『%s』がある。自分の名前を含む"
                              "別人のフルネームの疑い（掟A/B）" % part.strip())
    # 判定C：note も year も原曲情報も無い
    if not kept_facts:
        ng.append("裏の取れた事実が1件も無い。名前で検索して拾っただけの疑い（掟C）")
    # 本人が演っているという裏が要る
    if not any((f.get("key") or "") == "performer" for f in kept_facts):
        ng.append("『この曲を演っているのは本人か』の裏が取れていない")
    return ng


# ===========================================================================
# 門3：文脈を決める（裏の取れた事実からしか決めない）
# ===========================================================================

# 「事実の中にこの語が確認できたら、この棚の文脈を付けてよい」という対応表。
# 当てずっぽうで文脈を付けないための唯一の入口。
#
# 書き方は3通り。
#   (棚の名前, 引き金になる語)
#   (棚の名前, 引き金になる語, 一緒に無いと付けない語)          ← 共起条件つき
#   (棚の名前, 引き金になる語, 一緒に無いと付けない語, 止める語)  ← これがあれば付けない
#
# 共起条件を足した理由（2026-09-22）:
#   友川カズキ（フォークの弾き語り）を入荷したとき、公式サイトの「友川かずき（vo, g）」
#   という演奏者表記だけで「ジャズ・ボーカル」が付いた。**別ジャンルの棚に入れる事故。**
#   「vocal」はジャンルを示さない。ジャズの語が一緒に無ければジャズの棚には入れない。
#   同じ理由で「カバー」の引き金から「作曲」を外した。作曲クレジットがあることは
#   カバーであることを意味しない（ミステリーナイトは大槻ケンヂ作詞・NARASAKI作曲の
#   バンドのオリジナル曲だが、「作曲」の一語で「カバー」が付いていた）。
#
# 止める語を足した理由（2026-09-22・門3の同じ型の2件目）:
#   友川カズキ「祭りの花を買いに行く」は**友川が書いてちあきなおみに渡した曲**で、
#   この映像は本人が自分の曲を歌っている。なのに公式サイトの「ちあきなおみに提供した
#   〜のセルフカバー」という一文から「カバー」が付いた。**作者を、他人の曲を歌った人に
#   してしまう事故。**「提供した」は渡した側の語であって、カバーの語ではない。
#   渡した事実は「他の歌手に渡した曲」という別の棚で受ける。
CONTEXT_RULES = (
    # ── ジャズまわり（ジャズの語が要る） ──────────────────────────
    ("ジャズ・シンガー", ("ジャズ", "jazz", "ヴァーヴ", "verve", "スタンダード")),
    ("ジャズ・ボーカル", ("vo)", "(vo", "ボーカル", "vocal", "歌唱"),
                      ("ジャズ", "jazz", "スタンダード", "standard", "ヴァーヴ", "verve")),
    ("スタンダード", ("スタンダード", "standard", "ジャズ・スタンダード")),
    # ── ジャンルを問わないもの ────────────────────────────────
    ("女性ボーカル", ("女性", "歌姫", "she ", "female")),
    ("カバー", ("カバー", "カヴァー", "cover", "written by", "first released"),
             None,
             ("提供した", "に提供", "提供曲", "セルフカバー", "セルフ・カバー")),
    ("他の歌手に渡した曲", ("提供した", "に提供", "提供曲")),
    ("デビュー作", ("デビュー", "debut", "1st album", "ファースト")),
    # ── ここから追加（2026-09-22）。日本のフォーク／ロックの入荷が
    #    文脈ゼロで門3に落ちていたのを直す ─────────────────────
    ("弾き語り", ("vo, g", "vo,g", "弾き語り", "（vo, g", "guitar）")),
    ("ライブ映像", ("live", "ライブ", "公演", "manda-la", "apia", "無観客")),
    ("バンド", ("編曲：特撮", "バンド", "band", "ドラム", "drums", "頭脳警察")),
    ("フォーク", ("フォーク", "folk", "シンガー・ソングライター", "singer-songwriter")),
    ("実際の出来事から", ("事件", "実話", "題材を求め")),
    # 2026-09-24：ドラマのタイアップ曲が棚ゼロで落ちていた（Bialystocks「差し色」＝
    #   ドラマ『先生のおとりよせ』のエンディングテーマ）。「ドラマ」「エンディングテーマ」
    #   「オープニングテーマ」が鍵に入っていなかっただけ。ジャンルを裏返す語ではないので
    #   共起条件は付けない。
    ("映画・ドラマから", ("映画", "主題歌", "劇中歌", "サントラ", "ドラマ",
                       "エンディングテーマ", "オープニングテーマ", "edテーマ",
                       "opテーマ", "挿入歌")),
    ("競輪", ("競輪",)),
    ("絵を描く人", ("画家", "絵画", "絵描き")),
    ("オカルト・不思議", ("ムー", "オカルト", "怪", "ミステリー")),
)


def gate3_context(kept_facts, declared=None):
    """裏の取れた事実の本文から、付けてよい文脈だけを拾う。
    declared（人が指定した文脈）も、事実で裏打ちできるものだけ通す。"""
    hay = " ".join([
        str(f.get("value") or "") + " " + str(f.get("claim") or "") + " " +
        " ".join(str(x) for x in (f.get("needles") or []))
        for f in kept_facts
    ]).lower()

    def _hit(rule):
        name, keys = rule[0], rule[1]
        require = rule[2] if len(rule) > 2 else None
        block = rule[3] if len(rule) > 3 else None
        if not any(k.lower() in hay for k in keys):
            return False
        # 共起条件つきの棚は、その語が一緒に無ければ付けない
        if require and not any(k.lower() in hay for k in require):
            return False
        # 止める語がひとつでもあれば付けない（意味が裏返る語を弾く）
        if block and any(k.lower() in hay for k in block):
            return False
        return True

    shelves = [r[0] for r in CONTEXT_RULES if _hit(r)]
    rejected = []
    for d in (declared or []):
        if d not in shelves:
            rejected.append(d)
    return shelves, rejected


# ===========================================================================
# 門4：コピーを機械で落とす（採点の前に、型で落ちるものは型で落とす）
# ===========================================================================

# ★これが今回の本題。**画像に写っているものだけで書ける語。**
# たまごさんの不合格例：「編み込まれた髪と横顔。その静かな視線の先に、
#   夜の会話の続きが聴こえてくる。」＝ジャケットを見ただけで書ける語しか無い。
LOOKS_ONLY = ("髪", "横顔", "視線", "まなざし", "眼差し", "瞳", "目もと", "目元",
              "微笑", "笑顔", "唇", "首筋", "うなじ", "ドレス", "帽子", "ジャケットの",
              "写真の", "うつむ", "伏し目", "肩", "指先", "たたずむ", "佇む")

# 水道水コピー・観測していない反応（skill bonjovi-ojisan-kobun の禁止）
TAP_WATER = ("代表曲のひとつ", "代表曲の一つ", "名曲のひとつ", "不朽の名作",
             "must listen", "必聴", "永遠の名曲")
UNOBSERVED = ("話題", "反響", "絶賛", "続出", "バズ", "殺到", "涙が止まらな")


def gate4_copy_shape(copy, kept_facts):
    """コピーの形を機械で見る。ここで落ちたものは外部AIに投げない（金を使わない）。"""
    ng = []
    c = copy or ""
    if not c.strip():
        return ["コピーが空"]
    if len(c) > 120:
        ng.append("長い（%d字）。深さは曲ページのメモへ回す" % len(c))

    looks = [w for w in LOOKS_ONLY if w in c]
    if looks:
        ng.append("見た目だけで書ける語がある：%s。"
                  "画像に写っているものだけで書かない" % "／".join(looks))
    for w in TAP_WATER:
        if w in c:
            ng.append("水道水コピー：『%s』" % w)
    for w in UNOBSERVED:
        if w in c:
            ng.append("観測していない反応：『%s』" % w)

    # ★1049番（2026-09-24）：**裏の取れていない数字を書かせない。**
    #   実測：この便で書いたコピーに「4分」「3分」「バンド4人」が混ざった。どれも
    #   動画を見ずに書いた数字＝嘘になりうる。年号・人数・尺は事実で裏打ちされた
    #   ものしか書かない（たまご憲法11条／関所 sekisho-jijitsu-shutten）。
    #   単位を絞ってあるのは「1曲目」「ひと言」のような言い回しまで落とさないため。
    hay_facts = " ".join(
        [str(f.get("value") or "") + " " + str(f.get("claim") or "") + " " +
         " ".join(str(x) for x in (f.get("needles") or [])) for f in kept_facts])
    for num, unit in re.findall(r"(\d+)\s*(分|秒|人|年|歳|枚|位|回|周年|作目|人組)", c):
        if num not in hay_facts:
            ng.append("裏の取れていない数字：『%s%s』。"
                      "事実として出典を取ったものしか数字は書かない" % (num, unit))

    # 裏取り済み事実が1つも入っていないコピーは通さない
    hit = []
    for f in kept_facts:
        for probe in [str(f.get("value") or "")] + \
                     [str(x) for x in (f.get("needles") or [])]:
            p = _norm(probe)
            if p and len(p) >= 2 and p in _norm(c):
                hit.append(probe)
                break
    if not hit:
        ng.append("裏取り済みの事実が1つも入っていない")
    return ng


# ===========================================================================
# 門5：採点は外部AIにやらせる（こちらの自己採点は使わない）
# ===========================================================================

SCORE_SYSTEM = """あなたは日本語音楽サイト「ごきげん補給所」の、コピーを採点する外部審査員です。
依頼者（たまごさん）は、見た目（ジャケット画像）だけを見て書いた雰囲気コピーを最も嫌います。
その典型例を、依頼者自身が60点と採点しました：
  「編み込まれた髪と横顔。その静かな視線の先に、夜の会話の続きが聴こえてくる。」
  （髪・横顔・視線＝ジャケットを見れば誰でも書ける。曲について何も知らずに書ける）
合格は80点です。甘くつけないでください。忖度は依頼者への裏切りです。

次の5つの観点で各0〜20点、合計100点で採点してください。

1. 事実（裏取り済み事実が入っていて、しかも誤りが無いか。
   「裏取り済み事実」として渡したもの以外の断定が混ざっていたら大幅減点）
2. 見た目依存の排除（画像を見れば誰でも書ける語で埋めていないか。
   髪・横顔・視線・瞳・微笑のような語が主役なら10点以下）
3. 事件になっているか（ただの行為が小さな事件に変わっているか。
   例：車の中でバラードを聴くだけ→ふたりだけの教会。単なる曲紹介なら10点以下）
4. 入口（初めて見る人が入れるか。かつ、そのアーティストのファンが動くか。
   難解すぎても、薄すぎても減点）
5. 水道水でないか（「代表曲のひとつ」のように誰にでも書ける説明になっていないか）

必ずこのJSONだけを返してください：
{"total": 整数, "axes": {"fact": 整数, "looks": 整数, "incident": 整数,
 "entry": 整数, "tapwater": 整数}, "ng": ["直すべき点", ...],
 "fix_hint": "80点に届かせるための具体的な一手"}"""


def score_prompt(item, copy, kept_facts):
    facts = "\n".join(
        "・[%s] %s ／ 出典: %s" % (f.get("key"), f.get("claim") or f.get("value"),
                                 ", ".join(f.get("src") or []))
        for f in kept_facts) or "(なし)"
    return (
        "【曲】%s ／ %s\n"
        "【棚の文脈】%s\n"
        "【裏取り済み事実（これ以外の断定は書いてはいけない）】\n%s\n\n"
        "【採点するコピー】\n%s\n"
    ) % (item.get("artist", ""), item.get("title", ""),
         " / ".join(item.get("context") or []), facts, copy)


def ask_external_score(item, copy, kept_facts):
    """外部AIに0〜100点を付けさせる。戻り値 (score:int|None, detail:dict, err:str)"""
    try:
        import gaibu_kenpin as gk
    except Exception as e:
        return None, {}, "gaibu_kenpin を読めませんでした（%s）" % e

    ok, why = gk.check_cost_cap()
    if not ok:
        return None, {}, "費用の上限で止めました：%s" % why

    api_key = gk._find_env_key(("OPENAI_API_KEY",))
    if not api_key:
        return None, {}, "OpenAIの鍵が見つかりません（このサンドボックスからは届かない）"

    body_base = {
        "messages": [
            {"role": "system", "content": SCORE_SYSTEM},
            {"role": "user", "content": score_prompt(item, copy, kept_facts)},
        ],
        "response_format": {"type": "json_object"},
    }
    errs = []
    for model in gk.OPENAI_MODEL_CANDIDATES:
        body = dict(body_base, model=model)
        try:
            req = urllib.request.Request(
                gk.OPENAI_URL, data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer %s" % api_key}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                j = json.loads(resp.read().decode("utf-8", "ignore"))
            content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
            parsed = json.loads(content)
            total = int(parsed.get("total"))
            row = gk.record_cost(item.get("id"), "入荷の関所 採点", "OpenAI", model,
                                 j.get("usage") or {},
                                 "PASS" if total >= PASS_SCORE else "FIX",
                                 note="入荷の関所(nyuka_sekisho) コピー採点")
            parsed["_model"] = model
            parsed["_ledger"] = row
            return total, parsed, ""
        except Exception as e:
            errs.append("%s: %s" % (model, e))
    return None, {}, "採点の呼び出しに失敗（%s）" % " / ".join(errs)


WRITE_SYSTEM = """あなたは日本語音楽サイト「ごきげん補給所」のコピーライターです。
書き方の型（これ以外の型で書いてはいけない）:
・普通の場所・普通の人・普通の曲が、急に事件になる。ただの行為を、気分の事件に変える。
  例：車の中でバラードを聴くだけ → 狭い車の中が、ふたりだけの教会になる。
・短く。2文まで。深い説明は書かない。
・**渡された「裏取り済み事実」から1つを必ず入れる。それ以外の断定は絶対に書かない。**
  年・原曲・誰の曲か・誰と演ったか以外の事実を勝手に足したら不合格。
・**ジャケット画像を見れば誰でも書ける語を使ってはいけない。**
  髪・横顔・視線・瞳・微笑・唇・ドレス・帽子……これらは禁止。
・「代表曲のひとつ」のような誰にでも書ける説明は禁止。
・話題／反響／絶賛／続出のような、観測していない反応は禁止。
返すのはJSONだけ：{"copy": "本文", "why": "どの事実をどう使ったか"}"""


def ask_external_rewrite(item, kept_facts, prev_copy, ng, hint):
    """落ちたコピーを書き直させる。"""
    try:
        import gaibu_kenpin as gk
    except Exception as e:
        return None, "gaibu_kenpin を読めませんでした（%s）" % e
    ok, why = gk.check_cost_cap()
    if not ok:
        return None, "費用の上限で止めました：%s" % why
    api_key = gk._find_env_key(("OPENAI_API_KEY",))
    if not api_key:
        return None, "OpenAIの鍵が見つかりません"

    user = score_prompt(item, prev_copy or "(まだ無し)", kept_facts) + (
        "\n【このコピーは落ちました。直すべき点】\n%s\n【一手】\n%s\n"
        "上の型と事実だけで、書き直してください。" %
        ("\n".join("・" + x for x in (ng or [])), hint or ""))
    for model in gk.OPENAI_MODEL_CANDIDATES:
        try:
            req = urllib.request.Request(
                gk.OPENAI_URL,
                data=json.dumps({"model": model, "response_format": {"type": "json_object"},
                                 "messages": [{"role": "system", "content": WRITE_SYSTEM},
                                              {"role": "user", "content": user}]}).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer %s" % api_key}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                j = json.loads(resp.read().decode("utf-8", "ignore"))
            content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
            copy = (json.loads(content).get("copy") or "").strip()
            gk.record_cost(item.get("id"), "入荷の関所 書き直し", "OpenAI", model,
                           j.get("usage") or {}, "FIX",
                           note="入荷の関所(nyuka_sekisho) コピー書き直し")
            if copy:
                return copy, ""
        except Exception as e:
            last = str(e)
            continue
    return None, "書き直しの呼び出しに失敗"


# ===========================================================================
# 通し（5つの門を順に）
# ===========================================================================

def run_gates(item, quiet=False):
    def say(s):
        if not quiet:
            print(s)

    out = {"id": item.get("id"), "artist": item.get("artist"),
           "title": item.get("title"), "url": item.get("url"),
           "at": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"), "gates": {}}

    # 門0 棚に出せるか ------------------------------------------------------
    # ★採点にお金を使う前にここで落とす。鳴らない札にAPI代を払う意味が無い。
    block = gate0_shelf(item)
    out["youtubeId"] = item.get("youtubeId")
    out["gates"]["0_shelf"] = ("NG: " + block) if block else "OK"
    if block:
        say("門0 棚：出せない … %s" % block)
        return _hold(out, "棚に出せない（門0）: %s" % block)
    say("門0 棚：出せる（動画id %s）" % item.get("youtubeId"))

    # 門1 ----------------------------------------------------------------
    kept, dropped = gate1_facts(item.get("facts"))
    out["facts"] = kept
    out["factsDropped"] = dropped
    out["gates"]["1_facts"] = {"kept": len(kept), "dropped": len(dropped)}
    say("門1 事実：裏が取れた %d件／落とした %d件" % (len(kept), len(dropped)))
    for d in dropped:
        say("   落: [%s] %s … %s" % (d.get("key"), d.get("value"), d.get("why")))
    if not kept:
        return _hold(out, "裏の取れた事実が1件も無い（門1）")

    # 門2 ----------------------------------------------------------------
    ng2 = gate2_not_someone_else(item.get("artist", ""), item.get("title", ""), kept)
    out["gates"]["2_artist"] = ng2 or "OK"
    say("門2 別人：%s" % ("OK" if not ng2 else " ／ ".join(ng2)))
    if ng2:
        return _hold(out, "別人混入の疑い（門2）：" + " ／ ".join(ng2))

    # 門3 ----------------------------------------------------------------
    shelves, rejected = gate3_context(kept, item.get("context"))
    out["context"] = shelves
    out["contextRejected"] = rejected
    out["gates"]["3_context"] = {"ok": shelves, "rejected": rejected}
    item["context"] = shelves
    say("門3 文脈：%s%s" % (" / ".join(shelves) or "(無し)",
                          "　※裏打ちできず外した：" + "/".join(rejected) if rejected else ""))
    if not shelves:
        return _hold(out, "事実から棚の文脈が決まらない（門3）")

    # 参考採点 … ゲートには使わない。before/after を並べて見せるためだけの採点。
    # （たまごさんへの報告で「前は何点だったのか」を外部AIの数字で示すため）
    also = []
    for ref in (item.get("alsoScore") or []):
        s, d, e = ask_external_score(item, ref, kept)
        also.append({"copy": ref, "score": s, "axes": d.get("axes"),
                     "ng": d.get("ng"), "by": d.get("_model"), "err": e})
        say("参考採点：%s点 … %s" % (s, ref[:40]))
    if also:
        out["alsoScored"] = also

    # 門4・門5（書く→型で落とす→外部AIで採点。通るまで最大3回）--------------
    copy = (item.get("copy") or "").strip()
    tries = []
    for attempt in range(1, MAX_REWRITES + 2):
        if not copy:
            copy, err = ask_external_rewrite(item, kept, "", ["まだ書かれていない"], "")
            if not copy:
                return _skip(out, err)
        shape_ng = gate4_copy_shape(copy, kept)
        if shape_ng:
            say("門4 型：落ちた（%d回目）%s" % (attempt, " ／ ".join(shape_ng)))
            tries.append({"attempt": attempt, "copy": copy, "score": None,
                          "ng": shape_ng, "by": "型（機械）"})
            if attempt > MAX_REWRITES:
                break
            copy, err = ask_external_rewrite(item, kept, copy, shape_ng, "")
            if not copy:
                return _skip(out, err)
            continue

        score, detail, err = ask_external_score(item, copy, kept)
        if score is None:
            out["tries"] = tries
            return _skip(out, err)
        say("門5 採点：%d点（%d回目・%s）" % (score, attempt, detail.get("_model")))
        tries.append({"attempt": attempt, "copy": copy, "score": score,
                      "axes": detail.get("axes"), "ng": detail.get("ng"),
                      "by": "外部AI(OpenAI %s)" % detail.get("_model")})
        if score >= PASS_SCORE:
            out["tries"] = tries
            out["copy"] = copy
            out["score"] = score
            out["axes"] = detail.get("axes")
            out["scoredBy"] = "OpenAI %s" % detail.get("_model")
            return _done(out)
        if attempt > MAX_REWRITES:
            break
        copy, err = ask_external_rewrite(item, kept, copy, detail.get("ng"),
                                         detail.get("fix_hint"))
        if not copy:
            out["tries"] = tries
            return _skip(out, err)

    out["tries"] = tries
    best = max([t for t in tries if t.get("score")], key=lambda t: t["score"], default=None)
    out["score"] = best and best["score"]
    return _hold(out, "%d回書き直しても%d点に届かなかった（最高%s点）"
                 % (len(tries), PASS_SCORE, out["score"]))


def _write(d, out):
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "%s.json" % (out.get("id") or int(time.time())))
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return p


def _done(out):
    out["state"] = "passed"
    out["path"] = _write(DONE_DIR, out)
    print("NYUKA_RESULT: PASS %s - %s" % (out.get("score"), out.get("copy")))
    return 0


def _hold(out, why):
    out["state"] = "hold"
    out["holdReason"] = why
    out["path"] = _write(HOLD_DIR, out)
    # 保留はたまごさんに出さない（依頼どおり）。棚にも検索にも載せない。
    print("NYUKA_RESULT: HOLD %s - %s" % (out.get("score"), why))
    return 1


def _skip(out, why):
    out["state"] = "skip"
    out["skipReason"] = why
    out["path"] = _write(HOLD_DIR, out)
    print("NYUKA_RESULT: SKIP - %s" % why)
    return 2


# ===========================================================================
# 積む（サンドボックス側）／走らせる（Mac側）
# ===========================================================================

def cmd_submit(path):
    item = json.load(io.open(path, encoding="utf-8"))
    if not item.get("id"):
        item["id"] = re.sub(r"[^A-Za-z0-9]+", "-",
                            "%s-%s" % (item.get("artist", ""), item.get("title", "")))[:60].strip("-") \
                     or str(int(time.time()))
    # ★門0はここでも見る。**積む前に落とす**＝鳴らない札が pending/ に溜まらない。
    block = gate0_shelf(item)
    if block:
        print("積めません（門0・棚に出せない）: %s" % block)
        print("  %s ― %s" % (item.get("artist", "?"), item.get("title", "?")))
        return 1
    item["submittedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    os.makedirs(PENDING_DIR, exist_ok=True)
    p = os.path.join(PENDING_DIR, "%s.json" % item["id"])
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(item, f, ensure_ascii=False, indent=1)
    print("積みました: %s" % p)
    print("Mac側の5分おきの便が --run-pending で拾います。")
    return 0


def cmd_run_pending(max_jobs, quiet):
    os.makedirs(PENDING_DIR, exist_ok=True)
    files = sorted(p for p in os.listdir(PENDING_DIR) if p.endswith(".json"))
    if not files:
        if not quiet:
            print("積まれているものはありません。")
        return 0
    last = 0
    for fn in files[:max_jobs]:
        p = os.path.join(PENDING_DIR, fn)
        try:
            item = json.load(io.open(p, encoding="utf-8"))
        except Exception as e:
            print("読めませんでした %s: %s" % (fn, e))
            continue
        rc = run_gates(item, quiet=quiet)
        last = rc
        if rc in (0, 1):          # 通った／保留 … 片づける
            try:
                os.remove(p)
            except Exception:
                pass
        # rc==2（鍵無し・上限）は積んだまま残す＝次の便で再挑戦する
    return last


def cmd_selftest():
    """関所が生きているかを見本で確かめる（落ちなくなったら関所が壊れている）。"""
    bad = "編み込まれた髪と横顔。その静かな視線の先に、夜の会話の続きが聴こえてくる。"
    facts = [{"key": "year", "value": "2001", "claim": "2001年", "src": ["https://example.invalid"]}]
    ng = gate4_copy_shape(bad, facts)
    print("見本（たまごさんが60点と言ったコピー）→ %d件で落ちた" % len(ng))
    for x in ng:
        print("  ・" + x)
    ok2 = gate4_copy_shape("2001年、パリで録った1曲目から、部屋がいきなり小さなクラブになる。", facts)
    print("見本（事実入り・見た目語なし）→ %s" % (ng2 := ("OK" if not ok2 else ok2)))
    # 出典照合が「取れないものを落とす」側に倒れているか
    kept, dropped = gate1_facts([{"key": "year", "value": "2001",
                                  "src": ["https://example.invalid/nothing"]}])
    print("出典が死んでいる事実 → 通った%d件／落とした%d件（落とした側が正しい）"
          % (len(kept), len(dropped)))
    assert ng, "関所が壊れている：60点コピーが通ってしまった"
    assert not kept, "関所が壊れている：出典が取れない事実が通ってしまった"

    # 門3が「別ジャンルの棚に入れる」事故を繰り返さないか（2026-09-22 の2件が見本）
    folk = [{"key": "performer", "value": "友川かずき",
             "claim": "公式サイトに「演奏者： 友川かずき（vo, g）」と明記。"}]
    s3, _ = gate3_context(folk)
    print("フォークの弾き語り → %s" % (" / ".join(s3) or "(無し)"))
    assert not [x for x in s3 if "ジャズ" in x], \
        "関所が壊れている：ジャズでない人にジャズの棚が付いた（vo, g だけで付けない）"

    gift = [{"key": "provided_to", "value": "ちあきなおみ",
             "claim": "公式サイトに「ちあきなおみに提供した「祭りの花を買いに行く」のセルフカバー」と明記。"}]
    s3b, _ = gate3_context(gift)
    print("他の歌手に渡した自作曲 → %s" % (" / ".join(s3b) or "(無し)"))
    assert "カバー" not in s3b, \
        "関所が壊れている：曲を書いて渡した人が、他人の曲を歌った人にされた"

    # 門0（2026-09-22）。見本は**実際に3日間止まっていた14曲**の形。作った例ではない。
    nashi = {"id": "tomokawa-kazuki-inu", "artist": "友川カズキ", "title": "犬・秋田・1976",
             "url": "https://tomokawakazuki.com/"}
    b0 = gate0_shelf(nashi)
    print("動画idの無い入荷票 → %s" % (b0 or "(通ってしまった)"))
    assert b0, "関所が壊れている：押しても鳴らない札が「通った」になった"

    kara = {"id": "x", "artist": "a", "title": "b",
            "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s"}
    b1 = gate0_shelf(kara)
    print("URLしか無い入荷票 → %s（idを取り出せたら正しい）"
          % (b1 or ("OK id=" + kara["youtubeId"])))
    assert not b1 and kara["youtubeId"] == "dQw4w9WgXcQ", \
        "関所が壊れている：YouTubeのURLから動画idを取り出せなくなった"

    hen = {"id": "y", "artist": "a", "title": "b", "youtubeId": "https://youtu.be/"}
    b2 = gate0_shelf(hen)
    print("形の違う動画id → %s" % (b2 or "(通ってしまった)"))
    assert b2, "関所が壊れている：11文字でないものが動画idとして通った"

    print("SELFTEST: OK")
    return 0


def cmd_shelf_check():
    """done/ に「通ったのに棚へ出せないもの」が残っていないか数えて、**進捗表から見える所**に出す。

    done/ の中は誰も見ない。14曲が3日間そこで止まっていたのに誰も気づかなかったのは、
    止まっている場所が暗かったから。数を status/public に出して、暗がりを無くす。
    """
    rows = []
    if os.path.isdir(DONE_DIR):
        for fn in sorted(os.listdir(DONE_DIR)):
            if not fn.endswith(".json"):
                continue
            try:
                d = json.load(io.open(os.path.join(DONE_DIR, fn), encoding="utf-8"))
            except Exception:
                continue
            block = gate0_shelf(d)
            if block:
                rows.append({"id": d.get("id"), "artist": d.get("artist"),
                             "title": d.get("title"), "at": d.get("at"),
                             "why": block.split("。")[0]})
    out = {
        "asOf": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "tsumatteru": len(rows),
        "hitokoto": ("棚に出せず止まっているものはありません。" if not rows else
                     "関所は通ったのに**棚に出せない**ものが %d曲あります。"
                     "動画idが無いので押しても鳴りません。"
                     "入荷票に youtubeId を入れて積み直すと棚に出ます。" % len(rows)),
        "rows": rows,
    }
    p = os.path.join(REPO, "status", "public", "nyuka_shelf.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("棚に出せず止まっているもの: %d曲" % len(rows))
    for r in rows:
        print("  ・%s ― %s（%s）" % (r["artist"], r["title"], (r["at"] or "")[:10]))
    print("書きました: %s" % p)
    return 0


def main():
    ap = argparse.ArgumentParser(description="入荷の関所 — 入口で事実・文脈・コピーを80点で決める")
    ap.add_argument("--submit", action="store_true", help="積むだけ（APIを呼ばない・サンドボックス用）")
    ap.add_argument("--json", dest="json_path", default=None, help="入荷票のJSON")
    ap.add_argument("--run", action="store_true", help="その場で5つの門を通す（鍵が要る）")
    ap.add_argument("--run-pending", action="store_true", help="積まれた分を通す（Mac側の便から）")
    ap.add_argument("--max-jobs", type=int, default=3)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--shelf-check", dest="shelf_check", action="store_true",
                    help="通ったのに棚へ出せないものを数えて status/public に出す")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return cmd_selftest()
    if a.shelf_check:
        return cmd_shelf_check()
    if a.submit:
        if not a.json_path:
            print("--json が必要です")
            return 2
        return cmd_submit(a.json_path)
    if a.run:
        if not a.json_path:
            print("--json が必要です")
            return 2
        return run_gates(json.load(io.open(a.json_path, encoding="utf-8")), quiet=a.quiet)
    if a.run_pending:
        return cmd_run_pending(a.max_jobs, a.quiet)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
