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
安全：本番DBへは SELECT（カタログ・Lovable の鍵が生きている日だけ）と Data API の GET ?limit=0（行は読まない）だけ。データは読まない・変えない。課金0。
表の一覧：カタログ ∪ joy-relief-station main の migration（create table）と .from()（~/tamago/jrs_fix で fetch＋git grep。作業場には触らない）。
"""
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


def _rest(url, key, table):
    """GET ?select=*&limit=0（行は1つも読まない）。返り値：ok／kyohi（GRANTが無い）／nai（本番に無い）／その他の文字。"""
    h = {"apikey": key, "Authorization": "Bearer " + key, "Accept": "application/json"}
    q = urllib.request.Request("%s/rest/v1/%s?select=*&limit=0" % (url.rstrip("/"), urllib.parse.quote(table)), headers=h)
    try:
        with urllib.request.urlopen(q, timeout=30) as r:
            return "ok" if r.status in (200, 206) else "HTTP %s" % r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        if "42501" in body or "permission denied" in body.lower():
            return "kyohi"
        if e.code == 404 or "PGRST205" in body or "42P01" in body:
            return "nai"
        if e.code in (401, 403):
            return "kyohi"
        return "HTTP %s" % e.code
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
    """本番のカタログ（Lovable 公式MCP query_database の SELECT）。鍵が死んでいる日は例外。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("tn", os.path.join(HERE, "2210_tanaire.py"))
    tn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tn)
    try:  # houou_sql と同じ：先に Lovable の鍵を巻き直す
        import lovable_token_keeper as keeper
        keeper.ensure_fresh()
    except Exception:  # noqa: BLE001
        pass
    rows = tn.DB().q(CATALOG_SQL)
    if not isinstance(rows, list):
        raise RuntimeError("カタログの返事が表でない：%s" % str(rows)[:160])
    return rows


JRS_CLONE = os.path.expanduser("~/tamago/jrs_fix")
RE_REPO_CREATE = re.compile(r'create\s+table\s+(?:if\s+not\s+exists\s+)?(?:"?public"?\.)?"?([a-z_][a-z0-9_]*)"?', re.I)
RE_REPO_DROP = re.compile(r'drop\s+table\s+(?:if\s+exists\s+)?(?:"?public"?\.)?"?([a-z_][a-z0-9_]*)"?', re.I)
RE_REPO_FROM = re.compile(r'\.from\(\s*[\'"`]([a-z_][a-z0-9_]*)[\'"`]\s*\)')


def _git(*a, timeout=90):
    import subprocess
    p = subprocess.run(["git", "-C", JRS_CLONE] + list(a), capture_output=True, text=True, timeout=timeout)
    return p.stdout if p.returncode in (0, 1) else ""


def repo_tables():
    """joy-relief-station の main から「作ったテーブル（migration）」と「画面・関数が読むテーブル（.from）」を拾う。
    作業場には触らない（fetch で印を進めて、origin/main の中身を git grep で読むだけ）。"""
    _git("fetch", "-q", "origin", "main")
    mig = _git("grep", "-h", "-i", "-E", "create table|drop table", "origin/main", "--", "supabase/migrations")
    made = set(m.group(1).lower() for m in RE_REPO_CREATE.finditer(mig))
    dropped = set(m.group(1).lower() for m in RE_REPO_DROP.finditer(mig))
    code = _git("grep", "-h", "-E", r"\.from\(", "origin/main", "--", "src", "supabase/functions", "scripts")
    used = set(RE_REPO_FROM.findall(code))
    return made - (dropped - used), used


def hantei(tables, kijun, first=False):
    """tables={t:{svc_priv,anon_priv(カタログ・無ければNone), anon(REST), svc(REST), used}}、kijun={t:{anon,svc}}。赤と黄を返す。"""
    aka, ki = [], []
    for t, x in sorted(tables.items()):
        b = kijun.get(t)
        if x.get("svc_priv") is False:
            aka.append("%s：service_role に GRANT が無い" % t)
        if x.get("svc") not in (None, "ok", "nai"):
            aka.append("%s：Data API（service_role）が %s" % (t, x.get("svc")))
        a = x.get("anon")
        if a is None:
            continue
        if b and b.get("anon") == "ok" and a != "ok":
            aka.append("%s：前は公開鍵で読めたのに %s（後退）" % (t, a))
        elif not b and a == "kyohi" and t not in HIKOUKAI:
            msg = "%s：公開鍵で読めない（GRANT が無い）" % t
            if first:
                ki.append(msg + "・既存")
            elif x.get("used"):
                aka.append(msg + "・画面が .from() で読んでいる")
            else:
                ki.append(msg + "・意図して非公開なら HIKOUKAI へ")
        elif not b and a == "nai" and x.get("used") and not first:
            ki.append("%s：画面が読むのに本番に無い（migration 未適用）" % t)
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
    doc = {"at": now(), "label": "全テーブルが Data API で読めるか（Supabase 10/30 仕様変更）", "kiroku": []}
    tables = {}
    try:  # ① 本番のカタログ（Lovable の鍵が生きている日だけ）
        for r in _catalog():
            tables[r["t"]] = {"svc_priv": bool(r.get("svc")), "anon_priv": bool(r.get("anon")), "rls": bool(r.get("rls"))}
        doc["kiroku"].append("カタログ %d" % len(tables))
    except Exception as e:  # noqa: BLE001
        doc["kiroku"].append("カタログは読めなかった（%s）→ リポの一覧と Data API で見る" % str(e)[:120])
    try:  # ② リポの migration と .from()
        made, used = repo_tables()
        for t in made | used:
            tables.setdefault(t, {})["used"] = t in used
        doc["kiroku"].append("リポ：作った %d・読む %d" % (len(made), len(used)))
    except Exception as e:  # noqa: BLE001
        doc["kiroku"].append("リポを読めなかった（%s）" % str(e)[:120])
    try:
        url, svc, pub = _keys([])
    except Exception as e:  # noqa: BLE001
        url = svc = pub = None
        doc["kiroku"].append("鍵が読めない（%s）" % str(e)[:80])
    if url and (pub or svc):  # ③ 本番の Data API を1テーブルずつ（行は読まない）
        for t, x in tables.items():
            x["anon"] = _rest(url, pub, t) if pub else None
            x["svc"] = _rest(url, svc, t) if svc else None
    doc["rest_keys"] = {"anon": bool(url and pub), "service_role": bool(url and svc)}
    kijun = {}
    try:
        kijun = json.load(open(KIJUN, encoding="utf-8"))
    except Exception:
        pass
    first = not kijun
    aka, ki = hantei(tables, kijun, first=first)
    yometa = sum(1 for x in tables.values() if x.get("anon") == "ok")
    doc.update({"tables": len(tables), "anon_ok": yometa, "aka": aka, "ki": ki, "first": first, "rows": tables})
    sokutei = bool(tables) and doc["rest_keys"]["anon"]
    doc["ok"] = sokutei and not aka
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    if sokutei:  # 基準：一度「ok」になったものは ok のまま（読めなくなったら毎回赤にする）
        for t, x in tables.items():
            b = kijun.setdefault(t, {})
            for k in ("anon", "svc"):
                if x.get(k) is not None and b.get(k) != "ok":
                    b[k] = x[k]
        os.makedirs(os.path.dirname(KIJUN), exist_ok=True)
        json.dump(kijun, open(KIJUN, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    if aka or not sokutei:
        line = {"ts": datetime.now(JST).isoformat(timespec="seconds"), "n": "db-grant-" + datetime.now(JST).strftime("%m%d"),
                "type": "db_grant", "title": ("Data API で読めないテーブル %d件" % len(aka)) if aka else "DBの見張りが本番を測れなかった",
                "message": ("；".join(aka[:3]) or "／".join(doc["kiroku"])) + "。詳しくは status/public/db_grant_mimawari.json"}
        open(os.path.join(ST, "dispatch_outbox.jsonl"), "a").write(json.dumps(line, ensure_ascii=False) + "\n")
    print("DB_GRANT_MIMAWARI: テーブル %d・公開鍵で読めた %d・赤 %d・黄 %d（%s）" % (len(tables), yometa, len(aka), len(ki), "／".join(doc["kiroku"])))
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
    tb = {"a": {"anon": "kyohi"}, "b": {"svc_priv": False, "anon": "ok"}, "c": {"anon": "kyohi", "used": True},
          "d": {"anon": "kyohi"}, "admin_runtime_secrets": {"anon": "kyohi", "used": True}, "e": {"anon": "nai", "used": True},
          "f": {"anon": "ok"}}
    aka, ki = hantei(tb, {"a": {"anon": "ok"}, "f": {"anon": "ok"}, "zz": {"anon": "ok"}})
    if {x.split("：")[0] for x in aka} != {"a", "b", "c"} or sorted(x.split("：")[0] for x in ki) != ["d", "e"]:
        print("判定がずれた:", aka, ki); good = False
    aka, ki = hantei({"c": {"anon": "kyohi", "used": True}}, {}, first=True)
    if aka or len(ki) != 1:
        print("初回の判定がずれた:", aka, ki); good = False
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
