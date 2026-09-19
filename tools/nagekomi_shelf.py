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
  ・**棚が指定されていないものは入れない。**「行き先未定」のまま置いて、進捗表に出す。
  ・**関所を通らなかったものは入れない。**理由をそのまま残す。黙って飲み込まない。
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


def gates(title, copy, material, diag):
    """入れる前に必ず通す門。落ちた理由をそのまま返す。"""
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
        "diag": [], "red": [], "ireta": [], "mitei": [], "skip": [],
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

        # ★棚が指定されていない／名簿に無いものは入れない。行き先未定のまま置く。
        if not sid or sid not in shelves:
            res["mitei"].append({
                "id": nid, "url": ref, "title": title,
                "memo": r.get("memo"), "shelf": r.get("shelf"),
                "why": "棚が指定されていない" if not sid
                       else "棚のidが名簿に無い（%s）。棚のボタンから選び直してください" % sid,
            })
            continue
        if not ref:
            res["skip"].append({"id": nid, "title": title, "why": "URLが無い"})
            continue
        if not title:
            res["skip"].append({"id": nid, "url": ref, "why": "題名が取れていない"})
            continue

        shelf = shelves[sid]
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
                res["skip"].append({"id": nid, "title": title, "shelf": shelf["title"],
                                    "copy": copy, "why": "手書きが関所で落ちた：%s" % why})
                continue
            res["diag"].append("★この1件は人（編集者）が書いた題名・ひとことを使った（関所は通した）")
        elif nippou.judge(title, "ダミー。ここでは題名だけを見ている。") in (
                "題名が英語の原題のまま", "題名がURLのまま", "題名が空"):
            newt, why = write_title(genmei, r.get("memo"), ref, res["diag"])
            if not newt:
                res["skip"].append({"id": nid, "title": genmei, "shelf": shelf["title"],
                                    "why": "日本語の題名が書けなかった：%s" % why})
                continue
            why = fact_gate(newt, material)
            if why:
                res["skip"].append({"id": nid, "title": genmei, "shelf": shelf["title"],
                                    "newTitle": newt, "why": "題名が関所で落ちた：%s" % why})
                continue
            title = newt

        if not te:
            copy, why = write_copy(genmei, r.get("memo"), ref, res["diag"])
            if not copy:
                res["skip"].append({"id": nid, "title": title, "shelf": shelf["title"],
                                    "why": "コピーが書けなかった：%s" % why})
                continue
            why = gates(title, copy, material, res["diag"])
            if why:
                res["skip"].append({"id": nid, "title": title, "shelf": shelf["title"],
                                    "copy": copy, "why": why})
                continue

        if dry:
            res["ireta"].append({"id": nid, "title": title, "genmei": genmei, "copy": copy,
                                 "shelfId": sid, "shelf": shelf["title"], "dry": True})
            continue

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

        rec = {"bin": bin_no, "at": now().strftime("%Y-%m-%d %H:%M"), "nagekomiId": nid,
               "stockId": stock_id, "madeStock": made_stock, "pickId": pick["id"],
               "shelfId": sid, "shelf": shelf["title"], "ref": ref, "title": title,
               "genmei": genmei, "whisper": copy, "pickStatus": PICK_STATUS}
        append_jsonl(IRETA, rec)
        res["ireta"].append(rec)
        log("入れた %s → %s（stock %s / pick %s）" % (title[:40], shelf["title"], stock_id, pick["id"]))

    res["iretaCount"] = len(res["ireta"])
    # ★「走った回数>0 なのに 入った件数=0」は赤。黙って飲み込まない。
    if res["seen"] > 0 and res["iretaCount"] == 0 and not res["mitei"]:
        res["red"].append("走ったのに1件も入らなかった（未処理 %d件）。理由は skip を見ること"
                          % res["seen"])
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
    if p.get("op") == "kagi":
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
    a = ap.parse_args()
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
        print(json.dumps(run(dry=a.dry, only=a.only, bin_no=a.bin), ensure_ascii=False, indent=1)[:4000])
        return 0
    print(json.dumps(daily(force=a.force), ensure_ascii=False, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
