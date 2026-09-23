#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1176番【投げ込み箱の入口・完成版レーン】たまごさんは .txt を1枚置くだけ。

たまごさんの言葉（2026-09-28）:
  「たまごさんは『この曲をやって』と情報を流すだけ。予約の棚は常に満杯。
    本人が押すのは永久に0回。」
  「ここに曲名とコピーを書けば勝手に並ぶ、が成立していること。」

■ 入口（たまごさんに伝えるのはこの1行だけ）
    ~/Desktop/nagekomi/ に、コピーをそのまま貼った .txt を1曲1枚置く。

  中身はXに出す本文そのまま（曲ページのURLの行を必ず入れる）。例：
      Some songs feel less like performances and more like letters.

      Leon Russell — "A Song for You"

      Written for the world, but ...

      https://joy-relief-station.lovable.app/cover-guide?artist=leon-russell&song=a-song-for-you

      #LeonRussell

  朝(日本)／夜(海外)の振り分けは自動で判定する（曲名に日本語があれば ja、無ければ en）。
  はっきり決めたいときはファイル名の頭に ja_ / en_ を付ける。それが最優先。

■ なぜチャッピー待ちの列に入れるのか（新しい道を作らない）
  たまごさんが持ってくるコピーは**すでにチャッピーと作った完成版**。だから
  「チャッピーに聞く」部分だけを飛ばして chappie="ok" で列に置く。
  そこから先は既にある道をそのまま通る：
      status/1170/chappie_machi.json
        ↓ tools/1170_nagekomi_nagasu.py の kanmon()  …本番ページを実際に開いて数える
          （本人の動画／関連4本以上／見出しが出ている。通らなければ並ばない）
        ↓ status/buffer_queue/machi.json（自動投稿の箱）
        ↓ tools/1170_hako.py  …朝09:00=日本／夜21:00=海外の空き枠へ1本ずつ入れる
  ★この係はBufferを1回も叩かない（0叩き）。

■ 二度入れない
  同じ曲（曲ページのURLの artist/song）が、箱・チャッピー待ち・出した台帳の
  どれかに1つでもあれば受け付けない。
"""
import datetime
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

JST = datetime.timezone(datetime.timedelta(hours=9))
HOME = os.path.expanduser("~")
HAKO_DIRS = [os.path.join(HOME, "Desktop", "nagekomi"),
             os.path.join(REPO, "status", "nagekomi_box")]
SUNDA = "sunda"
CH_MACHI = os.path.join(REPO, "status", "1170", "chappie_machi.json")
MACHI = os.path.join(REPO, "status", "buffer_queue", "machi.json")
DAICHO = os.path.join(REPO, "status", "buffer_queue", "dashita.jsonl")
OUT = os.path.join(REPO, "status", "1176_uketsuke.json")


def now():
    return datetime.datetime.now(JST)


def jload(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def jsave(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = "%s.%d.tmp" % (p, os.getpid())
    io.open(tmp, "w", encoding="utf-8").write(
        json.dumps(o, ensure_ascii=False, indent=1))
    os.replace(tmp, p)


def song_key(text):
    m = re.search(r"joy-relief-station\.lovable\.app/cover-guide\?([^\s\"'>)]+)",
                  text or "")
    if not m:
        return "", ""
    q = m.group(1).replace("&amp;", "&")
    a = s = ""
    for kv in q.split("&"):
        if kv.startswith("artist="):
            a = kv[7:].strip().lower()
        elif kv.startswith("song="):
            s = kv[5:].strip().lower()
    url = m.group(0)
    if not url.startswith("http"):
        url = "https://" + url
    return ("%s/%s" % (a, s) if a and s else ""), url


def nihongo(s):
    for ch in s or "":
        o = ord(ch)
        if (0x3040 <= o <= 0x30ff) or (0x4e00 <= o <= 0x9fff):
            return True
    return False


def midashi_gyou(text):
    """曲名の行（— を含む行）。無ければ2行目。"""
    for ln in (text or "").split("\n"):
        if "—" in ln or " - " in ln:
            return ln.strip()
    g = [x for x in (text or "").split("\n") if x.strip()]
    return g[1].strip() if len(g) > 1 else (g[0].strip() if g else "")


def sudeni_aru(sk, text):
    """箱・チャッピー待ち・出した台帳のどこかに居るか。居るなら理由を返す。"""
    if not sk:
        return "曲ページのURLが本文に無い（artist/song が読めない）"
    m = jload(MACHI, {})
    for x in (m.get("machi") or []):
        if (x.get("song_key") or "") == sk:
            return "もう自動投稿の箱に並んでいる"
    for x in (jload(CH_MACHI, {"retsu": []}).get("retsu") or []):
        if (x.get("song_key") or "") == sk:
            return "もうチャッピー待ちの列に居る"
    try:
        for ln in io.open(DAICHO, encoding="utf-8"):
            try:
                if (json.loads(ln).get("song_key") or "") == sk:
                    return "もう一度Bufferに入れた／出した曲（台帳にある）"
            except Exception:
                pass
    except Exception:
        pass
    return ""


def hitotsu(path, fn):
    text = io.open(path, encoding="utf-8", errors="replace").read().strip()
    if not text:
        return {"file": fn, "ok": False, "naze": "中身が空"}
    sk, url = song_key(text)
    naze = sudeni_aru(sk, text)
    if naze:
        return {"file": fn, "ok": False, "song_key": sk, "naze": naze}
    low = fn.lower()
    if low.startswith("ja_") or low.startswith("ja-"):
        lang = "ja"
    elif low.startswith("en_") or low.startswith("en-"):
        lang = "en"
    else:
        lang = "ja" if nihongo(midashi_gyou(text)) else "en"
    artist, song = (sk.split("/") + [""])[:2]
    rec = {
        "id": hashlib.sha1(sk.encode("utf-8")).hexdigest(),
        "text": text,
        "song_key": sk,
        "page_url": url,
        "artist": artist,
        "song": song,
        "lang": lang,
        "from": "nushi",
        "chappie": "ok",
        "moto": "たまごさんの完成版（投げ込み箱 %s）" % fn,
        "at": now().strftime("%F %T"),
    }
    d = jload(CH_MACHI, {"retsu": []})
    d.setdefault("retsu", []).append(rec)
    d["at"] = now().strftime("%F %H:%M")
    d["_これは何"] = ("★チャッピーOK待ちの列。1176番（投げ込み箱の完成版レーン）が置いたものは "
                    "chappie=ok で入る。次は 1170_nagekomi_nagasu.py の kanmon() が"
                    "本番ページを実測して、通ったものだけ自動投稿の箱へ移す。")
    jsave(CH_MACHI, d)
    sundad = os.path.join(os.path.dirname(path), SUNDA)
    os.makedirs(sundad, exist_ok=True)
    try:
        os.replace(path, os.path.join(sundad, fn))
    except Exception:
        pass
    return {"file": fn, "ok": True, "song_key": sk, "lang": lang,
            "midashi": midashi_gyou(text)}


def main():
    kekka, mita = [], []
    for d in HAKO_DIRS:
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            continue
        mita.append(d.replace(HOME, "~"))
        try:
            names = sorted(n for n in os.listdir(d)
                           if n.endswith(".txt") and not n.startswith("."))
        except Exception:
            names = []
        for n in names:
            try:
                kekka.append(hitotsu(os.path.join(d, n), n))
            except Exception as ex:
                kekka.append({"file": n, "ok": False, "naze": str(ex)[:160]})
    if kekka or not os.path.exists(OUT):
        jsave(OUT, {
            "_これは何": "1176番【投げ込み箱の入口】たまごさんが置いた .txt を受け付けた記録。★Bufferは0叩き。",
            "_入口": "~/Desktop/nagekomi/ に、コピーをそのまま貼った .txt を1曲1枚置くだけ",
            "at": now().strftime("%F %T"),
            "mita": mita,
            "uketsuketa": sum(1 for x in kekka if x.get("ok")),
            "kekka": kekka})
    for x in kekka:
        print(("○ 受け付けた %s [%s] %s" % (x.get("file"), x.get("lang"), x.get("midashi")))
              if x.get("ok") else
              ("× %s → %s" % (x.get("file"), x.get("naze"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
