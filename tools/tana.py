#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1039番【棚の口】投げ込み箱から棚へ入れる、工場(Mac)側の1本道。

たまごさん（2026-09-23・原文）:
  「棚一覧みたいのもボタンでつけてくれたら、そこを押して
    『これとこれとこれ、入れる方向性はこれ、キャッチコピーはこれ』みたいな。」
  「ラバブルでスマホで寝るときに、寝ながら入れようかなっていうときに落ちるわけだよ。」

■ ★決め（なぜこの形か）
  ・**Lovableの画面を一切通らない。**落ちる場所を通らないために作っている。
    棚の正本（admin_shelves / admin_stock）へは REST で直接触る。
    この道は既に `tools/gaibu_copy_naoshi.py` が PATCH で実績を出している。
  ・**GETと、自分が足した行だけのINSERT/DELETE。**他人の行は1文字も触らない。
  ・**入れた行は全部 status/nagekomi_ireta.jsonl に控える。**
    `--modoshi <便番号>` で、その便で入れた分だけを消す（自分が変えた範囲だけ戻す）。
  ・鍵の値はこのファイルから一歩も外へ出さない（ログにも報告にも出さない）。

■ ★棚がどこに在るかの実測（2026-09-23）
  「棚」は2種類ある。ここを混ぜると事故る。
    (1) 作り付けの棚 … joy-relief-station の `src/lib/worlds.ts`（＝コード・git）
    (2) 店主が作った棚 … Supabase の `admin_shelves`（＝データベース・gitに無い）
  そして**カード（＝棚に並ぶ現物）は `admin_stock`**。これもデータベース。
  → だから「投げたURLを棚に入れる」は **git では完結しない。**
     曲データ（coverGuide.ts）だけがコードで、棚の中身はDBにある。
     ★この一点は前の見立て（「棚のデータはコードなのでgitで書ける」）と違う。実測で違った。

■ 使い方
  python3 tools/tana.py --probe            # 棚と列の下見（GETだけ）
  python3 tools/tana.py --list             # 棚一覧を status/public/tana_ichiran.json に書く
  python3 tools/tana.py --ireru <jsonfile> # 入れる（控えを残す）
  python3 tools/tana.py --modoshi <便番号>  # その便で入れた分だけ消す
"""
import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
JST = timezone(timedelta(hours=9))

IRETA = os.path.join(REPO, "status", "nagekomi_ireta.jsonl")
ICHIRAN = os.path.join(REPO, "status", "public", "tana_ichiran.json")


def now():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------------------------ 鍵
def keys(diag):
    """(url, key, 鍵の名前, 見た場所)。値は返り値の外へ出さない。"""
    import gaibu_copy_naoshi as naoshi
    return naoshi.find_write_key(diag)


def _req(url, key, path, method="GET", body=None, prefer=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    h = {"apikey": key, "Authorization": "Bearer " + key, "Accept": "application/json"}
    if data is not None:
        h["Content-Type"] = "application/json"
    if prefer:
        h["Prefer"] = prefer
    req = urllib.request.Request(url + path, data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read().decode("utf-8", "replace")
        return r.status, (json.loads(raw) if raw.strip() else [])


# ------------------------------------------------------------------ 下見
def probe():
    diag = []
    url, key, keyname, where = keys(diag)
    if not url:
        return {"ok": False, "error": where, "diag": diag}
    out = {"ok": True, "keyName": keyname, "keyWhere": where, "diag": diag}
    # ★棚とカードを結んでいる表がどれかを、名前から当てずに一覧で見る
    try:
        req = urllib.request.Request(url + "/rest/v1/",
                                     headers={"apikey": key, "Authorization": "Bearer " + key,
                                              "Accept": "application/openapi+json"})
        with urllib.request.urlopen(req, timeout=45) as r:
            spec = json.loads(r.read().decode("utf-8", "replace"))
        names = sorted(p.strip("/") for p in (spec.get("paths") or {}) if p.strip("/"))
        out["tables"] = [n for n in names if any(
            w in n for w in ("shelf", "shelves", "stock", "card", "cover"))]
        out["tableCount"] = len(names)
    except Exception as e:
        out["tables"] = "取れず: %s" % type(e).__name__

    # ★棚とカードを結んでいる表を、名前を1つずつ叩いて確かめる（当てずっぽうを残さない）
    cand = ["admin_shelf_cards", "admin_shelf_items", "admin_shelf_stock", "shelf_cards",
            "shelf_items", "admin_shelves_stock", "admin_stock_shelves", "shelf_stock",
            "admin_shelf_entries", "public_shelves", "cover_hub_edges"]
    found = {}
    for t in cand:
        try:
            st, rows = _req(url, key, "/rest/v1/%s?select=*&limit=1" % t)
            found[t] = {"status": st, "columns": sorted(rows[0].keys()) if rows else [],
                        "sample": rows[0] if rows else None}
        except urllib.error.HTTPError as e:
            found[t] = {"status": e.code}
        except Exception as e:
            found[t] = {"error": type(e).__name__}
    out["link"] = found

    for table, q in (("admin_shelves", "select=*&limit=3"),
                     ("admin_stock", "select=*&order=created_at.desc&limit=2")):
        try:
            st, rows = _req(url, key, "/rest/v1/%s?%s" % (table, q))
            out[table] = {"status": st, "count": len(rows),
                          "columns": sorted(rows[0].keys()) if rows else [],
                          "sample": rows[0] if rows else None}
        except urllib.error.HTTPError as e:
            out[table] = {"status": e.code, "error": e.read().decode("utf-8", "replace")[:300]}
        except Exception as e:
            out[table] = {"error": "%s: %s" % (type(e).__name__, e)}
    return out


# ------------------------------------------------------------------ 棚一覧
def shelf_list():
    """★実在する棚を全部。手打ちしない。DBの admin_shelves ＋ コードの worlds.ts。"""
    diag = []
    url, key, keyname, where = keys(diag)
    shelves = []
    if url:
        try:
            st, rows = _req(url, key,
                            "/rest/v1/admin_shelves?select=*&order=world.asc&limit=1000")
            diag.append("admin_shelves HTTP %d / %d件" % (st, len(rows)))
            for r in rows:
                t = r.get("title") or r.get("name") or ""
                if not t:
                    continue
                if r.get("archived") or r.get("deleted_at"):
                    continue
                shelves.append({"id": str(r.get("id")), "title": t,
                                "world": r.get("world") or "", "from": "db"})
        except urllib.error.HTTPError as e:
            diag.append("admin_shelves HTTP %d" % e.code)
        except Exception as e:
            diag.append("admin_shelves 取れず: %s" % type(e).__name__)
    else:
        diag.append(where or "鍵なし")

    # 作り付けの棚（コード側）。JRSのクローンが在るときだけ。
    jrs = os.path.expanduser("~/Desktop/joy-relief-station")
    wp = os.path.join(jrs, "src", "lib", "worlds.ts")
    if os.path.exists(wp):
        import re
        src = io.open(wp, encoding="utf-8", errors="replace").read()
        n = 0
        for m in re.finditer(r'id:\s*"([a-z0-9][a-z0-9-]{2,})"\s*,\s*\n\s*title:\s*"((?:[^"\\]|\\.)*)"', src):
            shelves.append({"id": m.group(1), "title": m.group(2).replace('\\"', '"'),
                            "world": "", "from": "code"})
            n += 1
        diag.append("worlds.ts から %d件" % n)
    else:
        diag.append("worlds.ts が無い（作り付けの棚は拾えていない）")

    # 同じ題名は1つに。DB側を優先（そちらが今の正本）。
    seen, uniq = set(), []
    for s in shelves:
        k = s["title"].strip()
        if not k or k in seen:
            continue
        seen.add(k)
        uniq.append(s)
    uniq.sort(key=lambda s: (s["world"], s["title"]))

    os.makedirs(os.path.dirname(ICHIRAN), exist_ok=True)
    payload = {"at": now(), "count": len(uniq), "shelves": uniq, "diag": diag}
    io.open(ICHIRAN, "w", encoding="utf-8").write(
        json.dumps(payload, ensure_ascii=False, indent=1))
    return {"ok": bool(uniq), "count": len(uniq), "diag": diag, "path": "status/public/tana_ichiran.json"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.probe:
        print(json.dumps(probe(), ensure_ascii=False, indent=1)[:4000])
    elif a.list:
        print(json.dumps(shelf_list(), ensure_ascii=False, indent=1))


def run_job(payload=None):
    payload = payload or {}
    op = payload.get("op") or "list"
    if op == "probe":
        out = probe()
    elif op == "list":
        out = shelf_list()
    else:
        out = {"ok": False, "error": "知らない op: %s" % op}
    out["totalYen"] = 0.0
    return out


if __name__ == "__main__":
    main()
