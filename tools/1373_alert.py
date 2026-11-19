#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1373番【使いすぎアラート】「今使いすぎです、もうすぐ固まります」を、名指しで出す係。

たまごさん（2026-09-18・判定日赤）:
  「今使いすぎです、もうすぐ固まります」というアラートがほしい
  （例：「Notion を終了してください」「Spotify を落としてください、そうすれば空きができます」など）

━━ 既存資産との違い ━━
  tools/1200_tatamu.py は「こちら側（工場が自分で作ったプロセス）」だけを畳む係で、
  Brave・Notion・Spotify等のたまごさん自身のGUIアプリには**一切触らない**
  （brave_onegai() でBraveにだけ1回お願いする形はあるが、他アプリは対象外）。
  今回の依頼は「触る」ではなく「名指しで気づかせる」＝GUIアプリ全般を対象にした
  読み取り専用の警告係。1200_tatamu.py の測定ロジック（hakaru）とは独立して
  status/1200_tatamu.json を読むだけ（psを二重に叩かない・軽量）。

━━ 判定 ━━
  スワップ使用率・5分ロード比のどちらかが閾値を超えたら赤（危険）／黄（注意）。
  green のときは suggestions を出さない（機械が「問題あり」を偽装しない）。

━━ 出す提案 ━━
  ps -Ao rss=,command= から `/Applications/◯◯.app/` を含む行をアプリ名でグループ化し、
  RSS合計が大きい順に上位3つを「◯◯を終了してください（約◯GB空きます）」として出す。
  こちら側のプロセス（Claude.app・claude-code・工場のtools/*.py等）と、
  閉じられないと分かっているBraveは対象から除外する（Brave専用の1回お願いは1200番が担当）。

呼ばれ方（心臓から毎周・15秒サイクルに相乗り。GATE_SECで間引く）:
  python3 tools/1373_alert.py --shikii
単発で見るだけ:
  python3 tools/1373_alert.py --dry-run

出力: status/public/1373_alert.json（進捗表が読む1枚）
      status/1373_alert.jsonl（赤になった時だけ1行追記・証拠ログ）
"""
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
PUB = os.path.join(ST, "public")
OUT = os.path.join(PUB, "1373_alert.json")
LOG = os.path.join(ST, "1373_alert.jsonl")
GATE = os.path.join(ST, ".1373_alert_at")
TATAMU_JSON = os.path.join(ST, "1200_tatamu.json")

GATE_SEC = 55          # 心臓から毎周呼ばれても、実際に測るのは1分に1回（1200番と同じ間引き方式）
SWAP_RED = 0.85         # 固まる手前。1200番の「畳む」基準と同じ数字（実測でここまで来ると本当に重い）
SWAP_YELLOW = 0.65      # そろそろ危ない、の目安
LOAD_RED = 1.0          # 5分ロード ÷ コア数 が1.0以上＝コア数を超えて並んでいる
LOAD_YELLOW = 0.75
STALE_SEC = 6 * 60      # 1200_tatamu.json がこれより古い＝測定が止まっている（黙って握りつぶさない）

# こちら側（工場自身）とBrave（別の係が1回お願い済み）は提案の対象から外す。
# 1200_tatamu.py の KEEP と考え方は同じだが、ここは「殺さない・出さないだけ」なので
# 判定を厳しめにしても事故が起きない（読み取り専用）。
JIBUNGAWA = re.compile(
    r"(Brave Browser|Claude\.app|claude-code|/MacOS/claude |chrome-native-host|"
    r"Electron Framework|caffeinate|python3? |/tools/|node_modules|Xcode|Finder|Dock|"
    r"WindowServer|loginwindow|kernel_task|mds_stores|Spotlight|Virtualization\.framework|"
    r"XPCServices|coreaudiod|bird|cloudd|assistantd|typeless)"
)

APP_PATH = re.compile(r"/Applications/([^/]+?)\.app/")


def sh(cmd, timeout=15):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout or ""
    except Exception:
        return ""


def jload(p, d=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def jsave(p, o):
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
    except Exception:
        pass
    tmp = "%s.tmp.%d" % (p, os.getpid())
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(o, ensure_ascii=False, indent=1))
    os.replace(tmp, p)


def app_candidates():
    """ps を1回だけ読んで、たまごさんが閉じられる一般GUIアプリをRSS合計順に返す。"""
    out = sh(["ps", "-Ao", "rss=,command="], timeout=20)
    groups = {}
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        parts = ln.split(None, 1)
        if len(parts) != 2:
            continue
        rss_s, cmd = parts
        try:
            rss = int(rss_s)
        except Exception:
            continue
        if JIBUNGAWA.search(cmd):
            continue
        m = APP_PATH.search(cmd)
        if not m:
            continue
        name = m.group(1)
        groups[name] = groups.get(name, 0) + rss
    ranked = sorted(groups.items(), key=lambda kv: -kv[1])
    return [{"app": name, "rssGB": round(rss / 1048576.0, 2)} for name, rss in ranked if rss > 0]


def build(dry=False):
    m = jload(TATAMU_JSON, {}) or {}
    now_ts = time.time()
    stale = True
    try:
        stale = (now_ts - os.path.getmtime(TATAMU_JSON)) > STALE_SEC
    except Exception:
        stale = True

    swap_used = m.get("swapUsedGB")
    swap_total = m.get("swapTotalGB")
    load_ratio = m.get("loadRatio")
    swap_pct = (swap_used / swap_total) if (swap_used and swap_total) else None

    level = "green"
    reasons = []
    if not stale and swap_pct is not None:
        if swap_pct >= SWAP_RED:
            level = "red"
            reasons.append("スワップ %.1f/%.1fGB（%.0f%%）" % (swap_used, swap_total, swap_pct * 100))
        elif swap_pct >= SWAP_YELLOW and level != "red":
            level = "yellow"
            reasons.append("スワップ %.1f/%.1fGB（%.0f%%）" % (swap_used, swap_total, swap_pct * 100))
    if not stale and load_ratio is not None:
        if load_ratio >= LOAD_RED:
            level = "red"
            reasons.append("5分ロード比 %.2f" % load_ratio)
        elif load_ratio >= LOAD_YELLOW and level == "green":
            level = "yellow"
            reasons.append("5分ロード比 %.2f" % load_ratio)

    # 2026-10-01：Claudeが開いたBraveタブが1枚でも残っていたら赤（たまごさんの場所に置きっぱなし）。
    ct = (m.get("brave") or {}).get("claudeTabs")
    if not stale and ct:
        level = "red"
        reasons.append("ClaudeがBraveに開いたタブが%d枚残っている" % ct)

    suggestions = []
    if level in ("red", "yellow"):
        cands = app_candidates()[:3]
        for c in cands:
            if c["rssGB"] < 0.1:
                continue
            suggestions.append({
                "app": c["app"],
                "rssGB": c["rssGB"],
                "message": "%s を終了してください（約%.1fGB空きます）" % (c["app"], c["rssGB"]),
            })

    if level == "red" and ct and len(reasons) == 1:
        midashi = "ClaudeのタブがBraveに%d枚残っています" % ct
    elif level == "red":
        midashi = "今使いすぎです、もうすぐ固まります"
    elif level == "yellow":
        midashi = "そろそろ重くなってきています"
    else:
        midashi = None

    payload = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "level": level,
        "midashi": midashi,
        "reasons": reasons,
        "swapUsedGB": swap_used,
        "swapTotalGB": swap_total,
        "swapPct": round(swap_pct * 100, 1) if swap_pct is not None else None,
        "loadRatio": load_ratio,
        "suggestions": suggestions,
        "stale": stale,
        "sourceAt": m.get("at"),
    }
    if not dry:
        jsave(OUT, payload)
        if level == "red":
            try:
                with io.open(LOG, "a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            except Exception:
                pass
    return payload


def main():
    dry = "--dry-run" in sys.argv
    shikii = "--shikii" in sys.argv
    if shikii and not dry:
        try:
            if time.time() - os.path.getmtime(GATE) < GATE_SEC:
                return 0
        except Exception:
            pass
        try:
            io.open(GATE, "w").write(str(int(time.time())))
        except Exception:
            pass
    payload = build(dry=dry)
    print(json.dumps(payload, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
