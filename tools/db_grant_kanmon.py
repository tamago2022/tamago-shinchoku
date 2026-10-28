#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新しいテーブルは GRANT とセット（2026-10-29・Supabase の仕様変更を受けて）

なぜ要るか：
  Supabase 公式告知（changelog 45329「Breaking change: tables not exposed to Data and GraphQL API automatically」）
  2026-10-30 以降に作ったテーブルは、明示的に GRANT しないと Data API（/rest/v1）・GraphQL から読めない。
  既存のテーブルはそのまま。黙って「新しい機能だけ空っぽ」になるので、作る前に止め、作った後も毎日見張る。

テーブルを作る道（2026-10-29 洗い出し）：
  ① joy-relief-station supabase/migrations/*.sql（Lovable のチャット・手書きの migration）
     → 関所：joy-relief-station prebuild の scripts/patrol/check-table-grant.mjs（落ちたら公開が止まる）
  ② 工場から本番DBへ直接流すSQL（Lovable 公式MCP query_database。2210_tanaire.DB／houou_sql／admin_login_mimawari）
     → 関所：kohyou_osu.Lovable._rpc の頭で kensa() を通す（GRANT の無い CREATE TABLE は送らない）
  ③ Supabase のコネクタ（apply_migration／execute_sql）は工場では使っていない（2026-10-29 tools/ を検索して0件）

型（新しいテーブルはこの3行を同じSQLに必ず入れる。RLS で中身を守り、GRANT で道を開ける）：
  alter table public.<名前> enable row level security;
  grant select on public.<名前> to anon, authenticated;      -- 公開で読ませないなら書かない（下の service_role だけ）
  grant all on public.<名前> to service_role;

使い方：
  python3 tools/db_grant_kanmon.py --check-file a.sql [b.sql ...]   GRANT の無い CREATE TABLE があれば exit 2
  python3 tools/db_grant_kanmon.py --mimawari [--daily]             本番の全テーブルが Data API で読めるかを見る（--daily は20時間に1回）
  python3 tools/db_grant_kanmon.py --self-test
結果：status/public/db_grant_mimawari.json（鍵の値・行の中身は書かない）。赤があれば Dispatch へ1行。
安全：本番DBへは SELECT（カタログ）と REST の HEAD だけ。データは読まない・変えない。課金0。
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUT = os.path.join(ST, "public", "db_grant_mimawari.json")
KIJUN = os.path.join(ST, "db_grant", "kijun.json")
STAMP = os.path.join(ST, ".db_grant_mimawari_at")
JST = timezone(timedelta(hours=9))

EXPOSED = {"public"}          # Data API に出しているスキーマ（supabase/config.toml の既定）
API_ROLES = {"anon", "authenticated", "service_role"}
# 公開鍵で読めないのが正しいテーブル（意図して非公開）。ここに無いのに公開鍵で読めなくなったら赤。
HIKOUKAI = {"admin_runtime_secrets"}

IDENT = r'(?:"[^"]+"|[A-Za-z_][\w$]*)'
QNAME = r'%s(?:\s*\.\s*%s)?' % (IDENT, IDENT)
RE_CREATE = re.compile(
    r'\bcreate\s+(?:or\s+replace\s+)?(?:(?:global|local)\s+)?(?:(temp|temporary)\s+)?(?:unlogged\s+)?'
    r'(table|view|materialized\s+view)\s+(?:if\s+not\s+exists\s+)?(' + QNAME + r')', re.I)
RE_GRANT = re.compile(r'\bgrant\s+([^;]*?)\s+on\s+([^;]*?)\s+to\s+([^;]*?)(?:\s+with\s+grant\s+option)?\s*(?:;|$)', re.I | re.S)


def now():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M")


def strip_comments(sql):
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.S)
    return re.sub(r'--[^\n]*', ' ', sql)


def norm(q):
    parts = [p.strip() for p in re.findall(IDENT, q)]
    parts = [p[1:-1] if p.startswith('"') else p.lower() for p in parts]
    if len(parts) == 1:
        parts = ["public"] + parts
    return ".".join(parts[:2])


def kensa(sql):
    """GRANT の無い CREATE TABLE/VIEW（公開スキーマ・一時テーブル以外）の名前を返す。空なら合格。"""
    s = strip_comments(sql or "")
    made = []
    for m in RE_CREATE.finditer(s):
        if m.group(1):  # temp
            continue
        name = norm(m.group(3))
        if name.split(".")[0] in EXPOSED and name not in made:
            made.append(name)
    if not made:
        return []
    granted, all_schema = set(), set()
    for g in RE_GRANT.finditer(s):
        roles = {r.strip().strip('"').lower() for r in g.group(3).split(",")}
        if not (roles & API_ROLES or "public" in roles):
            continue
        target = g.group(2).strip()
        m = re.match(r'all\s+tables\s+in\s+schema\s+(.+)$', target, re.I)
        if m:
            for sc in m.group(1).split(","):
                all_schema.add(sc.strip().strip('"').lower())
            continue
        target = re.sub(r'^(table|materialized\s+view|view)\s+', '', target, flags=re.I)
        for t in re.findall(QNAME, target):
            granted.add(norm(t))
    return [t for t in made if t not in granted and t.split(".")[0] not in all_schema]


def kanmon_msg(missing):
    return ("DB_GRANT_KANMON: GRANT の無い新しいテーブル %s。2026-10-30 以降は GRANT しないと Data API から読めない。"
            "同じSQLに `grant select on <名前> to anon, authenticated;` と `grant all on <名前> to service_role;` を入れる"
            "（型は tools/db_grant_kanmon.py の冒頭）" % "、".join(missing))


# ---------------------------------------------------------------- 毎日の見張り
CATALOG_SQL = """select c.relname as t, c.relkind as k, c.relrowsecurity as rls,
 has_table_privilege('anon', c.oid, 'SELECT') as anon,
 has_table_privilege('authenticated', c.oid, 'SELECT') as authd,
 has_table_privilege('service_role', c.oid, 'SELECT') as svc
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind in ('r','p','v','m') order by 1"""


def _rest_head(url, key, table):
    h = {"apikey": key, "Authorization": "Bearer " + key, "Accept": "application/json"}
    q = urllib.request.Request("%s/rest/v1/%s?select=*&limit=1" % (url.rstrip("/"), urllib.request.quote(table)),
                               method="HEAD", headers=h)
    try:
        with urllib.request.urlopen(q, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # noqa: BLE001
        return "ERR %s" % type(e).__name__


def _keys(diag):
    sys.path.insert(0, HERE)
    import gaibu_copy_naoshi as naoshi  # noqa: E402
    import kagi  # noqa: E402
    url, svc, _kn, _w = naoshi.find_write_key(diag)
    pub = kagi.get("SUPABASE_PUBLISHABLE_KEY")
    url = url or kagi.get("SUPABASE_URL")
    if svc and pub and svc == pub:
        svc = None  # 書ける鍵が見つからず公開鍵に落ちた
    return url, svc, pub


def _catalog():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tn", os.path.join(HERE, "2210_tanaire.py"))
    tn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tn)
    rows = tn.DB().q(CATALOG_SQL)
    if not isinstance(rows, list):
        raise RuntimeError("カタログの返事が表でない：%s" % str(rows)[:160])
    return rows


def hantei(rows, rest, kijun):
    """rows=カタログ、rest={t:{svc:状態,anon:状態}}、kijun=前回までの {t:{anon,authd,svc}}。赤と黄の一覧を返す。"""
    aka, ki = [], []
    for r in rows:
        t = r["t"]
        b = kijun.get(t)
        if not r.get("svc"):
            aka.append("%s：service_role で読めない（GRANT が無い）" % t)
        if b and (b.get("anon") or b.get("authd")) and not (r.get("anon") or r.get("authd")):
            aka.append("%s：前は公開鍵で読めたのに読めなくなった（後退）" % t)
        if not b and not (r.get("anon") or r.get("authd")) and t not in HIKOUKAI:
            ki.append("%s：新しいテーブルが公開鍵で読めない（意図して非公開なら HIKOUKAI へ）" % t)
        x = rest.get(t) or {}
        if r.get("svc") and x.get("svc") not in (None, 200, 206):
            aka.append("%s：Data API（service_role）が %s" % (t, x.get("svc")))
        if (r.get("anon")) and x.get("anon") not in (None, 200, 206):
            aka.append("%s：Data API（公開鍵）が %s" % (t, x.get("anon")))
    return aka, ki


def mimawari(daily=False):
    if daily:
        try:
            if time.time() - os.path.getmtime(STAMP) < 20 * 3600:
                return 0
        except OSError:
            pass
    os.makedirs(os.path.dirname(STAMP), exist_ok=True)
    open(STAMP, "w").close()
    doc = {"at": now(), "label": "全テーブルが Data API で読めるか（Supabase 10/30 仕様変更）", "aka": [], "ki": []}
    try:
        rows = _catalog()
    except Exception as e:  # noqa: BLE001
        doc["error"] = "カタログが読めない：%s" % str(e)[:200]
        rows = []
    diag = []
    rest = {}
    try:
        url, svc, pub = _keys(diag)
    except Exception as e:  # noqa: BLE001
        url = svc = pub = None
        doc["rest_error"] = str(e)[:160]
    if url:
        for r in rows:
            t = r["t"]
            rest[t] = {"svc": _rest_head(url, svc, t) if svc else None,
                       "anon": _rest_head(url, pub, t) if (pub and r.get("anon")) else None}
    kijun = {}
    try:
        kijun = json.load(open(KIJUN, encoding="utf-8"))
    except Exception:
        pass
    aka, ki = hantei(rows, rest, kijun)
    doc.update({"tables": len(rows), "aka": aka, "ki": ki,
                "rest_keys": {"service_role": bool(svc) if url else False, "anon": bool(pub) if url else False},
                "rows": [dict(r, rest=rest.get(r["t"])) for r in rows]})
    doc["ok"] = bool(rows) and not aka and "error" not in doc
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if rows:  # 基準は「読めた」ものを足していくだけ（読めなくなったものを基準から消さない＝後退を毎回赤にする）
        for r in rows:
            b = kijun.setdefault(r["t"], {})
            for k in ("anon", "authd", "svc"):
                b[k] = bool(b.get(k)) or bool(r.get(k))
        os.makedirs(os.path.dirname(KIJUN), exist_ok=True)
        json.dump(kijun, open(KIJUN, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    if aka or doc.get("error"):
        line = {"ts": datetime.now(JST).isoformat(timespec="seconds"), "n": "db-grant-" + datetime.now(JST).strftime("%m%d"),
                "type": "db_grant", "title": "Data API で読めないテーブル %d件" % len(aka),
                "message": ("；".join(aka[:3]) or doc.get("error") or "") + "。詳しくは status/public/db_grant_mimawari.json"}
        open(os.path.join(ST, "dispatch_outbox.jsonl"), "a").write(json.dumps(line, ensure_ascii=False) + "\n")
    print("DB_GRANT_MIMAWARI: テーブル %d・赤 %d・黄 %d%s" % (len(rows), len(aka), len(ki),
                                                         ("・" + doc["error"]) if doc.get("error") else ""))
    return 0 if doc["ok"] else 2


# ---------------------------------------------------------------- 逆テスト
def self_test():
    ng = [
        "create table public.foo (id int);",
        "CREATE TABLE IF NOT EXISTS foo (id int); alter table foo enable row level security;",
        'create table "public"."Bar" (id int); grant select on public.bar to anon;',  # 大文字の取り違え
        "create table public.a (id int); create table public.b (id int); grant all on public.a to service_role;",
        "create view public.v as select 1; grant select on public.other to anon;",
        "create table public.c (id int); grant select on public.c to some_other_role;",
    ]
    ok_ = [
        "create table public.foo (id int); grant select on public.foo to anon, authenticated; grant all on public.foo to service_role;",
        "CREATE TABLE IF NOT EXISTS foo (id int);\nGRANT ALL ON TABLE foo TO service_role;",
        "create table public.a (id int); create table public.b (id int); grant select on public.a, public.b to anon;",
        "create temp table t (id int);",
        "create table private.x (id int);",
        "-- create table public.zzz (id int);\nselect 1",
        "create table public.d (id int); grant select on all tables in schema public to authenticated;",
        'create table "public"."Bar" (id int); grant all on "public"."Bar" to service_role;',
        "alter table public.admin_stock add column if not exists x text;",
        "select * from pg_class",
    ]
    good = True
    for s in ng:
        if not kensa(s):
            print("NG を見逃した:", s); good = False
    for s in ok_:
        if kensa(s):
            print("OK を止めた:", s, kensa(s)); good = False
    rows = [{"t": "a", "anon": True, "authd": True, "svc": True}, {"t": "b", "anon": False, "authd": False, "svc": False},
            {"t": "c", "anon": False, "authd": False, "svc": True}, {"t": "admin_runtime_secrets", "anon": False, "authd": False, "svc": True}]
    aka, ki = hantei(rows, {"a": {"svc": 200, "anon": 401}}, {"c": {"anon": True}, "admin_runtime_secrets": {"svc": True}})
    want_aka = {"b", "c", "a"}
    if {x.split("：")[0] for x in aka} != want_aka or [x.split("：")[0] for x in ki] != ["b"]:
        print("判定がずれた:", aka, ki); good = False
    print("DB_GRANT_SELFTEST:", "PASS" if good else "FAIL")
    return 0 if good else 1


def main(argv):
    if "--self-test" in argv:
        return self_test()
    if "--mimawari" in argv:
        return mimawari(daily="--daily" in argv)
    if "--check-file" in argv:
        bad = 0
        for p in argv[argv.index("--check-file") + 1:]:
            miss = kensa(open(p, encoding="utf-8").read())
            if miss:
                bad += 1
                print("%s: %s" % (p, kanmon_msg(miss)))
        print("DB_GRANT_KANMON_RESULT:", "FAIL" if bad else "PASS")
        return 2 if bad else 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
