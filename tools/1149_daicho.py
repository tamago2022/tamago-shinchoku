#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1149番【やりっぱなし4帳簿 ＋ 型分類 ＋ 門の死活】を機械で数える。

たまごさん（2026-09-26）:
  「やりっぱなしで行って帰ってこない問題も、もうゼロにしたい。」
  「4つとも件数を毎日出す。減っていなければ赤。」
  「1件ずつ直すのではなく型ごとにパイプを替える。」

------------------------------------------------------------------
なぜ「型」で数えるのか（＝今日いちばん効いた発見）
------------------------------------------------------------------
status/shinda.jsonl は今日だけで 2,804 行あった。だが中身は
  tunnel  1,403回（renzoku=1403）
  login   1,403回（renzoku=1403）
の**たった2種類が連番で積み上がっただけ**だった。
件数を数えると「今日2,804件壊れた」に見えるが、実際は**2つの型が1,403回鳴っただけ**。
→ 1件ずつ直すと2,804回の作業になる。型で直すと2回で終わる。
→ このファイルは **必ず「型の数」と「鳴った回数」を分けて出す。**

------------------------------------------------------------------
4帳簿の定義（機械が判定できる形にした。あいまい語を使わない）
------------------------------------------------------------------
 ① 始めたのに終わっていない
      startedAt があり finishedAt が無く、state が終わり系でない。
      3時間超＝黄 / 6時間超＝赤（たまごさん指定）。
 ② 出したのに確かめていない
      本番に出した跡（mergedAt / finishedAt）＋ urls があるのに、
      その後に checkedAt / evidenceCheckedAt が無い。
      → --naosu で「叩く仕事」を status/1149/tataku.jsonl に積む（回線がある側が叩く）。
 ③ 頼んだのに返ってきていない
      status/ai_daicho.jsonl の out に対して、同じ thread の in がまだ無いもの。
      ＋ status/gaibu_jobs/running に居座っているもの。
      24時間超＝期限切れ＝赤。
 ④ 見つけたのに直していない
      queue.json で state=fix_required、または kenpin* の指摘が付いたまま
      その後に直した跡（mergedAt/finishedAt）が無いもの。

------------------------------------------------------------------
最上位の赤（たまごさん指定）
------------------------------------------------------------------
  「動いているのに何も取れていない」＝ 走った回数>0 なのに 取れた回数=0。
  status/loop_history.jsonl の kaeri（帰り）と、各台帳の増分で判定する。
  ★ 赤が「走行0本のときだけ」出る作りだと、空回しが1本居るだけで赤が消える。
    だからここでは **走行>0 を赤の条件に入れる**（消えない向きにする）。

------------------------------------------------------------------
門の死活（たまごさん指定「弾き0が続いたら門が死んでいる＝赤」）
------------------------------------------------------------------
  status/*kanmon*.jsonl を全部読み、門ごとに「直近7日の通過数・弾き数」を出す。
  弾き0 かつ 通過>0 が続く門は「素通りの門」＝赤。
  1件も記録が無い門は「呼ばれていない門」＝赤（存在するのに使われていない）。

------------------------------------------------------------------
使い方
------------------------------------------------------------------
  python3 tools/1149_daicho.py            … 数えるだけ（何も書き換えない）
  python3 tools/1149_daicho.py --naosu    … 数えて、機械で直せるものを直す
  python3 tools/1149_daicho.py --json     … 結果のJSONだけ標準出力へ

戻し方（1行）:
  rm -rf ~/Desktop/tamago-shinchoku/status/1149   # 数えるだけなので消せば元通り
"""
from __future__ import annotations
import json, os, re, sys, glob
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUT = os.path.join(ST, "1149")
JST = timezone(timedelta(hours=9))

STALE_WARN_H = 3.0
STALE_RED_H = 6.0
REPLY_RED_H = 24.0

FINISHED_STATES = {"done", "merged", "passed", "closed", "archived", "cancelled"}


# ---------------------------------------------------------------- 読み込み
def jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def jload(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


TS_PAT = re.compile(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?")


def parse_ts(v):
    """いろんな書き方の時刻を1つに揃える。読めないものは None（**推測しない**）。"""
    if not v or not isinstance(v, str):
        return None
    m = TS_PAT.search(v)
    if not m:
        return None
    y, mo, d, h, mi, s = m.groups()
    try:
        dt = datetime(int(y), int(mo), int(d), int(h), int(mi), int(s or 0))
    except ValueError:
        return None
    tz = JST
    if v.endswith("Z"):
        tz = timezone.utc
    elif re.search(r"[+-]\d{2}:?\d{2}$", v):
        off = re.search(r"([+-])(\d{2}):?(\d{2})$", v)
        sign = 1 if off.group(1) == "+" else -1
        tz = timezone(sign * timedelta(hours=int(off.group(2)), minutes=int(off.group(3))))
    return dt.replace(tzinfo=tz)


def hours_since(dt, now):
    return None if dt is None else (now - dt).total_seconds() / 3600.0


# ---------------------------------------------------------------- 型分類
KATA_RULES = [
    ("A 鍵・ログインの取り合い", r"login|ログイン|oauth|token|鍵|expired|refresh"),
    ("B トンネル・通信が切れた", r"tunnel|トンネル|cloudflare|connection|econn|timeout|タイムアウト"),
    ("C 門が素通り／弾き数を数えていない", r"門|kanmon|関所|sekisho|gate|素通り"),
    ("D 動いているのに何も取れない（空回し）", r"karamawari|空回|取れ|0件|kazu|走行0"),
    ("E 枠・クレジットを使い切った", r"quota|limit|枠|クレジット|429|rate"),
    ("F 頼んだのに返ってこない", r"返って|未返信|pending|running|外部AI|jules|devin|codex"),
    ("G 心臓・常駐が止まった", r"heartbeat|心臓|runner|常駐|launchd|watchdog|停止"),
    ("H ファイル・ロックの事故", r"lock|錠前|mktemp|File exists|tmp|EMPTY"),
]


def kata_of(text: str) -> str:
    t = text or ""
    for name, pat in KATA_RULES:
        if re.search(pat, t, re.I):
            return name
    return "Z 未分類（型を作る候補）"


def bunrui(now):
    """今日壊れたものを型に分類する。★『何種類か』と『何回鳴ったか』を分けて出す。"""
    today = now.strftime("%Y-%m-%d")
    yest = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    kinds = defaultdict(lambda: {"kata": "", "narashi": 0, "rei": "", "moto": ""})
    narashi_total = 0

    for r in jsonl(os.path.join(ST, "shinda.jsonl")):
        at = str(r.get("at", ""))
        if not (at.startswith(today) or at.startswith(yest)):
            continue
        key = ("shinda", r.get("name", "?"))
        txt = f"{r.get('name','')} {r.get('midashi','')} {r.get('mieta','')}"
        e = kinds[key]
        e["kata"] = kata_of(txt)
        e["narashi"] += 1
        e["rei"] = (r.get("midashi") or r.get("name") or "")[:80]
        e["moto"] = "status/shinda.jsonl"
        narashi_total += 1

    for r in jsonl(os.path.join(ST, "ochita.jsonl")):
        at = str(r.get("t", ""))
        if not (at.startswith(today) or at.startswith(yest)):
            continue
        why = r.get("why") or "（理由なし）"
        key = ("ochita", why)
        e = kinds[key]
        e["kata"] = kata_of(f"{why} {r.get('level','')}")
        e["narashi"] += int(r.get("kietaN") or 1)
        e["rei"] = f"{r.get('level','')}／{why}"[:80]
        e["moto"] = "status/ochita.jsonl"
        narashi_total += int(r.get("kietaN") or 1)

    for r in jsonl(os.path.join(ST, "failures.jsonl")):
        if str(r.get("date", "")) not in (today, yest):
            continue
        key = ("failures", r.get("id", "?"))
        e = kinds[key]
        # 台帳の kata 欄には昔の指標名（"ame" "uso" など）が混じっている。
        # 型の名前は「英字1文字＋空白＋日本語」の形に揃えているので、その形でないものは数え直す。
        kk = r.get("kata") or ""
        e["kata"] = kk if re.match(r"^[A-Z] .", kk) else kata_of(f"{kk} {r.get('what','')}")
        e["narashi"] += 1
        e["rei"] = (r.get("what") or "")[:80]
        e["moto"] = "status/failures.jsonl"
        narashi_total += 1

    by_kata = defaultdict(lambda: {"shurui": 0, "narashi": 0, "rei": []})
    for key, e in kinds.items():
        k = by_kata[e["kata"]]
        k["shurui"] += 1
        k["narashi"] += e["narashi"]
        if len(k["rei"]) < 3:
            k["rei"].append({"nani": e["rei"], "kaisu": e["narashi"], "moto": e["moto"]})

    rank = sorted(by_kata.items(), key=lambda kv: (-kv[1]["narashi"], kv[0]))
    return {
        "shuruiN": len(kinds),
        "narashiN": narashi_total,
        "kataN": len(by_kata),
        "ichiban": rank[0][0] if rank else None,
        "kata": [{"kata": k, **v} for k, v in rank],
    }


# ---------------------------------------------------------------- 4帳簿
def yarippanashi(now):
    q = jload(os.path.join(ST, "queue.json"), {}) or {}
    items = q.get("items", [])

    # ① 始めたのに終わっていない
    hajimeta = []
    for it in items:
        st = parse_ts(it.get("startedAt"))
        if not st:
            continue
        if it.get("finishedAt") or (it.get("state") in FINISHED_STATES) or (it.get("status") in FINISHED_STATES):
            continue
        h = hours_since(st, now)
        if h is None or h < STALE_WARN_H:
            continue
        hajimeta.append({
            "n": it.get("n"), "title": (it.get("title") or "")[:60],
            "keika_h": round(h, 1), "state": it.get("state") or it.get("status"),
            "iro": "赤" if h >= STALE_RED_H else "黄",
        })
    hajimeta.sort(key=lambda x: -x["keika_h"])

    # ② 出したのに確かめていない
    tashikamete = []
    for it in items:
        dashi = parse_ts(it.get("mergedAt")) or parse_ts(it.get("finishedAt"))
        urls = [u for u in (it.get("urls") or []) if isinstance(u, str) and u.startswith("http")]
        if not dashi or not urls:
            continue
        ck = parse_ts(it.get("evidenceCheckedAt")) or parse_ts(it.get("checkedAt"))
        if ck and ck >= dashi:
            continue
        tashikamete.append({
            "n": it.get("n"), "title": (it.get("title") or "")[:60],
            "urls": urls[:3], "dashita": it.get("mergedAt") or it.get("finishedAt"),
            "keika_h": round(hours_since(dashi, now) or 0, 1),
        })
    tashikamete.sort(key=lambda x: -x["keika_h"])

    # ③ 頼んだのに返ってきていない
    ai = jsonl(os.path.join(ST, "ai_daicho.jsonl"))
    kaeri_by_thread = defaultdict(list)
    for r in ai:
        kaeri_by_thread[(r.get("thread") or "?", r.get("ai") or "?")].append(r)
    kaettekonai = []
    for (thread, who), rows in kaeri_by_thread.items():
        outs = [r for r in rows if r.get("dir") == "out"]
        ins = [r for r in rows if r.get("dir") == "in"]
        if not outs:
            continue
        last_out = max((parse_ts(r.get("at")) for r in outs if parse_ts(r.get("at"))), default=None)
        last_in = max((parse_ts(r.get("at")) for r in ins if parse_ts(r.get("at"))), default=None)
        if last_out is None:
            continue
        if last_in and last_in >= last_out:
            continue
        h = hours_since(last_out, now) or 0
        kaettekonai.append({
            "aite": who, "thread": thread, "keika_h": round(h, 1),
            "nani": (outs[-1].get("topic") or "")[:60],
            "iro": "赤（期限切れ）" if h >= REPLY_RED_H else "黄",
            "ref": outs[-1].get("ref"),
        })
    # 外部ジョブの走りっぱなし
    for p in sorted(glob.glob(os.path.join(ST, "gaibu_jobs", "running", "*"))):
        try:
            h = (now.timestamp() - os.path.getmtime(p)) / 3600.0
        except OSError:
            continue
        kaettekonai.append({
            "aite": "gaibu_jobs/running", "thread": os.path.basename(p),
            "keika_h": round(h, 1), "nani": "外部ジョブが running のまま",
            "iro": "赤（期限切れ）" if h >= REPLY_RED_H else "黄", "ref": None,
        })
    kaettekonai.sort(key=lambda x: -x["keika_h"])

    # ④ 見つけたのに直していない
    naoshitenai = []
    for it in items:
        bad = (it.get("state") == "fix_required") or (it.get("status") == "fix_required")
        notes = it.get("kenpinNotes") or it.get("failReasons") or []
        if notes and not it.get("mergedAt"):
            bad = True
        if not bad:
            continue
        mitsuketa = parse_ts(it.get("kenpinUpdatedAt")) or parse_ts(it.get("checkedAt")) or parse_ts(it.get("addedAt"))
        naoshitenai.append({
            "n": it.get("n"), "title": (it.get("title") or "")[:60],
            "keika_h": round(hours_since(mitsuketa, now) or 0, 1),
            "shiteki": str(notes[0] if isinstance(notes, list) and notes else (it.get("checkNote") or ""))[:70],
            "urgent": bool(it.get("urgent")),
        })
    naoshitenai.sort(key=lambda x: -x["keika_h"])

    return {
        "hajimeta_mama": hajimeta,
        "tashikametenai": tashikamete,
        "kaettekonai": kaettekonai,
        "naoshitenai": naoshitenai,
        "kensuu": {
            "始めたまま": len(hajimeta),
            "確かめてない": len(tashikamete),
            "返ってこない": len(kaettekonai),
            "直してない": len(naoshitenai),
        },
    }


# ---------------------------------------------------------------- 門の死活
def mon_shikatsu(now):
    """弾き0が続く門＝赤。記録が1件も無い門＝呼ばれていない＝赤。"""
    kiri = now - timedelta(days=7)
    mons = []
    paths = sorted(set(glob.glob(os.path.join(ST, "*kanmon*.jsonl")) +
                       glob.glob(os.path.join(ST, "*gate*.jsonl")) +
                       glob.glob(os.path.join(ST, "*sekisho*.jsonl"))))
    for p in paths:
        rows = jsonl(p)
        tsuuka = hajiki = 0
        saigo = None
        for r in rows:
            at = parse_ts(r.get("at") or r.get("t") or r.get("ts") or r.get("checkedAt") or "")
            if at and (saigo is None or at > saigo):
                saigo = at
            if at and at < kiri:
                continue
            ok = r.get("tsuuka")
            if ok is None:
                ok = r.get("ok")
            if ok is None:
                ok = r.get("pass")
            if ok is True:
                tsuuka += 1
            elif ok is False:
                hajiki += 1
        if hajiki == 0 and tsuuka > 0:
            han = "赤：素通りの門（7日間で弾き0）"
        elif tsuuka == 0 and hajiki == 0:
            han = "赤：呼ばれていない門（7日間で記録0）"
        else:
            han = "緑：生きている"
        mons.append({
            "mon": os.path.basename(p), "tsuuka": tsuuka, "hajiki": hajiki,
            "saigo": saigo.strftime("%Y-%m-%d %H:%M") if saigo else None, "han": han,
        })
    # 門の実装はあるのに台帳が1本も無いもの
    impl = {os.path.basename(p) for p in glob.glob(os.path.join(HERE, "*kanmon*.py")) +
            glob.glob(os.path.join(HERE, "*sekisho*.py"))}
    mons.sort(key=lambda m: (m["han"][0] != "赤", m["mon"]))
    aka = [m for m in mons if m["han"].startswith("赤")]
    return {"mon": mons, "akaN": len(aka), "monN": len(mons), "jissouN": len(impl)}


# ---------------------------------------------------------------- 最上位の赤
def karamawari(now):
    """『動いているのに何も取れていない』＝走行>0 かつ 成果0。★空回しが1本居ても消えない向き。"""
    lh = jsonl(os.path.join(ST, "loop_history.jsonl"))
    kiri = now - timedelta(hours=24)
    # ★ kaeri は「累計」。足し算すると 12万件取れたことになって赤が絶対に出ない。
    #   実際に取れた数は **窓の最後 − 窓の最初の差分**。ここを間違えると
    #   「動いているのに何も取れていない」が永久に検知できない（今日この形で4日半見逃した）。
    win = [r for r in lh if (parse_ts(r.get("at")) or kiri - timedelta(days=1)) >= kiri]
    shuu = len(win)
    sou = sum(int(r.get("ochita") or 0) + int(r.get("hajiki") or 0) + 1 for r in win)
    tore = 0
    if len(win) >= 2:
        tore = int(win[-1].get("kaeri") or 0) - int(win[0].get("kaeri") or 0)
    # 台帳が24時間で1件も増えていないか（＝本物の発車0本）
    fusshin = {}
    for name in ("gsk_daicho.jsonl", "ai_daicho.jsonl", "verify_log.jsonl", "self_repair_log.jsonl"):
        rows = jsonl(os.path.join(ST, name))
        n = 0
        for r in rows:
            at = parse_ts(r.get("at") or r.get("t") or r.get("ts") or r.get("checkedAt") or "")
            if at and at >= kiri:
                n += 1
        fusshin[name] = n
    aka = []
    if shuu > 0 and tore == 0:
        aka.append("最上位の赤：巡回は回っているのに、24時間で1件も取れていない")
    for name, n in fusshin.items():
        if n == 0:
            aka.append(f"赤：{name} が24時間まったく増えていない（動いているのに何も生んでいない）")
    return {"shuukai": shuu, "soukou": sou, "toreta": tore, "fusshin": fusshin, "aka": aka}


# ---------------------------------------------------------------- 直す
def naosu(res, now):
    """機械で安全に直せるものだけ直す。直せないものは赤のまま名前を出す（1142番と同じ思想）。"""
    os.makedirs(OUT, exist_ok=True)
    done = []

    # ② 確かめてない → 「叩く仕事」を積む（回線がある側が叩く。ここでは判定しない）
    tataku = os.path.join(OUT, "tataku.jsonl")
    already = {r.get("url") for r in jsonl(tataku)}
    n = 0
    with open(tataku, "a", encoding="utf-8") as f:
        for it in res["yari"]["tashikametenai"]:
            for u in it["urls"]:
                if u in already:
                    continue
                f.write(json.dumps({"at": now.isoformat(), "n": it["n"], "url": u,
                                    "why": "出したのに叩いていない"}, ensure_ascii=False) + "\n")
                already.add(u)
                n += 1
    if n:
        done.append(f"②叩く仕事を{n}件積んだ → status/1149/tataku.jsonl")

    # ③ 期限切れの依頼 → 赤台帳へ（別経路に回す判断材料）
    kigen = [x for x in res["yari"]["kaettekonai"] if x["iro"].startswith("赤")]
    if kigen:
        p = os.path.join(OUT, "kigengire.jsonl")
        with open(p, "a", encoding="utf-8") as f:
            for x in kigen:
                f.write(json.dumps({"at": now.isoformat(), **x}, ensure_ascii=False) + "\n")
        done.append(f"③期限切れの依頼を{len(kigen)}件、赤として記録 → status/1149/kigengire.jsonl")

    # ④ 直していない → 繰り上げ候補を出す（queue.json は書き換えない＝戻せる形）
    kuriage = [x for x in res["yari"]["naoshitenai"] if not x["urgent"]]
    if kuriage:
        p = os.path.join(OUT, "kuriage.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"at": now.isoformat(), "items": kuriage}, f, ensure_ascii=False, indent=1)
        done.append(f"④繰り上げ候補を{len(kuriage)}件出した → status/1149/kuriage.json")

    return done


# ---------------------------------------------------------------- 本体
def main():
    now = datetime.now(JST)
    os.makedirs(OUT, exist_ok=True)
    res = {
        "at": now.isoformat(),
        "kata": bunrui(now),
        "yari": yarippanashi(now),
        "mon": mon_shikatsu(now),
        "kara": karamawari(now),
    }
    if "--naosu" in sys.argv:
        res["naoshita"] = naosu(res, now)

    # 履歴（減っているかを毎日見るため。減っていなければ赤）
    hist = os.path.join(OUT, "rireki.jsonl")
    line = {"at": now.isoformat(), **res["yari"]["kensuu"],
            "門の赤": res["mon"]["akaN"], "型の数": res["kata"]["kataN"],
            "鳴った回数": res["kata"]["narashiN"]}
    with open(hist, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

    # 前回と比べて減っているか
    rows = jsonl(hist)
    zen = rows[-2] if len(rows) >= 2 else None
    res["suii"] = {}
    for k in res["yari"]["kensuu"]:
        ima = res["yari"]["kensuu"][k]
        mae = zen.get(k) if zen else None
        res["suii"][k] = {"今": ima, "前": mae,
                          "判定": ("初回" if mae is None else
                                 "減った" if ima < mae else "同じ＝赤" if ima == mae else "増えた＝赤")}

    with open(os.path.join(OUT, "genzai.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    if "--json" in sys.argv:
        print(json.dumps(res, ensure_ascii=False))
        return

    k = res["yari"]["kensuu"]
    print("── やりっぱなし4帳簿 ─────────────────")
    for name, v in k.items():
        print(f"  {name}: {v}件  （前回: {res['suii'][name]['前']} → {res['suii'][name]['判定']}）")
    print("── 今日壊れた型 ─────────────────────")
    print(f"  鳴った回数 {res['kata']['narashiN']}回 ／ 種類 {res['kata']['shuruiN']} ／ 型 {res['kata']['kataN']}")
    for row in res["kata"]["kata"][:6]:
        print(f"  {row['kata']}: {row['narashi']}回（{row['shurui']}種）")
    print("── 門の死活 ────────────────────────")
    for m in res["mon"]["mon"]:
        print(f"  {m['mon']}: 通過{m['tsuuka']} 弾き{m['hajiki']} … {m['han']}")
    print("── 空回り（最上位の赤）──────────────")
    print(f"  巡回{res['kara']['shuukai']} 走行{res['kara']['soukou']} 取れた{res['kara']['toreta']}")
    for a in res["kara"]["aka"]:
        print("  " + a)
    for d in res.get("naoshita", []):
        print("  直した: " + d)
    print(f"\n書いた: status/1149/genzai.json")


if __name__ == "__main__":
    main()
