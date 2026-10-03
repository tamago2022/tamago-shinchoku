#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2210番【投げ込み箱 → 本番の棚】投げた瞬間に棚へ書き込む係。鍵もたまごさんの手も要らない。

■ たまごさん（2026-10-01・原文）
  「スマホで入れたら1秒で入るのに、全部まだ『作業中』になってる。こんなのすぐに終わらせてほしい。
    そもそも『作業中』って言うほどの手間でもないよね。」
  → **段階は2つだけ：「済（棚のリンク）」か「入らない（理由1語）」。**後回しの周回はやめた。
    箱 → 中継所 → command_ingest → nagekomi.add() → ここの ima() を**その場で**呼ぶ。

■ 道（2026-10-01・4つ並べて実測で決めた）
  ① Edge Function 新設 → pushでは本番に出ない（#1386実測）。不採用
  ② 管理用サーバー関数を合言葉で叩く → Unauthorized。合言葉は探さない。不採用
  ③ 公開台帳を読むサーバー関数を足す → コード変更＋公開が要る。控え
  ④ ★Lovable 公式MCP の query_database（Lovable Cloud のDBに直接SQL）。service_role不要・0円
  ★速さのため、棚1つにつき**SQL1本**で「棚を引く→カードを作る（無ければ）→結ぶ」まで済ませる。

■ 守ること
  ・画面の［URLから追加］［棚に入れる］と同じ行（admin_stock / admin_shelf_picks status=candidate）。
  ・同じカード（kind+ref）は作り直さない。同じ棚に同じカードは結ばない。
  ・本番の棚は**サムネの無いカードを隠す**（worlds.ts filterPlayableCards）。サムネは 1152番 media() で実測。
  ・棚が50枚以上なら入れない（本番の管理画面は50枚を超えると古いカードを消しにいくため）＝理由「満杯」。
  ・機械の試し投げ（nageta=test）は入れない。

■ 理由の1語（たまごさんに見せるのはこれだけ）
  棚未定 … 行き先の棚が決まっていない      棚なし … 指定の棚が本番に無い
  満杯   … 棚が50枚                        サムネ無し … 画像が取れない（棚に出せない）
  動画切れ … YouTubeが見られない            URL無し … ひとことだけ
  失敗   … 書き込みで転んだ（次の周回でもう一度）

使い方:
  python3 tools/2210_tanaire.py            … 「済」でないものを全部やり直す
  python3 tools/2210_tanaire.py --only <id>
  python3 tools/2210_tanaire.py --daily    … 5分便から（取りこぼしの拾い直しだけ。30分に1回）
"""
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import kohyou_osu as kohyou  # noqa: E402  Lovable MCP の口（鍵の巻き直しつき）

JST = timezone(timedelta(hours=9))
ST = os.path.join(REPO, "status")
LEDGER = os.path.join(ST, "nagekomi.jsonl")
IRETA = os.path.join(ST, "nagekomi_ireta.jsonl")
KEKKA = os.path.join(ST, "public", "nagekomi_kekka.json")
OUT = os.path.join(ST, "public", "nagekomi_shelf.json")
GATE = os.path.join(ST, ".2210_tanaire_last")
PID = kohyou.MATO["ごきげん補給所"]["project_id"]
HONBAN = "https://joy-relief-station.lovable.app"
CAP = 50
RE_YT = re.compile(r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})")
RE_X = re.compile(r"^https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/([^/?#]+)/status/(\d+)", re.I)
WORLD = {"食": "food", "食べ物": "food", "音楽": "music", "かわいい": "cute",
         "笑い": "laugh", "旅": "travel", "ダンス": "dance"}


def now():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M")


class DB(object):
    """Lovable 公式MCP の query_database だけを呼ぶ（エージェント・ビルドは呼ばない）。"""

    def __init__(self):
        self.lv = kohyou.Lovable()
        if not self.lv.ok():
            raise RuntimeError("Lovable の鍵（~/.tamago/lovable_oauth.json）が無い")
        self.lv.hello()
        self.lv._rpc("notifications/initialized", {})

    def q(self, sql, tries=2):
        for i in range(tries):
            raw = self.lv._rpc("tools/call", {"name": "query_database",
                                              "arguments": {"project_id": PID, "sql": sql}})
            try:
                line = [x for x in raw.splitlines() if x.startswith("data: ")][-1][6:]
                res = json.loads(line)["result"]
            except Exception:
                if i + 1 < tries:
                    time.sleep(1)
                    continue
                raise RuntimeError("query_database の返事が読めない：%s" % (raw or "")[:200])
            txt = "".join(c.get("text", "") for c in (res.get("content") or []))
            if res.get("isError"):
                # 499（向こうが途中で切った）は1回だけやり直す。SQLは冪等に書いてある
                if "499" in txt and i + 1 < tries:
                    time.sleep(1)
                    continue
                raise RuntimeError("SQLが通らない：%s" % txt[:200])
            try:
                d = json.loads(txt)
            except Exception:
                return txt
            if isinstance(d, dict):
                for k in ("rows", "result", "data"):
                    if isinstance(d.get(k), list):
                        return d[k]
            return d


def lit(s):
    if s is None:
        return "NULL"
    return "'" + str(s).replace("\x00", "").replace("'", "''") + "'"


def read_jsonl(p):
    out = []
    try:
        for line in io.open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except OSError:
        pass
    return out


def _media(url):
    """1152番 media() が正本（YouTube=サムネ実測＋oEmbed／X=cdn.syndication でサムネ＋公式埋め込み）。"""
    import importlib
    return importlib.import_module("1152_ireru").media(url)


def media_hayai(url, r):
    """★その場で入れるための速い版（1152番 media() と同じ判定を、待ち時間の長い所だけ省く）。
      YouTube … 箱が受け取った時点で YouTube Data API で生きているのを確かめ済み（metaMissing が無い）なら、
                サムネは決まった場所（img.youtube.com/vi/<id>/hqdefault.jpg）なので取りに行かない。
      X       … cdn.syndication 1本だけ（動画が入っているか・サムネ）。埋め込みHTMLは後ろで埋める。
      それ以外・判定できないときは正本の media() に任せる。"""
    m = RE_YT.search(url)
    if m and r.get("videoId") and not r.get("metaMissing"):
        return "https://img.youtube.com/vi/%s/hqdefault.jpg" % m.group(1), None, ""
    mx = RE_X.match(url)
    if mx:
        try:
            import importlib
            ir = importlib.import_module("1152_ireru")
            code, body = ir._get("https://cdn.syndication.twimg.com/tweet-result?id=%s&lang=ja&token=a" % mx.group(2), timeout=8)
            if code == 200 and body:
                d = json.loads(body)
                md = d.get("mediaDetails") or []
                kinds = [x.get("type") for x in md]
                if "video" not in kinds and "animated_gif" not in kinds:
                    return None, None, "この投稿に動画が入っていない（%s）" % (kinds or "メディア無し")
                thumb = (d.get("video") or {}).get("poster") or (md[0].get("media_url_https") if md else None)
                if thumb:
                    return thumb, (r.get("_embed") or None), ""
        except Exception:
            pass
    return _media(url)


def note_ato(ref, url):
    """Xの公式埋め込みHTMLを後ろで埋める（たまごさんを待たせない）。"""
    def go():
        try:
            import importlib
            ir = importlib.import_module("1152_ireru")
            code, body = ir._get("https://publish.twitter.com/oembed?url=%s&omit_script=1&dnt=true"
                                 % urllib.parse.quote(url, safe=""))
            html = json.loads(body).get("html") if code == 200 and body else ""
            if html:
                DB().q("update admin_stock set note = %s where kind = 'x' and ref = %s and note is null"
                       % (lit(html), lit(ref)))
        except Exception:
            pass
    import threading
    threading.Thread(target=go, daemon=True).start()


def clean_title(t):
    t = str(t or "").replace("&mdash;", "—").replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
    t = re.sub(r"\s*(pic\.twi\w*|https?://)\S*[\s\S]*$", "", t)
    t = re.sub(r"\s*—\s*.*\(@[^)]+\).*$", "", t)
    return re.sub(r"\s+", " ", t).strip()


def page_url(row):
    """本番の棚ページ。既存棚の受け皿なら元の棚id、店主が作った棚なら db-<uuid>（publicShelves:507）。"""
    sid = row.get("extends_shelf_id") or ("db-" + row["shelf_db"])
    return "%s/shelf/%s/%s" % (HONBAN, row.get("world") or "", sid), sid


# ★棚1つにつき SQL 1本。棚を引く→カードが無ければ作る→（満杯でなく、まだ結んでいなければ）結ぶ。
#   データを変えるCTEは必ず走るので、カードを作るのは「棚が見つかったとき」だけに絞ってある。
SQL_IRERU = """
with sh as (
  select id, world, title, extends_shelf_id from admin_shelves
  where (%(sid)s <> '' and (id::text = %(sid)s or extends_shelf_id = %(sid)s))
     or (%(sid)s = '' and %(stitle)s <> '' and title = %(stitle)s)
  order by (id::text = %(sid)s) desc, (extends_shelf_id = %(sid)s) desc, position nulls last
  limit 1),
ex as (select id from admin_stock where kind = %(kind)s and ref = %(ref)s limit 1),
fix as (update admin_stock set thumbnail_url = coalesce(thumbnail_url, %(thumb)s), note = coalesce(note, %(note)s)
        where id in (select id from ex) and (thumbnail_url is null or note is null) returning id),
ins as (insert into admin_stock (kind, ref, title, thumbnail_url, note)
        select %(kind)s, %(ref)s, %(title)s, %(thumb)s, %(note)s
        where not exists (select 1 from ex) and exists (select 1 from sh) returning id),
st as (select id from ex union all select id from ins),
have as (select p.id from admin_shelf_picks p join sh on p.shelf_id = sh.id join st on p.stock_id = st.id),
cnt as (select count(*)::int n from admin_shelf_picks p join sh on p.shelf_id = sh.id
        where p.status in ('candidate','fixed')),
pk as (insert into admin_shelf_picks (shelf_id, stock_id, position, status, pinned)
       select sh.id, st.id,
              coalesce((select max(position) from admin_shelf_picks where shelf_id = sh.id), -1) + 1,
              'candidate', false
       from sh, st
       where not exists (select 1 from have) and (select n from cnt) < %(cap)s
       returning id)
select sh.id::text as shelf_db, sh.world, sh.title, sh.extends_shelf_id,
       (select id::text from st limit 1) as stock_id,
       (select id::text from have limit 1) as have_id,
       (select id::text from pk limit 1) as pick_id,
       (select n from cnt) as n
from sh
"""


def wants_of(r):
    if isinstance(r.get("shelves"), list) and r.get("shelves"):
        return [w if isinstance(w, dict) else {"title": w} for w in r["shelves"]]
    if r.get("shelfId") or r.get("shelf"):
        return [{"id": r.get("shelfId"), "title": r.get("shelf")}]
    return []


def ensure_named_shelf(db, r, want_title):
    """★たまごさんが「食＞スープ」と世界と棚を名指ししたときだけ棚を作る（機械の推測では作らない）。"""
    mm = re.match(r"^\s*(食|食べ物|音楽|かわいい|笑い|旅|ダンス)\s*[＞>]\s*(.+?)\s*$", str(r.get("memo") or ""))
    if not (mm and want_title and mm.group(2) == str(want_title).strip()):
        return False
    wid = WORLD[mm.group(1)]
    db.q("insert into admin_shelves (world, title, position) select %s, %s, coalesce(max(position), 0) + 1 "
         "from admin_shelves where world = %s and not exists (select 1 from admin_shelves where world = %s and title = %s)"
         % (lit(wid), lit(want_title), lit(wid), lit(wid), lit(want_title)))
    return True


def ireru(db, r):
    """1件を棚へ。返り値 {ok, why1, why, links:[{title,url}], rec}。"""
    rid = r.get("id")
    url = str(r.get("url") or "").strip()
    if not url.startswith("https://"):
        return {"ok": False, "why1": "URL無し", "why": "ひとことだけ届いています"}
    wants = wants_of(r)
    if not wants:
        return {"ok": False, "why1": "棚未定", "why": "行き先の棚がまだ決まっていません"}
    m = RE_YT.search(url)
    mx = RE_X.match(url)
    kind = "youtube" if m else ("x" if mx else "link")
    ref = ("https://www.youtube.com/watch?v=%s" % m.group(1)) if m else \
          (("https://x.com/%s/status/%s" % (mx.group(1), mx.group(2))) if mx else url)
    tm = time.time()
    try:
        thumb, note, why_m = media_hayai(url, r)
    except Exception as e:  # noqa: BLE001
        thumb, note, why_m = None, None, "サムネを調べる係が転んだ（%s）" % type(e).__name__
    t_media = round(time.time() - tm, 1)
    if not thumb:
        w1 = "動画切れ" if (m and "oEmbed" in str(why_m)) else "サムネ無し"
        return {"ok": False, "why1": w1, "why": why_m}
    title = clean_title(r.get("title"))
    if not title and mx:
        title = "@%s のポスト" % mx.group(1)
    title = (title or ref)[:300]

    got, why1, why = [], "", ""
    for w in wants:
        sid = str(w.get("id") or "").strip()
        stitle = str(w.get("title") or "").strip()
        args = {"sid": lit(sid), "stitle": lit(stitle), "kind": lit(kind), "ref": lit(ref),
                "title": lit(title), "thumb": lit(thumb), "note": lit(note or None), "cap": CAP}
        rows = db.q(SQL_IRERU % args)
        if not rows and ensure_named_shelf(db, r, stitle):
            args["sid"] = lit("")
            rows = db.q(SQL_IRERU % args)
        if not rows:
            why1, why = "棚なし", "棚「%s」が本番に無い" % (stitle or sid)
            continue
        row = rows[0]
        if not (row.get("pick_id") or row.get("have_id")):
            why1, why = "満杯", "棚「%s」が%s枚で満杯" % (row.get("title"), row.get("n"))
            continue
        link, page_id = page_url(row)
        got.append({"title": row.get("title"), "url": link, "shelfId": page_id, "world": row.get("world"),
                    "dbShelfId": row.get("shelf_db"), "pickId": row.get("pick_id") or row.get("have_id"),
                    "stockId": row.get("stock_id")})
    if not got:
        return {"ok": False, "why1": why1 or "失敗", "why": why}
    if mx and not note:
        note_ato(ref, url)
    rec = {"bin": "2210", "at": now(), "id": rid, "nagekomiId": rid, "stockId": got[0]["stockId"],
           "pickId": got[0]["pickId"], "shelfId": got[0]["shelfId"], "dbShelfId": got[0]["dbShelfId"],
           "shelf": got[0]["title"], "world": got[0]["world"],
           "hokaShelves": [{"shelfId": g["shelfId"], "shelf": g["title"], "world": g["world"]} for g in got[1:]],
           "ref": ref, "title": title, "titleAfter": title, "pickStatus": "candidate",
           "copyBefore": str(r.get("titleRaw") or r.get("title") or "")[:400], "via": "query_database"}
    return {"ok": True, "why1": "", "why": "", "links": [{"title": g["title"], "url": g["url"]} for g in got],
            "rec": rec, "partial": why1, "t_media": t_media}


def kekka_write(rid, k):
    try:
        d = json.load(io.open(KEKKA, encoding="utf-8"))
    except Exception:
        d = {}
    d[rid] = {"at": now(), "ok": k.get("ok"), "why1": k.get("why1") or "", "why": k.get("why") or "",
              "links": k.get("links") or [], "byou": k.get("byou"), "t_media": k.get("t_media")}
    os.makedirs(os.path.dirname(KEKKA), exist_ok=True)
    tmp = KEKKA + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
    os.replace(tmp, KEKKA)


def sumi_ids():
    return {(r.get("nagekomiId") or r.get("id")) for r in read_jsonl(IRETA) if not r.get("modoshiAt")}


def kiroku(rid, k):
    """結果を控える：済なら ireta に1行。どちらでも kekka に1行。受付一覧も作り直す。"""
    if k.get("ok") and rid not in sumi_ids():
        with io.open(IRETA, "a", encoding="utf-8") as f:
            f.write(json.dumps(k["rec"], ensure_ascii=False) + "\n")
    kekka_write(rid, k)
    try:
        import nagekomi_list
        nagekomi_list.write() if hasattr(nagekomi_list, "write") else None
    except Exception:
        pass


_DB = {"db": None, "at": 0.0}


def db_kept():
    """★中継所の中では Lovable との接続を使い回す（毎回の挨拶で数秒かかっていたため）。30分で張り直す。
    切れていたら ima() が1回だけ張り直してやり直す。"""
    if _DB["db"] is None or time.time() - _DB["at"] > 1800:
        _DB["db"], _DB["at"] = DB(), time.time()
    return _DB["db"]


def ima(rid, db=None, row=None):
    """★投げた瞬間に呼ぶ口（nagekomi.add から）。その場で棚へ入れて結果を返す。"""
    t0 = time.time()
    r = row
    if r is None:
        rows = [x for x in read_jsonl(LEDGER) if x.get("id") == rid]
        if not rows:
            return {"ok": False, "why1": "失敗", "why": "台帳に見当たらない"}
        r = rows[-1]
    if str(r.get("nageta") or "") == "test":
        return {"ok": False, "why1": "試し", "why": "機械の試し投げは棚に入れない"}
    try:
        try:
            k = ireru(db or db_kept(), r)
        except RuntimeError:
            _DB["db"] = None            # 接続が切れていたら1回だけ張り直す
            k = ireru(db or db_kept(), r)
    except Exception as e:  # noqa: BLE001
        k = {"ok": False, "why1": "失敗", "why": str(e)[:200]}
        # ★2026-10-04：鍵切れは専門用語を見せず、「消えていない・直れば自動で入る」を言う
        if "鍵" in str(e):
            k = {"ok": False, "why1": "鍵切れ",
                 "why": "棚へ書く鍵が切れています。投げた分は台帳に残っていて、鍵が戻ると自動で棚に入ります"}
    k["byou"] = round(time.time() - t0, 1)
    kiroku(rid, k)
    return k


def run(only=None):
    """取りこぼし・前の分の拾い直し。「済」でないものを全部やる。"""
    res = {"ranAt": now(), "bin": "2210", "via": "Lovable公式MCP query_database",
           "sumi": [], "hairanai": [], "red": [], "totalYen": 0.0}
    done = sumi_ids()
    rows = read_jsonl(LEDGER)
    if only:
        rows = [r for r in rows if r.get("id") == only]
    todo = [r for r in rows if r.get("id") and r["id"] not in done and str(r.get("nageta") or "") != "test"]
    if not todo:
        res["ok"] = True
        return res
    db = DB()
    for r in todo:
        try:
            k = ireru(db, r)
        except Exception as e:  # noqa: BLE001
            k = {"ok": False, "why1": "失敗", "why": str(e)[:200]}
        kiroku(r["id"], k)
        (res["sumi"] if k.get("ok") else res["hairanai"]).append(
            {"id": r["id"], "why1": k.get("why1"), "why": k.get("why"), "links": k.get("links") or []})
    res["ok"] = True
    return res


def main():
    a = sys.argv[1:]
    only = a[a.index("--only") + 1] if "--only" in a else None
    if "--daily" in a:
        try:
            if time.time() - os.path.getmtime(GATE) < 30 * 60:
                return 0
        except OSError:
            pass
        try:
            io.open(GATE, "w", encoding="utf-8").write(now())
        except OSError:
            pass
    res = run(only=only)
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
