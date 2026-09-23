#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
落ちた記録（ochita_kiroku）  2026-09-24

たまごさん「3本同時に落ちた。まず落ちた理由を突き止めてから続きをやる」
「二度と黙って死なない形にする」「落ちたが status/ に必ず残るようにして、Dispatchが気づける形にする」

■ なぜ作ったか（実測に基づく）
  2026-09-24、便が3本同時に途中で落ちた。ところが status/ のどこを見ても
  「落ちた」という記録が1件も無かった。history.jsonl には「その瞬間に生きていた便」が
  並ぶだけで、**居なくなったことは誰も書いていない。**
  だから「なぜ止まったのか」が誰にも分からないまま時間だけが過ぎる（憲法§11-3の最悪形）。

■ 何をするか（これだけ。重い処理はしない。1秒で終わる）
  1. status/history.jsonl の直近2スイープを突き合わせ、**消えた便**を出す。
     2本以上が同じスイープで消えていたら「同時落ち」として印を付ける。
  2. 消えた瞬間の「周りの状態」を一緒に凍らせる（後から原因を当てられるように）：
     ログイン／週枠／git index.lock／メモリ・スワップ／ディスク／工場が空回ししていないか
  3. status/ochita.json（最新1件・PWAとDispatchが読む）と
     status/ochita.jsonl（全履歴・追記のみ）に書く。
  4. 原因が確定できないときは **"why": "不明"** と書く。取り繕わない（たまごさんの指示）。

■ 消さない・動かさない
  このスクリプトは書き込みしかしない。既存ファイルの削除・移動・上書きはしない
  （ochita.json のみ毎回作り直す。これは自分が作ったファイル）。

使い方:
  python3 ochita_kiroku.py           # 判定して記録
  python3 ochita_kiroku.py --dry-run # 判定だけ表示（書かない）
  python3 ochita_kiroku.py --show    # いまの ochita.json を表示
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(REPO, "status")

HISTORY = os.path.join(ST, "history.jsonl")
OUT_JSON = os.path.join(ST, "ochita.json")
OUT_JSONL = os.path.join(ST, "ochita.jsonl")
SEEN = os.path.join(ST, ".ochita_seen.json")


def now():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")


def jload(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def tail_lines(path, n):
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = min(size, 200_000)
            f.seek(size - block)
            data = f.read().decode("utf-8", "replace")
        return [x for x in data.splitlines() if x.strip()][-n:]
    except Exception:
        return []


# ---------- 1. 周りの状態を凍らせる ----------

def snapshot_shuui():
    """落ちた瞬間の周辺状況。ここに全部の容疑者を並べる。"""
    s = {}

    # ログイン（過去に全セッションを黙って殺している最有力容疑者）
    auth = jload(os.path.join(ST, "auth_keeper.json"), {}) or {}
    flag = os.path.join(ST, "auth_expired.flag")
    s["login"] = {
        "state": auth.get("state") or ("expired" if os.path.exists(flag) else "unknown"),
        "why": auth.get("lastNgWhy"),
        # flagの更新時刻は毎回の巡回で上書きされるので「いつから切れているか」にならない。
        # auth_keeper.log の最初のNG行を正本にする（2026-09-24 実測で 03:25 と出てしまった修正）
        "ngSince": _auth_ng_since(),
        "ng": (auth.get("state") == "expired") or os.path.exists(flag),
    }

    # 週のクレジット
    q = jload(os.path.join(ST, "quota.json"), {}) or {}
    s["waku"] = {
        "allPct": q.get("allPct"),
        "level": q.get("allLevel"),
        "resetAt": q.get("resetAt"),
        "ng": _num(q.get("allPct")) is not None and _num(q.get("allPct")) >= _num(q.get("stopPct"), 85),
    }

    # git のロック（心臓の自動コミットが止まる）
    lock = os.path.join(REPO, ".git", "index.lock")
    s["gitLock"] = {"exists": os.path.exists(lock), "since": now_of(lock), "ng": os.path.exists(lock)}

    # Macの体力
    h = jload(os.path.join(ST, "health.json"), {}) or {}
    swap = _last_swap_gb()
    s["mac"] = {
        "memPressure": h.get("memPressure"),
        "memAvailGB": h.get("memAvailGB"),
        "diskFreeGB": h.get("diskFreeGB"),
        "swapGB": swap,
        "ng": (h.get("memPressure") in ("red", "yellow"))
        or (_num(h.get("diskFreeGB"), 999) < 5)
        or (swap is not None and swap >= 20),
    }

    # 工場が本物を出せているか（空回しだけなら実質止まっている）
    s["kojo"] = _karamawashi()

    return s


def now_of(path):
    try:
        return datetime.fromtimestamp(os.path.getmtime(path), JST).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None


def _auth_ng_since():
    """auth_keeper.log を頭から見て、最後にOKだった行より後の最初のNG行を返す。"""
    path = os.path.join(ST, "auth_keeper.log")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = [x for x in f.read().splitlines() if x.strip()]
    except Exception:
        return None
    # 「通知: expired」のような添え書きでリセットしてしまわないこと（2026-09-24 実測で誤り）。
    # 戻った合図が出た行だけでリセットする。
    MODOTTA = ("戻りました", "復活", "ログインできています", "通知: ok", "ok(")
    since = None
    for ln in lines:
        if any(k in ln for k in MODOTTA):
            since = None
        elif "切れています" in ln and since is None:
            since = ln[:16]
    return since


def _num(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def _last_swap_gb():
    for ln in reversed(tail_lines(os.path.join(ST, "heavy_events.jsonl"), 40)):
        try:
            d = json.loads(ln)
        except Exception:
            continue
        g = d.get("swapGB")
        if isinstance(g, (int, float)):
            return round(g / 1024.0, 2) if g > 1000 else round(g, 2)
    return None


def _karamawashi():
    """auto_launch.log の直近から、本物が出せているかを見る。"""
    lines = tail_lines(os.path.join(ST, "auto_launch.log"), 120)
    minogashi = sum(1 for x in lines if "見送り" in x)
    kara = sum(1 for x in lines if "空回し" in x)
    honmono = sum(1 for x in lines if "発車" in x and "空回し" not in x and "テスト発車" not in x)
    return {
        "直近120行": {"見送り": minogashi, "空回し": kara, "本物の発車": honmono},
        "ng": honmono == 0 and (minogashi + kara) > 0,
        "note": "本物の発車が0で見送り・空回しだけなら、工場は動いて見えて何も作っていない",
    }


# ---------- 2. 消えた便を見つける ----------

def find_kieta():
    """history.jsonl の直近2スイープを突き合わせ、居なくなった便を返す。"""
    rows = []
    for ln in tail_lines(HISTORY, 400):
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
    if not rows:
        return None, [], []

    sweeps = {}
    for r in rows:
        sweeps.setdefault(r.get("t"), []).append(r)
    keys = sorted(sweeps.keys())
    if len(keys) < 2:
        return None, [], []

    ima, mae = keys[-1], keys[-2]
    now_pids = {r.get("pid") for r in sweeps[ima]}
    kieta = [r for r in sweeps[mae] if r.get("pid") not in now_pids]
    return ima, kieta, sweeps[ima]


# ---------- 3. 理由を決める（分からなければ「不明」） ----------

def kimeru(shuui, kieta_n):
    """容疑者のうち ng が立っているものを並べる。1つも無ければ不明。"""
    hits = []
    if shuui["login"]["ng"]:
        hits.append(("ログイン切れ", f"Claudeのログインが切れています（{shuui['login']['why'] or '理由不明'}）／{shuui['login']['ngSince']}から"))
    if shuui["waku"]["ng"]:
        hits.append(("週のクレジット上限", f"全モデル {shuui['waku']['allPct']}%（リセット {shuui['waku']['resetAt']}）"))
    if shuui["gitLock"]["ng"]:
        hits.append(("git index.lock が残っている", f"{shuui['gitLock']['since']}から。心臓の自動コミットが止まる"))
    if shuui["mac"]["ng"]:
        hits.append(("Macの体力", f"メモリ={shuui['mac']['memPressure']} 空き={shuui['mac']['memAvailGB']}GB スワップ={shuui['mac']['swapGB']}GB ディスク={shuui['mac']['diskFreeGB']}GB"))
    if shuui["kojo"]["ng"]:
        k = shuui["kojo"]["直近120行"]
        hits.append(("工場が空回しだけ", f"直近120行で 本物の発車0／見送り{k['見送り']}／空回し{k['空回し']}"))

    if not hits:
        return "不明", ["どの容疑者にも印が立っていません。分かりません（取り繕わない）"], "unknown"

    level = "同時落ち" if kieta_n >= 2 else ("落ちた" if kieta_n == 1 else "危険な状態")
    return hits[0][0], [f"{k}：{v}" for k, v in hits], level


def main():
    dry = "--dry-run" in sys.argv
    if "--show" in sys.argv:
        print(json.dumps(jload(OUT_JSON, {}), ensure_ascii=False, indent=1))
        return 0

    ima, kieta, ikiteru = find_kieta()
    shuui = snapshot_shuui()
    why, dansho, level = kimeru(shuui, len(kieta))

    rec = {
        "t": now(),
        "sweep": ima,
        "level": level,
        "kietaN": len(kieta),
        "kieta": [
            {
                "pid": r.get("pid"),
                "cli": r.get("cli"),
                "title": r.get("title"),
                "kind": r.get("kind"),
                "start": r.get("start"),
            }
            for r in kieta
        ],
        "ikiteruN": len(ikiteru),
        "why": why,
        "dansho": dansho,
        "shuui": shuui,
        "hitokoto": _hitokoto(level, len(kieta), why),
    }

    if dry:
        print(json.dumps(rec, ensure_ascii=False, indent=1))
        return 0

    # ochita.json は毎回上書き（自分が作ったファイルのみ）
    os.makedirs(ST, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)

    # 履歴は「何か起きたときだけ」追記（毎回書くと流れて消える）
    seen = jload(SEEN, {}) or {}
    key = f"{level}|{why}|{len(kieta)}"
    if (len(kieta) > 0 or level == "危険な状態") and seen.get("last") != key:
        with open(OUT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        seen["last"] = key
        seen["at"] = now()
        with open(SEEN, "w", encoding="utf-8") as f:
            json.dump(seen, f, ensure_ascii=False)
        _dispatch_ni_shiraseru(rec)

    print(rec["hitokoto"])
    return 0


def _dispatch_ni_shiraseru(rec):
    """Dispatchの受信箱（dispatch_outbox.jsonl）に1行だけ積む。追記のみ。
    たまごさんの指示「落ちたが status/ に必ず残るようにして、Dispatchが気づける形にする」。"""
    try:
        naka = "／".join(
            f"{k.get('title') or '（不明）'}(pid {k.get('pid')})" for k in rec["kieta"][:5]
        ) or "（消えた便の名前は取れていません）"
        line = {
            "ts": datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "n": "ochita",
            "type": "red" if rec["level"] == "同時落ち" else "ochita",
            "title": f"{rec['hitokoto']}",
            "message": (
                f"消えた便：{naka}。"
                f"いちばん濃い容疑：{rec['why']}。"
                f"断章：{' / '.join(rec['dansho'])}。"
                f"詳しくは status/ochita.json（履歴は status/ochita.jsonl）。"
            ),
        }
        with open(os.path.join(ST, "dispatch_outbox.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 知らせに失敗しても記録そのものは残っている。ここで落ちない


def _hitokoto(level, n, why):
    if level == "同時落ち":
        return f"🚨 {n}本が同時に消えました。いちばん濃い容疑：{why}"
    if level == "落ちた":
        return f"⚠️ 1本消えました。いちばん濃い容疑：{why}"
    if level == "危険な状態":
        return f"⚠️ まだ落ちていませんが危険です：{why}"
    return "異常なし"


if __name__ == "__main__":
    sys.exit(main())
