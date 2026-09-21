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
GATE_SEC = 10 * 60
FORCE = os.path.join(STATUS, ".gaibu_copy_nippou_force")


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
    # 2026-09-22 追加：直す係の1回目が出した文を実際に読んで足した分。
    # 「誘う。脅さない。煽らない」の線を越えている呼びかけ・煽り。
    # ボンジョビおじさん構文の見本（「狭い車の中が、ふたりだけの教会になる。」）は
    # 一度も読み手に命令していない。命令・勧誘で終わる文はこの棚の文ではない。
    "お見逃しなく", "間違いなし", "体感し", "参加しよう", "感じてみて",
    "準備はできて", "ぜひその目で", "目撃し",
]
# 「！」は煽りの合図として扱う（見本の文には1つも無い）。judge() で別に見る。
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
    if "！" in c or "!" in c:
        return "煽りの「！」が入っている（見本の文には1つも無い）"
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


RE_SB_URL = re.compile(r"https://[a-z0-9]{8,}\.supabase\.co")
RE_SB_KEY = re.compile(r"\b(eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}"
                       r"|sb_(?:secret|publishable)_[A-Za-z0-9_\-]{10,})")

ENV_RELS = (".env", ".env.local", ".env.production", ".env.development",
            ".env.example", "scripts/patrol/.env", "scripts/.env",
            "supabase/.env", "ai-brain/.env")
SRC_RELS = ("src/integrations/supabase/client.ts",
            "src/integrations/supabase/client.js",
            "src/lib/supabaseClient.ts", "src/lib/supabase.ts",
            "scripts/patrol/supabase.mjs", "scripts/patrol/_supabase.mjs",
            "scripts/lib/supabase.mjs")


def _read(p):
    try:
        return io.open(p, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def find_supabase(diag):
    """(url, key, 鍵の名前, 見た場所) を返す。無ければ (None, None, None, 理由)。

    値（鍵の中身）はこの関数の戻り値から一歩も外へ出さない。
    diag には「在ったか／無かったか」と**名前だけ**を積む。
    """
    if not os.path.isdir(JRS):
        diag.append("joy-relief-station が %s に無い" % JRS)
        return None, None, None, "joy-relief-station のフォルダ自体が見つからない"

    # ① .env 系（名前で拾う）
    for rel in ENV_RELS:
        p = os.path.join(JRS, rel)
        if not os.path.exists(p):
            continue
        env = read_env_names(p)
        names = [k for k in env if "SUPABASE" in k.upper()]
        diag.append("%s あり（SUPABASE系の名前 %d個）" % (rel, len(names)))
        url = next((env[k] for k in env
                    if "SUPABASE" in k.upper() and k.upper().endswith("URL") and env[k]), None)
        key = keyname = None
        for pref in ("SERVICE_ROLE", "SERVICE", "SECRET", "ANON", "PUBLISHABLE", "KEY"):
            for k in env:
                ku = k.upper()
                if "SUPABASE" in ku and pref in ku and env[k]:
                    key, keyname = env[k], k
                    break
            if key:
                break
        if url and key:
            return url.rstrip("/"), key, keyname, rel

    # ② Lovableが吐くクライアント等、ソースに直書きされているもの
    for rel in SRC_RELS:
        p = os.path.join(JRS, rel)
        if not os.path.exists(p):
            continue
        s = _read(p)
        mu, mk = RE_SB_URL.search(s), RE_SB_KEY.search(s)
        diag.append("%s あり（URL %s・鍵 %s）" % (rel, "有" if mu else "無", "有" if mk else "無"))
        if mu and mk:
            return mu.group(0).rstrip("/"), mk.group(0), "ソース直書き", rel

    diag.append("既知の置き場に SUPABASE の URL と鍵が揃っていない")
    return None, None, None, "joy-relief-station の既知の置き場に鍵が無い（置き場を1か所決める必要あり）"


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
        "diag": [],
    }

    # 既存パイプラインが吐くレポートが在るか（在れば、鍵が無くてもここから数えられる）
    rep = os.path.join(JRS, "scripts/patrol/reports/today-ingest-copy-latest.json")
    if os.path.exists(rep):
        d0 = load(rep, None)
        if isinstance(d0, dict):
            out["diag"].append("既存レポートあり（中身の見出し：%s）"
                               % "・".join(list(d0.keys())[:8]))
        elif isinstance(d0, list):
            out["diag"].append("既存レポートあり（配列 %d件・1件目の見出し：%s）"
                               % (len(d0), "・".join(list(d0[0].keys())[:8])
                                  if d0 and isinstance(d0[0], dict) else "—"))
        else:
            out["diag"].append("既存レポートあり（読めなかった）")
    else:
        out["diag"].append("既存レポート（scripts/patrol/reports/today-ingest-copy-latest.json）が無い")

    url, key, keyname, where = find_supabase(out["diag"])
    if not url:
        out["source"] = "取れていない"
        out["sourceNote"] = where
        out["red"].append("正本（admin_stock）に手が届かない：" + where)
    else:
        out["sourceNote"] = "admin_stock（鍵：%s・%s）" % (keyname, where)
        try:
            rows = fetch_stock(url, key, since.isoformat())
            out["source"] = "admin_stock"
            if rows and isinstance(rows[0], dict):
                # 列の名前だけ控える（値は書かない）。取りこぼした列を後から直せるように。
                out["diag"].append("admin_stock の列：" + "・".join(sorted(rows[0].keys())))
            buckets = {}
            for r in rows:
                if not isinstance(r, dict):
                    continue
                if r.get("deleted_at"):
                    continue  # 消したものは数えない
                created = pick(r, ["created_at", "createdAt", "inserted_at"])
                day = created[:10] if created else "?"
                title = pick(r, ["title", "name", "song_title"])
                # コピー＝whisper（カードの一言）。note は曲ページの長い方なので数に入れない。
                copy = pick(r, ["whisper", "copy", "lead"])
                artist = pick(r, ["detected_artist_id", "artist", "artist_name",
                                  "channel_title", "channel", "author"])
                if not artist:
                    artist = "アーティスト未判定"
                link = pick(r, ["url", "source_url", "link", "youtube_url", "ref"])
                kind = pick(r, ["kind"])
                if link and not link.startswith("http"):
                    link = ("https://youtu.be/" + link) if kind == "youtube" else ""
                reason = judge(title, copy)
                b = buckets.setdefault(day, {"date": day, "in": 0, "written": 0, "todo": 0})
                b["in"] += 1
                if reason:
                    b["todo"] += 1
                    out["todo"].append({
                        "date": day, "title": title or "（題名なし）",
                        "artist": artist,
                        "kind": kind,
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

    # 出した1枚が本当に外から見えるかを、ここ（ネットがあるMac側）で毎回確かめる。
    # 「公開しました」のログではなく、**実際に叩いた番号**だけを載せる。
    page = "https://tamago2022.github.io/tamago-shinchoku/971-gaibu-copy-nippou.html"
    try:
        req = urllib.request.Request(page, method="HEAD")
        with urllib.request.urlopen(req, timeout=20) as r:
            out["publicCheck"] = {"url": page, "status": r.status}
    except urllib.error.HTTPError as e:
        out["publicCheck"] = {"url": page, "status": e.code}
    except Exception as e:
        out["publicCheck"] = {"url": page, "status": None, "why": type(e).__name__}
    if (out["publicCheck"] or {}).get("status") != 200:
        out["red"].append("この1枚が外から見えていない（%s）"
                          % ((out["publicCheck"] or {}).get("status") or "繋がらない"))

    # ---- 直す係（gaibu_copy_naoshi.py）の成績をここに合流させる ----
    # たまごさん（2026-09-22）「走った回数と、直した件数の両方を数える。
    #   走った>0 なのに 直した=0 は赤」。数えるだけの1枚にしない。
    na = load(os.path.join(PUBLIC, "gaibu_copy_naoshi.json"), {}) or {}
    out["naoshi"] = {
        "ranAt": na.get("generatedAt"),
        "runs": na.get("runs") or 0,
        "targets": na.get("targets") or 0,
        "fixed": na.get("fixed") or 0,
        "fixedTotal": na.get("fixedTotal") or 0,
        "remaining": na.get("remaining"),
        "changes": (na.get("changes") or [])[:30],
        "history": (na.get("history") or [])[:30],
        "skips": (na.get("skips") or [])[:30],
        "red": na.get("red") or [],
    }
    if not na:
        out["red"].append("直す係（gaibu_copy_naoshi）がまだ一度も走っていない")
    else:
        today = now.strftime("%Y-%m-%d")
        if (na.get("generatedAt") or "")[:10] != today:
            out["red"].append("直す係が今日まだ走っていない（最後に走ったのは %s）"
                              % (na.get("generatedAt") or "不明"))
        if (na.get("targets") or 0) > 0 and (na.get("fixed") or 0) == 0:
            out["red"].append("直す係は走ったのに1件も直っていない（対象%d件）"
                              % na.get("targets"))
        for r in (na.get("red") or []):
            if r not in out["red"]:
                out["red"].append(r)

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
    # 前回が赤（正本から数えられていない）なら、30分ゲートで寝かせない。
    # 「赤のまま座っている」を作らないため（969番の台帳と同じ考え方）。
    prev = load(OUT_JSON, {}) or {}
    stuck_red = prev.get("source") != "admin_stock"
    if os.path.exists(FORCE):
        force = True
        try:
            os.remove(FORCE)
        except Exception:
            pass
    if not force and not stuck_red and os.path.exists(GATE):
        if time.time() - os.path.getmtime(GATE) < GATE_SEC:
            return
    out = build()
    save(OUT_JSON, out)
    try:
        with io.open(GATE, "w", encoding="utf-8") as f:
            f.write(datetime.now(JST).strftime("%Y-%m-%d %H:%M"))
    except Exception:
        pass  # 印が書けなくても日報そのものは出す（止まらない）


if __name__ == "__main__":
    main()
