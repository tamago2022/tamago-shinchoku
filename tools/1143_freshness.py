#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1143番【成果の鮮度計（Freshness SLO）】——「動いているのに何も出ていない」を年齢で捕まえる。

━━ なぜ要るか（2026-09-25 実測）━━
  本物の発車が 4日半ゼロだったのに、誰も気づかなかった。
  赤の出し方が「走行0本のとき」だけで、空回しが1本いると赤が消えていたから。
  さらに実測すると queue.json の最後の finishedAt は **2026-09-17**。
  ＝実際には8日間、完了が1件も出ていない。

  この作りの何が悪いか（OneUptime / Prefactor の言い方で）：
    「走っているか」を見るのは *liveness* であって *freshness* ではない。
    走っているかどうかは、成果が出ているかどうかを一切保証しない。

━━ 何を真似たか（実運用事例の移植。オリジナルの発明はしていない）━━
  ① OneUptime「Freshness SLOs」
     https://oneuptime.com/blog/post/2026-01-30-freshness-slos/view
     ・data_freshness_age_seconds（成果の年齢・秒）を出口ごとに測る
     ・閾値を出口ごとに持つ（data_freshness_threshold_seconds）
     ・Freshness SLI =（年齢が閾値以下だった期間）/（総期間）× 100
     ・アラートは3種：DataFreshnessViolation / FreshnessBurnRateHigh / DataPipelineStalled
     ・for: 5m ＝ 1回のブレでは鳴らさない（連続2回で鳴らす形に写した）
  ② Prefactor「Detecting silent failures in agent responses」
     https://prefactor.tech/blog/detecting-silent-failures-in-agent-responses
     ・Presence：0バイト／0件の応答を「成功」に数えない
     ・Schema：必要なフィールドと型が揃っているか
     ・（Semantic＝2次モデルでの内容評価は、ここでは入れない。金が出るのと、
        推測で埋めることになるため。入れるなら別便）
  ③ ScaleKit / Nango（認証まわり）は別便。ここでは扱わない。

━━ この道具が絶対にしないこと（ここが今回の眼目）━━
  ★「何かが走っているから大丈夫」という判定を一切しない。
    走行本数・プロセス数・ラベルの文字列を、判定に一度も使わない。
    見るのは **最後に本物の成果が出た時刻と、いまの時刻の差だけ。**
    こうしておくと、空回しが何本走っていようと赤は消えない。

━━ お金 ━━
  0円。AIを1回も叩かない。ファイルを読むだけ。

━━ 使い方 ━━
  python3 tools/1143_freshness.py            # 測って status/1143/freshness.json を書く
  python3 tools/1143_freshness.py --show     # 人が読む形で出す
  python3 tools/1143_freshness.py --no-write # 測るだけ（履歴を汚さない）
"""
from __future__ import annotations

import datetime
import io
import json
import os
import re
import subprocess
import sys

JST = datetime.timezone(datetime.timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUTDIR = os.path.join(ST, "1143")
OUT = os.path.join(OUTDIR, "freshness.json")
HIST = os.path.join(OUTDIR, "freshness_history.jsonl")

H = 3600
SLI_WINDOW_SEC = 7 * 24 * H       # SLIを出す窓（OneUptimeの例にならい7日）
BURN_WINDOW_SEC = 3 * H           # 直近の燃え方を見る窓
STALLED_MULT = 3                  # 閾値の3倍を超えたら Stalled
VIOLATION_STREAK = 2              # 連続2回で鳴らす（OneUptimeの for: 5m にあたる）


def now():
    return datetime.datetime.now(JST)


def jread(p, default=None):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def jl_read(p, limit=None):
    rows = []
    try:
        with io.open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return rows[-limit:] if limit else rows


def parse_ts(s):
    """いろいろな形で書かれた時刻を秒（epoch）に。読めなければ None。"""
    if not s:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d"):
        try:
            if fmt is None:
                d = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
            else:
                d = datetime.datetime.strptime(s, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=JST)
            return d.timestamp()
        except Exception:
            continue
    return None


# ───────────────────────── 出口ごとの測り方 ─────────────────────────
# 1つの出口＝1つの「本物の成果が出る場所」。
# それぞれ (最後に成果が出たepoch, presence所見, schema所見, 補足) を返す。

# 工場が自分で自分を更新しているだけのコミット＝成果ではない（＝空回しのコミット版）
KARA_COMMIT = re.compile(r"^(画面・共有資料・道具の更新|自動|auto|chore|進捗表)")


def p_hassha():
    """本物の発車が終わった時刻。queue.json の完了系タイムスタンプの最大。"""
    q = jread(os.path.join(ST, "queue.json"), {}) or {}
    items = q.get("items") or []
    best, who, n_done = None, None, 0
    for x in items:
        if x.get("status") not in ("awaiting_check", "merged", "done"):
            continue
        n_done += 1
        for k in ("mergedAt", "finishedAt", "evidenceCheckedAt", "kenpinUpdatedAt"):
            t = parse_ts(x.get(k))
            if t and (best is None or t > best):
                best, who = t, "%s #%s" % (k, x.get("n"))
    presence = (n_done > 0, "完了系の案件 %d件" % n_done)
    schema = (best is not None, "完了時刻のフィールドが読めた" if best else "完了時刻がどの案件にも無い")
    return best, presence, schema, who


def p_commit():
    """工場の自動更新でない、中身のあるコミットの時刻。"""
    try:
        r = subprocess.run(["git", "log", "-60", "--format=%ct\t%s"], cwd=REPO,
                           capture_output=True, text=True, timeout=25)
        lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    except Exception:
        return None, (False, "gitが読めない"), (False, "gitが読めない"), None
    best, who, honmono = None, None, 0
    for l in lines:
        try:
            ts, msg = l.split("\t", 1)
        except ValueError:
            continue
        if KARA_COMMIT.match(msg.strip()):
            continue
        honmono += 1
        t = float(ts)
        if best is None or t > best:
            best, who = t, msg.strip()[:60]
    presence = (honmono > 0, "直近60本のうち中身のあるコミット %d本" % honmono)
    schema = (True, "gitのログが読めた")
    return best, presence, schema, who


def p_kanmon():
    """門が最後に「弾いた」時刻。弾きが止まる＝門が開けっぱなし（1142_loop.py と同じ考え方）。"""
    cands = ["1142_kanmon.jsonl", "1133_og_kanmon.jsonl",
             "1131_kanmon_daicho.jsonl", "main_kanmon_daicho.jsonl"]
    best, who, hajiita = None, None, 0
    for c in cands:
        for r in jl_read(os.path.join(ST, c), 500):
            tsuuka = r.get("tsuuka")
            if tsuuka is True:
                continue
            hajiita += 1
            t = parse_ts(r.get("at") or r.get("t"))
            if t and (best is None or t > best):
                best, who = t, "%s: %s" % (c, str(r.get("riyuu") or "")[:40])
    presence = (hajiita > 0, "直近の台帳で弾いた記録 %d件" % hajiita)
    schema = (True, "門の台帳が読めた")
    return best, presence, schema, who


def p_gaibu():
    """外のAIから最後に返ってきた時刻（投げっぱなしを年齢で捕まえる）。"""
    rows = jl_read(os.path.join(ST, "gaibu_ai", "daicho.jsonl"))
    best, who, kaeri = None, None, 0
    for r in rows:
        if r.get("kaeri") not in ("yes", "partial"):
            continue
        kaeri += 1
        t = parse_ts(r.get("kaeri_at"))
        if t and (best is None or t > best):
            best, who = t, "%s: %s" % (r.get("ai"), str(r.get("what") or "")[:40])
    nage = len(rows)
    presence = (kaeri > 0, "投げた %d件 / 返った %d件" % (nage, kaeri))
    schema = (True, "外部AI台帳が読めた")
    return best, presence, schema, who


def p_shukudai():
    """宿題（未完了）の件数が最後に減った時刻。減らないなら残高は増える一方。"""
    hist = jl_read(HIST)
    cur = None
    d = jread(os.path.join(ST, "public", "shukudai.json"), {}) or {}
    tally = d.get("tally") or {}
    if isinstance(tally.get("open"), int):
        cur = tally["open"]
    best, who = None, None
    prev = None
    for row in hist:
        v = ((row.get("pipes") or {}).get("shukudai") or {}).get("value")
        t = parse_ts(row.get("at"))
        if v is None or t is None:
            continue
        if prev is not None and v < prev:
            best, who = t, "%d件 → %d件" % (prev, v)
        prev = v
    if best is None and cur is not None:
        # 履歴がまだ無いあいだは「分からない」を偽装しない。ファイルの更新時刻で代用する。
        try:
            best = os.path.getmtime(os.path.join(ST, "public", "shukudai.json"))
            who = "履歴がまだ無いので台帳の更新時刻で代用（%s件）" % cur
        except Exception:
            pass
    presence = (cur is not None, "未完了 %s件" % (cur if cur is not None else "不明"))
    schema = (cur is not None, "shukudai.json の tally.open が読めた"
              if cur is not None else "tally.open が無い")
    return best, presence, schema, who, cur


PIPES = [
    {"id": "hassha", "na": "本物の発車が終わった", "shikii": 12 * H, "fn": p_hassha},
    {"id": "commit", "na": "中身のあるコミット", "shikii": 6 * H, "fn": p_commit},
    {"id": "kanmon", "na": "門が弾いた", "shikii": 24 * H, "fn": p_kanmon},
    {"id": "gaibu", "na": "外のAIから返ってきた", "shikii": 24 * H, "fn": p_gaibu},
    {"id": "shukudai", "na": "宿題が減った", "shikii": 48 * H, "fn": p_shukudai},
]


def sli(pipe_id, shikii, window_sec):
    """Freshness SLI =（年齢が閾値以下だった標本）/（全標本）× 100。標本が無ければ None。"""
    t0 = now().timestamp() - window_sec
    ok = tot = 0
    for row in jl_read(HIST):
        t = parse_ts(row.get("at"))
        if t is None or t < t0:
            continue
        p = (row.get("pipes") or {}).get(pipe_id)
        if not p or p.get("ageSec") is None:
            continue
        tot += 1
        if p["ageSec"] <= shikii:
            ok += 1
    if tot == 0:
        return None, 0
    return round(ok * 100.0 / tot, 1), tot


def streak(pipe_id, shikii):
    """直近から数えて、連続で閾値超えだった回数。"""
    n = 0
    for row in reversed(jl_read(HIST)):
        p = (row.get("pipes") or {}).get(pipe_id)
        if not p or p.get("ageSec") is None:
            break
        if p["ageSec"] > shikii:
            n += 1
        else:
            break
    return n


def hakaru(write=True):
    t_now = now()
    pipes, alerts = {}, []
    for p in PIPES:
        res = p["fn"]()
        last, presence, schema, who = res[0], res[1], res[2], res[3]
        value = res[4] if len(res) > 4 else None
        age = None if last is None else int(t_now.timestamp() - last)
        s7, n7 = sli(p["id"], p["shikii"], SLI_WINDOW_SEC)
        sb, nb = sli(p["id"], p["shikii"], BURN_WINDOW_SEC)
        pipes[p["id"]] = {
            "na": p["na"],
            "ageSec": age,
            "ageH": None if age is None else round(age / 3600.0, 1),
            "shikiiH": round(p["shikii"] / 3600.0, 1),
            "lastAt": None if last is None else
                      datetime.datetime.fromtimestamp(last, JST).isoformat(timespec="seconds"),
            "nani": who,
            "value": value,
            "presenceOK": bool(presence[0]), "presenceNaze": presence[1],
            "schemaOK": bool(schema[0]), "schemaNaze": schema[1],
            "sli7d": s7, "sli7dN": n7, "sliNow": sb, "sliNowN": nb,
        }

    # ── 判定（OneUptimeの3種をそのまま写す）──────────────────────────
    # ★ここで「走行本数」を一切見ない。見るのは年齢だけ。
    for p in PIPES:
        d = pipes[p["id"]]
        age, shikii = d["ageSec"], p["shikii"]
        if age is None:
            alerts.append({"rule": "FreshnessUnknown", "pipe": p["id"], "level": "warn",
                           "midashi": "「%s」がいつ出たのか測れません" % p["na"],
                           "naze": d["schemaNaze"]})
            continue
        st = streak(p["id"], shikii) + (1 if age > shikii else 0)
        if age > shikii * STALLED_MULT:
            alerts.append({"rule": "DataPipelineStalled", "pipe": p["id"], "level": "red",
                           "midashi": "「%s」が%.1f時間出ていません（閾値%.0f時間の%d倍超）"
                                      % (p["na"], age / 3600.0, shikii / 3600.0, STALLED_MULT),
                           "naze": d["nani"]})
        elif age > shikii and st >= VIOLATION_STREAK:
            alerts.append({"rule": "DataFreshnessViolation", "pipe": p["id"], "level": "red",
                           "midashi": "「%s」が%.1f時間出ていません（閾値%.0f時間）"
                                      % (p["na"], age / 3600.0, shikii / 3600.0),
                           "naze": d["nani"]})
        if d["sli7d"] is not None and d["sliNow"] is not None and \
                d["sliNowN"] >= 3 and d["sliNow"] < d["sli7d"] - 20:
            alerts.append({"rule": "FreshnessBurnRateHigh", "pipe": p["id"], "level": "warn",
                           "midashi": "「%s」の直近が急に悪くなっています（%.0f%% → %.0f%%）"
                                      % (p["na"], d["sli7d"], d["sliNow"]),
                           "naze": "直近%d標本" % d["sliNowN"]})
        if not d["presenceOK"]:
            alerts.append({"rule": "PresenceCheckFailed", "pipe": p["id"], "level": "red",
                           "midashi": "「%s」の出口が空です" % p["na"],
                           "naze": d["presenceNaze"]})

    aka = [a for a in alerts if a["level"] == "red"]
    payload = {
        "at": t_now.isoformat(timespec="seconds"),
        "moto": ["OneUptime Freshness SLOs "
                 "https://oneuptime.com/blog/post/2026-01-30-freshness-slos/view",
                 "Prefactor Detecting silent failures "
                 "https://prefactor.tech/blog/detecting-silent-failures-in-agent-responses"],
        "kime": "走行本数・プロセス数・ラベルの文字列は判定に使わない。成果の年齢だけで判定する。",
        "pipes": pipes,
        "alerts": alerts,
        "akaN": len(aka),
        "ichigyou": (aka[0]["midashi"] if aka else
                     ("成果の鮮度は全部いまの閾値の中です" if alerts == [] else alerts[0]["midashi"])),
    }
    if write:
        os.makedirs(OUTDIR, exist_ok=True)
        tmp = "%s.tmp.%d" % (OUT, os.getpid())
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        os.replace(tmp, OUT)
        with io.open(HIST, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": payload["at"],
                                "pipes": {k: {"ageSec": v["ageSec"], "value": v["value"]}
                                          for k, v in pipes.items()},
                                "akaN": len(aka)}, ensure_ascii=False) + "\n")
    return payload


def show(p):
    print("成果の鮮度計  %s" % p["at"])
    print("  %s" % p["kime"])
    for k, v in p["pipes"].items():
        age = "測れない" if v["ageH"] is None else "%.1fh" % v["ageH"]
        sli7 = "—" if v["sli7d"] is None else "%.0f%%(%d)" % (v["sli7d"], v["sli7dN"])
        mark = "赤" if (v["ageSec"] is not None and v["ageSec"] > v["shikiiH"] * 3600) else "　"
        print("  %s %-10s %-16s 年齢%-9s 閾値%.0fh  SLI7d=%s  %s"
              % (mark, k, v["na"], age, v["shikiiH"], sli7, v["nani"] or ""))
    print("  ---")
    if not p["alerts"]:
        print("  鳴っていません")
    for a in p["alerts"]:
        print("  [%s] %s / %s" % (a["level"].upper(), a["midashi"], a["rule"]))


if __name__ == "__main__":
    w = "--no-write" not in sys.argv
    res = hakaru(write=w)
    if "--show" in sys.argv or "--no-write" in sys.argv:
        show(res)
    else:
        print("鮮度計：赤%d件／%s" % (res["akaN"], res["ichigyou"]))
