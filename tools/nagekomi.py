#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1036番【投げ込み箱】棚に置く前の、放り込んでおくだけの場所。

たまごさん（2026-09-23・原文）:
  「Twitterでネタ拾うじゃん。これは棚に置きたいなって。だけど棚に置こうとしたら
    ジャーンって落ちるわけだよ、Lovableで。だからまとめて後で実装できるような、
    なんか放り込んでおくとこが欲しいんだよね。メモじゃないけど。」
  「後の振り分け、どの棚に置くかっていうのは俺が口頭でバーって言うからさ。」

■ 決め（なぜこの形か）
  ・**Lovableの棚を一切触らない。**落ちる場所を通らないために作るものなので、
    ここが棚のデータへ書きに行ったら本末転倒。書き先は status/nagekomi.jsonl だけ。
  ・**入口はURL1本＋一言だけ。**それ以上聞かない。振り分けは強制しない
    （shelf が空のまま置ける。決まっていないものは決まっていないまま置く）。
  ・**新しい常駐を増やさない。**既にある15秒便（heartbeat → command_ingest）に
    action="nagekomi" として相乗りする。スマホ側は obsidian://new で受信箱に
    JSONを1枚置くだけ＝PWAのリモコンと同じ、実績のある道。
  ・**台帳は公開しない。**status/nagekomi.jsonl は .gitignore に入れる
    （公開リポなので、入れたものが勝手に世界に出ない側へ倒す）。

■ 機械が勝手に埋めるもの（たまごさんが何も書かなくても後で分かるように）
  YouTube : 題名・チャンネル名・公開日・長さ（.env の YOUTUBE_DATA_API_KEY があれば）
            鍵が無くても oEmbed で題名・チャンネル名までは取れる（鍵不要・0円）
  X       : 本文・投稿者（publish.twitter.com の oEmbed。鍵不要・0円）
  その他  : ページの <title>
  ★取れなかったものは「取れなかった」と理由をそのまま残す。想像で埋めない。

■ 使い方
  python3 tools/nagekomi.py --add "https://..." --memo "一言"
  python3 tools/nagekomi.py --shiji "口で言った振り分け・コピーの方向"
  python3 tools/nagekomi.py --list
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
import uuid
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
JST = timezone(timedelta(hours=9))

LEDGER = os.path.join(REPO, "status", "nagekomi.jsonl")
SHIJI = os.path.join(REPO, "status", "nagekomi_shiji.jsonl")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def now():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M")


def env_key(name):
    p = os.path.join(REPO, ".env")
    if not os.path.exists(p):
        return ""
    try:
        for line in io.open(p, encoding="utf-8"):
            if line.strip().startswith(name + "="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


# ------------------------------------------------------------------ 種類を見分ける
def kind_of(url):
    u = (url or "").lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "twitter.com" in u or "x.com" in u:
        return "x"
    if "instagram.com" in u:
        return "instagram"
    if "tiktok.com" in u:
        return "tiktok"
    return "web"


def youtube_id(url):
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})", url or "")
    return m.group(1) if m else ""


def iso8601_to_mmss(s):
    """PT4M13S → 4:13"""
    m = re.match(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return ""
    h, mi, se = (int(x) if x else 0 for x in m.groups())
    return ("%d:%02d:%02d" % (h, mi, se)) if h else ("%d:%02d" % (mi, se))


# ------------------------------------------------------------------ 機械が調べて埋める
def enrich(url):
    """戻り値: (meta dict, 取れなかった理由 or '')"""
    k = kind_of(url)
    meta = {"kind": k}
    why = []

    if k == "youtube":
        vid = youtube_id(url)
        meta["videoId"] = vid
        key = env_key("YOUTUBE_DATA_API_KEY")
        if vid and key:
            try:
                api = ("https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails"
                       "&id=%s&key=%s" % (vid, urllib.parse.quote(key)))
                code, body = get(api)
                items = (json.loads(body).get("items") or [])
                if items:
                    sn = items[0].get("snippet", {})
                    cd = items[0].get("contentDetails", {})
                    meta["title"] = sn.get("title", "")
                    meta["channel"] = sn.get("channelTitle", "")
                    meta["publishedAt"] = (sn.get("publishedAt") or "")[:10]
                    meta["duration"] = iso8601_to_mmss(cd.get("duration", ""))
                    meta["source"] = "YouTube Data API v3 %s" % code
                    return meta, ""
                why.append("Data APIが0件（非公開・削除の可能性）")
            except Exception as e:
                why.append("Data API失敗：%s" % e)
        elif not key:
            why.append("YOUTUBE_DATA_API_KEYが.envに無い（公開日・長さは取れない）")
        # 鍵が無くても題名とチャンネル名はここまで取れる
        try:
            code, body = get("https://www.youtube.com/oembed?url=%s&format=json"
                             % urllib.parse.quote(url, safe=""))
            d = json.loads(body)
            meta["title"] = d.get("title", "")
            meta["channel"] = d.get("author_name", "")
            meta["source"] = "youtube oEmbed %s" % code
        except Exception as e:
            why.append("oEmbedも失敗：%s" % e)

    elif k == "x":
        try:
            code, body = get("https://publish.twitter.com/oembed?url=%s&omit_script=1&dnt=true"
                             % urllib.parse.quote(url, safe=""))
            d = json.loads(body)
            html = d.get("html", "")
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            meta["title"] = text[:200]
            meta["channel"] = d.get("author_name", "")
            meta["source"] = "publish.twitter.com oEmbed %s" % code
        except Exception as e:
            why.append("X oEmbed失敗：%s（鍵の要る投稿・削除・非公開だと取れない）" % e)

    else:
        try:
            code, body = get(url)
            m = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
            if m:
                t = re.sub(r"\s+", " ", m.group(1)).strip()
                meta["title"] = t[:200]
            meta["source"] = "ページの<title> %s" % code
        except Exception as e:
            why.append("ページが取れない：%s" % e)

    return meta, "／".join(why)


# ------------------------------------------------------------------ 台帳
def append_jsonl(path, row):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def add(url, memo="", shelf=None, shelf_id=None):
    url = (url or "").strip()
    if not url:
        return {"ok": False, "message": "URLが空です"}
    if not re.match(r"^https?://", url):
        return {"ok": False, "message": "http(s)で始まるURLだけ受け付けます"}
    meta, why = enrich(url)
    row = {
        "id": uuid.uuid4().hex[:12],
        "at": now(),
        "url": url,
        "memo": (memo or "").strip(),
        # ★1039番：箱の棚ボタンを押していればその場で入る。押さなければ None のまま
        #   （決まっていないものは決まっていないまま置く、を崩さない）
        "shelf": (shelf or "").strip() or None,
        "shelfId": (shelf_id or "").strip() or None if isinstance(shelf_id, str) else shelf_id,
        "copyDirection": None,  # 「コピーはこの方向で」も後から入る
        "status": "inbox",
    }
    row.update(meta)
    if why:
        row["metaMissing"] = why
    append_jsonl(LEDGER, row)
    return {"ok": True, "id": row["id"],
            "message": "投げ込み受け取り：%s" % (row.get("title") or url)[:60]}


def shiji(text, shelf=None):
    """口で言った振り分け／コピーの方向を1行として置く。棚には触らない。"""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "message": "中身が空です"}
    row = {"id": uuid.uuid4().hex[:12], "at": now(), "text": text, "status": "unapplied"}
    if (shelf or "").strip():
        row["shelf"] = shelf.strip()
    append_jsonl(SHIJI, row)
    return {"ok": True, "id": row["id"], "message": "振り分けの指示を受け取りました（%d文字）" % len(text)}


def load(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in io.open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


# ------------------------------------------------------------------ 工場（Mac）側で走らせる口
def run_job(payload):
    """gaibu_runner から kind="nagekomi" で呼ばれる。
    サンドボックスからは YouTube も X も 403 で出られない（実測 2026-09-23 12:56）。
    Macからは出られるので、**調べて埋める所だけ**をここへ寄せる。
    GETだけ・棚には一切書かない・課金0（YouTube Data APIは無料枠、oEmbedは鍵不要）。
    """
    op = (payload or {}).get("op") or "add"
    if op == "probe":
        # 実測用：台帳に書かず、取れるかどうかだけ確かめる
        meta, why = enrich((payload or {}).get("url") or "")
        return {"ok": bool(meta.get("title")), "meta": meta, "missing": why, "totalYen": 0.0}
    if op == "shiji":
        r = shiji((payload or {}).get("text") or "")
        r["totalYen"] = 0.0
        return r
    r = add((payload or {}).get("url") or "", (payload or {}).get("memo") or "")
    r["totalYen"] = 0.0
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add")
    ap.add_argument("--memo", default="")
    ap.add_argument("--shiji")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.add:
        print(json.dumps(add(a.add, a.memo), ensure_ascii=False))
    elif a.shiji:
        print(json.dumps(shiji(a.shiji), ensure_ascii=False))
    elif a.list:
        rows = load(LEDGER)
        print("投げ込み %d件／未振り分け %d件" % (len(rows), sum(1 for r in rows if not r.get("shelf"))))
        for r in rows[-20:]:
            print("  %s  %-10s %s" % (r.get("at"), r.get("kind", ""), (r.get("title") or r.get("url", ""))[:60]))
        sh = load(SHIJI)
        print("口頭の振り分け指示 %d件（未反映 %d件）"
              % (len(sh), sum(1 for r in sh if r.get("status") == "unapplied")))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
