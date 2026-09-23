#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1039番【入れる係】投げ込み箱に投げたものを、深夜0時に棚へ入れる。

たまごさん（2026-09-23・原文）:
  「これをもとにコピー書いて、指定の棚に入れてくれればいいわけだから。1日1回でもいいのよ。
    最後12時に、今日届いている分だけピックアップして入れる。」
  「ラバブルでスマホで寝ながら入れようとすると落ちる。読み込みも時間かかる。」

------------------------------------------------------------------
★棚とカードを結んでいる表（実測で特定した。2026-09-23 15:38）
------------------------------------------------------------------
  job `20260923-153749-9227` の下見では候補11個中10個が 404 で、**結び目は見つからなかった。**
  当てずっぽうの名前叩きをやめて、joy-relief-station のコードを読んで確かめた：

    status/_1039/lib/adminShelves.functions.ts:124  admin_shelf_picks
    同 :1199（adminAddPick の INSERT）
      db.from("admin_shelf_picks").insert({
        shelf_id, stock_id, position: max+1, status: "candidate", pinned: false })

  → **結び目は `admin_shelf_picks`。**列は id / shelf_id / stock_id / position / status / pinned。
  → 表に出るかどうかは status で決まる。`lib/publicShelves.functions.ts`:462 が正本：
      status が "excluded" と "unmarked" 以外は表に出る（＝"candidate" も "fixed" も出る）。
  → だからここは**画面の［棚に入れる］ボタンと同じ "candidate"** で入れる。
    人が押した時と1文字も違う行にしない（違う行を作ると、後で人が直せなくなる）。

  ★`admin_stock` には棚を指す列が無い。ここを勘で埋めない。カードを1行、結び目を1行、の2段。

------------------------------------------------------------------
決め（なぜこの形か）
------------------------------------------------------------------
  ・**Lovableの画面を一切通らない。**落ちる場所を通らないために作っている。REST だけ。
  ・**新しい常駐を増やさない。**5分便 machine_status_push.sh に相乗りし、中で1日1回ゲートする
    （tools/gaibu_copy_naoshi.py / tools/mainichi_kuchi.py と同じ型）。列（queue.json）に積まない。
  ・**日が変わった最初の便で走る。**＝深夜0時すぎ。たまごさんの「最後12時に」。
  ・**入れた行は全部 status/nagekomi_ireta.jsonl に控える。**`--modoshi <便番号>` で
    その便で入れた分**だけ**を消す。他人の行は1文字も触らない。
  ・★**1043番：どんな中身でも受ける。「入れられない」で止めない。**
    箱の役目は「あとで実装できるように放り込んでおく」こと。足りないものは
    「◯◯が未定」と印をつけて置くだけ。棚が未定でも、題名が書けなくても、捨てない。
    **入れられないのは「URLもひとことも両方空」のときだけ。**
  ・**関所を通らなかった文は棚へ入れない**が、投げ込み自体は「文が未定」として残す。
  ・鍵の値はこのファイルから一歩も外へ出さない（ログにも報告にも出さない）。

------------------------------------------------------------------
関所（どれも「ここで新しい基準を発明しない」）
------------------------------------------------------------------
  bonjovi-ojisan-kobun  … 文面の型は tools/gaibu_copy_naoshi.py の PROMPT が正本。輸入して使う。
  水道水の判定          … tools/gaibu_copy_nippou.py の judge() が正本。輸入して使う。
  鬼監督                … tools/oni_gate.py の judge() が正本。輸入して使う。
  sekisho-jijitsu-shutten … 材料に無い事実（年号・「原曲」「代表曲」「カバー」・受賞・数字）を
                            書いていたら落とす。下の fact_gate()。
  sekisho-artist-song   … ★detected_artist_id は**書かない。**名前の字が一致しただけで
                            別人の棚に入れる事故（akikoの棚に矢野顕子）は、ここでは
                            「紐づけない」ことで確実に防ぐ。紐づけは人が画面で決める。

------------------------------------------------------------------
回線についての実測事実
------------------------------------------------------------------
  Cowork/Dispatchのサンドボックスからは Supabase へ出られない（Tunnel 403）。
  たまごさんのMacからは出る。だからここ（5分便＝Mac側 / gaibu_runner kind=tanaire）で叩く。

使い方:
  python3 tools/nagekomi_shelf.py                 # 1日1回ゲートつき（5分便が呼ぶ形）
  python3 tools/nagekomi_shelf.py --force         # 今すぐ走らせる
  python3 tools/nagekomi_shelf.py --dry           # 入れずに、何を入れるつもりか出すだけ
  python3 tools/nagekomi_shelf.py --only <id>     # 台帳のその1件だけ
  python3 tools/nagekomi_shelf.py --modoshi <便番号>  # その便で入れた分だけ消す
  python3 tools/nagekomi_shelf.py --show          # 前回の成績
"""
from __future__ import annotations

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
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gaibu_copy_naoshi as naoshi      # noqa: E402  コピーを書く口・鍵の探索（正本）
import gaibu_copy_nippou as nippou      # noqa: E402  水道水の判定（正本）
import oni_gate                         # noqa: E402  鬼監督の判定（正本）
import tana                             # noqa: E402  棚一覧・REST の足回り（正本）
import tana_suiron as suiron            # noqa: E402  ★1177番 棚の推測（仮の棚を付ける・正本）

JST = timezone(timedelta(hours=9))
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
LEDGER = os.path.join(STATUS, "nagekomi.jsonl")
IRETA = os.path.join(STATUS, "nagekomi_ireta.jsonl")
ICHIRAN = os.path.join(PUBLIC, "tana_ichiran.json")
OUT_JSON = os.path.join(PUBLIC, "nagekomi_shelf.json")
GATE = os.path.join(STATUS, ".nagekomi_shelf_last")
FORCE = os.path.join(STATUS, ".nagekomi_shelf_force")
LOCK = os.path.join(STATUS, ".nagekomi_shelf.lock")
LOG = os.path.join(STATUS, "nagekomi_shelf.log")

LOCK_STALE_SEC = 60 * 60
DEADLINE_SEC = 15 * 60     # 1回の持ち時間。Macを占有し続けない
MAX_PER_RUN = 20           # 1回で入れる上限。残りは翌日へ
PICK_STATUS = "candidate"  # ★画面の［棚に入れる］と同じ（adminShelves.functions.ts:1199）


def now():
    return datetime.now(JST)


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


# ---------------------------------------------------------------- ロック
def lock_take():
    if os.path.exists(LOCK):
        try:
            pid = int(io.open(LOCK).read().strip() or 0)
        except Exception:
            pid = 0
        alive = False
        if pid:
            try:
                os.kill(pid, 0)
                alive = True
            except OSError:
                alive = False
        if alive and (time.time() - os.path.getmtime(LOCK)) < LOCK_STALE_SEC:
            return False
        try:
            os.remove(LOCK)
        except OSError:
            pass
    try:
        with io.open(LOCK, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        return True
    except OSError:
        return False


def lock_free():
    try:
        os.remove(LOCK)
    except OSError:
        pass


# ---------------------------------------------------------------- 台帳
def read_jsonl(path):
    rows = []
    try:
        with io.open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    except OSError:
        pass
    return rows


def append_jsonl(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def already_done_ids():
    """もう棚に入れた（または入れて戻した）投げ込みのid。二度入れない。"""
    done = set()
    for r in read_jsonl(IRETA):
        if r.get("nagekomiId") and not r.get("modoshiAt"):
            done.add(r["nagekomiId"])
    return done


# ---------------------------------------------------------------- 棚の名簿
def shelf_index():
    """tana_ichiran.json（棚の正本から吐いたもの）を id 引きにする。手打ちしない。"""
    try:
        d = json.load(io.open(ICHIRAN, encoding="utf-8"))
    except Exception:
        return {}
    return {s["id"]: s for s in (d.get("shelves") or []) if s.get("id")}


# ★1043番【名簿は1か所】棚の名簿は tana_ichiran.json だけ。2か所に持たない。
#   実測（2026-09-24）：箱のページが送るのは `SHELF.id`＝名簿の id そのもの
#   （share/nagekomi-c5fd9d5791b32e88.html:196）。だから箱から来た分はずれない。
#   ずれていた `cute` は、1039番の**機械の試し投げが手打ちした world の値**だった
#   （名簿では world="cute" に16棚。id ではない）。箱のバグではない。
#   → それでも**弾かない。**id で引けなければ棚名で引く。それでも決まらなければ
#     「行き先未定」として受ける（＝あとで棚を決められる）。
def resolve_shelf(sid, name, shelves):
    """棚を1つに決める。決まれば (棚, 経緯)。決まらなければ (None, 理由)。"""
    sid = (sid or "").strip()
    name = (name or "").strip()
    if sid and sid in shelves:
        return shelves[sid], None
    # 棚名で引く（箱が送った表示名、または手打ちの値が棚名だった場合）
    by_title = {}
    for s in shelves.values():
        by_title.setdefault((s.get("title") or "").strip(), s)
    for cand in (name, sid):
        if cand and cand in by_title:
            return by_title[cand], "棚のidでは引けなかったので棚名「%s」で決めた" % cand
    # world の値だった場合：その world に棚が1つだけなら決める。複数なら決めない
    if sid:
        same = [s for s in shelves.values() if (s.get("world") or "") == sid]
        if len(same) == 1:
            return same[0], "world「%s」の棚が1つだけだったので決めた" % sid
        if len(same) > 1:
            return None, ("「%s」は棚の名前ではなく世界の名前でした（%d棚ある）。"
                          "棚のボタンから1つ選べば入ります" % (sid, len(same)))
    return None, "行き先の棚がまだ決まっていません"


# ---------------------------------------------------------------- 材料
RE_YT = re.compile(r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})")


def kind_of(url):
    u = (url or "").lower()
    if RE_YT.search(url or ""):
        return "youtube"
    if "twitter.com/" in u or "x.com/" in u:
        return "x"
    return "link"


def thumb_of(url):
    m = RE_YT.search(url or "")
    return "https://img.youtube.com/vi/%s/hqdefault.jpg" % m.group(1) if m else None


# ---------------------------------------------------------------- 関所：事実
# sekisho-jijitsu-shutten：出典の取れない断定は書かせない。
# 材料（題名・チャンネル名・店主のひとこと・URL）に無い事実を書いていたら落とす。
DANTEI = ["原曲", "オリジナル", "代表曲", "カバー", "初の", "世界初", "史上初",
          "受賞", "グラミー", "ヒット曲", "大ヒット", "million", "枚売れ", "万枚"]
RE_YEAR = re.compile(r"(1[89]\d\d|20\d\d)\s*年?")
RE_LATIN = re.compile(r"[A-Za-z][A-Za-z'\-]{2,}")


def fact_gate(copy, material):
    """材料に無い断定を見つけたら理由を返す。無ければ None。"""
    c = copy or ""
    m = (material or "").lower()
    for w in DANTEI:
        if w in c and w.lower() not in m:
            return "材料に無い断定「%s」（関所：出典の取れない断定は書かない）" % w
    for y in RE_YEAR.findall(c):
        if y not in (material or ""):
            return "材料に無い年号「%s」（関所：出典の取れない断定は書かない）" % y
    for w in RE_LATIN.findall(c):
        if w.lower() not in m:
            return "材料に無い固有名「%s」（関所：見ていないものを想像で書かない）" % w
    return None


# ---------------------------------------------------------------- コピーを書く
# ★型（ボンジョビおじさん構文）の本文は naoshi.PROMPT が正本。ここで書き直さない。
#   「いま載っている一言」の枠を「店主の方向性」に読み替えるだけ。
PROMPT = naoshi.PROMPT.replace(
    "いま載っている一言：%(copy)s",
    "店主が投げるときに書いた方向性：%(copy)s\n"
    "　（これは温度の指定であって、事実ではありません。ここに書かれていない事実を足さないこと）")


def write_copy(title, direction, url, diag):
    """1行のコピーを書く。書けなければ (None, 理由)。"""
    text, why = _ask(PROMPT, title, direction, url, diag)
    return text, (None if text else (why or "コピーが書けなかった"))


# ★題名。YouTubeから来る題名は英語の原題のままのことが多い。
#   nippou.judge() は「題名が英語の原題のまま」を落とす（鬼監督5.『人を動かさない題名』）。
#   だから**落として捨てるのではなく、日本語の題名を書く。**原題は note に控えて残す。
PROMPT_TITLE = """あなたは「ごきげん補給所」の棚に並べるカードの題名を付ける編集者です。

下の動画・投稿に、**日本語の題名**を1つ付けてください。

【守ること】
・15〜30文字。短いほど強い。
・原題をそのまま訳しただけにしない。何が起きているかが分かる日本語にする。
・「！」「!」を使わない。
・「〜しよう」「必見」「話題」など、呼びかけ・煽り・他人の反応を書かない。
・**材料に書かれていないことを足さない。**年号・地名・人物名・受賞・数字を、
　材料に無いのに書いたら失格です。
・演者の名前が材料にあるなら、そのまま使ってよい。無いなら書かない。

【材料】ここに書いてあることだけが、あなたが知っている全部です。
原題：%(title)s
出どころ：%(url)s
店主が投げるときに書いた方向性：%(copy)s

【出し方】
題名だけを1行で出す。前置き・説明・かぎかっこ・箇条書きを付けない。
材料が薄すぎて書けない場合は、無理に書かず
NO_MATERIAL とだけ出す。**薄いまま無理に書くより、NO_MATERIAL の方が正解です。**
"""


def _ask(prompt, title, direction, url, diag):
    """★書き手は naoshi の口をそのまま使う（claude -p → 控えの外部の口）。
    型（PROMPT）だけ差し替える。書き手を2つ持たない。"""
    saved = naoshi.PROMPT
    try:
        naoshi.PROMPT = prompt
        text, why = naoshi.ask_claude(title, direction or "（指定なし）", url, diag)
        if not text:
            text, why2 = naoshi.ask_fallback(title, direction or "（指定なし）", url, diag)
            # ★両方の理由を残す。片方で上書きすると「なぜ書けなかったか」が消える。
            why = "claude=%s ／ 控え=%s" % (why, why2) if why2 else why
    finally:
        naoshi.PROMPT = saved
    return (naoshi.clean(text) if text else None), why


def write_title(title, direction, url, diag):
    """日本語の題名を書く。書けなければ (None, 理由)。"""
    text, why = _ask(PROMPT_TITLE, title, direction, url, diag)
    return text, (None if text else (why or "題名が書けなかった"))


_YT_IN_TEXT = re.compile(r"(?:youtu\.be/|v=|/embed/|/shorts/)([A-Za-z0-9_-]{11})")


def gates(title, copy, material, diag, artist=""):
    """入れる前に必ず通す門。落ちた理由をそのまま返す。

    ★1140番（2026-09-25）：ここに【完成の門】を足した。
      全26,400曲を機械で見たら、**再生できる動画が1本も無い曲が2,383件**棚に入っていた。
      入ってから隠すのではなく、入口で止める。判定の4つは表に出す条件と同じ
      （再生できる動画／サムネ／曲名・アーティスト名／コピー）。動画が生きているかは
      **oEmbedで実測**する。「IDが入っている」は証拠にならない。
      弾いた数は status/1140_kanmon.jsonl に1件1行。
      python3 tools/1140_kanmon.py --tally で通した数・弾いた数が出る。
    """
    try:
        import importlib
        _k = importlib.import_module("1140_kanmon")
        m = _YT_IN_TEXT.search(material or "")
        if m:
            why = _k.judge(title=title, artist=artist or "（棚の主）", youtube_id=m.group(1),
                           copy=copy, label="nagekomi_shelf")
            if why:
                return "完成の門で落ちた：%s" % why
    except Exception as e:  # noqa: BLE001
        diag.append("1140番の門が呼べなかった：%r（このぶんは門を通っていない＝赤）" % (e,))

    why = nippou.judge(title, copy)
    if why:
        return "水道水の判定で落ちた：%s" % why
    hits = oni_gate.judge(copy, label="nagekomi_shelf")
    if hits:
        return "鬼監督で落ちた：%s（%s）" % (hits[0]["name"], hits[0]["hit"])
    why = fact_gate(copy, material)
    if why:
        return why
    return None


# ---------------------------------------------------------------- 棚へ入れる
def find_stock_by_ref(url, key, ref):
    st, rows = tana._req(url, key, "/rest/v1/admin_stock?select=id,title&ref=eq.%s&limit=1"
                         % urllib.parse.quote(ref, safe=""))
    return rows[0] if rows else None


def next_position(url, key, shelf_id):
    st, rows = tana._req(
        url, key,
        "/rest/v1/admin_shelf_picks?select=position&shelf_id=eq.%s&order=position.desc&limit=1"
        % urllib.parse.quote(shelf_id, safe=""))
    return (rows[0]["position"] if rows else -1) + 1


def insert_stock(url, key, row):
    st, rows = tana._req(url, key, "/rest/v1/admin_stock", method="POST", body=row,
                         prefer="return=representation")
    if not rows:
        raise RuntimeError("admin_stock の INSERT が行を返さなかった（HTTP %s）" % st)
    return rows[0]


# ---------------------------------------------------------------- ★1164番【関連4つ】
# たまごさん（原文）「関連もちゃんと4つ付けて完了にしてくれると助かる。」
#                   「完了の条件に『関連4つ以上』を入れる。足りないものは完了にしない。」
#
# ■ 決め（なぜこの形か）
#   ・**関連は数えられるものだけを数える。**同じ棚に並ぶ他のカード（＝棚のページで
#     実際に隣に出るもの）を関連として控える。想像で「関連っぽいもの」を作らない。
#   ・**4つ取れなかったら完了にしない。**足りない数と理由をそのまま控える
#     （「関連が2つしか取れていません（4つ必要）」）。黙って完了にしない。
#   ・**数が取れなかったときは null。**0件と書かない（0件と「数えられなかった」は別物）。
KANREN_HITSUYOU = 4


def kanren_find(url, key, shelf_ids, stock_id, want=KANREN_HITSUYOU):
    """同じ棚に並んでいる他のカードを、関連として最大 want 件ひろう。
    返すのは (関連のリスト, 理由1行)。数えられなければ (None, 理由)。"""
    got, seen = [], {stock_id}
    for sid in [s for s in shelf_ids if s]:
        try:
            st, rows = tana._req(
                url, key,
                "/rest/v1/admin_shelf_picks?select=stock_id,position,admin_stock(id,title)"
                "&shelf_id=eq.%s&order=position.asc&limit=60"
                % urllib.parse.quote(sid, safe=""))
        except Exception as e:
            return None, "関連の数が取れませんでした（%s）" % type(e).__name__
        for row in (rows or []):
            s = row.get("admin_stock") or {}
            key_id = s.get("id") or row.get("stock_id")
            if not key_id or key_id in seen:
                continue
            seen.add(key_id)
            got.append({"id": key_id, "title": str(s.get("title") or "")[:80]})
            if len(got) >= want:
                return got, ""
    if len(got) < want:
        return got, ("関連が%d件しか取れていません（%d件必要）。棚の中身がまだ少ないか、"
                     "関連にできるカードが足りません" % (len(got), want))
    return got, ""


# ---------------------------------------------------------------- ★1164番【本人だけ紐づける】
# たまごさん（原文）「楽曲を入れたらアーティストページに登録されるのは当たり前として、
#                     そこまで連携して動く仕組みに。」
#
# ★ここは関所 sekisho-artist-song の門0をそのまま持ってくる。
#   「名前の字が一致しただけでは本人の証明にならない」（akiko × AKIKO の事故）。
#   だから **証拠が1つも無いものは紐づけない。**保留にして理由を控える。
#   証拠として認めるのは、この場で機械が持っているものだけ：
#     ・YouTube の**チャンネルID**が、そのアーティストの棚に控えてあるチャンネルIDと一致
#     ・棚の側に公式チャンネル／公式サイトが控えてあり、その動画がそこの持ち物
#   ★チャンネル名と棚の名前が一致している、は証拠にしない（それが akiko の事故）。
def artist_shoko(rec, shelf):
    """本人の証拠を1つ以上持っているか。(証拠の文, 理由) を返す。証拠が無ければ (None, 理由)。"""
    ch_id = str(rec.get("channelId") or "").strip()
    shelf_ch = str((shelf or {}).get("channelId") or "").strip()
    if ch_id and shelf_ch and ch_id == shelf_ch:
        return ("公式チャンネルID一致（%s）" % ch_id), ""
    ref = str(rec.get("url") or "")
    ch_name = str(rec.get("channel") or "").strip()
    shelf_name = str((shelf or {}).get("title") or "").strip()
    if ch_name and shelf_name and ch_name == shelf_name:
        # ★★ここが akiko × AKIKO。字が一致しているだけ。証拠にしない。
        return None, ("チャンネル名と棚の名前が一致しているだけです（本人の証拠になりません）。"
                      "公式チャンネルIDか公式サイトの案内が要ります")
    if not ch_name:
        return None, "チャンネル名が取れていないので、本人か判定できません"
    return None, ("本人を指す証拠が1つもありません（チャンネル「%s」／%s）"
                  % (ch_name[:30], ref[:40] or "URLなし"))


def artist_link(url, key, stock_id, rec, shelf, res):
    """曲を入れたとき、アーティストの棚にも紐づける。★証拠が無ければ紐づけずに保留。
    返すのは (紐づけたか, 控える1行)。"""
    shoko, why = artist_shoko(rec, shelf)
    if not shoko:
        res["diag"].append("アーティスト紐づけは保留：%s" % why)
        return False, {"tsunaida": False, "why": why}
    if not (shelf or {}).get("artistId"):
        # ★棚の側にアーティストのidが控えられていない＝紐づけ先が無い。作らずに保留。
        #   （関所：判定できないものは載せない側に倒す。勝手に新しい人を作らない）
        why = "この棚にアーティストのidが控えられていません（紐づけ先が無いので保留）"
        res["diag"].append("アーティスト紐づけは保留：%s" % why)
        return False, {"tsunaida": False, "why": why, "shoko": shoko}
    try:
        tana._req(url, key, "/rest/v1/admin_stock?id=eq.%s"
                  % urllib.parse.quote(stock_id, safe=""),
                  method="PATCH", body={"detected_artist_id": shelf.get("artistId")})
    except Exception as e:
        res["diag"].append("アーティスト紐づけに失敗：%s" % type(e).__name__)
        return False, {"tsunaida": False, "why": "紐づけに失敗（%s）" % type(e).__name__}
    return True, {"tsunaida": True, "shoko": shoko, "artistId": shelf.get("artistId")}


def insert_pick(url, key, shelf_id, stock_id):
    body = {"shelf_id": shelf_id, "stock_id": stock_id,
            "position": next_position(url, key, shelf_id),
            "status": PICK_STATUS, "pinned": False}
    st, rows = tana._req(url, key, "/rest/v1/admin_shelf_picks", method="POST", body=body,
                         prefer="return=representation")
    if not rows:
        raise RuntimeError("admin_shelf_picks の INSERT が行を返さなかった（HTTP %s）" % st)
    return rows[0]


# ---------------------------------------------------------------- 本体
def run(force=False, dry=False, only=None, bin_no="1039", teuchi=None):
    """teuchi＝`--only` の1件に限り、人（編集者）が書いた題名・ひとことを持ち込む口。
    ★書き手（claude -p／控えの外部の口）が両方止まっている日に、道そのものを実測するための穴。
      持ち込んでも**関所は同じように通す。**素通りさせない。毎日の便では使わない。"""
    t0 = time.time()
    res = {
        "ranAt": now().strftime("%Y-%m-%d %H:%M"), "bin": bin_no, "dry": bool(dry),
        # ★1043番：箱の役目は「あとで実装できるように放り込んでおく」こと。だから箱の中身は
        #   どんな形でも受ける。足りないものは「◯◯が未定」と印をつけて置くだけ。
        #     mitei … 行き先の棚が未定（あとで棚を決めれば入る）
        #     machi … 文が未定（題名・ひとことが書けていない。あとから埋められる）
        #     dame  … 本当に何も無い＝URLもひとことも両方空。これだけが「入れられない」
        "diag": [], "red": [], "ireta": [], "mitei": [], "machi": [], "dame": [], "skip": [],
        "seen": 0, "ranCount": 1, "iretaCount": 0, "totalYen": 0.0,
    }
    url, key, keyname, where = tana.keys(res["diag"])
    if not url:
        res["red"].append("Supabaseの鍵が見つからない：%s" % where)
        return res
    res["keyName"] = keyname

    shelves = shelf_index()
    if not shelves:
        res["red"].append("棚の名簿（status/public/tana_ichiran.json）が読めない。"
                          "先に `python3 tools/tana.py --list` を走らせること")
        return res
    res["diag"].append("棚の名簿 %d件" % len(shelves))

    done = already_done_ids()
    rows = read_jsonl(LEDGER)
    if only:
        rows = [r for r in rows if r.get("id") == only]
    todo = [r for r in rows if r.get("id") and r["id"] not in done]
    res["seen"] = len(todo)
    res["diag"].append("台帳 %d行 / うち未処理 %d件" % (len(rows), len(todo)))

    for r in todo[:MAX_PER_RUN]:
        if time.time() - t0 > DEADLINE_SEC:
            res["diag"].append("持ち時間を使い切ったので残りは次の回へ")
            break
        nid = r.get("id")
        ref = (r.get("url") or "").strip()
        title = (r.get("title") or "").strip()
        sid = (r.get("shelfId") or "").strip()

        memo = (r.get("memo") or "").strip()

        # ★★1043番：ここで弾かない。弾いていいのは「URLもひとことも両方空」のときだけ。
        if not ref and not memo:
            res["dame"].append({"id": nid, "url": "", "title": title, "memo": "",
                                "why": "URLもひとことも入っていません"})
            continue

        # ★棚は未定でよい。未定のまま置いて、あとで棚を決められるようにする（弾かない）。
        shelf, hint = resolve_shelf(sid, r.get("shelf"), shelves)
        kari = None
        if not shelf:
            # ★★1177番【棚の推測】棚が空なら、機械が中身を読んで**仮の棚**を付ける。
            #   たまごさん「棚の指定は任意にしたい」→ 空のまま止めるのをやめる。
            #   ★合う棚が無ければ「新しい棚が要る」と出す。**勝手に新設しない。**
            g = suiron.guess_row(r, list(shelves.values()))
            if g.get("ok") and g.get("shelfId") in shelves:
                shelf = shelves[g["shelfId"]]
                kari = g
                hint = "%s：%s" % (nid, g["why"])
            else:
                res["mitei"].append({
                    "id": nid, "url": ref, "title": title,
                    "memo": memo, "shelf": r.get("shelf"),
                    "why": g.get("why") or hint,
                    "candidates": g.get("candidates") or [],
                })
                continue
        sid = shelf["id"]          # ★名簿の id に寄せる（2か所に名簿を持たない）
        if hint:
            res["diag"].append("%s：%s" % (nid, hint))

        # ★URLが無い（ひとことだけ）／題名が取れていないものは「文が未定」として置く。
        #   あとで人が題名を書けば入る。捨てない。
        if not ref:
            res["machi"].append({"id": nid, "url": "", "title": title, "shelf": shelf["title"],
                                 "why": "ひとことだけ届いています（URLが未定）"})
            continue
        if not title:
            res["machi"].append({"id": nid, "url": ref, "shelf": shelf["title"],
                                 "why": "題名が未定（URLは入っています。あとで埋められます）"})
            continue
        genmei = title          # 原題（YouTube/Xから取れたそのまま）
        material = " / ".join(x for x in [title, r.get("channel"), r.get("memo"), ref] if x)

        # ★題名。原題が英語のままだと nippou.judge が落とす（鬼監督5.『人を動かさない題名』）。
        #   落として捨てるのではなく、日本語の題名を書く。原題は note に控えて残す。
        te = bool(teuchi and only and nid == only)
        if te:
            title = (teuchi.get("title") or title).strip()
            copy = (teuchi.get("whisper") or "").strip()
            why = gates(title, copy, material, res["diag"]) or fact_gate(title, material)
            if why:
                res["machi"].append({"id": nid, "title": title, "shelf": shelf["title"],
                                     "copy": copy, "why": "手書きが関所で落ちた：%s" % why})
                continue
            res["diag"].append("★この1件は人（編集者）が書いた題名・ひとことを使った（関所は通した）")
        elif nippou.judge(title, "ダミー。ここでは題名だけを見ている。") in (
                "題名が英語の原題のまま", "題名がURLのまま", "題名が空"):
            newt, why = write_title(genmei, r.get("memo"), ref, res["diag"])
            if not newt:
                # ★1043番：書き手が止まっているだけ。中身は届いている。捨てない。
                res["machi"].append({
                    "id": nid, "title": genmei, "shelf": shelf["title"],
                    "why": "題名が未定（書き手が止まっています。あとで埋められます）",
                    "kikai": why})
                continue
            why = fact_gate(newt, material)
            if why:
                res["machi"].append({"id": nid, "title": genmei, "shelf": shelf["title"],
                                     "newTitle": newt,
                                     "why": "題名が未定（関所で書き直し：%s）" % why})
                continue
            title = newt

        if not te:
            copy, why = write_copy(genmei, r.get("memo"), ref, res["diag"])
            if not copy:
                res["machi"].append({
                    "id": nid, "title": title, "shelf": shelf["title"],
                    "why": "ひとことが未定（書き手が止まっています。あとで埋められます）",
                    "kikai": why})
                continue
            why = gates(title, copy, material, res["diag"])
            if why:
                res["machi"].append({"id": nid, "title": title, "shelf": shelf["title"],
                                     "copy": copy,
                                     "why": "ひとことが未定（関所で書き直し：%s）" % why})
                continue

        if dry:
            res["ireta"].append({"id": nid, "title": title, "genmei": genmei, "copy": copy,
                                 "shelfId": sid, "shelf": shelf["title"], "dry": True})
            continue

        hoka = []          # ★2つ目以降の棚（前の回の値を持ち越さない）
        try:
            existing = find_stock_by_ref(url, key, ref)
            if existing:
                stock_id, made_stock = existing["id"], False
            else:
                stock = insert_stock(url, key, {
                    "kind": kind_of(ref), "ref": ref, "title": title,
                    "whisper": copy, "thumbnail_url": thumb_of(ref),
                    # ★原題は消さずに控える（店主が画面で見比べられるように）
                    "note": ("原題: %s" % genmei) if title != genmei else None,
                    # ★detected_artist_id は書かない（関所 sekisho-artist-song）。
                    #   字が一致しただけで別人の棚に入る事故を、紐づけないことで防ぐ。
                })
                stock_id, made_stock = stock["id"], True
            try:
                pick = insert_pick(url, key, sid, stock_id)
                # ★1164番：たまごさんが箱でポチポチ押した棚の**全部**に結ぶ。
                #   1つ目（sid）は上で結んだので、2つ目から。
                #   ★1つ失敗しても残りは結ぶ（全部おじゃんにしない）。失敗は控える。
                hoka = []
                for extra in (r.get("shelves") or [])[1:]:
                    esid = (extra.get("id") or "").strip() if isinstance(extra, dict) else ""
                    ename = (extra.get("title") or "") if isinstance(extra, dict) else str(extra)
                    esh, _h = resolve_shelf(esid, ename, shelves)
                    if not esh or esh["id"] == sid:
                        if not esh:
                            res["diag"].append("%s：2つ目の棚「%s」が名簿に無い（結んでいない）"
                                               % (nid, str(ename)[:20]))
                        continue
                    try:
                        p2 = insert_pick(url, key, esh["id"], stock_id)
                        hoka.append({"shelfId": esh["id"], "shelf": esh["title"],
                                     "pickId": p2["id"], "world": esh.get("world") or ""})
                    except Exception as e2:
                        res["diag"].append("%s：棚「%s」に結べなかった（%s）"
                                           % (nid, esh["title"], type(e2).__name__))
            except Exception:
                # ★結び目が作れなかったら、さっき作ったカードも取り消す。
                #   棚に繋がらないカードを倉庫に置き去りにしない（＝棚のデータを汚さない）。
                if made_stock:
                    try:
                        tana._req(url, key, "/rest/v1/admin_stock?id=eq.%s"
                                  % urllib.parse.quote(stock_id, safe=""), method="DELETE")
                        res["diag"].append("結び目が作れなかったので、作ったカードを取り消した")
                    except Exception as e2:
                        res["red"].append("★カードが倉庫に残った（stock %s）：%s"
                                          % (stock_id, type(e2).__name__))
                raise
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            res["red"].append("棚へ入れられなかった（%s）HTTP %d %s" % (title[:30], e.code, body))
            continue
        except Exception as e:
            res["red"].append("棚へ入れられなかった（%s）%s: %s" % (title[:30], type(e).__name__, e))
            continue

        # ★1164番【関連4つ以上で完了】足りないものは完了にしない（たまごさんの指示）
        zenbu_sid = [sid] + [h["shelfId"] for h in hoka]
        kanren, kanren_why = kanren_find(url, key, zenbu_sid, stock_id)
        kanren_ok = bool(kanren) and len(kanren) >= KANREN_HITSUYOU
        if not kanren_ok:
            res["diag"].append("%s：関連が足りないので完了にしない（%s）"
                               % (nid, kanren_why or "数が取れません"))

        # ★1164番【曲はアーティストの棚にも】ただし本人の証拠があるときだけ（関所 門0）
        tsunaida, artist_rec = artist_link(url, key, stock_id, r, shelf, res)

        # ★★1164番で見つけた取りこぼし（2026-09-26 実測）：
        #   受付一覧（tools/nagekomi_list.py）は控えを **"id"** で引いていたのに、
        #   ここは "nagekomiId" しか書いていなかった。＝棚に入れても一覧は永久に「まだ」。
        #   （1152_ireru.py は気づいて両方書いていた。こちらだけ直っていなかった）
        #   両方書く。読む側も両方見るようにした。
        rec = {"bin": bin_no, "at": now().strftime("%Y-%m-%d %H:%M"),
               "id": nid, "nagekomiId": nid,
               "stockId": stock_id, "madeStock": made_stock, "pickId": pick["id"],
               "shelfId": sid, "shelf": shelf["title"], "ref": ref, "title": title,
               "genmei": genmei, "whisper": copy, "pickStatus": PICK_STATUS,
               # ★複数の行き先（2つ目から）。受付一覧に「棚2つ」と出る
               "hokaShelves": hoka,
               # ★Before/After を控える（たまごさんが見比べられるように）
               "copyBefore": str(r.get("titleRaw") or genmei or "")[:400],
               "copyAfter": copy,
               "titleAfter": title,
               "copySame": bool(copy and copy.strip() == str(r.get("titleRaw") or "").strip()),
               # ★関連。4つ未満なら完了にしない
               "kanren": kanren,
               "kanrenCount": (len(kanren) if kanren is not None else None),
               "kanrenOk": kanren_ok,
               "kanrenWhy": kanren_why,
               # ★アーティスト紐づけ（証拠が無ければ保留のまま控える）
               "artist": artist_rec,
               # ★棚を機械が推測したものは「仮」と控える（受付一覧に「仮」と出る）
               "kari": bool(kari),
               "kariWhy": (kari or {}).get("why") or "",
               "world": shelf.get("world") or ""}
        append_jsonl(IRETA, rec)
        res["ireta"].append(rec)
        log("入れた %s → %s（stock %s / pick %s）" % (title[:40], shelf["title"], stock_id, pick["id"]))

    res["iretaCount"] = len(res["ireta"])
    res["miteiCount"] = len(res["mitei"])
    res["machiCount"] = len(res["machi"])
    res["dameCount"] = len(res["dame"])
    # ★1043番：「棚が未定」「文が未定」は**正常**。赤にしない（弾かない）。
    #   赤にするのは「全部そろっているのに1件も入らなかった」ときだけ。
    sorotta = res["seen"] - res["miteiCount"] - res["machiCount"] - res["dameCount"]
    if sorotta > 0 and res["iretaCount"] == 0:
        res["red"].append("そろっているのに1件も入らなかった（%d件）" % sorotta)
    if res["dame"]:
        res["diag"].append("URLもひとことも空＝%d件（これだけが入れられない）" % res["dameCount"])
    res["ok"] = not res["red"]
    return res


# ---------------------------------------------------------------- 棚を1本新設する
def shinsetsu(world, title, subtitle="", bin_no="1177", dry=False):
    """★棚を1本だけ新設する。名指しで頼まれたときだけ通る口（機械の推測では新設しない）。

    たまごさん（2026-09-25・原文）:
      「食べ物の『食』の中に『スープ』っていう棚を作って、これを入れておいてください。」

    ・同じ world に同じ題名の棚が既にあれば**作らない**（重複した棚を増やさない）。
    ・作った棚は status/nagekomi_ireta.jsonl に控える。`--modoshi <便番号>` で消せる。
    ・position は その world の最後（max+1）。既にある棚の並びを1つも動かさない。
    """
    res = {"ranAt": now().strftime("%Y-%m-%d %H:%M"), "bin": bin_no, "dry": bool(dry),
           "diag": [], "red": [], "totalYen": 0.0}
    world = (world or "").strip()
    title = (title or "").strip()
    if not world or not title:
        res["red"].append("world と title は要ります")
        return res
    url, key, keyname, where = tana.keys(res["diag"])
    if not url:
        res["red"].append("Supabaseの鍵が見つからない：%s" % where)
        return res
    try:
        st, same = tana._req(url, key, "/rest/v1/admin_shelves?select=*&world=eq.%s&title=eq.%s"
                             % (urllib.parse.quote(world, safe=""),
                                urllib.parse.quote(title, safe="")))
        if same:
            res["shelf"] = same[0]
            res["already"] = True
            res["diag"].append("同じ棚が既にありました（作っていません）")
            res["ok"] = True
            return res
        st, rows = tana._req(url, key, "/rest/v1/admin_shelves?select=position&world=eq.%s"
                                       "&order=position.desc&limit=1"
                             % urllib.parse.quote(world, safe=""))
        pos = int((rows[0].get("position") if rows else 0) or 0) + 1
        if dry:
            res["ok"] = True
            res["shelf"] = {"world": world, "title": title, "subtitle": subtitle,
                            "position": pos, "dry": True}
            return res
        st, made = tana._req(url, key, "/rest/v1/admin_shelves", method="POST",
                             body={"world": world, "title": title,
                                   "subtitle": (subtitle or None), "position": pos},
                             prefer="return=representation")
        row = made[0] if isinstance(made, list) and made else made
        res["shelf"] = row
        append_jsonl(IRETA, {"bin": bin_no, "at": now().strftime("%Y-%m-%d %H:%M"),
                             "shinsetsuShelfId": row.get("id"), "shelf": title,
                             "world": world, "subtitle": subtitle})
        log("棚を新設 %s / %s（%s）" % (world, title, row.get("id")))
        res["ok"] = True
        # 名簿を作り直す（棚が増えたら推測の語彙もここで増える）
        try:
            res["ichiran"] = tana.shelf_list()
        except Exception as e:
            res["diag"].append("名簿の作り直しに失敗: %s" % type(e).__name__)
    except urllib.error.HTTPError as e:
        res["red"].append("棚を作れなかった HTTP %d %s"
                          % (e.code, e.read().decode("utf-8", "replace")[:200]))
    except Exception as e:
        res["red"].append("棚を作れなかった %s: %s" % (type(e).__name__, e))
    res["ok"] = not res["red"]
    return res


# ---------------------------------------------------------------- 戻す
def modoshi(bin_no, dry=False):
    """★その便で入れた分**だけ**を消す。自分が作った行以外は1文字も触らない。"""
    res = {"ranAt": now().strftime("%Y-%m-%d %H:%M"), "bin": bin_no, "dry": bool(dry),
           "diag": [], "red": [], "keshita": [], "totalYen": 0.0}
    url, key, keyname, where = tana.keys(res["diag"])
    if not url:
        res["red"].append("Supabaseの鍵が見つからない：%s" % where)
        return res

    rows = [r for r in read_jsonl(IRETA) if str(r.get("bin")) == str(bin_no) and not r.get("modoshiAt")]
    res["diag"].append("控え %d件" % len(rows))
    if not rows:
        res["red"].append("その便（%s）で入れた控えが1件も無い" % bin_no)
        return res

    for r in rows:
        # ★新設した棚の控え（pickIdを持たない）。棚に何か載っていたら消さない。
        if r.get("shinsetsuShelfId"):
            ssid = r["shinsetsuShelfId"]
            try:
                st, used = tana._req(url, key, "/rest/v1/admin_shelf_picks?select=id&shelf_id=eq.%s"
                                     "&limit=1" % urllib.parse.quote(ssid, safe=""))
                if used:
                    res["diag"].append("棚「%s」にはカードが載っているので消さない" % r.get("shelf"))
                    continue
                if not dry:
                    tana._req(url, key, "/rest/v1/admin_shelves?id=eq.%s"
                              % urllib.parse.quote(ssid, safe=""), method="DELETE")
                    r["modoshiAt"] = now().strftime("%Y-%m-%d %H:%M")
                    append_jsonl(IRETA, r)
                res["keshita"].append({"shelf": r.get("shelf"), "shelfId": ssid, "kind": "棚"})
            except Exception as e:
                res["red"].append("棚を戻せなかった（%s）%s" % (r.get("shelf"), type(e).__name__))
            continue
        try:
            # ★消す前に、その行が自分の入れたものと一致するか確かめる。違えば触らない。
            st, got = tana._req(url, key, "/rest/v1/admin_shelf_picks?select=*&id=eq.%s"
                                % urllib.parse.quote(r["pickId"], safe=""))
            if not got:
                res["diag"].append("pick %s は既に無い" % r["pickId"][:8])
            elif got[0].get("stock_id") != r["stockId"] or got[0].get("shelf_id") != r["shelfId"]:
                res["red"].append("pick %s の中身が控えと違う。触らない" % r["pickId"][:8])
                continue
            elif not dry:
                tana._req(url, key, "/rest/v1/admin_shelf_picks?id=eq.%s"
                          % urllib.parse.quote(r["pickId"], safe=""), method="DELETE")

            if r.get("madeStock"):
                st, got = tana._req(url, key, "/rest/v1/admin_stock?select=id,ref&id=eq.%s"
                                    % urllib.parse.quote(r["stockId"], safe=""))
                if got and got[0].get("ref") != r["ref"]:
                    res["red"].append("stock %s の中身が控えと違う。触らない" % r["stockId"][:8])
                    continue
                # 他の棚からも参照されていたら、カードは残す（他人の棚を壊さない）
                st, other = tana._req(
                    url, key, "/rest/v1/admin_shelf_picks?select=id&stock_id=eq.%s&limit=1"
                    % urllib.parse.quote(r["stockId"], safe=""))
                if other:
                    res["diag"].append("stock %s は他の棚でも使われているので残す" % r["stockId"][:8])
                elif got and not dry:
                    tana._req(url, key, "/rest/v1/admin_stock?id=eq.%s"
                              % urllib.parse.quote(r["stockId"], safe=""), method="DELETE")
            res["keshita"].append({"title": r.get("title"), "shelf": r.get("shelf"),
                                   "stockId": r.get("stockId"), "pickId": r.get("pickId")})
            if not dry:
                r["modoshiAt"] = now().strftime("%Y-%m-%d %H:%M")
                append_jsonl(IRETA, r)
        except urllib.error.HTTPError as e:
            res["red"].append("戻せなかった（%s）HTTP %d" % ((r.get("title") or "")[:30], e.code))
        except Exception as e:
            res["red"].append("戻せなかった（%s）%s" % ((r.get("title") or "")[:30], type(e).__name__))
    res["ok"] = not res["red"]
    return res


# ---------------------------------------------------------------- 1日1回の口
def daily(force=False):
    """5分便から呼ばれる入口。中で1日1回に間引く。★日が変わった最初の便で走る＝深夜0時。"""
    today = now().strftime("%Y-%m-%d")
    if os.path.exists(FORCE):
        force = True
        try:
            os.remove(FORCE)
        except OSError:
            pass
    if not force:
        try:
            if io.open(GATE, encoding="utf-8").read().strip()[:10] == today:
                return {"skipped": "今日はもう走りました", "ranCount": 0}
        except OSError:
            pass
    if not lock_take():
        return {"skipped": "前の回がまだ握っています", "ranCount": 0}
    try:
        res = run()
        os.makedirs(PUBLIC, exist_ok=True)
        with io.open(OUT_JSON, "w", encoding="utf-8") as f:
            f.write(json.dumps(res, ensure_ascii=False, indent=1))
        # ★鍵が取れなかった／棚の名簿が無い日はゲートを押さない。
        #   「走ったことにして黙る」のが一番まずい（1018番と同じ事故の形）。
        if res.get("keyName"):
            with io.open(GATE, "w", encoding="utf-8") as f:
                f.write(today)
        return res
    finally:
        lock_free()


def shirabe(ref, souji=False):
    """★倉庫（admin_stock）にそのURLの行が在るか見る。souji=True なら
    **結び目が1本も無い行だけ**を消す（棚に繋がっているカードは絶対に触らない）。"""
    res = {"ranAt": now().strftime("%Y-%m-%d %H:%M"), "diag": [], "red": [],
           "rows": [], "keshita": [], "totalYen": 0.0}
    url, key, keyname, where = tana.keys(res["diag"])
    if not url:
        res["red"].append("Supabaseの鍵が見つからない：%s" % where)
        return res
    st, rows = tana._req(url, key, "/rest/v1/admin_stock?select=id,ref,title,whisper,note,created_at"
                         "&ref=eq.%s&order=created_at.desc" % urllib.parse.quote(ref, safe=""))
    for r0 in rows:
        st2, picks = tana._req(url, key, "/rest/v1/admin_shelf_picks?select=id,shelf_id,status"
                               "&stock_id=eq.%s" % urllib.parse.quote(r0["id"], safe=""))
        r0["picks"] = picks
        res["rows"].append(r0)
        if souji and not picks:
            try:
                tana._req(url, key, "/rest/v1/admin_stock?id=eq.%s"
                          % urllib.parse.quote(r0["id"], safe=""), method="DELETE")
                res["keshita"].append(r0["id"])
            except Exception as e:
                res["red"].append("消せなかった %s：%s" % (r0["id"][:8], type(e).__name__))
    res["ok"] = not res["red"]
    return res


def kagi_shirabe(shelf_id):
    """★いまの鍵で「どこまで書けるか」を実測する。当てずっぽうで INSERT しないため。

    自分で作った捨て行だけを使い、通っても通らなくても**必ず消してから帰る。**
    他人の行は1文字も触らない。ref は誰とも当たらない形にする。
    """
    res = {"ranAt": now().strftime("%Y-%m-%d %H:%M"), "diag": [], "red": [],
           "dekita": {}, "nokori": [], "totalYen": 0.0}
    url, key, keyname, where = tana.keys(res["diag"])
    if not url:
        res["red"].append("Supabaseの鍵が見つからない：%s" % where)
        return res
    res["keyName"] = keyname
    ref = "tamago://kagi-shirabe/%s" % now().strftime("%Y%m%d-%H%M%S")
    stock_id = pick_id = None
    try:
        try:
            row = insert_stock(url, key, {"kind": "link", "ref": ref,
                                          "title": "鍵の下見（すぐ消します）",
                                          "whisper": None, "thumbnail_url": None, "note": None})
            stock_id = row["id"]
            res["dekita"]["admin_stock INSERT"] = "通った"
        except urllib.error.HTTPError as e:
            res["dekita"]["admin_stock INSERT"] = "HTTP %d %s" % (
                e.code, e.read().decode("utf-8", "replace")[:120])
        if stock_id and shelf_id:
            try:
                pick_id = insert_pick(url, key, shelf_id, stock_id)["id"]
                res["dekita"]["admin_shelf_picks INSERT"] = "通った"
            except urllib.error.HTTPError as e:
                res["dekita"]["admin_shelf_picks INSERT"] = "HTTP %d %s" % (
                    e.code, e.read().decode("utf-8", "replace")[:120])
    finally:
        for path, rid in (("admin_shelf_picks", pick_id), ("admin_stock", stock_id)):
            if not rid:
                continue
            try:
                tana._req(url, key, "/rest/v1/%s?id=eq.%s"
                          % (path, urllib.parse.quote(rid, safe="")), method="DELETE")
                res["dekita"]["%s DELETE" % path] = "通った"
            except urllib.error.HTTPError as e:
                res["dekita"]["%s DELETE" % path] = "HTTP %d" % e.code
                res["nokori"].append("%s %s" % (path, rid))
                res["red"].append("★下見の行が消せずに残った：%s %s" % (path, rid))
    res["ok"] = not res["red"]
    return res


def run_job(payload):
    """工場側（gaibu_runner kind=tanaire）から呼ばれる入口。"""
    p = payload or {}
    if p.get("op") == "shinsetsu":
        out = shinsetsu(p.get("world") or "", p.get("title") or "",
                        p.get("subtitle") or "", bin_no=p.get("bin") or "1177",
                        dry=bool(p.get("dry")))
    elif p.get("op") == "kagi":
        out = kagi_shirabe(p.get("shelfId") or "")
    elif p.get("op") == "shirabe":
        out = shirabe(p.get("ref") or "", souji=bool(p.get("souji")))
    elif p.get("op") == "modoshi":
        out = modoshi(p.get("bin") or "1039", dry=bool(p.get("dry")))
    elif p.get("op") == "daily":
        out = daily(force=bool(p.get("force")))
    else:
        out = run(dry=bool(p.get("dry")), only=p.get("only"), bin_no=p.get("bin") or "1039",
                  teuchi=p.get("teuchi"))
    out.setdefault("totalYen", 0.0)
    out.setdefault("ok", not out.get("red"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--bin", default="1039")
    ap.add_argument("--modoshi")
    ap.add_argument("--show", action="store_true")
    # ★1155番：棚の新設を口から呼べるようにした（shinsetsu() は前からあったが
    #   CLIが無く、python -c の手打ちでしか叩けなかった＝次の人が再現できない）。
    ap.add_argument("--shinsetsu", help="棚を1本新設する題名（例 スープ）")
    ap.add_argument("--world", help="--shinsetsu の行き先の世界（例 food）")
    ap.add_argument("--subtitle", default="", help="--shinsetsu の副題（任意）")
    # ★1155番：書き手（claude -p／控えの外部の口）が両方止まっている日のための口。
    #   run() には前から teuchi= があったが CLI が無く、python -c の手打ちしか道が無かった。
    #   ★持ち込んでも関所は同じように通る（gates / fact_gate）。素通りはしない。
    ap.add_argument("--teuchi-title", help="--only の1件に、人が書いた題名を持ち込む")
    ap.add_argument("--teuchi-hitokoto", help="--only の1件に、人が書いたひとことを持ち込む")
    a = ap.parse_args()
    if a.shinsetsu:
        if not a.world:
            print("--shinsetsu には --world も要ります（例 --world food --shinsetsu スープ）")
            return 1
        r = shinsetsu(a.world, a.shinsetsu, a.subtitle, bin_no=a.bin, dry=a.dry)
        print(json.dumps(r, ensure_ascii=False, indent=1)[:4000])
        return 0 if r.get("ok") else 1
    if a.show:
        try:
            print(io.open(OUT_JSON, encoding="utf-8").read())
        except OSError:
            print("まだ1回も走っていません")
        return 0
    if a.modoshi:
        print(json.dumps(modoshi(a.modoshi, dry=a.dry), ensure_ascii=False, indent=1)[:4000])
        return 0
    if a.dry or a.only:
        teuchi = None
        if a.teuchi_title or a.teuchi_hitokoto:
            if not a.only:
                print("--teuchi-title / --teuchi-hitokoto は --only <id> と一緒にだけ使えます")
                return 1
            teuchi = {"title": a.teuchi_title or "", "whisper": a.teuchi_hitokoto or ""}
        print(json.dumps(run(dry=a.dry, only=a.only, bin_no=a.bin, teuchi=teuchi),
                         ensure_ascii=False, indent=1)[:6000])
        return 0
    print(json.dumps(daily(force=a.force), ensure_ascii=False, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
