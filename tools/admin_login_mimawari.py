#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""編集ログインの毎日見回り（2026-10-10・6回目の再発を受けて）

たまごさん（2026-10-10）：「本当に終わらせてほしい」
  PCで編集しようとすると、またログインを求められる。「@」で入れるはずなのに入れない。
  スマホでは @ を入れると「合言葉が違うようです」。

何をするか（心臓から。1日1回だけ本番を叩く・AIを呼ばない＝0円）：
  1. tools/admin_login_probe.mjs で、本番 /admin に半角「@」と全角「＠」で実際にログインし、
     画面の控えを消して再読込しても入ったまま（Cookieで覚えている）かを、headlessで確かめる。
  2. 落ちていたら自動で直す：本番DBの金庫（admin_runtime_secrets）の行が無い・壊れているなら
     入れ直す（Lovable公式MCPの query_database。鍵は既存の ~/.tamago/lovable_oauth.json）。
     直したあと、もう一度試す。
  3. それでも落ちていたら、進捗表に赤帯（status/public/admin_login_mimawari.json の aka）。
     コードが戻された（金庫の読み口を消された）時はDBでは直らないので、赤のまま原因の当たりを書く。

結果：status/public/admin_login_mimawari.json（合言葉の値は書かない）
使い方：
  python3 tools/admin_login_mimawari.py           # 今すぐ1回
  python3 tools/admin_login_mimawari.py --daily   # 心臓から（前回から20時間未満なら何もしない）
  python3 tools/admin_login_mimawari.py --self-test
"""
import hashlib
import importlib.util
import io
import json
import os
import secrets
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUT = os.path.join(ST, "public", "admin_login_mimawari.json")
GATE = os.path.join(ST, ".admin_login_mimawari_last")
PROBE = os.path.join(HERE, "admin_login_probe.mjs")
ENV_PATH = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")
PASSPHRASE = "@"  # 店主が決めた合言葉（半角）。金庫に入れるのは塩つきSHA-256だけ


def now():
    return time.strftime("%Y-%m-%d %H:%M")


def probe():
    try:
        p = subprocess.run(["node", PROBE], capture_output=True, text=True, timeout=170,
                           env=dict(os.environ, PATH=ENV_PATH))
        line = [x for x in (p.stdout or "").splitlines() if x.startswith("{")][-1]
        return json.loads(line)
    except Exception as e:  # noqa: BLE001
        return {"ok": None, "error": "試せなかった：%s" % str(e)[:160]}


def _db():
    spec = importlib.util.spec_from_file_location("tn", os.path.join(HERE, "2210_tanaire.py"))
    tn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tn)
    return tn, tn.DB()


def verifier_for(passphrase, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt + ":" + hashlib.sha256((salt + passphrase).encode("utf-8")).hexdigest()


def heal():
    """金庫の行を確かめ、無い・壊れている時だけ入れ直す。返り値：やったことの短い説明。"""
    tn, db = _db()
    db.q("""create table if not exists public.admin_runtime_secrets (
  name text primary key, value text not null, updated_at timestamptz not null default now());
alter table public.admin_runtime_secrets enable row level security;
revoke all on table public.admin_runtime_secrets from anon, authenticated;
select 1 as ok""")
    rows = db.q("select name, value from public.admin_runtime_secrets") or []
    have = {r["name"]: r["value"] for r in rows}
    did = []
    v = have.get("admin_password_sha256") or ""
    salt = v.split(":", 1)[0] if ":" in v else ""
    if not salt or verifier_for(PASSPHRASE, salt) != v:
        db.q("insert into public.admin_runtime_secrets (name, value) values ('admin_password_sha256', %s) "
             "on conflict (name) do update set value = excluded.value, updated_at = now() returning name"
             % tn.lit(verifier_for(PASSPHRASE)))
        did.append("合言葉の行を入れ直した")
    if len(have.get("session_secret") or "") < 32:
        db.q("insert into public.admin_runtime_secrets (name, value) values ('session_secret', %s) "
             "on conflict (name) do update set value = excluded.value, updated_at = now() returning name"
             % tn.lit(secrets.token_hex(32)))
        did.append("Cookieの鍵を入れ直した")
    return "、".join(did) or "金庫は正常（DBでは直らない＝コードが戻された可能性）"


def run():
    doc = {"at": now(), "label": "編集ログイン（@ と ＠）", "aka": []}
    r = probe()
    doc["first"] = r
    if r.get("ok") is not True:
        try:
            doc["heal"] = heal()
        except Exception as e:  # noqa: BLE001
            doc["heal"] = "直せなかった：%s" % str(e)[:160]
        time.sleep(310)  # サーバー側の金庫の控え（5分）が切れるのを待つ
        r = probe()
        doc["second"] = r
    doc["ok"] = r.get("ok") is True
    if not doc["ok"]:
        bad = [x.get("name") for x in (r.get("results") or []) if not (x.get("login") and x.get("remembered"))]
        names = {"half": "@", "full": "＠"}
        doc["aka"].append("編集ログインが本番で通りません（%s）。%s" % (
            "・".join(names.get(b, b) for b in bad) or r.get("error") or "不明", doc.get("heal") or ""))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    os.replace(OUT + ".tmp", OUT)
    with open(GATE, "w") as f:
        f.write(now())
    print(json.dumps(doc, ensure_ascii=False))
    return 0 if doc["ok"] else 1


def self_test():
    v = verifier_for("@", "abcd")
    ok = v.startswith("abcd:") and v == verifier_for("@", "abcd") and v != verifier_for("x", "abcd")
    ok = ok and "＠".encode("utf-8") != PASSPHRASE.encode("utf-8")
    print("self-test", "OK" if ok else "NG")
    return 0 if ok else 1


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        return self_test()
    if "--daily" in a:
        try:
            if time.time() - os.path.getmtime(GATE) < 20 * 3600:
                return 0
        except OSError:
            pass
    return run()


if __name__ == "__main__":
    sys.exit(main())
