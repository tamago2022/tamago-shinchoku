#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2210番【投げ込み箱 → 本番の棚】鍵をMacに置かず、たまごさんの手も使わずに入れる係。

■ 道の選び方（2026-10-01・4つ並べて実測で決めた）
  ① Supabase Edge Function を新設（実行環境に SUPABASE_SERVICE_ROLE_KEY が既定で入る＝公式）
     → GitHubにpushしても Edge Function は本番に出ない（#1386 で4日届かなかった実測）。
       CLIデプロイ用の鍵も無い。Lovableエージェントは禁止。→ 不採用
  ② 既存の管理用サーバー関数（adminAddStockFromUrl／adminAddPick）を合言葉で叩く
     → 実測で Unauthorized（合言葉が変わっている）。合言葉を探して使うことはしない。→ 不採用
  ③ 本番に「公開台帳を読んで棚へ入れる」サーバー関数を1本足す → コード変更＋公開が要る。控え
  ④ ★Lovable 公式MCP の query_database（Lovable Cloud のDBに直接SQL）
     → 鍵は既にMacにある Lovable のOAuth（lovable_12h.py が12時間ごとに巻き直している）。
       service_role 不要・コード変更不要・公開不要・エージェント不使用（0円）。★採用

■ 入れ方（画面の［URLから追加］［棚に入れる］と同じ行を作る）
  admin_stock  : kind / ref / title / thumbnail_url（同じ kind+ref があれば作らない）
  admin_shelf_picks : shelf_id / stock_id / position=末尾 / status='candidate' / pinned=false
  ★棚が50枚以上なら入れない（本番は50枚を超えると古いカードを押し出して消す）。
  ★機械の試し投げ（nageta=test：Bon Jovi / Keyboard Cat / Skrillex）は入れない。
  ★YouTubeは oEmbed で動画が生きているかを確かめてから入れる。
  入れた分は status/nagekomi_ireta.jsonl に控える（受付一覧がそのまま拾う形）。

使い方:
  python3 tools/2210_tanaire.py            … 未処理を全部（上限20）
  python3 tools/2210_tanaire.py --dry      … 何を入れるかだけ
  python3 tools/2210_tanaire.py --only <id>
  python3 tools/2210_tanaire.py --daily    … 5分便から。30分に1回だけ動く
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
sys.path.insert(0, HERE)
import kohyou_osu as kohyou  # noqa: E402  Lovable MCP の口（鍵の巻き直しつき）

JST = timezone(timedelta(hours=9))
ST = os.path.join(REPO, "status")
LEDGER = os.path.join(ST, "nagekomi.jsonl")
IRETA = os.path.join(ST, "nagekomi_ireta.jsonl")
OUT = os.path.join(ST, "public", "nagekomi_shelf.json")
GATE = os.path.join(ST, ".2210_tanaire_last")
PID = kohyou.MATO["ごきげん補給所"]["project_id"]
CAP = 50
MAX = 20
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
RE_YT = re.compile(r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})")
RE_X = re.compile(r"^https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/([^/?#]+)/status/(\d+)", re.I)
# ★MCPで呼んでよい道具（これ以外は呼ばない。send_message＝エージェントは絶対に呼ばない）
YURUSU = ("query_database", "get_database_status")


def now():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M")


class DB(object):
    def __init__(self):
        self.lv = kohyou.Lovable()
        if not self.lv.ok():
            raise RuntimeError("Lovable の鍵（~/.tamago/lovable_oauth.json）が無い")
        self.lv.hello()
        self.lv._rpc("notifications/initialized", {})

    def q(self, sql):
        raw = self.lv._rpc("tools/call", {"name": "query_database",
                                          "arguments": {"project_id": PID, "sql": sql}})
        try:
            line = [x for x in raw.splitlines() if x.startswith("data: ")][-1][6:]
            res = json.loads(line)["result"]
        except Exception:
            raise RuntimeError("query_database の返事が読めない：%s" % (raw or "")[:300])
        txt = "".join(c.get("text", "") for c in (res.get("content") or []))
        if res.get("isError"):
            raise RuntimeError("SQLが通らない：%s" % txt[:300])
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
    """SQLの文字列リテラル（' を二重に）。None は NULL。"""
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


def oembed_youtube(ref):
    try:
        u = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(ref, safe="")
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "tamago-2210"}),
                                    timeout=20) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def _media(url):
    """1152番 media() が正本（YouTube=サムネ実測＋oEmbed／X=cdn.syndication でサムネ＋公式埋め込み）。"""
    import importlib
    return importlib.import_module("1152_ireru").media(url)


def hosei(db, res):
    """★前に入れた分で、サムネが空のまま（＝本番の棚で隠れている）カードを埋め直す。"""
    for r in read_jsonl(IRETA):
        if r.get("via") != "query_database" or not r.get("stockId"):
            continue
        got = db.q("select thumbnail_url, note from admin_stock where id = %s" % lit(r["stockId"]))
        if not got or got[0].get("thumbnail_url"):
            continue
        thumb, note, why = _media(r.get("ref") or "")
        if not thumb:
            res["machi"].append({"id": r.get("id"), "why": "サムネが取れない：%s" % why})
            continue
        db.q("update admin_stock set thumbnail_url = %s, note = coalesce(note, %s) where id = %s"
             % (lit(thumb), lit(note or None), lit(r["stockId"])))
        res["diag"].append("%s：サムネを埋めた" % r.get("id"))


def resolve_shelf(db, want):
    sid = str((want or {}).get("id") or "").strip()
    title = str((want or {}).get("title") or "").strip()
    cols = "id, world, title, extends_shelf_id"
    if sid and UUID.match(sid):
        r = db.q("select %s from admin_shelves where id = %s" % (cols, lit(sid)))
        if r:
            return r[0]
    if sid:
        r = db.q("select %s from admin_shelves where extends_shelf_id = %s" % (cols, lit(sid)))
        if len(r) == 1:
            return r[0]
    if title:
        r = db.q("select %s from admin_shelves where title = %s" % (cols, lit(title)))
        if len(r) == 1:
            return r[0]
    return None


def run(dry=False, only=None):
    res = {"ranAt": now(), "bin": "2210", "dry": dry,
           "via": "Lovable公式MCP query_database（service_role不要・人の手不要）",
           "diag": [], "red": [], "ireta": [], "mitei": [], "machi": [], "manpai": [], "totalYen": 0.0}
    done = set()
    for r in read_jsonl(IRETA):
        if not r.get("modoshiAt") and not r.get("dry"):
            done.add(r.get("nagekomiId") or r.get("id"))
    rows = read_jsonl(LEDGER)
    if only:
        rows = [r for r in rows if r.get("id") == only]
    kikai = [r for r in rows if str(r.get("nageta") or "") == "test"]
    todo = [r for r in rows if r.get("id") and r["id"] not in done and str(r.get("nageta") or "") != "test"]
    res["diag"].append("台帳 %d行／機械の試し投げ %d件は入れない／未処理 %d件" % (len(rows), len(kikai), len(todo)))
    db = DB()
    if not dry:
        try:
            hosei(db, res)
        except Exception as e:  # noqa: BLE001
            res["red"].append("サムネの埋め直しでつまずいた：%s" % str(e)[:200])
    if not todo:
        res["ok"] = not res["red"]
        return res
    for r in todo[:MAX]:
        url = str(r.get("url") or "").strip()
        if not url.startswith("https://"):
            res["mitei"].append({"id": r["id"], "why": "URLが未定（ひとことだけ）"})
            continue
        wants = r.get("shelves") if isinstance(r.get("shelves"), list) and r.get("shelves") else \
            ([{"id": r.get("shelfId"), "title": r.get("shelf")}] if (r.get("shelfId") or r.get("shelf")) else [])
        shelves = []
        for w in wants:
            s = resolve_shelf(db, w if isinstance(w, dict) else {"title": w})
            if s and s["id"] not in [x["id"] for x in shelves]:
                shelves.append(s)
            elif not s and not dry:
                # ★たまごさんが「食＞スープ」のように**世界と棚の名前を名指し**したときだけ棚を作る
                #   （2026-09-25「食べ物の『食』の中に『スープ』っていう棚を作って、これを入れておいて」）。
                #   機械の推測では作らない。同じ世界に同じ名前があれば作らない。
                want_t = (w or {}).get("title") if isinstance(w, dict) else w
                mm = re.match(r"^\s*(食|食べ物|音楽|かわいい|笑い|旅|ダンス)\s*[＞>]\s*(.+?)\s*$", str(r.get("memo") or ""))
                WORLD = {"食": "food", "食べ物": "food", "音楽": "music", "かわいい": "cute",
                         "笑い": "laugh", "旅": "travel", "ダンス": "dance"}
                if mm and want_t and mm.group(2) == str(want_t).strip():
                    wid = WORLD[mm.group(1)]
                    same = db.q("select id, world, title, extends_shelf_id from admin_shelves where world = %s and title = %s"
                                % (lit(wid), lit(want_t)))
                    if not same:
                        same = db.q("insert into admin_shelves (world, title, position) select %s, %s, "
                                    "coalesce(max(position), 0) + 1 from admin_shelves where world = %s "
                                    "returning id, world, title, extends_shelf_id" % (lit(wid), lit(want_t), lit(wid)))
                        res["diag"].append("棚を新設：%s ＞ %s（たまごさんの名指し）" % (mm.group(1), want_t))
                    if same and same[0]["id"] not in [x["id"] for x in shelves]:
                        shelves.append(same[0])
                        continue
                res["diag"].append("%s：棚「%s」が本番に見つからない" % (r["id"], (w or {}).get("title") if isinstance(w, dict) else w))
        if not shelves:
            res["mitei"].append({"id": r["id"], "url": url, "shelf": r.get("shelf"),
                                 "why": "行き先の棚がまだ決まっていません" if not wants else "棚が本番の名簿に無い"})
            continue
        m = RE_YT.search(url)
        mx = RE_X.match(url)
        kind = "youtube" if m else ("x" if mx else "link")
        ref = ("https://www.youtube.com/watch?v=%s" % m.group(1)) if m else \
              (("https://x.com/%s/status/%s" % (mx.group(1), mx.group(2))) if mx else url)
        # 題名の掃除（箱の画面の clean() と同じ切り方）：Xの oEmbed に付く「pic.twitter.com/…」
        # 「&mdash; 名前 (@id) 日付」を落とす。残りが空ならあとで決める
        title = str(r.get("title") or "")
        title = title.replace("&mdash;", "—").replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
        title = re.sub(r"\s*(pic\.twi\w*|https?://)\S*[\s\S]*$", "", title)
        title = re.sub(r"\s*—\s*.*\(@[^)]+\).*$", "", title)
        title = re.sub(r"\s+", " ", title).strip()
        thumb, note = None, None
        if m:
            o = oembed_youtube(ref)
            if not o:
                res["red"].append("%s：動画が生きていない（oEmbedが返らない）" % r["id"])
                continue
            if not title:
                title = " / ".join(x for x in [o.get("title"), o.get("author_name")] if x)
        # ★サムネと埋め込みは 1152番の media()（正本）で実測して取る。
        #   本番の棚は「サムネが解決できないカード」を隠す（worlds.ts filterPlayableCards）。
        #   サムネ無しで入れても棚に出ない＝入れたことにならないので、取れなければ入れずに理由を残す。
        try:
            thumb, note, why_m = _media(url)
        except Exception as e:  # noqa: BLE001
            thumb, note, why_m = None, None, "サムネを調べる係が転んだ（%s）" % type(e).__name__
        if not thumb:
            res["machi"].append({"id": r["id"], "url": url, "why": "サムネが取れないので棚に出せない：%s" % why_m})
            continue
        if not title and mx:
            title = "@%s のポスト" % mx.group(1)
        title = title or ref
        if dry:
            res["ireta"].append({"id": r["id"], "ref": ref, "title": title,
                                 "shelves": [s["title"] for s in shelves], "dry": True})
            continue
        try:
            ex = db.q("select id, thumbnail_url, note from admin_stock where kind = %s and ref = %s limit 1" % (lit(kind), lit(ref)))
            made = not ex
            if ex:
                stock_id = ex[0]["id"]
                # 前に入った分でサムネ／埋め込みが空のものだけ埋める（入っている値は触らない）
                if not ex[0].get("thumbnail_url") or (note and not ex[0].get("note")):
                    db.q("update admin_stock set thumbnail_url = coalesce(thumbnail_url, %s), note = coalesce(note, %s) where id = %s"
                         % (lit(thumb), lit(note or None), lit(stock_id)))
            else:
                got = db.q("insert into admin_stock (kind, ref, title, thumbnail_url, note) values (%s, %s, %s, %s, %s) returning id"
                           % (lit(kind), lit(ref), lit(title[:300]), lit(thumb), lit(note or None)))
                stock_id = got[0]["id"]
            musunda = []
            for s in shelves:
                have = db.q("select id, status from admin_shelf_picks where shelf_id = %s and stock_id = %s"
                            % (lit(s["id"]), lit(stock_id)))
                if have:
                    musunda.append(dict(s, pickId=have[0]["id"], already=True))
                    continue
                n = db.q("select count(*)::int as n from admin_shelf_picks where shelf_id = %s and status in ('candidate','fixed')"
                         % lit(s["id"]))
                cnt = int((n[0] or {}).get("n") or 0) if n else 0
                if cnt >= CAP:
                    res["manpai"].append({"id": r["id"], "shelf": s["title"], "count": cnt,
                                          "why": "棚が%d枚で満杯（入れると他のカードが押し出されて消えるので入れていない）" % cnt})
                    continue
                pk = db.q("insert into admin_shelf_picks (shelf_id, stock_id, position, status, pinned) "
                          "select %s, %s, coalesce(max(position), -1) + 1, 'candidate', false "
                          "from admin_shelf_picks where shelf_id = %s returning id"
                          % (lit(s["id"]), lit(stock_id), lit(s["id"])))
                musunda.append(dict(s, pickId=pk[0]["id"], already=False))
            if not musunda:
                continue

            def page(s):
                # 本番の棚ページのid：既存棚の受け皿なら元の棚id、店主が作った棚なら "db-<uuid>"
                #   （publicShelves.functions.ts:507 と同じ決め）
                return {"shelfId": s.get("extends_shelf_id") or ("db-" + s["id"]), "shelf": s["title"],
                        "world": s.get("world") or "", "pickId": s.get("pickId"), "dbShelfId": s["id"]}
            p0 = page(musunda[0])
            rec = {"bin": "2210", "at": now(), "id": r["id"], "nagekomiId": r["id"],
                   "stockId": stock_id, "madeStock": made, "pickId": p0["pickId"],
                   "shelfId": p0["shelfId"], "dbShelfId": p0["dbShelfId"], "shelf": p0["shelf"],
                   "world": p0["world"], "hokaShelves": [page(s) for s in musunda[1:]],
                   "ref": ref, "title": title, "titleAfter": title, "pickStatus": "candidate",
                   "copyBefore": str(r.get("titleRaw") or r.get("title") or "")[:400],
                   "via": "query_database"}
            with io.open(IRETA, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            res["ireta"].append(rec)
        except Exception as e:
            res["red"].append("%s：%s" % (r["id"], str(e)[:300]))
    res["iretaCount"] = len(res["ireta"])
    res["ok"] = not res["red"]
    return res


def main():
    a = sys.argv[1:]
    dry = "--dry" in a
    only = a[a.index("--only") + 1] if "--only" in a else None
    if "--daily" in a:
        # ★5分便から毎回呼ばれる。実際に動くのは30分に1回（投げてから30分以内に棚へ出る）
        try:
            if time.time() - os.path.getmtime(GATE) < 30 * 60:
                return 0
        except OSError:
            pass
        try:
            io.open(GATE, "w", encoding="utf-8").write(now())
        except OSError:
            pass
    res = run(dry=dry, only=only)
    if not dry:
        with io.open(OUT, "w", encoding="utf-8") as f:
            f.write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1)[:8000])
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
