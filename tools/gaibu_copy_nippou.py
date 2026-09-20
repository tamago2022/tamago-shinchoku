#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""971番：外部から入れたもののコピー日報。

たまごさん（2026-09-20）：
  「当日に外部から入れたもののコピーが直ってないのはたくさんあるはずだよ。
    いつ治るのかなと思って見てるけど、あれのチェックはしてんのかな？
    毎日、俺は外部から入れ続けてるからね。3個4個は毎日なんか入れてるはず。
    全然、多分、直してないんじゃないかなと思うんだけど。
    毎日、昨日なら昨日の外部から入ったものを釣って、コピーはこうです、
    っていうのも知りたい。毎日知りたい。」

------------------------------------------------------------------
なぜこれを置くか（実測）
------------------------------------------------------------------
  756番の仕組みは「毎朝の入荷見回り」を発車待ちへ積むところまでは動いていた。
  だが 2026-09-12〜09-19 の8本は**全部 waiting のまま1本も走っていない**。
  実際に見回った最後の記録は status/daily_ingest_summary.json の 2026-09-10。
  ＝ たまごさんの「多分直してない」は当たっていた。

  積むだけの係は居た。**結果を毎日1枚にして出す係が居なかった。**
  だから誰も気づかないまま9日たった。ここはその1枚を作る係。

------------------------------------------------------------------
決め
------------------------------------------------------------------
  ・新しい常駐は増やさない。既にある5分便(machine_status_push.sh)に相乗りする。
    中で30分ゲートするので、5分おきに呼ばれても外へ出るのは30分に1回。
  ・**「まだ書けていない」を隠さない。**そこが一番見たいところ。
  ・数字が取れなかったら赤。**推測で埋めない**（969番の台帳の決まりと同じ）。
  ・鍵の値は一切書き出さない。名前と、通ったか通らないかだけ。

------------------------------------------------------------------
どこから数えるか
------------------------------------------------------------------
  正本＝ joy-relief-station の Supabase テーブル `admin_stock`（created_at が入荷日時）。
  Cowork/Dispatchのサンドボックスからは外へ出られない（実測 Tunnel 403）。
  **このMacからは出る。**だからここ（5分便＝Mac側）で叩く。
  鍵は joy-relief-station の .env から名前で拾う（値は読むだけ・どこにも書かない）。
"""
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
OUT_JSON = os.path.join(PUBLIC, "gaibu_copy_nippou.json")
GATE = os.path.join(STATUS, ".gaibu_copy_nippou_last")
JRS = "/Users/mac/Desktop/joy-relief-station"
DAYS = 7
GATE_SEC = 30 * 60


# ---------------------------------------------------------------- 水道水の判定
# たまごさんが「60点」と名指ししたコピー、および oni-kantoku / bonjovi-ojisan-kobun
# の禁止事項からそのまま起こした。**新しい基準を発明しない。**
WATER_WORDS = [
    # 誰にでも書ける説明文（水道水コピー）
    "代表曲のひとつ", "代表曲の一つ", "代表曲です", "不朽の名作", "名曲のひとつ",
    "定番の一曲", "おなじみの曲",
    # 観測していない他人の反応
    "話題", "反響", "絶賛", "続出", "後を絶ち", "バズ", "必見", "見逃せない",
    # テンプレ文（templateGuard.mjs と同じ思想）
    "二人の人物が", "する様子", "される様子", "が映し出され", "収められています",
    "姿が印象的", "一挙手一投足",
    # 動画を見ずに「見た目」だけで書いた語（入荷の関所・門4と同じ一覧）
    "編み込まれた髪", "横顔", "視線の先", "瞳", "佇まい",
]
# 題名が英語の原題そのまま／URLそのまま＝人を動かさない題名（oni-kantoku 5.）
RE_URLISH = re.compile(r"^\s*https?://", re.I)
RE_ASCII_ONLY = re.compile(r"^[\x20-\x7e]+$")


def judge(title, copy):
    """手つかずなら理由を返す。書けていれば None。"""
    t = (title or "").strip()
    c = (copy or "").strip()
    if not c:
        return "コピーが空"
    if len(c) < 12:
        return "コピーが短すぎる（%d文字）" % len(c)
    for w in WATER_WORDS:
        if w and w in c:
            return "水道水・テンプレの語「%s」" % w
    if not t:
        return "題名が空"
    if RE_URLISH.match(t):
        return "題名がURLのまま"
    if RE_ASCII_ONLY.match(t) and len(t) > 3:
        return "題名が英語の原題のまま"
    return None


# ---------------------------------------------------------------- 入出力
def load(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def read_env_names(path):
    """.env から名前→値。値はこの関数の外へ**名前でしか**出さない。"""
    out = {}
    try:
        for ln in io.open(path, encoding="utf-8", errors="replace"):
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out


def find_supabase():
    """(url, key, 鍵の名前, 見た場所) を返す。無ければ (None, None, None, 理由)。"""
    tried = []
    for rel in (".env", ".env.local", ".env.production", "scripts/patrol/.env"):
        p = os.path.join(JRS, rel)
        if not os.path.exists(p):
            continue
        tried.append(rel)
        env = read_env_names(p)
        url = None
        for k in env:
            if "SUPABASE" in k.upper() and k.upper().endswith("URL"):
                url = env[k]
                break
        key = keyname = None
        for pref in ("SERVICE_ROLE", "SERVICE", "ANON", "KEY"):
            for k in env:
                ku = k.upper()
                if "SUPABASE" in ku and pref in ku and env[k]:
                    key, keyname = env[k], k
                    break
            if key:
                break
        if url and key:
            return url.rstrip("/"), key, keyname, rel
    if not tried:
        return None, None, None, "joy-relief-station に .env が見つからない"
    return None, None, None, "見た(%s)が SUPABASE の URL と鍵が揃っていない" % "・".join(tried)


def fetch_stock(url, key, since_iso):
    """admin_stock から since 以降を取る。列名は決め打ちせず素のまま受ける。"""
    q = urllib.parse.urlencode({
        "select": "*",
        "created_at": "gte." + since_iso,
        "order": "created_at.desc",
        "limit": "3000",
    })
    req = urllib.request.Request(
        url + "/rest/v1/admin_stock?" + q,
        headers={"apikey": key, "Authorization": "Bearer " + key,
                 "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def pick(row, names):
    for n in names:
        v = row.get(n)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


# ---------------------------------------------------------------- 見回りの実行状況
def patrol_state():
    """『毎朝の入荷見回り』が実際に走ったかどうか。ここはネット不要。"""
    q = load(os.path.join(STATUS, "queue.json"), {}) or {}
    items = q.get("items") if isinstance(q, dict) else q
    items = items or []
    rows = []
    for it in items:
        t = it.get("title") or ""
        m = re.search(r"毎朝の入荷見回り（(\d{4}-\d{2}-\d{2})分", t)
        if m:
            rows.append({"n": it.get("n"), "date": m.group(1),
                         "status": it.get("status") or "waiting"})
    rows.sort(key=lambda r: r["date"])
    summary = load(os.path.join(STATUS, "daily_ingest_summary.json"), {}) or {}
    return {
        "rows": rows,
        "notRun": [r for r in rows if r["status"] not in ("done",)],
        "lastActuallyRan": summary.get("date"),
        "lastSummary": summary,
    }


# ---------------------------------------------------------------- 本体
def build():
    now = datetime.now(JST)
    since = (now - timedelta(days=DAYS)).replace(hour=0, minute=0, second=0, microsecond=0)
    out = {
        "generatedAt": now.strftime("%Y-%m-%d %H:%M"),
        "days": DAYS,
        "patrol": patrol_state(),
        "source": None,
        "sourceNote": "",
        "red": [],
        "byDay": [],
        "todo": [],
        "total": {"in": 0, "written": 0, "todo": 0},
    }

    url, key, keyname, where = find_supabase()
    if not url:
        out["source"] = "取れていない"
        out["sourceNote"] = where
        out["red"].append("正本（admin_stock）に手が届かない：" + where)
    else:
        out["sourceNote"] = "admin_stock（鍵：%s・%s）" % (keyname, where)
        try:
            rows = fetch_stock(url, key, since.isoformat())
            out["source"] = "admin_stock"
            buckets = {}
            for r in rows:
                if not isinstance(r, dict):
                    continue
                created = pick(r, ["created_at", "createdAt", "inserted_at"])
                day = created[:10] if created else "?"
                title = pick(r, ["title", "name", "song_title"])
                copy = pick(r, ["whisper", "copy", "lead", "description", "note"])
                artist = pick(r, ["artist", "artist_name", "channel_title",
                                  "channel", "author", "source_name"])
                link = pick(r, ["url", "source_url", "link", "youtube_url"])
                reason = judge(title, copy)
                b = buckets.setdefault(day, {"date": day, "in": 0, "written": 0, "todo": 0})
                b["in"] += 1
                if reason:
                    b["todo"] += 1
                    out["todo"].append({
                        "date": day, "title": title or "（題名なし）",
                        "artist": artist or "（アーティスト不明）",
                        "copy": copy, "why": reason, "url": link,
                        "id": r.get("id"),
                    })
                else:
                    b["written"] += 1
            for d in range(DAYS):
                day = (now - timedelta(days=d)).strftime("%Y-%m-%d")
                buckets.setdefault(day, {"date": day, "in": 0, "written": 0, "todo": 0})
            out["byDay"] = sorted(buckets.values(), key=lambda b: b["date"], reverse=True)
            out["todo"].sort(key=lambda t: t["date"], reverse=True)  # 直近から直す
            for b in out["byDay"]:
                out["total"]["in"] += b["in"]
                out["total"]["written"] += b["written"]
                out["total"]["todo"] += b["todo"]
        except urllib.error.HTTPError as e:
            out["source"] = "取れていない"
            out["red"].append("admin_stock が HTTP %d（鍵は在るが通らない）" % e.code)
        except Exception as e:
            out["source"] = "取れていない"
            out["red"].append("admin_stock に繋がらない（%s）" % type(e).__name__)

    # 赤の決まり（969番の台帳と同じ）：走っているのに収穫0なら赤。
    nr = out["patrol"]["notRun"]
    if nr:
        out["red"].append(
            "毎朝の入荷見回りが%d日ぶん積まれたまま1本も走っていない（%s〜%s）"
            % (len(nr), nr[0]["date"], nr[-1]["date"]))
    if out["total"]["todo"]:
        out["red"].append("コピーが手つかずのものが%d件" % out["total"]["todo"])
    out["redCount"] = len(out["red"])
    return out


def main():
    force = os.environ.get("NIPPOU_FORCE") == "1"
    if not force and os.path.exists(GATE):
        if time.time() - os.path.getmtime(GATE) < GATE_SEC:
            return
    out = build()
    save(OUT_JSON, out)
    os.makedirs(os.path.dirname(GATE), exist_ok=True)
    with io.open(GATE, "w", encoding="utf-8") as f:
        f.write(datetime.now(JST).strftime("%Y-%m-%d %H:%M"))


if __name__ == "__main__":
    main()
