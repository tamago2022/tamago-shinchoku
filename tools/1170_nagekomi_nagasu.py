#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1170番【投げ込み箱 → 自動投稿の箱】たまごさんはURLを投げるだけ。

たまごさんの言葉（2026-09-27・原文）:
  「秋の曲の配信、俺がどんどん投げ込み箱に追加していく形にしようか。」
  「曲は俺が適当に入れていくので、仕組みだけ作っておいてください。」
  「コピーはチャッピーに相談して整えてもらってから、予約投稿の仕組みに入れる
    ようにしようか。関連曲もチャッピーに調べてもらって指定しようかな。」

■ 道は3つの部屋に分かれている。1周回で1部屋ぶんだけ進める（心臓を重くしない）
   投げ込み箱(status/nagekomi.jsonl)
      ↓ ① uketsuke    たまごさんが投げたものだけ拾う。機械の試し投げは拾わない
   チャッピー待ち(status/1170/chappie_machi.json)
      ↓ ② tou         チャッピーへの問いを1件ぶん書き出す（公開リポ経由・0円）
      ↓ ③ kotae       チャッピーの答え（コピー＋関連曲）を受け取る
      ↓ ④ kanmon      本番ページを実際に開いて数える（本人の動画／関連4本／完成）
   自動投稿の箱(status/buffer_queue/machi.json の machi)
      ↓ tools/1170_hako.py が朝=日本の曲／夜=洋楽で1本ずつ入れる

■ 絶対にやらないこと
  ・★コピーを機械で書いて予約に流す。書くのはチャッピー、選ぶのはたまごさん。
    ここがやるのは「運ぶ」ことだけ。
  ・★チャッピーのOKが出ていないものを machi へ入れる。
  ・★関所を通っていないものを machi へ入れる（未完成ページへのリンクを投稿しない）。
  ・★勝手に大量にチャッピーへ投げる（1周回に1件だけ。たまごさんが「相談してみる」と
    言っている段階なので、器だけ先に置いて待つ）。

■ チャッピーとの受け渡し（0円）
  こちらから: status/chappie/ask.jsonl    …… 1行1件の問い
  あちらから: status/chappie/kotae.jsonl  …… 1行1件の答え
  公開リポ tamago2022/ai-kaigi 経由で往復する（push/pull は別の係の仕事）。
  答えの形（これだけ守ってもらえばよい）:
    {"id":"<問いのid>", "ok":true, "text":"投稿の本文（URLは最後の行）",
     "kanren":["https://www.youtube.com/watch?v=...", ...],
     "lang":"ja" or "en", "header":"ヘッダーのコピー（任意）"}

■ 使い方
  python3 tools/1170_nagekomi_nagasu.py            … 1部屋ぶん進める
  python3 tools/1170_nagekomi_nagasu.py --miru     … 今どこに何本あるか見るだけ
  python3 tools/1170_nagekomi_nagasu.py --zenbu    … 詰まりが取れるまで回す（手で使う用）
"""
import datetime
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

JST = datetime.timezone(datetime.timedelta(hours=9))
NAGEKOMI = os.path.join(REPO, "status", "nagekomi.jsonl")
D = os.path.join(REPO, "status", "1170")
MACHI_CH = os.path.join(D, "chappie_machi.json")     # チャッピー待ち
DAICHO = os.path.join(D, "nagashita.jsonl")          # 何をどこまで運んだか
HAZURE = os.path.join(D, "hazure.json")              # 通らなかったものと理由
CH_D = os.path.join(REPO, "status", "chappie")
ASK = os.path.join(CH_D, "ask.jsonl")
KOTAE = os.path.join(CH_D, "kotae.jsonl")
MACHI = os.path.join(REPO, "status", "buffer_queue", "machi.json")
KANREN_SAITEI = 4
MAIN_HABA = 500
ADD_ID = "c48face2f76689376654c71af910f14f7f4c0c314789b24bb968eb252d8b157e"


def now():
    return datetime.datetime.now(JST)


def jload(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def jsave(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8").write(
        json.dumps(o, ensure_ascii=False, indent=1))


def jlload(p):
    out = []
    try:
        for ln in io.open(p, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    except Exception:
        pass
    return out


def jladd(p, row):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with io.open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def nihongo_ga_aru(s):
    for c in s or "":
        o = ord(c)
        if (0x3040 <= o <= 0x30FF) or (0x4E00 <= o <= 0x9FFF) \
           or (0x3400 <= o <= 0x4DBF) or (0xFF66 <= o <= 0xFF9D):
            return True
    return False


def hazusu(row_id, midashi, why):
    h = jload(HAZURE, [])
    h.append({"id": row_id, "nani": midashi, "riyuu": why,
              "at": now().strftime("%F %T")})
    jsave(HAZURE, h)


# ───────────────────────── ① 受付：投げ込み箱から拾う

def uketsuke():
    """たまごさんが投げたものを、チャッピー待ちの列へ移す。何本移したかを返す。"""
    rows = jlload(NAGEKOMI)
    sumi = set(x.get("id") for x in jlload(DAICHO))
    retsu = jload(MACHI_CH, {"retsu": []})
    ima = set(e.get("id") for e in retsu.get("retsu") or [])
    n = 0
    for r in rows:
        rid = r.get("id")
        if not rid or rid in sumi or rid in ima:
            continue
        # ★機械の試し投げは拾わない（1043番の決め）
        if (r.get("nageta") or "nushi") != "nushi":
            continue
        title = r.get("titleRaw") or r.get("title") or ""
        e = {
            "id": rid,
            "uketsuke": now().strftime("%F %H:%M"),
            "url": r.get("url") or "",
            "memo": r.get("memo") or "",
            "youtube_title": title,
            "channel": r.get("channel") or "",
            "videoId": r.get("videoId") or "",
            # ★ここで機械が曲名・アーティスト名を「決めつけない」。
            #   取れた題名をそのまま渡して、同定はチャッピーとたまごさんに任せる。
            "artist": "",
            "song": "",
            "lang": "ja" if nihongo_ga_aru(title) else "",
            "from": "nagekomi",
            "chappie": "machi",     # machi → ok／ng
            "kanmon_ok": False,
            "text": "",
            "kanren": [],
        }
        retsu.setdefault("retsu", []).append(e)
        jladd(DAICHO, {"at": now().strftime("%F %T"), "id": rid,
                       "doko": "chappie_machi", "url": e["url"],
                       "title": title[:120]})
        n += 1
    if n:
        retsu["at"] = now().strftime("%F %H:%M")
        jsave(MACHI_CH, retsu)
    return n


# ───────────────────────── ② 問い：チャッピーへ1件だけ

def tou():
    """コピーと関連曲を、チャッピーに1件だけ聞く（器に置くだけ・0円）。"""
    retsu = jload(MACHI_CH, {"retsu": []})
    kiita = set(x.get("id") for x in jlload(ASK))
    for e in retsu.get("retsu") or []:
        if e.get("id") in kiita or e.get("chappie") != "machi":
            continue
        jladd(ASK, {
            "at": now().strftime("%F %T"),
            "id": e["id"],
            "url": e["url"],
            "youtube_title": e.get("youtube_title") or "",
            "channel": e.get("channel") or "",
            "memo": e.get("memo") or "",
            "onegai": (
                "この動画の曲について、Xの投稿1本ぶんの本文と、関連曲を4本以上お願いします。"
                "決まり：①本文の最後の行がリンク（joy-relief-station の曲ページ）。"
                "②断定する事実（年号・原曲・代表曲・受賞）は出典が取れるものだけ。"
                "取れないものは書かない。③テンプレート文（『代表曲のひとつ。』等）は使わない。"
                "④関連は本人の公式チャンネルの動画を優先。素人カバー・AIカバーは入れない。"
                "⑤日本の曲なら lang=\"ja\"、洋楽なら lang=\"en\"。"
                "朝9時の枠に日本の曲、夜21時21分の枠に洋楽が出ます。"),
            "kotae_no_kata": {
                "id": e["id"], "ok": True, "text": "（本文。URLは最後の行）",
                "kanren": ["https://www.youtube.com/watch?v=..."],
                "lang": "ja|en", "header": "（ヘッダーのコピー・任意）"},
        })
        return 1
    return 0


# ───────────────────────── ③ 答え：チャッピーのOKを受け取る

def kotae():
    """答えを1件ぶん取り込む。ok でないものは列に残して理由を書く。"""
    ans = jlload(KOTAE)
    if not ans:
        return 0
    byid = {}
    for a in ans:
        if a.get("id"):
            byid[a["id"]] = a        # 後から来たものが勝つ（直しを受ける）
    retsu = jload(MACHI_CH, {"retsu": []})
    n = 0
    for e in retsu.get("retsu") or []:
        a = byid.get(e.get("id"))
        if not a or e.get("chappie") == "ok":
            continue
        if not a.get("ok"):
            e["chappie"] = "ng"
            e["chappie_riyuu"] = str(a.get("riyuu") or a.get("why") or "")[:300]
            hazusu(e["id"], e.get("youtube_title") or e["url"],
                   "チャッピーがNG：" + (e.get("chappie_riyuu") or ""))
            n += 1
            continue
        text = str(a.get("text") or "").strip()
        lines = [x for x in text.split("\n") if x.strip()]
        if not lines or "http" not in lines[-1]:
            e["chappie_riyuu"] = "本文の最後の行がリンクになっていない"
            continue
        kan = [u for u in (a.get("kanren") or []) if str(u).startswith("http")]
        if len(kan) < KANREN_SAITEI:
            e["chappie_riyuu"] = "関連が %d 本（最低 %d 本）" % (len(kan), KANREN_SAITEI)
            continue
        e["text"] = text
        e["kanren"] = kan
        e["lang"] = (str(a.get("lang") or e.get("lang") or "").strip().lower()
                     or ("ja" if nihongo_ga_aru(text.split("\n")[1] if len(text.split("\n")) > 1 else text) else "en"))
        e["header"] = str(a.get("header") or "")[:300]
        e["page_url"] = re.search(r'https?://\S+', lines[-1]).group(0)
        e["chappie"] = "ok"
        e["chappie_riyuu"] = ""
        n += 1
    if n:
        retsu["at"] = now().strftime("%F %H:%M")
        jsave(MACHI_CH, retsu)
    return n


# ───────────────────────── ④ 関所：本番ページを実際に開いて数える

def page_wo_kazoeru(url):
    """headless Chrome で1本だけ開いて数える（たまごさんのChromeには触らない）。"""
    os.makedirs(D, exist_ok=True)
    lst = os.path.join(D, "_url.txt")
    out = os.path.join(D, "_page.json")
    io.open(lst, "w", encoding="utf-8").write(url + "\n")
    env = dict(os.environ, SEKISHO_SETTLE_MS="18000")
    try:
        subprocess.run(["node", os.path.join(HERE, "1164_page_sekisho.mjs"), lst, out],
                       cwd=REPO, env=env, timeout=150,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as ex:
        return None, "ページを開けなかった：%s" % ex
    d = jload(out, {})
    rows = d.get("rows") if isinstance(d, dict) else d
    row = (rows or [None])[0]
    if not row:
        return None, "ページの数字が取れなかった"
    return (row.get("data") or {}), ""


def kanmon():
    """チャッピーOKのものを1本だけ実測して、通ったら machi の末尾へ。"""
    retsu = jload(MACHI_CH, {"retsu": []})
    for e in retsu.get("retsu") or []:
        if e.get("chappie") != "ok" or e.get("kanmon_ok"):
            continue
        u = e.get("page_url") or ""
        if not u:
            e["kanmon_riyuu"] = "リンク先が分からない"
            jsave(MACHI_CH, retsu)
            return 0
        k, why = page_wo_kazoeru(u)
        if k is None:
            e["kanmon_riyuu"] = why
            jsave(MACHI_CH, retsu)
            return 0
        vids = k.get("videos") or []
        main_v = vids[0] if vids else None
        kanren_n = int(k.get("kanren_honsuu") or 0)
        ng = []
        if not main_v or int(main_v.get("w") or 0) < MAIN_HABA:
            ng.append("本人の動画（大きい方）がページに無い")
        if kanren_n < KANREN_SAITEI:
            ng.append("ページの関連が %d 本（最低 %d 本）" % (kanren_n, KANREN_SAITEI))
        if not k.get("h1"):
            ng.append("ページの見出しが出ていない＝未完成")
        e["kanmon_mita"] = {"at": now().strftime("%F %H:%M"),
                            "kanren": kanren_n,
                            "main": ("%sx%s" % (main_v.get("w"), main_v.get("h")))
                                    if main_v else "なし",
                            "h1": k.get("h1") or ""}
        if ng:
            e["kanmon_ok"] = False
            e["kanmon_riyuu"] = "／".join(ng)
            jsave(MACHI_CH, retsu)
            return 0
        e["kanmon_ok"] = True
        e["kanmon_riyuu"] = ""

        # ★通った。自動投稿の箱の末尾へ移す
        m = jload(MACHI, {})
        ima = m.get("machi") or []
        if any(str(x.get("text") or "").strip() == e["text"].strip() for x in ima) \
           or e["text"].strip() in [str(s).strip() for s in (m.get("sumi") or [])]:
            e["kanmon_riyuu"] = "もう箱に居る／もう出している"
            jsave(MACHI_CH, retsu)
            return 0
        ima.append({"text": e["text"], "song_key": e.get("song_key") or e["id"],
                    "from": "nagekomi", "artist": e.get("artist") or "",
                    "song": e.get("song") or (e.get("youtube_title") or "")[:80],
                    "lang": e.get("lang") or "", "chappie": "ok",
                    "kanmon_ok": True, "nagekomi_id": e["id"],
                    "kanren": e.get("kanren") or []})
        m["machi"] = ima
        jsave(MACHI, m)
        retsu["retsu"] = [x for x in retsu["retsu"] if x.get("id") != e["id"]]
        retsu["at"] = now().strftime("%F %H:%M")
        jsave(MACHI_CH, retsu)
        jladd(DAICHO, {"at": now().strftime("%F %T"), "id": e["id"],
                       "doko": "machi", "lang": e.get("lang"),
                       "kanren": kanren_n})
        return 1
    return 0


# ───────────────────────── 回す

def miru():
    nk = jlload(NAGEKOMI)
    ch = jload(MACHI_CH, {"retsu": []}).get("retsu") or []
    m = jload(MACHI, {}).get("machi") or []
    print("投げ込み箱: %d 本（たまごさんのぶん %d 本）"
          % (len(nk), sum(1 for r in nk if (r.get("nageta") or "nushi") == "nushi")))
    print("チャッピー待ち: %d 本" % len(ch))
    for e in ch:
        print("  %-12s chappie=%-5s 関所=%s %s %s"
              % (e.get("id"), e.get("chappie"), "◯" if e.get("kanmon_ok") else "✕",
                 (e.get("youtube_title") or e.get("url") or "")[:52],
                 ("← " + e["chappie_riyuu"]) if e.get("chappie_riyuu") else
                 ("← " + e["kanmon_riyuu"]) if e.get("kanmon_riyuu") else ""))
    print("自動投稿の箱（待機列）: %d 本" % len(m))
    print("チャッピーへの問い: %d 件／答え: %d 件"
          % (len(jlload(ASK)), len(jlload(KOTAE))))
    return 0


def ikkai():
    n = uketsuke()
    if n:
        print("投げ込み箱から %d 本受け付けた" % n)
        return n
    n = kotae()
    if n:
        print("チャッピーの答えを %d 件取り込んだ" % n)
        return n
    n = kanmon()
    if n:
        print("関所を通して箱へ %d 本入れた" % n)
        return n
    n = tou()
    if n:
        print("チャッピーへの問いを %d 件置いた" % n)
        return n
    return 0


def main():
    if "--miru" in sys.argv:
        return miru()
    if "--zenbu" in sys.argv:
        for _ in range(40):
            if not ikkai():
                break
        return miru()
    ikkai()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as ex:
        print("落ちた:", ex)
        sys.exit(1)
