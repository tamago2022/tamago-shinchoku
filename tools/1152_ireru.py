#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1152番【今すぐ入れる4本】箱の完成を待たずに、先に棚へ入れる。

たまごさん（2026-09-26・原文）:
  「箱の完成を待たない。先に棚へ。」
  「中身を必ず読んでからコピーを書く。」
  「動画が入っていること・サムネが出ることを確認してから棚に入れる。空のカードを作らない。」

■ 決め（なぜこの形か）
  ・**新しい道を作らない。**入れ口は既にある tools/nagekomi_shelf.py の
    insert_stock / insert_pick / gates をそのまま使う。関所も同じように通す。
  ・**題名とひとことは人（編集者）が書いたものを持ち込む**（teuchi の口と同じ扱い）。
    書き手（claude -p）が止まっている日でも棚が止まらないようにするため。
    ★持ち込んでも関所は素通りさせない。落ちたら入れない。
  ・**サムネと動画を先に実測する。**X は cdn.syndication の mediaDetails、
    YouTube は img.youtube.com を叩いて、**200が返ったものだけ**棚に入れる。
    取れなかったものは入れない（空のカードを作らない）。
  ・**控えを必ず残す。**status/nagekomi_ireta.jsonl に bin=1152 で控える。
    `python3 tools/nagekomi_shelf.py --modoshi 1152` でこの便の分だけ消える。
  ・**受付一覧に出るようにする。**status/nagekomi.jsonl にも1行ずつ足す
    （たまごさんが「何が入って、反映されたか」を1枚で見られるように）。
"""
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import tana                      # noqa: E402
import nagekomi_shelf as ns      # noqa: E402

STATUS = os.path.join(REPO, "status")
LEDGER = os.path.join(STATUS, "nagekomi.jsonl")
IRETA = os.path.join(STATUS, "nagekomi_ireta.jsonl")
BIN = "1152"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

INU = "6fd4f321-5be6-4050-bfe2-4a91dbd16362"        # 犬の棚（cute）
SUKI = "c60b35e2-a881-4997-abfb-2aad14d3384b"       # 飼い主大好き（cute）

# ★中身を読んでから書いた。thumb/ の4枚を実際に見て、本文（yomu.py）も読んだうえで書いている。
TAMA = [
    {
        "key": "inu-x",
        "url": "https://x.com/7wVy1/status/2103318579668221963",
        "shelves": [("cute", INU, "犬の棚"), ("cute", SUKI, "飼い主大好き")],
        "title": "抱っこされた瞬間、この犬は全部あずけた",
        "whisper": "腕の中におさまっただけで、顔つきが「もう何も心配ない」に変わる。",
        "memo": "犬の棚と飼い主大好きの棚、両方に",
        "channel": "尊い動物",
        "material": "飼い主への信頼が表情から溢れてる／尊い動物／抱き上げられて"
                    "目を細めているダックスフント",
    },
    {
        "key": "peco-yt",
        "url": "https://youtube.com/shorts/y-jVOubKCe0",
        "shelves": [("cute", INU, "犬の棚")],
        "title": "褒めたのに、柴犬に怒られた",
        "whisper": "よかれと思って褒めた飼い主が、その場で一喝される。家の中でいちばん短い裁判。",
        "memo": "犬の棚",
        "channel": "PECOチャンネルさん【癒やしのペット動画】",
        "artist": "PECOチャンネルさん【癒やしのペット動画】",
        "material": "褒めたのに…w｜PECO／PECOチャンネルさん【癒やしのペット動画】／"
                    "口を開けて吠える柴犬",
    },
    {
        "key": "nabe-x",
        "url": "https://x.com/XWorldCuisines/status/2103191906322657290",
        "shelves": [("food", None, "スープ")],
        "title": "白菜と肉を重ねるだけで、鍋がまるごと花になる",
        "whisper": "白菜と肉を交互に立てて、だしを注ぐだけ。それだけで、鍋の中に見せ場の断面ができる。",
        "memo": "食＞スープ",
        "channel": "𝕏 Cuisines",
        "material": "白菜と薄切り肉を重ねたミルフィーユ鍋／赤い鍋／だし・しょうゆ・"
                    "すき焼きの割下／𝕏 Cuisines",
    },
    {
        "key": "potage-x",
        "url": "https://x.com/aya_bistro/status/2102918949474373942",
        "shelves": [("food", None, "スープ")],
        "title": "さつまいもが、とろりと黄金になるまで",
        "whisper": "玉ねぎが甘くなるまで弱火で待つ。その待ち時間のぶんだけ、寒い朝がやさしくなる。",
        "memo": "食＞スープ",
        "channel": "あやシェフ",
        "material": "さつまいものポタージュ／さつまいも・玉ねぎ・バター・牛乳／"
                    "玉ねぎを弱火でじっくり／あやシェフ",
    },
]


def now():
    return time.strftime("%Y-%m-%d %H:%M")


def _get(u, timeout=20):
    try:
        with urllib.request.urlopen(
                urllib.request.Request(u, headers={"User-Agent": UA}), timeout=timeout) as r:
            return r.getcode(), r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", 0), ""


def _head_ok(u):
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.getcode() == 200 and int(r.headers.get("Content-Length") or 1) > 1000
    except Exception:
        return False


RE_X = re.compile(r"(?:twitter|x)\.com/[^/]+/status/(\d+)")
RE_YT = re.compile(r"(?:youtu\.be/|shorts/|v=|embed/)([A-Za-z0-9_\-]{11})")


def media(url):
    """★実測。動画とサムネが本当に在るときだけ (thumb, note) を返す。無ければ (None, why)。"""
    m = RE_YT.search(url)
    if m:
        t = "https://img.youtube.com/vi/%s/hqdefault.jpg" % m.group(1)
        if not _head_ok(t):
            return None, None, "サムネ(%s)が取れなかった" % t
        code, body = _get("https://www.youtube.com/oembed?url=%s&format=json"
                          % urllib.parse.quote(url, safe=""))
        if code != 200:
            return None, None, "oEmbedが %s（動画が生きている証拠が取れない）" % code
        return t, None, ""
    m = RE_X.search(url)
    if not m:
        return None, None, "XでもYouTubeでもないURL"
    code, body = _get("https://cdn.syndication.twimg.com/tweet-result?id=%s&lang=ja&token=a"
                      % m.group(1))
    if code != 200 or not body:
        return None, None, "cdn.syndication が %s" % code
    d = json.loads(body)
    md = d.get("mediaDetails") or []
    kinds = [x.get("type") for x in md]
    if "video" not in kinds and "animated_gif" not in kinds:
        return None, None, "この投稿に動画が入っていない（%s）" % (kinds or "メディア無し")
    thumb = (d.get("video") or {}).get("poster") or (md[0].get("media_url_https") if md else None)
    if not thumb or not _head_ok(thumb):
        return None, None, "サムネが取れなかった"
    code2, body2 = _get("https://publish.twitter.com/oembed?url=%s&omit_script=1&dnt=true"
                        % urllib.parse.quote(url, safe=""))
    note = ""
    if code2 == 200 and body2:
        try:
            note = json.loads(body2).get("html") or ""
        except Exception:
            note = ""
    return thumb, note, ""


def ensure_soup_shelf(res):
    """食＞スープ。無ければ1本だけ新設する（名指しで頼まれた棚だけ通る口）。"""
    out = ns.shinsetsu("food", "スープ", subtitle="", bin_no=BIN)
    res["diag"].append("スープの棚：%s" % ("既にあった" if out.get("already") else "新設した"))
    sid = (out.get("shelf") or {}).get("id")
    if not sid:
        res["red"].append("スープの棚が作れなかった：%s" % (out.get("red") or out.get("diag")))
    return sid


def pick_exists(url, key, shelf_id, stock_id):
    st, rows = tana._req(url, key,
                         "/rest/v1/admin_shelf_picks?select=id&shelf_id=eq.%s&stock_id=eq.%s&limit=1"
                         % (urllib.parse.quote(shelf_id, safe=""),
                            urllib.parse.quote(stock_id, safe="")))
    return rows[0] if rows else None


def append_jsonl(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def ledger_id(key, shelf_name):
    """★受付番号は「何を・どの棚へ」で決める（棚のidが後から分かっても番号が変わらない）。"""
    import hashlib
    return hashlib.sha1(("1152/" + key + "/" + shelf_name).encode("utf-8")).hexdigest()[:12]


KAGI_JSON = os.path.join(STATUS, "public", "nagekomi_kagi.json")


def kakeru(url, key, res):
    """★棚に**本当に書けるか**を、押す前に1回だけ実測する。

    実測（2026-09-26）：いま在る鍵は SUPABASE_PUBLISHABLE_KEY だけで、
    admin_stock / admin_shelves への INSERT は RLS が 401(42501) で弾く。
    さらに UPDATE は **200を返すのに0行**（RLSが黙って弾く）＝ログだけ成功に見える。
    だから「200が返った」を成功の証拠にしない。**返った行数で判定する。**
    """
    why = ""
    try:
        st, rows = tana._req(url, key, "/rest/v1/admin_stock?select=id,whisper&limit=1")
        if not rows:
            why = "admin_stock が1行も読めない"
        else:
            tid, w = rows[0]["id"], rows[0]["whisper"]
            st2, back = tana._req(
                url, key, "/rest/v1/admin_stock?id=eq.%s" % urllib.parse.quote(tid, safe=""),
                method="PATCH", body={"whisper": w}, prefer="return=representation")
            if not back:
                why = ("いまの鍵（読み取り用）では棚に書けません。"
                       "RLSが黙って弾いています（HTTP200・書けた行は0）")
    except Exception as e:
        why = "書けるか確かめられなかった：%r" % (e,)
    ok = not why
    naoshi = ("Supabaseの画面 → Project Settings → API → service_role の鍵をコピーして、"
              "Macの ~/.tamago/supabase_service_role に貼って保存する（権限600・gitの外）。"
              "そのあと `python3 tools/1152_ireru.py` を1回走らせれば、"
              "この4本はそのまま棚に入ります。")
    try:
        os.makedirs(os.path.dirname(KAGI_JSON), exist_ok=True)
        io.open(KAGI_JSON, "w", encoding="utf-8").write(json.dumps(
            {"at": now(), "kakeru": ok, "why": why, "naoshikata": "" if ok else naoshi,
             "tsukau": "tools/1152_ireru.py"}, ensure_ascii=False, indent=1))
    except Exception:
        pass
    if not ok:
        res["red"].append(why)
        res["naoshikata"] = naoshi
    return ok


def uketsuke():
    """★先に受付だけ済ませる。棚に書けない日でも「何が入ったか」は受付一覧に出す。
    idは固定（key＋棚id）なので、何回走らせても同じ行が増えない。"""
    have = set()
    try:
        for ln in io.open(LEDGER, encoding="utf-8"):
            try:
                have.add(json.loads(ln).get("id"))
            except Exception:
                pass
    except OSError:
        pass
    added = []
    for t in TAMA:
        for world, sid, name in t["shelves"]:
            nid = ledger_id(t["key"], name)
            if nid in have:
                continue
            append_jsonl(LEDGER, {
                "id": nid, "at": now(), "url": t["url"], "memo": t["memo"],
                "shelf": name, "shelfId": sid,
                "copyDirection": None, "status": "inbox", "kind": ns.kind_of(t["url"]),
                "title": t["title"], "channel": t["channel"],
                "source": "1152（たまごさんの口頭指示・貼られたURL）"})
            added.append({"no": nid[:6], "shelf": name, "title": t["title"]})
    return added


def run(dry=False):
    res = {"ranAt": now(), "bin": BIN, "dry": bool(dry),
           "diag": [], "red": [], "ireta": [], "skip": [], "totalYen": 0.0}
    url, key, keyname, where = tana.keys(res["diag"])
    if not url:
        res["red"].append("Supabaseの鍵が見つからない：%s" % where)
        return res

    if not dry:
        res["uketsuke"] = uketsuke()
        if not kakeru(url, key, res):
            res["ok"] = False
            res["diag"].append("★受付だけ済ませました。鍵が入れば同じコマンドで続きから入ります。")
            return res

    soup = ensure_soup_shelf(res) if not dry else "（dry）"
    try:
        tana.shelf_list()          # 名簿を作り直す（反映先URLの world を引けるように）
    except Exception as e:
        res["diag"].append("名簿の作り直しに失敗: %r" % (e,))

    for t in TAMA:
        thumb, note, why = media(t["url"])
        if not thumb:
            res["skip"].append({"key": t["key"], "why": "入れなかった（%s）" % why})
            res["red"].append("%s：%s" % (t["key"], why))
            continue
        res["diag"].append("%s：動画とサムネを実測で確認した" % t["key"])

        g = ns.gates(t["title"], t["whisper"], t["material"] + " " + t["url"],
                     res["diag"], artist=t.get("artist", ""))
        if g:
            res["skip"].append({"key": t["key"], "why": "関所で落ちた：%s" % g})
            res["red"].append("%s：関所で落ちた %s" % (t["key"], g))
            continue

        shelves = []
        for world, sid, name in t["shelves"]:
            sid = sid or (soup if name == "スープ" else None)
            if not sid:
                res["red"].append("%s：棚 %s のidが取れない" % (t["key"], name))
                continue
            shelves.append((world, sid, name))
        if not shelves:
            continue

        if dry:
            res["ireta"].append({"key": t["key"], "title": t["title"], "whisper": t["whisper"],
                                 "thumb": thumb, "shelves": [s[2] for s in shelves], "dry": True})
            continue

        try:
            ex = ns.find_stock_by_ref(url, key, t["url"])
            if ex:
                stock_id, made = ex["id"], False
            else:
                st, rows = tana._req(url, key, "/rest/v1/admin_stock", method="POST",
                                     body={"kind": ns.kind_of(t["url"]), "ref": t["url"],
                                           "title": t["title"], "whisper": t["whisper"],
                                           "thumbnail_url": thumb, "note": note or None},
                                     prefer="return=representation")
                row = rows[0] if isinstance(rows, list) and rows else rows
                stock_id, made = row["id"], True
        except Exception as e:
            res["red"].append("%s：カードが作れなかった %r" % (t["key"], e))
            continue

        for world, sid, name in shelves:
            try:
                p = pick_exists(url, key, sid, stock_id)
                if p:
                    res["diag"].append("%s は %s に既に入っていた（足していない）" % (t["key"], name))
                    pick = p
                    atarashii = False
                else:
                    pick = ns.insert_pick(url, key, sid, stock_id)
                    atarashii = True
            except Exception as e:
                res["red"].append("%s：%s に入れられなかった %r" % (t["key"], name, e))
                continue

            nid = ledger_id(t["key"], name)   # ★受付は uketsuke() が済ませている
            append_jsonl(IRETA, {
                "bin": BIN, "at": now(),
                # ★受付一覧(tools/nagekomi_list.py)は "id" で引く。nagekomiId だけだと
                #   棚に入れたのに「まだ」と出続ける。両方の名前で控える。
                "id": nid, "nagekomiId": nid,
                "stockId": stock_id, "madeStock": made, "pickId": pick["id"],
                "shelfId": sid, "shelf": name, "ref": t["url"], "title": t["title"],
                "genmei": t["title"], "whisper": t["whisper"], "pickStatus": ns.PICK_STATUS,
                "kari": False, "kariWhy": "", "world": world,
                "atarashii": atarashii})
            res["ireta"].append({"key": t["key"], "shelf": name, "no": nid[:6],
                                 "url": "https://joy-relief-station.lovable.app/shelf/%s/%s"
                                        % (world, sid), "new": atarashii})
            made = False   # 2つ目の棚では同じカードを使い回す

    res["iretaCount"] = len(res["ireta"])
    res["ok"] = not res["red"]
    return res


if __name__ == "__main__":
    print(json.dumps(run(dry="--dry" in sys.argv), ensure_ascii=False, indent=1)[:6000])
