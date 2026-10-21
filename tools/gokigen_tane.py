#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ごきげんの種（今週のごきげん一粒）の配信便（2026-10-21 たまごさん決定）。

■ 何をするか
  週に1回、金曜20時（日本時間）に、LINE公式アカウントの友だち全員へ「1粒」を送る。
  1粒＝本当にいい曲1つ＋事実1行＋卵コンシェルジュ（変な面白いおっちゃん）の一言＋曲ページのリンク。案A（一言だけ・3秒）。
  目的はリスト取り。最初の客はたまごさん本人（テスト）。

■ 決め
  ・送り方は LINE Messaging API の broadcast（友だち全員へ）だけ。公式の口。新しい課金APIは増やさない。
      POST https://api.line.me/v2/bot/message/broadcast   （X-Line-Retry-Key で二重送信を防ぐ）
      GET  https://api.line.me/v2/bot/message/quota        （今月の上限）
      GET  https://api.line.me/v2/bot/message/quota/consumption（今月使った数）
      GET  https://api.line.me/v2/bot/insight/followers?date=YYYYMMDD（届く人数＝targetedReaches）
  ・鍵は ~/.tamago/keys/api_keys.env の LINE_CHANNEL_ACCESS_TOKEN。無い間は送らず、下書きだけ作る（ログに1回だけ書く）。
  ・お金の関所：今月使った数＋今回届く人数が無料枠（200通）を超えるなら送らない。Dispatch へ1行。
    届く人数が取れない日も送らない（数えられないものは送らない）。
  ・曲は #642 の選曲台帳（joy-relief-station ops/social/q4-2026-candidate-queue.jsonl）から選ぶ。
      条件：曲ページの点検（status/public/toukou_tenken.json＝SNSに出した曲の5点）が80点以上／
            曲ページの紹介文に出典（src）がある／季節に合う（台帳の「秋」「冬」等）／まだ「種」で出していない／
            直近4号と同じアーティストではない。発売月が配信月と同じ曲を先に。
  ・文は「手書き」（status/gokigen_tane/tegaki/<日付>.json）があればそれを使う。無ければ claude -p（工場の既存の口・
    gaibu_copy_naoshi）に書かせる。どちらも機械の検品（kenpin）を通らないと送らない。
  ・下書きはその金曜のためのもの。送れなかった号を次の週へずらさない（日付の入った一言があるため）。
  ・下書きができたら Googleドライブ「AI制作物/Claude/ごきげん一粒/」へ納品（tools/claude_nouhin.py put）。

■ 使い方
  python3 tools/gokigen_tane.py --tick        # 心臓から5分おき。1日1回の準備＋金曜20〜23時の送信
  python3 tools/gokigen_tane.py --junbi       # 次の2号の下書きを作る（あれば何もしない）
  python3 tools/gokigen_tane.py --okuru       # 今が送る時間なら送る（鍵が無ければ下書きのまま）
  python3 tools/gokigen_tane.py --kenpin DATE # その号を検品して結果を出す
  python3 tools/gokigen_tane.py --self-test
置き場：status/gokigen_tane/（号ごとの json・送った記録 sent.jsonl）・公開してよい要約 status/public/gokigen_tane.json（鍵・人数は書かない）。
"""
from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

JST = timezone(timedelta(hours=9))
D = os.path.join(REPO, "status", "gokigen_tane")
TEGAKI = os.path.join(D, "tegaki")
SENT = os.path.join(D, "sent.jsonl")
STATE = os.path.join(D, "state.json")
PUBLIC = os.path.join(REPO, "status", "public", "gokigen_tane.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
TENKEN = os.path.join(REPO, "status", "public", "toukou_tenken.json")
KEYS = os.path.expanduser("~/.tamago/keys/api_keys.env")
JRS = "/Users/mac/Desktop/joy-relief-station"
LEDGER = "ops/social/q4-2026-candidate-queue.jsonl"
COVER = "src/lib/coverGuide.ts"
SITE = "https://joy-relief-station.lovable.app"
API = "https://api.line.me"

NAME = "今週のごきげんの種"
FREE_LIMIT = 200          # LINE 公式アカウント コミュニケーションプランの無料メッセージ数（月）
SEND_HOUR = 20            # 金曜20時
SEND_UNTIL = 23           # 23時を過ぎたらその週は送らない（夜中に飴が届かないように）
MIN_SCORE = 80
FIRST_DATE = date(2026, 10, 30)  # 創刊号（たまごさん「第1号は来週金曜分」2026-10-21）
BODY_MAX = 160            # URLを除いた本文の文字数（3秒で読める長さ）
NG_WORDS = ["代表曲のひとつ", "名曲です", "話題", "反響", "絶賛", "続出", "バズ", "必聴", "ぜひ聴いて", "いかがでしょう",
            "出典", "Wikipedia"]

SEASON = {1: ["冬"], 2: ["冬"], 3: ["春"], 4: ["春"], 5: ["春", "初夏"], 6: ["初夏", "夏"], 7: ["夏"], 8: ["夏"],
          9: ["秋", "秋冬"], 10: ["秋", "秋冬"], 11: ["秋", "秋冬"], 12: ["冬", "秋冬"]}
XMAS = re.compile(r"(?i)christmas|クリスマス|xmas|聖夜")


# ---------------------------------------------------------------- 小道具
def now():
    return datetime.now(JST)


def log(msg):
    print("[%s] %s" % (now().strftime("%m-%d %H:%M:%S"), msg), flush=True)


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def read_jsonl(p):
    out = []
    try:
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return out


def append_jsonl(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def dispatch(kind, title, message):
    """Dispatch へ1行（同じ件名は1日1回まで）。"""
    st = load(STATE, {})
    key = "%s|%s" % (kind, title)
    today = now().strftime("%Y-%m-%d")
    if st.get("told", {}).get(key) == today:
        return
    append_jsonl(OUTBOX, {"ts": now().isoformat(timespec="seconds"), "n": "gokigen-tane-%s" % now().strftime("%Y%m%d%H%M"),
                          "type": kind, "title": title, "message": message})
    st.setdefault("told", {})[key] = today
    save(STATE, st)


def norm(s):
    return unicodedata.normalize("NFKC", s or "").lower().replace(" ", "")


def gou_path(d):
    return os.path.join(D, "gou", "%s.json" % d)


def fridays(n=2, base=None):
    """次の金曜から n 回分（今日が金曜で20時前なら今日を含む）。"""
    t = base or now()
    d = t.date()
    ahead = (4 - d.weekday()) % 7
    if ahead == 0 and t.hour >= SEND_UNTIL:
        ahead = 7
    first = max(d + timedelta(days=ahead), FIRST_DATE)
    return [first + timedelta(days=7 * i) for i in range(n)]


def issue_no(d):
    """第何号か（創刊号＝2026-10-30）。"""
    return (d - date(2026, 10, 30)).days // 7 + 1


# ---------------------------------------------------------------- 材料
def git_show(path):
    """joy-relief-station の origin/main の中身（手元の作業中の枝に左右されない）。"""
    subprocess.run(["git", "-C", JRS, "fetch", "-q", "origin", "main"], capture_output=True, timeout=120)
    r = subprocess.run(["git", "-C", JRS, "show", "origin/main:" + path], capture_output=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError("joy-relief-station から %s を読めない" % path)
    return r.stdout.decode("utf-8")


def song_entry(cover_src, key):
    """coverGuide.ts から1曲（note・year・src）。"""
    a, s = key.split("/", 1)
    ai = cover_src.find('{ id: "%s", name:' % a)
    if ai < 0:
        return None
    nxt = cover_src.find('\n  { id: "', ai + 10)
    block = cover_src[ai: nxt if nxt > 0 else len(cover_src)]
    m = re.search(r'\{ id: "%s", title: "((?:[^"\\]|\\.)*)"[^\n]*' % re.escape(s), block)
    if not m:
        return None
    line = m.group(0)
    note = re.search(r'note: "((?:[^"\\]|\\.)*)"', line)
    year = re.search(r"year: (\d{4})", line)
    srcs = re.search(r"src: \[([^\]]*)\]", line)
    artist = re.search(r'name: "((?:[^"\\]|\\.)*)"', block)
    return {"note": note.group(1) if note else "", "year": int(year.group(1)) if year else None,
            "src": re.findall(r'"([^"]+)"', srcs.group(1)) if srcs else [], "title": m.group(1),
            "artist": artist.group(1) if artist else ""}


def page_score(item):
    """SNSに出した曲の5点（toukou_tenken）を100点満点に。1つ落ちるごとに20点引く。"""
    return 100 - 20 * len(item.get("fails") or [])


def sent_keys():
    """送った曲＋下書きにした曲（同じ曲を2回選ばない）。"""
    return {r.get("key") for r in read_jsonl(SENT)} | {load(p, {}).get("key") for p in _gou_files()}


def _gou_files():
    g = os.path.join(D, "gou")
    return [os.path.join(g, f) for f in sorted(os.listdir(g))] if os.path.isdir(g) else []


def recent_artists(n=4):
    rows = [load(p, {}) for p in _gou_files()]
    return [norm(r.get("artist_key")) for r in rows[-n:]]


def candidates(send_day, ledger_text=None, cover_src=None, tenken=None, used=None, avoid=None):
    """選曲。点数の高い順の候補リスト。"""
    ledger_text = ledger_text if ledger_text is not None else git_show(LEDGER)
    cover_src = cover_src if cover_src is not None else git_show(COVER)
    tenken = tenken if tenken is not None else load(TENKEN, {}).get("items", [])
    used = used if used is not None else sent_keys()
    avoid = avoid if avoid is not None else recent_artists()
    rows = [json.loads(l) for l in ledger_text.splitlines() if l.strip()]
    rows = [r for r in rows if r.get("id")]
    by_title = {}
    for it in tenken:
        by_title.setdefault(norm(it.get("title")), []).append(it)
    want = SEASON[send_day.month]
    out = []
    for order, r in enumerate(rows):
        if r.get("status") not in ("CANDIDATE", "PRIORITY"):
            continue
        tags = set((r.get("shelves") or []) + (r.get("batch_tags") or []))
        if not tags & set(want):
            continue
        hint = r.get("schedule_hint") or ""
        if hint and ("%d月" % send_day.month) not in hint:
            continue
        if XMAS.search(r.get("song", "")) and send_day.month != 12:
            continue
        for it in by_title.get(norm(r.get("song")), []):
            if norm(it.get("artist")) != norm(r.get("artist")):
                continue
            key = it["key"]
            if key in used or page_score(it) < MIN_SCORE:
                continue
            if norm(key.split("/")[0]) in avoid:
                continue
            e = song_entry(cover_src, key)
            if not e or not e["src"] or not e["note"]:
                continue
            pts = page_score(it)
            months = re.findall(r"(\d{4})年(\d{1,2})月", e["note"])
            if any(int(m) == send_day.month for _, m in months):
                pts += 30
            if r.get("status") == "PRIORITY":
                pts += 10
            out.append({"key": key, "artist": r["artist"], "title": r["song"], "year": e["year"], "url": it["url"],
                        "note": e["note"], "src": e["src"], "ledger_id": r["id"], "points": pts, "score": page_score(it), "order": order,
                        "artist_key": key.split("/")[0]})
    out.sort(key=lambda c: (-c["points"], c["order"]))
    return out


# ---------------------------------------------------------------- 文
def compose(g):
    """案Aの型（一言だけ・3秒）。"""
    year = "（%s）" % g["year_label"] if g.get("year_label") else ("（%s）" % g["year"] if g.get("year") else "")
    return "\n".join([
        NAME,
        "%s「%s」%s" % (g["artist_ja"], g["title_ja"], year),
        "",
        "へぇ：" + g["fact"],
        "",
        "卵コンシェルジュ：" + g["hitokoto"],
        "",
        "▶ 聴く " + g["url"],
    ])


PROMPT = """あなたは「ごきげん補給所」の店主の分身として、週に1回LINEで届く「ごきげんの種」を書きます。
変な面白いおっちゃんから飴が1粒届く感じ。3秒で読めて、クスッとして、押したくなる。余計なことは書かない。

曲：%(title)s
材料（曲ページに載っている、出典つきの事実。ここに無い事実は書かない）：
%(copy)s
曲ページ：%(url)s

書くもの2つを「へぇ｜一言」の1行で返してください（全角の｜で区切る。前置き・説明・かぎかっこは不要）。
・へぇ＝材料から事実を1つだけ。40字以内。数字・年・人名は材料に書いてあるものだけ。歌詞は引用しない。
・一言＝卵コンシェルジュ（おっちゃん）のツッコミ。60字以内。先に笑わせてから刺す。人じゃなく仕様を殴る。自分にも返す。
  ボンジョビおじさん構文（ただの行為が小さな事件になる）が はまる時だけ使う。「代表曲」「名曲」「話題」「絶賛」「ぜひ」は禁止。
材料が足りず書けないときは NO_MATERIAL とだけ返す。"""


def write_by_ai(c):
    naoshi = importlib.import_module("gaibu_copy_naoshi")
    saved = naoshi.PROMPT
    diag = []
    try:
        naoshi.PROMPT = PROMPT
        text, why = naoshi.ask_claude("%s「%s」" % (c["artist"], c["title"]), c["note"], c["url"], diag)
    finally:
        naoshi.PROMPT = saved
    if not text:
        return None, None, why or "書き手が書けなかった"
    text = text.strip().strip("「」").replace("|", "｜")
    if "｜" not in text:
        return None, None, "「へぇ｜一言」の形で返ってこなかった：%s" % text[:60]
    f, h = [x.strip().strip("「」") for x in text.split("｜", 1)]
    return f, h, None


# ---------------------------------------------------------------- 検品
def kenpin(g, today=None, check_url=True):
    """機械の検品。落ちた理由のリスト（空＝合格）。"""
    bad = []
    text = g.get("text") or ""
    for need in (NAME, "へぇ：", "卵コンシェルジュ：", "▶ 聴く "):
        if need not in text:
            bad.append("型が崩れている（%s が無い）" % need.strip())
    url = g.get("url") or ""
    if not url.startswith(SITE + "/cover-guide?artist="):
        bad.append("曲ページのリンクがごきげん補給所の曲ページではない")
    body = text.replace(url, "")
    if len(body) > BODY_MAX:
        bad.append("長い（%d字・%d字まで）" % (len(body), BODY_MAX))
    for w in NG_WORDS:
        if w in (g.get("fact", "") + g.get("hitokoto", "")):
            bad.append("使わない言葉「%s」" % w)
    if len(g.get("fact", "")) > 45:
        bad.append("へぇが長い（%d字）" % len(g.get("fact", "")))
    if len(g.get("hitokoto", "")) > 70:
        bad.append("一言が長い（%d字）" % len(g.get("hitokoto", "")))
    # 事実の数字は材料（曲ページの紹介文＋確かめた出典のメモ）にあるものだけ
    material = (g.get("note") or "") + " " + " ".join(g.get("shutten_memo") or [])
    mat_nums = set(re.findall(r"\d+", unicodedata.normalize("NFKC", material)))
    for n in re.findall(r"\d+", unicodedata.normalize("NFKC", g.get("fact", ""))):
        if n not in mat_nums:
            bad.append("へぇの数字「%s」が材料に無い" % n)
    for n in re.findall(r"\d+", unicodedata.normalize("NFKC", g.get("hitokoto", ""))):
        if n not in mat_nums and n not in (g.get("hitokoto_nums_ok") or []):
            bad.append("一言の数字「%s」が材料に無い" % n)
    # 歌詞を引用しない：曲名以外の長いかぎかっこを止める
    for q in re.findall(r"「([^」]{12,})」", g.get("fact", "") + g.get("hitokoto", "")):
        if norm(q) != norm(g.get("title_ja")):
            bad.append("長いかぎかっこ（歌詞の引用に見える）：%s" % q[:20])
    if not g.get("src"):
        bad.append("曲ページに出典が無い")
    if (g.get("score") or 0) < MIN_SCORE:
        bad.append("曲ページの点検が%d点（%d点以上）" % (g.get("score") or 0, MIN_SCORE))
    if today and g.get("date") != today:
        bad.append("この号は %s のための下書き（今日は %s）" % (g.get("date"), today))
    if check_url and url:
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "gokigen-tane/1.0"}), timeout=25)
            if r.status != 200:
                bad.append("曲ページが %s" % r.status)
        except Exception as e:
            bad.append("曲ページが開けない（%s）" % type(e).__name__)
    return bad


# ---------------------------------------------------------------- 準備（下書き）
def junbi(n=2, cands_fn=candidates):
    made = []
    for d in fridays(n):
        p = gou_path(d.isoformat())
        if os.path.exists(p):
            continue
        tg = load(os.path.join(TEGAKI, d.isoformat() + ".json"), None)
        cs = cands_fn(d)
        c = None
        if tg:
            c = next((x for x in cs if x["key"] == tg["key"]), None)
            if not c:
                log("%s 手書きの曲 %s が選曲の条件から外れている。手書きは使わず選び直す" % (d, tg.get("key")))
                tg = None
        if not c:
            if not cs:
                dispatch("gokigen_tane", "ごきげんの種：%s の曲が選べない" % d, "選曲台帳(#642)に、条件（80点以上・出典あり・季節・未配信）に合う曲が無い。")
                continue
            c = cs[0]
        g = {"date": d.isoformat(), "no": issue_no(d), "key": c["key"], "artist_key": c["artist_key"], "ledger_id": c["ledger_id"],
             "url": c["url"], "note": c["note"], "src": c["src"], "year": c["year"], "score": c["score"],
             "artist_ja": c["artist"], "title_ja": c["title"], "status": "shitagaki", "made_at": now().isoformat(timespec="seconds")}
        if tg:
            g.update({k: tg[k] for k in ("artist_ja", "title_ja", "year_label", "fact", "hitokoto", "shutten_memo", "hitokoto_nums_ok") if k in tg})
            g["kakite"] = "手書き（店主の書き方）"
        else:
            f, h, why = write_by_ai(c)
            if not f:
                g.update({"status": "kakite_machi", "why": why})
                save(p, g)
                dispatch("gokigen_tane", "ごきげんの種：%s の文が書けない" % d, why)
                continue
            g.update({"fact": f, "hitokoto": h, "kakite": "claude -p"})
        g["text"] = compose(g)
        g["kenpin"] = kenpin(g)
        if g["kenpin"]:
            g["status"] = "kenpin_ochi"
            dispatch("gokigen_tane", "ごきげんの種：%s の下書きが検品で落ちた" % d, " / ".join(g["kenpin"]))
        save(p, g)
        made.append(g)
        nouhin(g)
    write_public()
    return made


def draft_md(g):
    return "\n".join([
        "# ごきげんの種　第%d号（%s 金曜20時）下書き" % (g["no"], g["date"]),
        "",
        "- 曲：%s「%s」 ／ 曲ページ：%s" % (g["artist_ja"], g["title_ja"], g["url"]),
        "- 選曲台帳 #642：%s ／ 曲ページの点検 %s点" % (g["ledger_id"], g["score"]),
        "- 出典（曲ページと同じ）：" + " ／ ".join(g["src"]),
        "- 書き手：%s ／ 機械の検品：%s" % (g.get("kakite", ""), "合格" if not g.get("kenpin") else "落ち（" + " / ".join(g["kenpin"]) + "）"),
        "",
        "## LINE（このまま届く）",
        "",
        "```",
        g["text"],
        "```",
        "",
    ])


def nouhin(g):
    """Googleドライブ「AI制作物/Claude/ごきげん一粒/」へ。"""
    tmp = os.path.join(D, "nouhin")
    os.makedirs(tmp, exist_ok=True)
    p = os.path.join(tmp, "ごきげんの種_第%d号_%s_下書き.md" % (g["no"], g["date"]))
    with open(p, "w", encoding="utf-8") as f:
        f.write(draft_md(g))
    r = subprocess.run([sys.executable, os.path.join(HERE, "claude_nouhin.py"), "put", p, "--anken", "ごきげん一粒", "--move"],
                       capture_output=True, text=True, timeout=300)
    log("納品 %s rc=%s %s" % (os.path.basename(p), r.returncode, (r.stdout or r.stderr).strip()[-200:]))


# ---------------------------------------------------------------- 送る
def token():
    t = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if t:
        return t.strip()
    try:
        for line in open(KEYS, encoding="utf-8"):
            m = re.match(r"\s*(?:export\s+)?LINE_CHANNEL_ACCESS_TOKEN\s*=\s*(.*)$", line)
            if m:
                return m.group(1).strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return ""


def line_api(tok, method, path, body=None, headers=None):
    h = {"Authorization": "Bearer " + tok}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    req = urllib.request.Request(API + path, data=data, headers=h, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=30)
        raw = r.read().decode("utf-8") or "{}"
        return r.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            return e.code, {}


def reach(tok, today):
    """今回届く人数（友だち−ブロック）。取れなければ None。"""
    for back in (1, 2, 3):
        d = (today - timedelta(days=back)).strftime("%Y%m%d")
        st, j = line_api(tok, "GET", "/v2/bot/insight/followers?date=" + d)
        if st == 200 and j.get("status") == "ready":
            if j.get("targetedReaches") is not None:
                return int(j["targetedReaches"])
            if j.get("followers") is not None:
                return int(j["followers"]) - int(j.get("blocks") or 0)
    return None


def okane_kanmon(tok, today):
    """お金の関所。(送ってよいか, 理由)。"""
    st, q = line_api(tok, "GET", "/v2/bot/message/quota")
    st2, c = line_api(tok, "GET", "/v2/bot/message/quota/consumption")
    if st != 200 or st2 != 200:
        return False, "LINEの残り通数が読めない（quota %s / consumption %s）" % (st, st2)
    limit = FREE_LIMIT
    if q.get("type") == "limited" and q.get("value") is not None:
        limit = min(int(q["value"]), FREE_LIMIT)
    used = int(c.get("totalUsage") or 0)
    need = reach(tok, today)
    if need is None:
        return False, "届く人数が取れない（数えられないまま送らない）"
    if used + need > limit:
        return False, "無料枠を超える（今月 %d通使用＋今回 %d人＞%d通）" % (used, need, limit)
    return True, "今月 %d通使用＋今回 %d人≦%d通" % (used, need, limit)


def okuru(force_time=None):
    t = force_time or now()
    today = t.date()
    if today.weekday() != 4 or not (SEND_HOUR <= t.hour < SEND_UNTIL):
        return "送る時間ではない"
    p = gou_path(today.isoformat())
    g = load(p, None)
    if not g:
        dispatch("gokigen_tane", "ごきげんの種：今日（%s）の下書きが無い" % today, "下書きが無いので送らない。")
        return "下書きが無い"
    if g.get("status") == "sent":
        return "もう送った"
    bad = kenpin(g, today=today.isoformat())
    if bad:
        g.update({"status": "kenpin_ochi", "kenpin": bad})
        save(p, g)
        dispatch("gokigen_tane", "ごきげんの種：%s は検品で止めた" % today, " / ".join(bad))
        return "検品で止めた"
    tok = token()
    if not tok:
        if g.get("status") != "kagi_nashi":
            g["status"] = "kagi_nashi"
            save(p, g)
            log("鍵（LINE_CHANNEL_ACCESS_TOKEN）が無いので送らない。下書きのまま：%s" % p)
        write_public()
        return "鍵が無い（下書きのまま）"
    ok, why = okane_kanmon(tok, today)
    if not ok:
        g.update({"status": "okane_kanmon", "why": why})
        save(p, g)
        dispatch("gokigen_tane", "ごきげんの種：お金の関所で止めた（%s）" % today, why)
        return "お金の関所：" + why
    g.setdefault("retry_key", str(uuid.uuid4()))
    save(p, g)
    st, j = line_api(tok, "POST", "/v2/bot/message/broadcast", {"messages": [{"type": "text", "text": g["text"]}]},
                     {"X-Line-Retry-Key": g["retry_key"]})
    if st in (200, 409):   # 409＝同じ Retry-Key で既に受け付け済み（二重送信にはならない）
        g.update({"status": "sent", "sent_at": now().isoformat(timespec="seconds"), "kanmon": why})
        save(p, g)
        append_jsonl(SENT, {"date": g["date"], "no": g["no"], "key": g["key"], "sent_at": g["sent_at"]})
        log("送った：第%d号 %s「%s」" % (g["no"], g["artist_ja"], g["title_ja"]))
        write_public()
        return "送った"
    g.update({"status": "okuri_shippai", "why": "broadcast %s %s" % (st, json.dumps(j, ensure_ascii=False)[:200])})
    save(p, g)
    dispatch("gokigen_tane", "ごきげんの種：送れなかった（%s）" % today, g["why"])
    return "送れなかった"


def write_public():
    rows = [load(p, {}) for p in _gou_files()]
    save(PUBLIC, {"at": now().isoformat(timespec="seconds"), "name": NAME, "kagi": bool(token()),
                  "gou": [{k: r.get(k) for k in ("no", "date", "status", "artist_ja", "title_ja", "url")} for r in rows]})


def tick():
    st = load(STATE, {})
    today = now().strftime("%Y-%m-%d")
    if st.get("junbi_at") != today:
        try:
            junbi()
        except Exception as e:
            log("準備でつまずいた：%s" % e)
        st = load(STATE, {})
        st["junbi_at"] = today
        save(STATE, st)
    log(okuru())


# ---------------------------------------------------------------- 逆テスト
def self_test():
    ok = True

    def eq(a, b, what):
        nonlocal ok
        if a != b:
            ok = False
            print("NG", what, a, "!=", b)

    eq(fridays(2, datetime(2026, 10, 21, 16, 0, tzinfo=JST)), [date(2026, 10, 30), date(2026, 11, 6)], "創刊号から数える")
    eq(fridays(1, datetime(2026, 11, 6, 19, 0, tzinfo=JST)), [date(2026, 11, 6)], "金曜20時前は今日を含む")
    eq(fridays(1, datetime(2026, 11, 6, 23, 30, tzinfo=JST)), [date(2026, 11, 13)], "金曜23時過ぎは次の週")
    eq(issue_no(date(2026, 11, 6)), 2, "号数")
    ledger = "\n".join([json.dumps({"schema": 1}),
                        json.dumps({"id": "q4-a", "artist": "A", "song": "Aki", "status": "CANDIDATE", "shelves": ["秋"]}),
                        json.dumps({"id": "q4-b", "artist": "B", "song": "Fuyu", "status": "CANDIDATE", "shelves": ["冬"]}),
                        json.dumps({"id": "q4-c", "artist": "C", "song": "Low", "status": "CANDIDATE", "shelves": ["秋"]}),
                        json.dumps({"id": "q4-d", "artist": "D", "song": "Nov", "status": "CANDIDATE", "shelves": ["秋"]})])
    cover = "\n".join(['  { id: "a", name: "A", songs: [', '    { id: "aki", title: "Aki", note: "1971年4月に出た。", year: 1971, src: ["https://x"] },',
                       '  ]},', '  { id: "c", name: "C", songs: [', '    { id: "low", title: "Low", note: "x", year: 1980, src: ["https://x"] },', '  ]},',
                       '  { id: "d", name: "D", songs: [', '    { id: "nov", title: "Nov", note: "1978年11月5日に出た。", year: 1978, src: ["https://x"] },', '  ]},'])
    tk = [{"key": "a/aki", "artist": "A", "title": "Aki", "url": SITE + "/cover-guide?artist=a&song=aki", "fails": []},
          {"key": "b/fuyu", "artist": "B", "title": "Fuyu", "url": "u", "fails": []},
          {"key": "c/low", "artist": "C", "title": "Low", "url": "u", "fails": ["x", "y"]},
          {"key": "d/nov", "artist": "D", "title": "Nov", "url": "u", "fails": []}]
    cs = candidates(date(2026, 11, 6), ledger, cover, tk, used=set(), avoid=[])
    eq([c["key"] for c in cs], ["d/nov", "a/aki"], "選曲（冬・60点を外し、発売月が同じ曲を先に）")
    eq([c["key"] for c in candidates(date(2026, 11, 6), ledger, cover, tk, used={"d/nov"}, avoid=[])], ["a/aki"], "出した曲は選ばない")
    eq([c["key"] for c in candidates(date(2026, 11, 6), ledger, cover, tk, used=set(), avoid=["d"])], ["a/aki"], "直近と同じアーティストは避ける")
    g = {"date": "2026-10-30", "url": tk[0]["url"], "note": "1971年4月に出た。", "src": ["https://x"], "score": 100,
         "artist_ja": "A", "title_ja": "Aki", "year": 1971, "fact": "1971年4月に出た歌。", "hitokoto": "おっちゃんは笑う。"}
    g["text"] = compose(g)
    eq(kenpin(g, check_url=False), [], "合格する下書き")
    g2 = dict(g, fact="1972年に全米1位。")
    g2["text"] = compose(g2)
    eq(any("1972" in b for b in kenpin(g2, check_url=False)), True, "材料に無い数字は落とす")
    g3 = dict(g, hitokoto="ぜひ聴いてほしい名曲です。")
    g3["text"] = compose(g3)
    eq(len([b for b in kenpin(g3, check_url=False) if "使わない言葉" in b]) >= 2, True, "水道水コピーは落とす")
    eq(any("ための下書き" in b for b in kenpin(g, today="2026-11-06", check_url=False)), True, "別の週の下書きは送らない")
    eq(okuru(datetime(2026, 10, 29, 20, 0, tzinfo=JST)), "送る時間ではない", "金曜以外は送らない")
    eq(okuru(datetime(2026, 10, 30, 23, 10, tzinfo=JST)), "送る時間ではない", "23時を過ぎたら送らない")
    print("SELF-TEST", "OK" if ok else "NG")
    return 0 if ok else 1


def main():
    a = sys.argv[1:]
    if not a or a[0] == "--tick":
        tick()
    elif a[0] == "--junbi":
        for g in junbi():
            print(g["date"], g["status"], g.get("kenpin"))
    elif a[0] == "--okuru":
        print(okuru())
    elif a[0] == "--kenpin":
        g = load(gou_path(a[1]), None)
        print(json.dumps(kenpin(g) if g else ["号が無い"], ensure_ascii=False))
    elif a[0] == "--self-test":
        sys.exit(self_test())
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
