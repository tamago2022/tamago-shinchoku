#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1080番【50人の客】誰が入ってきても答えられるか。年内に85〜90点にするための物差し。

━━ なぜ作ったか（2026-09-24・たまごさん原文）━━

  「おばちゃんが入ってきました。ギャルが入ってきました。当然好きなもの違うよね。
    ミャンマー人の45歳のおばちゃんが入ってきました。アメリカ人の12歳のキッズが入ってきました。
    ラップ好きのヒップホップの兄ちゃんが入ってきました。それに答えられるかってことだよ。
    バリエーションはいくらでもAIできるでしょう。誰が入ってきても答えられるか。」
  「それで在庫がないんだったら、とっとと仕入れる。その周辺も仕入れる。
    『これないんですか』って言われたら仕入れる。」
  「それぞれ85点、90点出せるように頑張ろう。すぐにとは言わない。年内にはそれ出せるようにしよう。」

■ ★この道具の一番大事な考え方：**「答えが返った」を合格にしない**

  既にある tools/annai_mawasu.py は「案内人が黙らなかったか」を300問で数える（0円・機械の目）。
  この道具が数えるのはその先＝**「その人が好きそうなものを出せたか」「そもそも在庫があったか」。**
  同じことを2回測らない。**annai_mawasu は黙ったかどうか、こちらは中身。混ぜない。**

■ ★在庫の切り分け（ここが一番大事。たまごさん指定）

  客が「これが欲しかった」と言った名前を、**手元の索引（953番の head.json / t/NN.json）に照合する。**
    棚に無い          → **買い物リスト。**仕入れとしてキューに積む（周辺も一緒に）
    棚にあるのに出ない → **案内人の問題。**別リストに分ける。仕入れではない
  この2つを混ぜると、「足りないのか下手なのか」が永久に分からない。

■ ★3つの口を分ける（1つの口に2つ喋らせない）
  ① 役を作る       … Genspark（外に聞く方が偏らない＝たまごさん指定）。1周で1回だけ
  ② 案内人に話す   … Playwrightで本番を触る。**0クレジット**
  ③ 点を付ける     … Genspark が客の役のまま採点。1人1回（実測 約2〜3クレジット）

■ ★Gensparkを通っていない結果は機械が自動で弾く（1076番と同じ栓）
  たまごさん「自分で書いた感想をGensparkの名前で出したら失点」。
  **残クレジットが1つも減っていない答えは不合格。**感想ではなく残高の差という数字で弾く。

■ 走らせ方（★Macの上でしか動かない。サンドボックスからは gsk にも本番にも届かない）

    python3 tools/kyaku50.py --yaku 44          # 役を作る（Gensparkに1回・50人ぶんに満たす）
    python3 tools/kyaku50.py --mawasu --limit 10   # 10人ぶん回す（★今日はここまで）
    python3 tools/kyaku50.py --page             # 1枚のページにして公開
    python3 tools/kyaku50.py --shukan           # 毎週1回のゲート（既存の定期便から呼ぶ）
    python3 tools/kyaku50.py --ichiran          # 今までの点数の推移（0円）

■ 置き場所
  status/kyaku50/yaku.json          … 役の名簿（50人ぶんの正本）
  status/kyaku50/<日付>/r<周>.json  … 1人ずつの生データ（答えを要約せずそのまま）
  status/kyaku50/score.jsonl        … 1周＝1行。平均点・最低の役・仕入れ件数
  status/gsk_daicho.jsonl           … 使ったクレジット（1回ごと）
"""
from __future__ import annotations

import argparse
import glob
import html
import io
import json
import os
import re
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

BASE = "https://joy-relief-station.lovable.app"
CONCIERGE_URL = BASE + "/cover-guide"
CONCIERGE_SEL = 'input[placeholder*="気分でも"]'   # ★1039番で確かめた本番の入力欄

OUT = os.path.join(REPO, "status", "kyaku50")
YAKU = os.path.join(OUT, "yaku.json")
SCORE = os.path.join(OUT, "score.jsonl")
SHIIRE = os.path.join(OUT, "shiire.jsonl")        # 仕入れに積んだものの台帳（二度積み防止）
DAICHO = os.path.join(REPO, "status", "gsk_daicho.jsonl")
STAMP = os.path.join(REPO, "status", ".kyaku50_last")
SONGS = os.path.join(REPO, "share", "check", "assets", "953-songs")
DAIHON_YAKU = os.path.join(HERE, "prompts", "kyaku50_yaku.md")
DAIHON_SAITEN = os.path.join(HERE, "prompts", "kyaku50_saiten.md")

KOUKAI_REPO = "tamago2022/ai-kaigi"
KOUKAI_PATH = "kyaku50/index.html"
KOUKAI_URL = "https://tamago2022.github.io/ai-kaigi/kyaku50/"

DANMARI = ("★これはお客さんの<b>感想</b>です。事実の主張（枚数・年号・有無）は裏を取っていません。"
           "在庫の有無だけは、手元の索引に機械で照合しています。")

# ── たまごさんが名指しした6人。★この6人は必ず入る（Gensparkには作らせない）──────
KOTEI = [
    {"id": "myanmar-45-oba", "kuni": "ミャンマー・ヤンゴン", "toshi": 45, "sei": "女",
     "suki": "ミャンマーの歌謡曲、Sai Sai Kham Leng、インドの映画音楽",
     "riyuu": "日本で働いていて、家のことを思い出して少し寂しい",
     "hitokoto": "ငါ့နိုင်ငံရဲ့ သီချင်းလိုမျိုး ရှိလား？", "go": "my"},
    {"id": "usa-12-kid", "kuni": "アメリカ・オハイオ", "toshi": 12, "sei": "男",
     "suki": "Olivia Rodrigo、Imagine Dragons、ゲームのサントラ",
     "riyuu": "学校から帰ってYouTubeを見ていたら流れてきて、なんとなく入ってきた",
     "hitokoto": "got anything cool? i'm bored", "go": "en"},
    {"id": "hiphop-nii", "kuni": "日本・川崎", "toshi": 24, "sei": "男",
     "suki": "Kendrick Lamar、BAD HOP、舐達麻、90sのブーンバップ",
     "riyuu": "作業中に流すやつを探している。ダサいのが出てきたら即帰る",
     "hitokoto": "ヒップホップある？日本語ラップでもいい", "go": "ja"},
    {"id": "akiba-idol", "kuni": "日本・秋葉原", "toshi": 33, "sei": "男",
     "suki": "モーニング娘。、BiSH、乃木坂46、地下アイドル",
     "riyuu": "現場帰り。誰かとアイドルの話がしたい",
     "hitokoto": "アイドルの曲ってあります？", "go": "ja"},
    {"id": "belafonte-75", "kuni": "日本・世田谷", "toshi": 75, "sei": "男",
     "suki": "ハリー・ベラフォンテ、ナット・キング・コール、カリプソ",
     "riyuu": "昔ラジオで聴いた曲をもう一度聴きたい。機械は苦手",
     "hitokoto": "ハリー・ベラフォンテはありますか", "go": "ja"},
    {"id": "gal-19", "kuni": "日本・渋谷", "toshi": 19, "sei": "女",
     "suki": "ちゃんみな、NewJeans、Ado、TikTokで流れてくる曲",
     "riyuu": "友達を待ってる間の暇つぶし。長い文は読まない",
     "hitokoto": "なんか映える曲ある？", "go": "ja"},
]


# ═════════════════════════ 小道具 ═════════════════════════

def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _append(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _rows(path):
    out = []
    try:
        for ln in io.open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
    except Exception:
        pass
    return out


def _daihon(path, repl):
    t = io.open(path, encoding="utf-8").read()
    for k, v in repl.items():
        t = t.replace("{{%s}}" % k, str(v))
    m = re.search(r"\n##\s*役\s*\n(.*?)\n##\s*問い\s*\n(.*)$", t, re.S)
    if not m:
        raise RuntimeError("台本に `## 役` と `## 問い` が見つかりません: %s" % path)
    toi = [re.sub(r"^-\s*", "", ln).strip()
           for ln in m.group(2).splitlines() if ln.strip().startswith("- ")]
    if not toi:
        raise RuntimeError("台本の `## 問い` に1問もありません: %s" % path)
    return m.group(1).strip(), toi


def _gsk_toosu(url, toi_all, nani, timeout=420):
    """gsk を1回だけ通し、**残クレジットの差**を必ず記録する。
    ★減っていない＝Gensparkを通っていない。呼び出し側はこれで弾く。"""
    import genspark_nagashi as gn
    os.makedirs(OUT, exist_ok=True)
    af = os.path.join(OUT, "_toi.json")
    json.dump({"url": url, "question": toi_all},
              io.open(af, "w", encoding="utf-8"), ensure_ascii=False)
    zen = gn.zandaka(record=False).get("zan")
    t0 = time.time()
    r = gn.gsk_run(["summarize", url, "--args-file", af], timeout=timeout)
    byou = round(time.time() - t0, 1)
    ato = gn.zandaka(record=True).get("zan")
    tsukatta = (round(zen - ato, 3) if (zen is not None and ato is not None) else None)
    _append(DAICHO, {"at": _now(), "nani": nani, "url": url, "ok": bool(r.get("ok")),
                     "残クレジット前": zen, "残クレジット": ato,
                     "使ったクレジット": tsukatta, "秒": byou})
    return {"r": r, "zen": zen, "ato": ato, "tsukatta": tsukatta, "byou": byou}


def _codex_toosu(toi_all, nani):
    """★もう1つの口＝codex（ChatGPTのログイン・1回ごとの課金なし＝0円）。

    たまごさん（2026-09-24・原文）
      「Gensparkだけにしない。★どんどん色んなのにテストさせようよ。
        1周したらペルソナチェンジして、他のAIに『じゃあ次あなた、ミャンマー45歳ね』ってやらせる。」
      「同じ役を違うAIにやらせて、答えが割れたらそれも記録。どれが正解かをこちらが決めない。」

    ★Gensparkは「残クレジットが減ったか」で通ったことを確かめられるが、codexは0円なので
      減る残高が無い。代わりに **秒数と返ってきた本文の長さ** を台帳に残す。
      ★『通ったふり』をしないために、返事が空なら不合格にする（下の gouhi が見る）。
    """
    import gaibu_kuchi as g
    t0 = time.time()
    d, who, err = g.kiku_codex(
        "あなたはこれからお客さんの役を演じて、店の案内人に点を付けます。",
        toi_all + '\n\n★返すのは {"kotae": "上の問いに全部答えた文章そのまま"} '
                  "の形のJSONひとつだけ。文章の中の改行はそのまま入れてよい。",
        timeout=600)
    byou = round(time.time() - t0, 1)
    kotae = ""
    if isinstance(d, dict):
        kotae = str(d.get("kotae") or d.get("answer") or "")
    _append(DAICHO, {"at": _now(), "nani": nani, "口": who or "codex", "ok": bool(kotae),
                     "使ったクレジット": 0, "円": 0, "秒": byou, "字数": len(kotae),
                     "error": err or ""})
    return {"kotae": kotae, "who": who or "codex", "err": err, "byou": byou}


def _kotae_toridasu(stdout):
    """gsk の返事から読める答えを作る。★形が想像と違っても生のまま残す（切り捨てない）。"""
    if not stdout:
        return ""
    if not stdout.lstrip().startswith("{"):
        return stdout
    try:
        d = json.loads(stdout)
    except Exception:
        return stdout
    if isinstance(d, dict) and d.get("status") == "error":
        return stdout
    hiroi = []

    def walk(o):
        if isinstance(o, dict):
            a = o.get("answer") or o.get("result") or o.get("a")
            if isinstance(a, str) and a.strip():
                hiroi.append(a.strip())
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    if not hiroi:
        return stdout
    out, mita = [], set()
    for a in hiroi:
        if a not in mita:
            mita.add(a)
            out.append(a)
    return "\n\n".join(out).strip()


# ═════════════════════════ ① 役を作る ═════════════════════════

def yaku_tsukuru_codex(n=44):
    """★2026-09-24 実測：Gensparkの `summarize` は**新しいものを作れない。**
      「この紙を読んで44人作って」と頼むと、44人を作らずに**紙の要約**を返す
      （27.5クレジットを捨てた。答えの中に『実際の44件のデータは含まれておらず、設計指示のみ』
        とはっきり書いてある＝要約の口であって、生成の口ではない）。
      ★役づくりは別の口＝codex（ChatGPTのログイン・1回ごとの課金なし＝0円）に頼む。
      たまごさん「覆面テストはGensparkじゃなくて各AIにやってもらっていい。仲間だから、
      いろんな意見があっていい」。**こちらが50人考えない**という肝は守れている。"""
    import gaibu_kuchi as g
    yaku, toi = _daihon(DAIHON_YAKU, {"URL": CONCIERGE_URL, "N": n})
    d, who, err = g.kiku_codex(
        yaku, "\n".join(toi) + '\n\n★返すのは {"yaku":[ … ]} の形のJSONひとつだけ。',
        timeout=420)
    if d is None:
        return {"ok": False, "error": err or "codexが答えませんでした"}
    lst = d.get("yaku") or d.get("list") or (d if isinstance(d, list) else [])
    return {"ok": bool(lst), "ai": who, "kane": "0円", "list": lst,
            "error": "" if lst else "codexは答えたが役が0人"}


def yaku_tsukuru(n=44, dry=False):
    """Gensparkに役を作らせ、固定の6人と合わせて名簿にする。
    ★たまごさん「こちらが50人考えるより、外に聞く方が偏らない」。"""
    yaku, toi = _daihon(DAIHON_YAKU, {"URL": CONCIERGE_URL, "N": n})
    toi_all = "%s\n\n----\n%s" % (yaku, "\n".join(toi))
    if dry:
        return {"ok": True, "dry": True, "toi": toi_all}

    # ★役づくりは codex に頼む（Gensparkの summarize は生成できない。上の関数の注を読むこと）。
    c = yaku_tsukuru_codex(n)
    if not c.get("ok"):
        return {"ok": False, "error": c.get("error")}
    atarashii = c["list"]
    tsukatta = 0.0

    hitsuyou = ("id", "kuni", "toshi", "sei", "suki", "riyuu", "hitokoto", "go")
    kirei, mita = [], set(x["id"] for x in KOTEI)
    for y in atarashii:
        if not isinstance(y, dict) or any(k not in y for k in hitsuyou):
            continue
        i = re.sub(r"[^a-z0-9-]", "", str(y["id"]).lower())[:40]
        if not i or i in mita:
            continue
        mita.add(i)
        kirei.append({k: (i if k == "id" else y[k]) for k in hitsuyou})

    meibo = KOTEI + kirei                     # ★固定6人が必ず先頭
    os.makedirs(OUT, exist_ok=True)
    json.dump({"at": _now(), "n": len(meibo), "kotei": len(KOTEI),
               "外のAIが作った": len(kirei), "dare": c.get("ai"),
               "使ったクレジット": tsukatta, "yaku": meibo},
              io.open(YAKU, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"ok": True, "n": len(meibo), "外のAIが作った": len(kirei), "dare": c.get("ai"),
            "使ったクレジット": tsukatta, "path": YAKU}


def yaku_tasu(n=50, chunk=25):
    """★名簿を後ろに足す。**すでに居る人は1人も動かさない。**

    たまごさん（2026-09-24・原文）
      「1周したらペルソナチェンジして、他のAIに『じゃあ次あなた、ミャンマー45歳ね』ってやらせる。
        1ヶ月後に来たミャンマー45歳でどう変わったか検証してもいい。
        ★とりあえず100人くらいペルソナを作って、ガンガンやってガンガン直そう。」
      「1回目の10人はそのまま残して、★同じ役で点数の推移を追えるようにする。」

    ★だから並び順を絶対に変えない（--limit 10 が毎回同じ10人を指すため）。
    ★役を作るのは codex（0円）。こちらが考えない＝偏らない。
    """
    import gaibu_kuchi as g
    cur = yaku_yomu()
    mita = set(x["id"] for x in cur)
    kuni_mochi = {}
    for x in cur:
        kuni_mochi[x["kuni"]] = kuni_mochi.get(x["kuni"], 0) + 1
    hitsuyou = ("id", "kuni", "toshi", "sei", "suki", "riyuu", "hitokoto", "go")
    yaku, toi = _daihon(DAIHON_YAKU, {"URL": CONCIERGE_URL, "N": chunk})
    log = []
    nokori = n
    while nokori > 0:
        ima = min(chunk, nokori)
        sude = "、".join(sorted(kuni_mochi.keys()))
        user = ("\n".join(toi).replace("ちょうど %d" % chunk, "ちょうど %d" % ima)
                + "\n\n★配列の長さはちょうど %d です。" % ima
                + "\n★すでにこの国・地域の人は名簿に居ます（同じ国を増やしすぎないでください）：\n%s" % sude
                + "\n★すでに使った id（同じ id を返さないでください）：\n%s" % "、".join(sorted(mita))
                + '\n\n★返すのは {"yaku":[ … ]} の形のJSONひとつだけ。')
        d, who, err = g.kiku_codex(yaku, user, timeout=600)
        if d is None:
            log.append("codexが答えませんでした: %s" % err)
            break
        lst = d.get("yaku") or d.get("list") or (d if isinstance(d, list) else [])
        fueta = 0
        for y in lst:
            if not isinstance(y, dict) or any(k not in y for k in hitsuyou):
                continue
            i = re.sub(r"[^a-z0-9-]", "", str(y["id"]).lower())[:40]
            if not i or i in mita:
                continue
            mita.add(i)
            cur.append({k: (i if k == "id" else y[k]) for k in hitsuyou})
            kuni_mochi[y["kuni"]] = kuni_mochi.get(y["kuni"], 0) + 1
            fueta += 1
        log.append("%s が %d人 足しました（いま%d人）" % (who, fueta, len(cur)))
        nokori -= fueta
        if fueta == 0:
            break

    os.makedirs(OUT, exist_ok=True)
    nihon = sum(1 for x in cur if str(x["kuni"]).startswith("日本"))
    json.dump({"at": _now(), "n": len(cur), "kotei": len(KOTEI),
               "日本の人": nihon, "日本の割合": round(100.0 * nihon / len(cur), 1),
               "log": log, "yaku": cur},
              io.open(YAKU, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"ok": len(cur) > 0, "n": len(cur), "日本の割合": round(100.0 * nihon / len(cur), 1),
            "log": log, "path": YAKU}


def yaku_yomu():
    if not os.path.exists(YAKU):
        return KOTEI[:]                        # ★まだ作っていなければ固定6人だけで回す
    try:
        return json.load(io.open(YAKU, encoding="utf-8"))["yaku"]
    except Exception:
        return KOTEI[:]


# ═════════════════════════ 棚の照合（0円） ═════════════════════════

_TANA = {"a": None, "s": None}


def _norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return re.sub(r"[\s　'’\"“”・･,\.\-_!?()\[\]:;/&+]", "", s)


def _tana_yomu():
    """953番の索引を読む。★案内人が引くのと同じ索引を見る（別の紙を見ない）。"""
    if _TANA["a"] is not None:
        return _TANA
    arts, songs = set(), set()
    try:
        d = json.load(io.open(os.path.join(SONGS, "head.json"), encoding="utf-8"))
        for a in d.get("A", []):
            arts.add(_norm(a.get("n")))
            for al in (a.get("al") or []):
                arts.add(_norm(al))
    except Exception:
        pass
    for p in glob.glob(os.path.join(SONGS, "t", "*.json")):
        try:
            for row in json.load(io.open(p, encoding="utf-8")):
                if isinstance(row, list) and len(row) > 2:
                    songs.add(_norm(row[2]))
        except Exception:
            pass
    _TANA["a"], _TANA["s"] = arts, songs
    return _TANA


FUMEI = "★判定できない（名前が短すぎて索引と照合できない）"


def tana_ni_aruka(name):
    """この名前は棚にあるか。★推測しない。索引に無ければ「無い」（None）。

    ★2026-09-24：1文字の題名（「楓」「糸」「柔」「M」「X」）を「無い」に数えていた。
      これは**分かっていないものを分かった顔で数えていた**＝たまごさんが一番嫌う形。
      短すぎて照合できないものは「無い」ではなく **FUMEI**（判定できない）として別に出す。
      買い物リストには入れない。人が見て決める。"""
    t = _tana_yomu()
    k = _norm(name)
    if len(k) < 2:
        return FUMEI
    if k in t["a"]:
        return "アーティストの棚にある"
    if k in t["s"]:
        return "曲の棚にある"
    for s in t["s"]:
        if k and k in s:
            return "曲の棚にある（題名の一部一致）"
    for a in t["a"]:
        if k and (k in a or a in k) and len(a) >= 3:
            return "アーティストの棚にある（表記ゆれ一致）"
    return None


# ═════════════════════════ ② 案内人に話しかける（0円） ═════════════════════════

def annai_ni_kiku(hitokoto, page=None, ctx=None):
    """本番の案内人に1言だけ投げて、**返ってきたものをそのまま**持って帰る。
    ★Macの上でしか動かない。★AIを1回も呼ばない＝0円。"""
    before = set(x.strip() for x in page.inner_text("body", timeout=20000).split("\n") if x.strip())
    page.fill(CONCIERGE_SEL, hitokoto, timeout=15000)
    page.keyboard.press("Enter")
    page.wait_for_timeout(4000)
    after = [x.strip() for x in page.inner_text("body", timeout=20000).split("\n") if x.strip()]
    new = [l for l in after if l not in before]
    return "\n".join(new)


# ═════════════════════════ ③ 採点（Genspark） ═════════════════════════

TEN_NAMES = (("techuu", "的中"), ("zaiko", "在庫"), ("kotoba", "言葉"),
             ("mouikkyoku", "もう一曲"), ("sougou", "総合"))


def _setsu(kotae, maru):
    """【⑦…】のような節の中身だけを取り出す。

    ★2026-09-24（たまごさん「答えまで聞く」）で足した。
      Gensparkは問いの文をそのまま echo し、そのあと `verbatim:`（ページからの引用）、
      そのあと `answer:` を出す。**answer: の後ろだけが客の言葉。**
      前を読むと、問いの文そのものを「客が言ったこと」として拾ってしまう
      （r03で実際に『私が本当に聴きたかったのは以下のものです』を仕入れに積んだ）。
    """
    # ★⓪(U+24EA)は①〜⑩(U+2460〜)より後ろの番号なので [⓪-⑩] と書くと範囲エラーになる。並べて書く。
    m = re.search(r"【%s[^】]*】(.*?)(?=###\s*Question|【[⓪①②③④⑤⑥⑦⑧⑨⑩]|$)" % maru,
                  kotae or "", re.S)
    if not m:
        return ""
    body = m.group(1)
    am = re.search(r"^\s*answer\s*[:：]\s*(.*)$", body, re.S | re.M)
    if am:
        body = am.group(1)
    body = re.split(r"^\s*verbatim\s*[:：]", body, maxsplit=1, flags=re.M)[0]
    return body.strip()


def _namae_gyou(body, kazu=5, nagasa=60):
    """節の中身から「名前だけの行」を拾う。★文（です・ます・、。）は名前ではないので落とす。"""
    out = []
    for ln in (body or "").splitlines():
        ln = re.sub(r"^[\-\*・>]\s*|^\d+[\.\)、]\s*", "", ln.strip()).strip()
        if not ln or len(ln) > 80:
            continue
        if re.match(r"^(なし|特になし|ありません|該当なし|無い|ない|answer|verbatim)$", ln, re.I):
            continue
        if re.search(r"(です|ます|ください|でした|ません|。|以下のもの|以下の通り)", ln):
            continue
        ln = re.sub(r"[「」『』\"]", " ", ln).split("（")[0].split("(")[0]
        ln = re.sub(r"\s+", " ", ln).strip(" 　-–—:：")
        if 2 <= len(ln) <= nagasa:
            out.append(ln)
    return out[:kazu]


def shiire_teian(kotae):
    """【⑦仕入れ】★「では誰を仕入れておけばよかったですか」の答え（名前だけ・最大5）。
    たまごさん「文句を言うんだったら、じゃあ誰を入れたらいいんだい？」"""
    return _namae_gyou(_setsu(kotae, "⑦"), kazu=5)


def narabi(kotae):
    """【⑧並び】★「誰と誰が隣にあったら嬉しいか」（最大3）。
    ★『A と B』の形だけを採る。1つしか名前が無い行は並びではないので落とす。"""
    out = []
    for ln in (_setsu(kotae, "⑧") or "").splitlines():
        ln = re.sub(r"^[\-\*・>]\s*|^\d+[\.\)、]\s*", "", ln.strip()).strip()
        ln = re.sub(r"[「」『』\"]", "", ln).strip(" 　-–—:：")
        if not ln or len(ln) > 90:
            continue
        if re.match(r"^(なし|特になし|ありません|該当なし|無い|ない|answer|verbatim)$", ln, re.I):
            continue
        if not re.search(r"(\s+と\s+|\sと|と\s|×|✕|&|＆|・と・| and | AND )", ln):
            continue
        out.append(ln)
    return out[:3]


def daiichisei(kotae):
    """【⑨第一声】★「案内人は最初の一言で何と言えばよかったですか」。★セリフを1行そのまま。"""
    for ln in (_setsu(kotae, "⑨") or "").splitlines():
        ln = re.sub(r"^[\-\*・>]\s*|^\d+[\.\)、]\s*", "", ln.strip()).strip()
        ln = ln.strip("「」『』\"“” 　")
        if len(ln) >= 3 and not re.match(r"^(answer|verbatim)", ln, re.I):
            return ln[:200]
    return ""


def yokatta(kotae):
    """【⑩良かった点】★たまごさん「いいコメントもあるんだったらそれも欲しいよね」。
    ★無ければ空（無いものを有ることにしない）。"""
    body = _setsu(kotae, "⑩")
    for ln in (body or "").splitlines():
        ln = re.sub(r"^[\-\*・>]\s*|^\d+[\.\)、]\s*", "", ln.strip()).strip()
        if not ln or re.match(r"^(answer|verbatim)", ln, re.I):
            continue
        if re.match(r"^(無い|ない|なし|特になし|ありません|該当なし)[。\.]?$", ln):
            return ""
        return ln[:200]
    return ""


def tensuu(kotae):
    """答えから5つの点を拾う。★拾えなければ None（勝手に埋めない）。"""
    out = {}
    for key, name in TEN_NAMES:
        m = re.search(name + r"\s*[:：]?\s*\**\s*(\d{1,2})\s*(?:/|／|点)\s*(?:10)?", kotae)
        out[key] = int(m.group(1)) if m and 0 <= int(m.group(1)) <= 10 else None
    return out


def amedama(kotae):
    """★一番上の判定。0〜10点より先にこれを見る。

    たまごさん（2026-09-24・原文）
      「誰が来ても飴玉1個ぐらいはあげたいね。ごきげん補給所なわけだから。
        何か1つでも持って帰ってもらって。★これが最低ライン。
        笑いでもいいし、癒しでもいいし、テンション上がるでもいいし、何か1つだけでも。」
      「『ここつまんねぇな』って言われたら、もう負けですよ。誰に対してもだよ。」
      「『俺の好きなの何にもねぇ、つまんねぇ』って言われたら、もう我々のサイトの負けです。」

    戻り値 True＝何か1つ持って帰れた／False＝1つも無かった／None＝読めない（★埋めない）。
    """
    m = re.search(r"飴玉\s*[:：]?\s*\**\s*([◯○〇×✕✗x])", kotae)
    if m:
        return m.group(1) in "◯○〇"
    # 印が無いときだけ、⓪の本文を見る。★ここでも推測で◯にしない
    b = re.search(r"【⓪飴玉】(.{0,300})", kotae, re.S)
    if b:
        t = b.group(1)
        if re.search(r"(つまんな|つまらな|何も無|何もなか|一つも|1つも|ひとつも)", t):
            return False
    return None


def amedama_riyuu(rec):
    """★✕になった人の「何も無かった理由」を1行で。**在庫が無い／あるのに出せない**で割る。
    ★推測で書かない。機械で照合した結果からしか書かない。"""
    kai = rec.get("kaimono") or []
    mon = rec.get("annainin_no_mondai") or []
    if kai and mon:
        return "在庫が無い（%s）と、あるのに出せていない（%s）の両方" % ("・".join(kai[:3]),
                                                                    "・".join(mon[:3]))
    if kai:
        return "★在庫が無い：%s" % "・".join(kai[:5])
    if mon:
        return "★棚にはあるのに案内人が出せていない：%s" % "・".join(mon[:5])
    if not (rec.get("annai") or "").strip():
        return "★案内人が何も返さなかった（%s）" % (rec.get("annaiError") or "理由不明")
    return "★欲しかったものの具体名が出てこなかった（在庫か案内人かをまだ割れていない）"


def hoshikatta(kotae):
    """【②在庫】に客が書いた「欲しかったのに出てこなかった名前」を拾う。

    ★2026-09-24 実測で分かった形（Gensparkの返事）:
        ### Question: 2. 【②在庫】…（★問いの文がここに丸ごと echo される）
        verbatim: …（★ページから引いた原文。名前ではない）
        answer: Sai Sai Kham Leng
                Phyu Phyu Kyaw Thein
        在庫: 0/10
      ★最初の実走（13:41）で、この「問いの文」と「verbatim」まで名前として拾ってしまい、
        仕入れのキューに『### Question: 3.』『あなたが本当に聴きたかったのに…』という
        ゴミを2件積んだ（1155番・1156番）。**answer: の後ろだけを読む。**
    """
    body = ""
    m = re.search(r"【②在庫】(.*?)(?=###\s*Question|【③|$)", kotae, re.S)
    if m:
        body = m.group(1)
        # ★answer: があるなら、その後ろだけが客の言葉。前は問いの echo と原文引用。
        am = re.search(r"^\s*answer\s*[:：]\s*(.*)$", body, re.S | re.M)
        if am:
            body = am.group(1)
        body = re.split(r"^\s*(?:在庫|verbatim)\s*[:：]", body, maxsplit=1, flags=re.M)[0]
    out = []
    for ln in body.splitlines():
        ln = ln.strip()
        ln = re.sub(r"^[\-\*・>]\s*|^\d+[\.\)、]\s*", "", ln).strip()
        if not ln or ln.startswith("在庫") or len(ln) > 80:
            continue
        if re.match(r"^(なし|特になし|ありません|該当なし|answer|verbatim)", ln, re.I):
            continue
        # ★名前ではなく「文」を落とす。2026-09-24 実測：「私が本当に聴きたかったのは
        #   以下のものです」を仕入れの名前として拾った。文末・助詞で機械的に弾く。
        if re.search(r"(です|ます|ください|でした|ません|、|。|以下のもの|以下の通り)", ln):
            continue
        ln = re.sub(r"[「」『』\"]", " ", ln).split("（")[0].split("(")[0]
        ln = re.sub(r"\s+", " ", ln).strip(" 　-–—:：")
        if 2 <= len(ln) <= 60:
            out.append(ln)
    return out[:5]


def gouhi(kotae):
    """忖度だけの答えを落とす。★辛口が1行も無いものは不合格。"""
    r = []
    if len(kotae.strip()) < 200:
        r.append("短すぎる（200字未満）")
    if amedama(kotae) is None:
        r.append("飴玉の◯✕が読めない（★一番上の判定なので、無いものは合格にしない）")
    t = tensuu(kotae)
    if t.get("sougou") is None:
        r.append("総合点が読めない")
    if sum(1 for v in t.values() if v is None) >= 3:
        r.append("点数が3つ以上読めない")
    m = re.search(r"【⑥いちばん辛口な一言】(.{0,120})", kotae, re.S)
    if m and re.match(r"\s*(なし|特になし|ありません|該当なし)", m.group(1)):
        r.append("辛口が『なし』（忖度している）")
    return (len(r) == 0), r


def saiten(y, kotae_annai, kuchi="gsk"):
    """客の役のまま、案内人の答えに点を付けさせる。

    kuchi="gsk"   … Genspark（前払いクレジット。10/4で消えるので使い切る方が得）
    kuchi="codex" … ChatGPTのcodex（0円）。★同じ役を別のAIにやらせて割れたら記録するため。
    ★1周＝1つの口。混ぜない（混ぜると平均点が何の平均か分からなくなる）。
    """
    yaku, toi = _daihon(DAIHON_SAITEN, {
        "URL": CONCIERGE_URL, "KUNI": y["kuni"], "TOSHI": y["toshi"], "SEI": y["sei"],
        "SUKI": y["suki"], "RIYUU": y["riyuu"], "HITOKOTO": y["hitokoto"],
        "KOTAE": (kotae_annai or "（案内人は何も返してきませんでした）")[:6000]})
    honbun = "\n".join("%d. %s" % (i + 1, q) for i, q in enumerate(toi))
    toi_all = ("%s\n\n----\nこの役になりきって、下の問いに**上から順に、番号と【見出し】を付けて**"
               "全部答えてください。1つも飛ばさないでください。\n\n%s" % (yaku, honbun))

    if kuchi == "codex":
        c = _codex_toosu(toi_all, "50人の客・採点（%s）" % y["id"])
        kotae = c["kotae"]
        ok, riyuu = (gouhi(kotae) if kotae
                     else (False, ["codexが答えを返さなかった：%s" % (c["err"] or "理由不明")]))
        g = {"byou": c["byou"], "zen": None, "ato": None, "tsukatta": 0}
        dare = c["who"]
    else:
        g = _gsk_toosu(CONCIERGE_URL, toi_all, "50人の客・採点（%s）" % y["id"])
        kotae = _kotae_toridasu((g["r"].get("stdout") or "").strip())
        dare = "genspark(gsk)"

        ok, riyuu = (gouhi(kotae) if g["r"].get("ok") and kotae
                     else (False, ["Gensparkが答えを返さなかった"]))
        # ★1076番と同じ栓：クレジットが減っていない結果は機械が弾く（感想ではなく残高の差で判定）
        if g["tsukatta"] is None:
            ok, riyuu = False, riyuu + ["残クレジットが読めない＝Gensparkを通ったか確かめられない"]
        elif g["tsukatta"] <= 0:
            ok, riyuu = False, riyuu + ["クレジットが1つも減っていない＝Gensparkは通っていない（前%s→後%s）"
                                        % (g["zen"], g["ato"])]

    return {"ok": ok, "口": dare, "fugoukakuRiyuu": riyuu, "amedama": amedama(kotae) if kotae else None,
            "ten": tensuu(kotae) if kotae else {},
            "hoshikatta": hoshikatta(kotae) if kotae else [],
            # ★ここからが2026-09-24に足した「答えまで聞く」4つ。
            #   たまごさん「文句で終わらせない。必ず『じゃあどうすれば』まで出させる」
            "shiireTeian": shiire_teian(kotae) if kotae else [],
            "narabi": narabi(kotae) if kotae else [],
            "daiichisei": daiichisei(kotae) if kotae else "",
            "yokatta": yokatta(kotae) if kotae else "",
            "kotae": kotae, "秒": g["byou"],
            "残クレジット前": g["zen"], "残クレジット後": g["ato"],
            "使ったクレジット": g["tsukatta"]}


# ═════════════════════════ 1周回す ═════════════════════════

def mawasu(limit=10, koukai=True, kuchi="gsk", tobasu=0):
    from playwright.sync_api import sync_playwright

    # ★tobasu＝先頭から何人飛ばすか。名簿の並びは変えないまま、11人目から回すときに使う。
    meibo = yaku_yomu()[tobasu:tobasu + limit]
    day = time.strftime("%Y-%m-%d")
    outdir = os.path.join(OUT, day)
    os.makedirs(outdir, exist_ok=True)
    rnd = len([r for r in _rows(SCORE)]) + 1
    outpath = os.path.join(outdir, "r%02d.json" % rnd)
    rows = []

    def save():
        tmp = outpath + ".tmp"
        json.dump({"at": _now(), "round": rnd, "base": BASE, "rows": rows},
                  io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, outpath)

    with sync_playwright() as pw:
        br = pw.chromium.launch(args=["--disable-dev-shm-usage"])

        def fresh():
            # ★1人ごとに客を入れ替える（前の客の会話が残っていると点が嘘になる）
            c = br.new_context(viewport={"width": 390, "height": 844},
                               user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 "
                                           "like Mac OS X) AppleWebKit/605.1.15"))
            p = c.new_page()
            p.goto(CONCIERGE_URL, wait_until="domcontentloaded", timeout=60000)
            p.wait_for_timeout(2500)
            p.wait_for_selector(CONCIERGE_SEL, timeout=20000)
            return c, p

        for i, y in enumerate(meibo, 1):
            rec = {"id": y["id"], "kuni": y["kuni"], "toshi": y["toshi"], "sei": y["sei"],
                   "suki": y["suki"], "riyuu": y["riyuu"],
                   "hitokoto": y["hitokoto"], "go": y["go"]}
            ctx = None
            try:
                ctx, page = fresh()
                rec["annai"] = annai_ni_kiku(y["hitokoto"], page=page, ctx=ctx)
                rec["annaiError"] = ""
            except Exception as ex:
                rec["annai"] = ""
                rec["annaiError"] = "%s: %s" % (type(ex).__name__, str(ex)[:160])
            finally:
                try:
                    ctx and ctx.close()
                except Exception:
                    pass

            s = saiten(y, rec["annai"], kuchi=kuchi)
            rec.update(s)
            # ★在庫の切り分けは機械がやる（客の言葉を事実として扱わない）
            # ★②在庫で挙げた名前＋⑦「誰を仕入れておけばよかったか」の名前、両方を照合する。
            #   たまごさん「そこまでがセット」。⑦だけに出てきた名前も仕入れに積む。
            nm_all, mita_nm = [], set()
            for nm in list(s["hoshikatta"]) + list(s.get("shiireTeian") or []):
                if _norm(nm) in mita_nm:
                    continue
                mita_nm.add(_norm(nm))
                nm_all.append(nm)
            rec["zaiko"] = [{"name": nm, "tana": tana_ni_aruka(nm)} for nm in nm_all]
            rec["kaimono"] = [z["name"] for z in rec["zaiko"] if not z["tana"]]
            rec["annainin_no_mondai"] = [z["name"] for z in rec["zaiko"]
                                         if z["tana"] and z["tana"] != FUMEI]
            rec["hantei_dekinai"] = [z["name"] for z in rec["zaiko"] if z["tana"] == FUMEI]
            rows.append(rec)
            save()
            print("  %d/%d %s 飴玉%s 総合%s %s／買い物%d件・案内人%d件"
                  % (i, len(meibo), "○" if s["ok"] else "×",
                     {True: "◯", False: "✕", None: "—"}[s.get("amedama")],
                     s["ten"].get("sougou"), y["id"], len(rec["kaimono"]),
                     len(rec["annainin_no_mondai"])), flush=True)

        br.close()

    matome = matomeru(rows, rnd, outpath)
    matome["口"] = (rows[-1].get("口") if rows else kuchi)   # ★どのAIが付けた点か
    _append(SCORE, matome)
    tsunda = shiire_tsumu(rows)
    matome["仕入れに積んだ"] = tsunda
    if koukai:
        matome["koukaiUrl"] = page_dasu()
    return matome


def matomeru(rows, rnd, outpath):
    ok = [r for r in rows if r.get("ok")]
    sou = [r["ten"]["sougou"] for r in ok if r.get("ten", {}).get("sougou") is not None]
    hei = round(sum(sou) / len(sou), 2) if sou else None
    saitei = None
    if sou:
        w = min(ok, key=lambda r: (r["ten"].get("sougou") if r["ten"].get("sougou") is not None else 99))
        saitei = {"id": w["id"], "kuni": w["kuni"], "toshi": w["toshi"],
                  "ten": w["ten"].get("sougou")}
    # ★飴玉が一番上の判定。★✕が1人でも出たら赤。平均点がいくら高くても合格にしない。
    batsu = [r for r in ok if r.get("amedama") is False]
    return {"at": _now(), "round": rnd, "人数": len(rows), "合格": len(ok),
            "飴玉ゼロ人数": len(batsu),
            "飴玉ゼロ率": (round(100.0 * len(batsu) / len(ok), 1) if ok else None),
            "飴玉ゼロの人": [{"id": r["id"], "kuni": r["kuni"], "toshi": r["toshi"],
                             "riyuu": amedama_riyuu(r)} for r in batsu],
            "判定": ("🔴 赤（飴玉ゼロが%d人。平均で隠さない）" % len(batsu) if batsu
                     else ("✅ 全員が何か1つ持って帰れた" if ok else "⚪ まだ1人も通っていない")),
            "平均点": hei, "百点換算": (round(hei * 10, 1) if hei is not None else None),
            "最低の役": saitei,
            "買い物リスト件数": sum(len(r.get("kaimono") or []) for r in rows),
            "案内人の問題件数": sum(len(r.get("annainin_no_mondai") or []) for r in rows),
            # ★「答えまで聞く」がどれだけ返ってきたか。★返ってこなかった数も隠さない
            "仕入れ提案あり": sum(1 for r in rows if r.get("shiireTeian")),
            "並び提案あり": sum(1 for r in rows if r.get("narabi")),
            "第一声あり": sum(1 for r in rows if r.get("daiichisei")),
            "良かった点あり": sum(1 for r in rows if r.get("yokatta")),
            "使ったクレジット": round(sum(r.get("使ったクレジット") or 0 for r in rows), 3),
            "残クレジット": (rows[-1].get("残クレジット後") if rows else None),
            "file": os.path.relpath(outpath, REPO)}


# ═════════════════════════ ④ 仕入れリストをキューに積む ═════════════════════════

def shiire_tsumu(rows):
    """★たまごさん指定：在庫が無い＝買い物リスト。人が写し替えない。工場のキューに直接積む。
    ★『その周辺も』＝同じ役が挙げた他の名前を一緒に1件にまとめて渡す（別々に積むと薄くなる）。"""
    try:
        import command_ingest as ci
    except Exception as e:
        return {"ok": False, "error": "キューに積めませんでした: %s" % str(e)[:160]}

    sudeni = set()
    for r in _rows(SHIIRE):
        for nm in (r.get("names") or []):
            sudeni.add(_norm(nm))

    tsunda = []
    for r in rows:
        nm = [n for n in (r.get("kaimono") or []) if _norm(n) not in sudeni]
        if not nm:
            continue
        for n in nm:
            sudeni.add(_norm(n))
        label = "仕入れ｜%s歳・%s が欲しがった %d件" % (r["toshi"], r["kuni"], len(nm))
        text = "\n".join([
            "【仕入れ】50人の客（1080番）が欲しがったのに棚に無かったもの。",
            "",
            "■ 誰が欲しがったか",
            "  %s／%s歳・%s" % (r["kuni"], r["toshi"], r["sei"]),
            "  好きな音楽: %s" % r["suki"],
            "  案内人に言った一言: %s" % r["hitokoto"],
            "",
            "■ 棚に無かったもの（★索引に機械で照合済み。推測ではない）",
        ] + ["  ・%s" % n for n in nm] + [
            "",
            "■ やること",
            "  ① 上の名前を仕入れる（tools/shiire_fetch.py --names で素材を集める）",
            "  ② ★その周辺も仕入れる（同時代・同ジャンル・同じ国の隣のアーティスト）。",
            "     たまごさん「その周辺も仕入れる。『これないんですか』って言われたら仕入れる」",
            "  ③ 棚出しの可否はたまごさんが決める。勝手に載せない。",
            "",
            "※出どころ: %s" % KOUKAI_URL,
        ])
        try:
            st, msg = ci.queue_add(text, priority=2, label=label, origin="factory")
            tsunda.append({"id": r["id"], "names": nm, "status": st, "msg": str(msg)[:120]})
            _append(SHIIRE, {"at": _now(), "id": r["id"], "names": nm, "status": st})
        except Exception as e:
            tsunda.append({"id": r["id"], "names": nm, "status": "failed",
                           "msg": str(e)[:120]})
    return tsunda


# ═════════════════════════ ⑤ 1枚のページ ═════════════════════════

def e(s):
    return html.escape(str(s if s is not None else ""))


def _saikin():
    day = sorted(glob.glob(os.path.join(OUT, "*", "r*.json")))
    if not day:
        return None
    return json.load(io.open(day[-1], encoding="utf-8"))


def page_tsukuru():
    d = _saikin()
    if not d:
        return None
    rows = d["rows"]
    hist = _rows(SCORE)
    ima = hist[-1] if hist else matomeru(rows, 0, "")
    kaimono, mondai = [], []
    for r in rows:
        for n in (r.get("kaimono") or []):
            kaimono.append((n, r["kuni"], r["toshi"]))
        for n in (r.get("annainin_no_mondai") or []):
            mondai.append((n, r["kuni"], r["toshi"]))

    # ★飴玉✕の人を必ず先頭に出す（たまごさん指定）。そのあとは点の低い順。
    narabi = sorted(rows, key=lambda r: (0 if r.get("amedama") is False else 1,
                                         r.get("ten", {}).get("sougou")
                                         if r.get("ten", {}).get("sougou") is not None else 99))
    batsu = [r for r in rows if r.get("amedama") is False]
    tsuuka = [r for r in rows if r.get("ok")]
    zeroritsu = (round(100.0 * len(batsu) / len(tsuuka), 1) if tsuuka else None)
    ame = "".join(
        "<li><b>%s・%s歳%s</b>「%s」<br><span class=dare>%s</span></li>"
        % (e(r["kuni"]), e(r["toshi"]), e(r["sei"]), e(r["hitokoto"]), e(amedama_riyuu(r)))
        for r in batsu) or "<li>★この回は全員が何か1つ持って帰れました。</li>"

    suii = "".join(
        "<tr><td>%s</td><td>%s人</td><td class=%s>%s人（%s%%）</td><td class=big>%s点</td>"
        "<td>%s</td><td>%s件</td></tr>"
        % (e((h.get("at") or "")[:16]), e(h.get("人数")),
           ("akaji" if (h.get("飴玉ゼロ人数") or 0) else "aoji"),
           e(h.get("飴玉ゼロ人数")), e(h.get("飴玉ゼロ率")), e(h.get("百点換算")),
           e((h.get("最低の役") or {}).get("id")), e(h.get("買い物リスト件数")))
        for h in hist[-12:])

    hito = ""
    for r in narabi:
        t = r.get("ten") or {}
        sou = t.get("sougou")
        iro = "warui" if (sou is not None and sou < 6) else ("futsuu" if (sou is not None and sou < 8.5) else "ii")
        if r.get("amedama") is False:
            iro = "warui"
        ameji = ("<span class=ame-x>飴玉 ✕ つまんない</span>" if r.get("amedama") is False
                 else ("<span class=ame-o>飴玉 ◯</span>" if r.get("amedama") is True
                       else "<span class=tag>飴玉 —（読めず）</span>"))
        hito += """
<details class="hito %s"><summary>
%s <b>%s点</b>　%s・%s歳%s　<span class=q>「%s」</span>
<span class=tag>的中%s／在庫%s／言葉%s／もう一曲%s</span>%s</summary>""" % (
            iro, ameji,
            e("%s" % (sou * 10 if isinstance(sou, int) else "—")),
            e(r["kuni"]), e(r["toshi"]), e(r["sei"]), e(r["hitokoto"]),
            e(t.get("techuu")), e(t.get("zaiko")), e(t.get("kotoba")), e(t.get("mouikkyoku")),
            ("" if r.get("ok") else '<span class="ng">不合格：%s</span>'
             % e("、".join(r.get("fugoukakuRiyuu") or []))))
        hito += """
<div class=naka>
%s
<p class=meta>好きな音楽: %s<br>来た理由: %s</p>
<h4>案内人が返したもの（★そのまま）</h4><pre>%s</pre>
<h4>お客さんの採点（★Gensparkの答え。要約していません）</h4><pre>%s</pre>
</div></details>""" % (
            ('<p class=amewake>★何も持って帰れなかった理由：%s</p>' % e(amedama_riyuu(r))
             if r.get("amedama") is False else ""),
            e(r["suki"]), e(r["riyuu"]),
            e(r.get("annai") or ("（案内人は何も返しませんでした）%s" % (r.get("annaiError") or ""))),
            e(r.get("kotae") or "（空）"))

    # ★「答えまで聞く」の4つ（2026-09-24）。客の言葉をそのまま並べる。要約しない。
    teian, nara, koe, yoka = [], [], [], []
    for r in rows:
        dare = "%s・%s歳%s" % (r["kuni"], r["toshi"], r["sei"])
        for n in (r.get("shiireTeian") or []):
            teian.append((n, dare, tana_ni_aruka(n)))
        for n in (r.get("narabi") or []):
            nara.append((n, dare))
        if r.get("daiichisei"):
            koe.append((r["daiichisei"], dare, r["hitokoto"]))
        if r.get("yokatta"):
            yoka.append((r["yokatta"], dare))
    teian_h = "".join(
        "<li><b>%s</b><span class=dare>%s／%s</span></li>"
        % (e(n), e(d), e(t or "★棚に無い＝仕入れる")) for n, d, t in teian) \
        or "<li>まだ誰も答えていません</li>"
    narabi_h = "".join("<li><b>%s</b><span class=dare>%s</span></li>" % (e(n), e(d))
                       for n, d in nara) or "<li>まだ誰も答えていません</li>"
    koe_h = "".join("<li><b>%s</b><span class=dare>%s が「%s」と入ってきたとき</span></li>"
                    % (e(n), e(d), e(h)) for n, d, h in koe) or "<li>まだ誰も答えていません</li>"
    yoka_h = "".join("<li>%s<span class=dare>%s</span></li>" % (e(n), e(d))
                     for n, d in yoka) or "<li>★この回は誰も「良かった点」を挙げませんでした</li>"

    kai = "".join("<li><b>%s</b><span class=dare>%s・%s歳が欲しがった</span></li>"
                  % (e(n), e(k), e(t)) for n, k, t in kaimono) or "<li>なし</li>"
    mon = "".join("<li><b>%s</b><span class=dare>%s・%s歳が欲しがった（★棚にはある）</span></li>"
                  % (e(n), e(k), e(t)) for n, k, t in mondai) or "<li>なし</li>"

    return """<!doctype html><html lang=ja><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>50人の客｜誰が入ってきても答えられるか</title>
<style>
:root{--bg:#12100e;--fg:#f4efe6;--dim:#a79e8f;--line:#2e2a25;--ii:#7fd1a6;--futsuu:#e8c06a;--warui:#e8796a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.75 -apple-system,"Hiragino Sans",sans-serif;padding:20px 16px 80px}
.wrap{max-width:820px;margin:0 auto}
h1{font-size:23px;margin:0 0 4px;letter-spacing:.02em}
.date{color:var(--dim);font-size:12px;margin-bottom:22px}
.atama{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:0 0 18px}
.card{background:#1b1815;border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.card .k{color:var(--dim);font-size:11px;letter-spacing:.08em}
.card .v{font-size:30px;font-weight:700;line-height:1.2;margin-top:2px}
.card .v small{font-size:13px;color:var(--dim);font-weight:400}
.mokuhyou{color:var(--dim);font-size:12px;margin:-10px 0 22px}
h2{font-size:15px;margin:30px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line);letter-spacing:.06em}
ul{margin:0;padding-left:20px}
li{margin:5px 0}
.dare{color:var(--dim);font-size:12px;margin-left:8px}
.hito{border:1px solid var(--line);border-radius:10px;margin:7px 0;background:#181613}
.hito summary{cursor:pointer;padding:12px 14px;font-size:14px;list-style:none}
.hito summary::-webkit-details-marker{display:none}
.hito.ii summary b{color:var(--ii)} .hito.futsuu summary b{color:var(--futsuu)} .hito.warui summary b{color:var(--warui)}
.hito summary b{font-size:19px;margin-right:8px}
.q{color:var(--dim)}
.tag{display:block;color:var(--dim);font-size:11px;margin-top:3px}
.ng{display:block;color:var(--warui);font-size:11px;margin-top:3px}
.naka{padding:0 14px 14px;border-top:1px solid var(--line)}
.meta{color:var(--dim);font-size:12px}
h4{font-size:12px;color:var(--dim);margin:14px 0 5px;letter-spacing:.06em}
pre{white-space:pre-wrap;word-break:break-word;background:#100e0c;border:1px solid var(--line);border-radius:8px;padding:11px;font-size:12.5px;line-height:1.7;max-height:420px;overflow:auto;margin:0}
table{width:100%%;border-collapse:collapse;font-size:13px}
td,th{border-bottom:1px solid var(--line);padding:7px 4px;text-align:left}
td.big{font-size:17px;font-weight:700}
.danmari{color:var(--dim);font-size:12px;border-left:2px solid var(--line);padding-left:11px;margin:22px 0}
.hantei{font-size:17px;font-weight:700;padding:13px 16px;border-radius:12px;margin:0 0 14px}
.hantei.aka{background:#2a1512;border:1px solid #6a2e26;color:var(--warui)}
.hantei.ao{background:#12211a;border:1px solid #2b4a3a;color:var(--ii)}
ul.ame{padding-left:20px;margin-bottom:6px}
ul.ame li{margin:9px 0}
.ame-x{display:inline-block;background:#2a1512;border:1px solid #6a2e26;color:var(--warui);border-radius:99px;padding:1px 9px;font-size:11.5px;margin-right:6px}
.ame-o{display:inline-block;border:1px solid #2b4a3a;color:var(--ii);border-radius:99px;padding:1px 9px;font-size:11.5px;margin-right:6px}
.amewake{color:var(--warui);font-size:12.5px;margin:10px 0 0}
.ori{border:1px solid var(--line);border-radius:10px;margin:9px 0;background:#181613}
.ori>summary{cursor:pointer;padding:12px 14px;font-size:14px;list-style:none;color:var(--fg)}
.ori>summary::-webkit-details-marker{display:none}
.ori>summary::before{content:"＋ ";color:var(--dim)}
.ori[open]>summary::before{content:"− "}
.ori .naka{border-top:1px solid var(--line);padding-top:10px}
td.akaji{color:var(--warui);font-weight:700}
td.aoji{color:var(--ii)}
</style>
<div class=wrap>
<h1>50人の客｜誰が入ってきても答えられるか</h1>
<div class=date>%s ／ %d人ぶん ／ 使ったクレジット %s（残 %s）</div>

<div class=atama>
<div class=card><div class=k>飴玉ゼロ率 ★目標はゼロ</div><div class=v>%s<small>%%</small></div></div>
<div class=card><div class=k>平均点</div><div class=v>%s<small> / 100</small></div></div>
</div>
<div class=mokuhyou>★たまごさんが見るのはこの<b>2つだけ</b>で足ります。下は全部畳んであります。</div>

<h2>点数の推移</h2>
<table><tr><th>いつ</th><th>人数</th><th>飴玉ゼロ ★目標0</th><th>100点換算</th><th>最低の役</th><th>仕入れ</th></tr>%s</table>

<div class="hantei %s">%s</div>

<details class=ori><summary>飴玉ゼロ（「つまんない」と言われた人）★%s人</summary>
<ul class=ame>%s</ul></details>

<details class=ori><summary>★客が名指しした「これを仕入れておけばよかった」（⑦）</summary>
<div class=naka><p class=meta>たまごさん「文句を言うんだったら、じゃあ誰を入れたらいいんだい？と聞いて、それをどんどん反映していこう」<br>★右側は手元の索引に機械で照合した結果です。「棚に無い」は仕入れのキューに積んであります。</p>
<ul>%s</ul></div></details>

<details class=ori><summary>★「誰と誰が隣にあったら嬉しい」（⑧）</summary>
<div class=naka><ul>%s</ul></div></details>

<details class=ori><summary>★案内人の第一声は、こう言えばよかった（⑨・客の言葉そのまま）</summary>
<div class=naka><ul>%s</ul></div></details>

<details class=ori><summary>★良かった点（⑩）</summary>
<div class=naka><p class=meta>たまごさん「いいコメントもあるんだったらそれも欲しいよね。謙虚に受け入れよう」</p>
<ul>%s</ul></div></details>

<details class=ori><summary>仕入れリスト（棚に無かったもの）★工場のキューに自動で積んであります</summary>
<div class=naka><ul>%s</ul></div></details>

<details class=ori><summary>★あるのに出せない（案内人の問題。これは仕入れではありません）</summary>
<div class=naka><ul>%s</ul></div></details>

<details class=ori><summary>1人ずつ（点の低い順）★中身は全部そのまま残してあります</summary>
<div class=naka>%s</div></details>

<div class=mokuhyou>★一番上の判定は点数ではなく<b>飴玉</b>です。たまごさん「誰が来ても飴玉1個ぐらいはあげたいね。ごきげん補給所なわけだから。何か1つでも持って帰ってもらって。これが最低ライン。」／「『ここつまんねぇな』って言われたら、もう負けですよ。誰に対してもだよ。」<br>★<b>✕が1人でも出たら赤。平均点がいくら高くても合格にしません。平均で隠さない。</b><br>★点数の目標：年内に 85〜90点。</div>

<div class=danmari>%s</div>
</div>""" % (
        e(d.get("at")), len(rows), e(ima.get("使ったクレジット")), e(ima.get("残クレジット")),
        e(zeroritsu if zeroritsu is not None else "—"),
        e(ima.get("百点換算") if ima.get("百点換算") is not None else "—"),
        suii,
        ("aka" if batsu else "ao"), e(ima.get("判定") or ("🔴 赤（飴玉ゼロ%d人）" % len(batsu) if batsu else "✅ 全員が何か1つ持って帰れた")),
        len(batsu), ame,
        teian_h, narabi_h, koe_h, yoka_h,
        kai, mon, hito, DANMARI)


def page_dasu():
    """1枚にして公開リポ（ai-kaigi）へ出す。★Gensparkは非公開リポを読めない。"""
    h = page_tsukuru()
    if not h:
        return "（まだ1周も回していないのでページを作れません）"
    local = os.path.join(OUT, "index.html")
    io.open(local, "w", encoding="utf-8").write(h)
    try:
        import _965_keijiban as kj
        # ★2026-09-24 実測：ai-kaigi に gh-pages は無い。Pagesは main の / から出ている。
        r = kj.run_job({"repo": KOUKAI_REPO, "action": "putfile", "path": KOUKAI_PATH,
                        "branch": "main", "text": h,
                        "message": "50人の客（1080番）%s" % time.strftime("%F %T")})
        return KOUKAI_URL if r.get("ok") else "（公開できませんでした：%s）" % r.get("error")
    except Exception as ex:
        return "（公開できませんでした：%s）" % str(ex)[:160]


# ═════════════════════════ ⑥ 毎週回す ═════════════════════════

STAMP_N = os.path.join(REPO, "status", ".kyaku50_last_nichiji")


def nichiji(limit=10):
    """★1日1回、名簿の**続きから**10人ぶん回す。

    たまごさん（2026-09-24・原文）
      「1回で終わらせない。定期で回す。」「もう開始でいいよ。どんどん走らせて、
        出るように変えていって、どんどん。」「とりあえず100人くらいペルソナを作って、
        ガンガンやってガンガン直そう。」

    ★先頭10人は触らない（--shukan の物差し。同じ役で点の推移を追うため）。
      11人目から10人ずつ進めて、端まで行ったら11人目に戻る。
    ★口は残クレジットで決める：残っていれば Genspark（10/4で消えるので使い切る方が得）、
      尽きたら codex（0円）に自動で移る。★新しい常駐は増やさない（既存の定期便から呼ばれる）。
    """
    day = time.strftime("%Y-%m-%d")
    last_day, offset = "", 10
    try:
        t = io.open(STAMP_N).read().split()
        last_day = t[0]
        offset = int(t[1])
    except Exception:
        pass
    if last_day == day:
        return {"ok": True, "skip": "今日はもう回しました（%s・次は%d人目から）" % (last_day, offset + 1)}
    try:
        load = os.getloadavg()[0]
    except Exception:
        load = 0
    if load > 40.0:
        return {"ok": True, "skip": "Macが混んでいます（load %.1f）。次に回す番は消費しません" % load}

    n = len(yaku_yomu())
    if offset >= n:
        offset = 10 if n > 10 else 0

    kuchi = "gsk"
    try:
        import gaibu_kuchi as g
        z = g.gsk_zandaka()
        if z is not None and z < 60:
            kuchi = "codex"   # ★クレジットが尽きたら0円の口へ自動で移る（止めない）
    except Exception:
        pass

    m = mawasu(limit=limit, kuchi=kuchi, tobasu=offset)
    m["何人目から"] = offset + 1
    m["口の選び方"] = "残クレジットで決めた（%s）" % kuchi
    nxt = offset + limit
    if nxt >= n:
        nxt = 10 if n > 10 else 0
    io.open(STAMP_N, "w").write("%s %d\n" % (day, nxt))   # ★走り切った時だけ書く
    return m


def shukan(limit=10):
    """★新しい常駐は増やさない。既存の定期便から呼ばれて、週に1回だけ外に出る。
    ★ゲートを使い切るのは『最後まで走り切った時だけ』（931番の穴を繰り返さない）。"""
    try:
        last = io.open(STAMP).read().strip()
    except Exception:
        last = ""
    ima = time.strftime("%Y-W%W")
    if last == ima:
        return {"ok": True, "skip": "今週はもう回しました（%s）" % last}
    try:
        load = os.getloadavg()[0]
    except Exception:
        load = 0
    if load > 40.0:
        return {"ok": True, "skip": "Macが混んでいます（load %.1f）。ゲートは消費しません" % load}

    m = mawasu(limit=limit)
    io.open(STAMP, "w").write(ima)      # ★走り切った時だけ書く
    return m


# ═════════════════════════ 入口 ═════════════════════════

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--yaku", type=int, help="Gensparkに役を作らせる（この人数ぶん。固定6人は別に足す）")
    p.add_argument("--tasu", type=int, help="名簿の後ろに足す（★すでに居る人は動かさない。100人にするならこれ）")
    p.add_argument("--mawasu", action="store_true")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--tobasu", type=int, default=0, help="名簿の先頭から何人飛ばすか")
    p.add_argument("--kuchi", default="gsk", choices=["gsk", "codex"],
                   help="点を付ける口。gsk=Genspark（クレジット）／codex=ChatGPT（0円）")
    p.add_argument("--page", action="store_true")
    p.add_argument("--shukan", action="store_true")
    p.add_argument("--nichiji", action="store_true",
                   help="1日1回・名簿の続きから10人（★先頭10人は物差しなので触らない）")
    p.add_argument("--ichiran", action="store_true")
    p.add_argument("--tana", help="この名前は棚にあるか（0円で確かめる）")
    p.add_argument("--no-koukai", action="store_true")
    p.add_argument("--dry", action="store_true")
    a = p.parse_args()

    if a.tana:
        print("%s → %s" % (a.tana, tana_ni_aruka(a.tana) or "★棚に無い（＝買い物リスト）"))
        return 0
    if a.ichiran:
        for h in _rows(SCORE):
            print("%s  %s人  %s点／100  最低=%s  仕入れ%s件  案内人%s件"
                  % (h.get("at"), h.get("人数"), h.get("百点換算"),
                     (h.get("最低の役") or {}).get("id"),
                     h.get("買い物リスト件数"), h.get("案内人の問題件数")))
        return 0
    if a.tasu:
        r = yaku_tasu(a.tasu)
        print(json.dumps(r, ensure_ascii=False, indent=1)[:4000])
        return 0 if r.get("ok") else 3
    if a.yaku:
        r = yaku_tsukuru(a.yaku, dry=a.dry)
        print(json.dumps(r, ensure_ascii=False, indent=1)[:4000])
        return 0 if r.get("ok") else 3
    if a.nichiji:
        print(json.dumps(nichiji(a.limit), ensure_ascii=False, indent=1, default=str))
        return 0
    if a.shukan:
        print(json.dumps(shukan(a.limit), ensure_ascii=False, indent=1, default=str))
        return 0
    if a.page:
        print(page_dasu())
        return 0
    if a.mawasu:
        m = mawasu(limit=a.limit, koukai=not a.no_koukai, kuchi=a.kuchi, tobasu=a.tobasu)
        print(json.dumps(m, ensure_ascii=False, indent=1, default=str))
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
