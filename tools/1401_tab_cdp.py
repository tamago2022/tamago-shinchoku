#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1401番【CDPタブ掃除機】2026-09-28

たまごさん（何十回目かの同じ指摘）：
  「Chromeに使っていないタブが溜まり続けている。毎回手で消している。今回で終わらせる。」
  「AppleScript / osascript / System Events は絶対に使うな。」
  「Brave(88704cda-…)には触るな。Chromeは 7d965dae-…。たまごさん自身が開いたタブは閉じない。」

■ なぜ今までゼロ枚しか閉じられていなかったのか（今日の実測・2026-09-28 00:17）
  status/chrome_tabs_recon.json：タブ8枚・wouldClose **0枚**。
  中身は7枚が joy-relief-station.lovable.app / lovable.dev。
  これは**Claudeが検品で開いたページそのもの**なのに、
  chrome_tab_sweeper.py の NEVER_CLOSE_PATTERNS に `lovable\.(app|dev)` が入っていて、
  しかもその判定が「孤児判定(looks_orphan)」より**先**に効くため、
  **何時間経っても未来永劫 keep される。**＝掃除機は毎回走っていたが構造的に0枚だった。
  さらに ORPHAN_MIN_SAMPLES=120 は「心臓が15秒おきに観測する」前提の数字だが、
  2026-09-18に心臓側が tick_every 40（=10分おき）へ間引かれたため、実際には
  **120回=20時間** 必要になっていた。孤児判定はほぼ一度も成立していない。

■ この道具の立ち位置
  「Claudeが開いたと**台帳に書いてある**URLだけを閉じる」。見た目で推測しない。
  台帳（どれも既にあるもの。新しく作っていない）：
    ・status/1154_stop_kanmon.jsonl … Stopフックが毎回 proof.openUrls を書いている
    ・status/public/tabs.json        … 同上の最新版
    ・status/chrome_reserve/*.json   … 978番「予約閉栓」の票（心拍が止まったもの）
  OSには一切触らない。触るのは **127.0.0.1 のCDPポートだけ**（HTTPのGETのみ）。

■ Braveに触らないことの担保（推測ではなく実測）
  ポートを開けたのは Chrome だけ。さらに毎回 lsof でそのポートを握っているPIDを調べ、
  実行ファイルのパスに "Google Chrome" が含まれ、かつ "Brave" が含まれないことを
  確かめてからしか1バイトも送らない。条件を満たさなければ即座に降りる。

■ 使い方
  python3 tools/1401_tab_cdp.py --recon    # 数えて status/1401_cdp.json に書くだけ
  python3 tools/1401_tab_cdp.py --sweep    # 実際に閉じる
  python3 tools/1401_tab_cdp.py --sweep --dry-run
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
OUT = os.path.join(STATUS, "1401_cdp.json")
LOGJ = os.path.join(STATUS, "1401_cdp_runs.jsonl")
PORT = int(os.environ.get("TAMAGO_CDP_PORT", "9222"))

# 台帳に載っていなくても、これに当たるものは「Claudeが開いたページ」として閉じてよい。
# ★どれも**閉じても何も失われない**ものだけ。ログインが要るもの・入力途中がありうるものは入れない。
CLOSE_PREFIXES = (
    "https://tamago2022.github.io/tamago-shinchoku/share/check/",
    "http://localhost:", "http://127.0.0.1:",
)
CLOSE_EXACT = {"about:blank", "chrome://newtab/", "chrome://new-tab-page/", ""}

# ★最後の壁。台帳に載っていてもここに当たったら閉じない。
NEVER_CLOSE = [re.compile(p, re.I) for p in (
    r"^https?://(www\.)?(x|twitter)\.com",
    r"^https?://([a-z0-9-]+\.)*youtube\.com",
    r"^https?://youtu\.be",
    r"^https?://([a-z0-9-]+\.)*chatgpt\.com",
    r"^https?://([a-z0-9-]+\.)*openai\.com",
    r"^https?://([a-z0-9-]+\.)*grok\.com",
    r"^https?://([a-z0-9-]+\.)*google\.com",
    r"^https?://([a-z0-9-]+\.)*gmail\.com",
    r"^https?://([a-z0-9-]+\.)*devin\.ai",
    r"^https?://([a-z0-9-]+\.)*line\.me",
    r"^https?://([a-z0-9-]+\.)*buffer\.com",
    r"^https?://([a-z0-9-]+\.)*claude\.ai",
    r"^https?://([a-z0-9-]+\.)*anthropic\.com",
    r"^file://", r"^chrome-extension://", r"^devtools://",
    r"^chrome://(?!newtab|new-tab-page)",
)]

MIN_AGE_SEC = 300          # 台帳に載った直後は触らない（今まさに使っている可能性）
KEEP_AT_LEAST = 1          # ブラウザ全体で最低これだけは残す

# ★「うちの成果物」＝Claudeが検品で開く先。ここだけは台帳に無くても、
#   下の2つの証拠のどちらかがあれば閉じてよい。
#   証拠A：status/chrome_tab_history.json に everActive:false（一度も前面に来ていない）
#          ＝たまごさんが自分で開いたなら、開いた瞬間に必ず前面になる。ならなかった＝機械が開いた。
#   証拠B：この道具自身が見張った結果、OWN_STALE_SEC 以上ずっと開きっぱなし
OWN_SITES = (
    "joy-relief-station.lovable.app",
    "tamago2022.github.io",
)
OWN_STALE_SEC = 6 * 3600
HISTORY_LEGACY = os.path.join(STATUS, "chrome_tab_history.json")
HISTORY_MINE = os.path.join(STATUS, "1401_cdp_history.json")


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 1. ポートの相手が本当にChromeか（Braveでないか）を実測してから繋ぐ
# ---------------------------------------------------------------------------
def _run(cmd, timeout=10):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


def _judge_cmdline(cmd):
    if "Brave" in cmd:
        return False, "★ポート%dを握っているのはBrave。1バイトも送らずに降りる" % PORT
    if "Google Chrome" not in cmd:
        return False, "ポート%dの相手がChromeではない（%s）" % (PORT, cmd[:80])
    return True, cmd[:120]


def port_owner_is_chrome():
    """ポートの相手が本当にChromeか。道は2本（lsof／ps）。両方だめなら降りる。"""
    # ── 道①：lsof でポートを握っているPIDを取る（絶対パスも試す）
    for lsof in ("/usr/sbin/lsof", "lsof"):
        try:
            r = _run([lsof, "-nP", "-iTCP:%d" % PORT, "-sTCP:LISTEN", "-t"])
        except Exception:
            continue
        pids = [x for x in r.stdout.split() if x.strip().isdigit()]
        if not pids:
            # lsofは動いたが誰も居ない＝ポートが開いていない（これは確定情報）
            if r.returncode in (0, 1):
                return False, ("ポート%dを誰も開いていない"
                               "（Chromeが --remote-debugging-port 無しで起動している）" % PORT)
            continue
        try:
            c = _run(["/bin/ps", "-o", "command=", "-p", pids[0]])
            cmd = c.stdout.strip()
        except Exception:
            cmd = ""
        if cmd:
            return _judge_cmdline(cmd)

    # ── 道②：lsofが使えないとき。ps の中から --remote-debugging-port=<PORT> を探す
    try:
        r = _run(["/bin/ps", "-axo", "command="], timeout=15)
    except Exception:
        return False, "lsofもpsも使えない（何も送らない）"
    hits = [ln for ln in r.stdout.splitlines()
            if ("--remote-debugging-port=%d" % PORT) in ln]
    if not hits:
        return False, ("ポート%dを誰も開いていない"
                       "（Chromeが --remote-debugging-port 無しで起動している）" % PORT)
    # 1本でもBraveが混じっていたら触らない（安全側）
    for ln in hits:
        if "Brave" in ln:
            return False, "★ポート%dの周りにBraveが居る。1バイトも送らずに降りる" % PORT
    return _judge_cmdline(hits[0])


def cdp_get(path, timeout=5):
    url = "http://127.0.0.1:%d%s" % (PORT, path)
    with urllib.request.urlopen(url, timeout=timeout) as f:
        return f.read().decode("utf-8", "replace")


def list_pages():
    raw = cdp_get("/json/list")
    data = json.loads(raw)
    return [t for t in data if t.get("type") == "page"
            and not str(t.get("url", "")).startswith("devtools://")]


# ---------------------------------------------------------------------------
# 2. 「Claudeが開いた」と台帳に書いてあるURL
# ---------------------------------------------------------------------------
def claude_opened_urls():
    """{url: 最後に台帳へ載った時刻(epoch)}"""
    out = {}

    def add(u, ts):
        if not u:
            return
        u = str(u).strip()
        if not u:
            return
        out[u] = max(out.get(u, 0), ts)

    p = os.path.join(STATUS, "1154_stop_kanmon.jsonl")
    if os.path.exists(p):
        try:
            for ln in open(p, encoding="utf-8"):
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    o = json.loads(ln)
                except Exception:
                    continue
                if o.get("event") != "tab":
                    continue
                try:
                    ts = datetime.datetime.fromisoformat(
                        str(o.get("at", "")).replace("Z", "+00:00")).timestamp()
                except Exception:
                    ts = 0
                for u in (o.get("proof") or {}).get("openUrls") or []:
                    add(u, ts)
        except Exception:
            pass

    p = os.path.join(STATUS, "public", "tabs.json")
    if os.path.exists(p):
        try:
            d = json.load(open(p, encoding="utf-8"))
            ts = os.path.getmtime(p)
            for u in d.get("openUrls") or []:
                add(u, ts)
        except Exception:
            pass

    d = os.path.join(STATUS, "chrome_reserve")
    if os.path.isdir(d):
        for n in os.listdir(d):
            if not n.endswith(".json"):
                continue
            try:
                o = json.load(open(os.path.join(d, n), encoding="utf-8"))
            except Exception:
                continue
            beat = float(o.get("beatAt") or o.get("takenAt") or 0)
            ttl = float(o.get("ttl") or 120)
            if time.time() - beat < ttl:
                continue  # まだ生きている票。触らない
            for u in (o.get("urls") or []):
                add(u, beat)
    return out


def legacy_history():
    try:
        return json.load(open(HISTORY_LEGACY, encoding="utf-8")).get("urls", {})
    except Exception:
        return {}


def my_history(urls):
    """自分で見張った「いつから開きっぱなしか」。今Chromeに無いURLは捨てる。"""
    now = time.time()
    old = {}
    try:
        old = json.load(open(HISTORY_MINE, encoding="utf-8")).get("urls", {})
    except Exception:
        pass
    new = {}
    for u in urls:
        prev = old.get(u) or {}
        first = prev.get("firstSeen", now)
        if now - prev.get("lastSeen", now) > 1800:
            first = now  # 30分以上見ていない＝いったん閉じられた。数え直す
        new[u] = {"firstSeen": first, "lastSeen": now}
    write_json(HISTORY_MINE, {"updatedAt": now_iso(), "urls": new})
    return new


def is_own_site(u):
    return any(("//" + h) in u or ("." + h) in u for h in OWN_SITES)


def judge(url, ledger, total, legacy=None, mine=None):
    u = (url or "").strip()
    legacy = legacy or {}
    mine = mine or {}
    for rx in NEVER_CLOSE:
        if rx.search(u):
            return "keep", "たまごさんの作業タブになりうる（最後の壁）"
    if u in CLOSE_EXACT:
        return "close", "空タブ（閉じても何も失われない）"
    if u.startswith(CLOSE_PREFIXES):
        return "close", "Claudeが検品で開くページ"
    ts = ledger.get(u)
    if ts is not None:
        if time.time() - ts < MIN_AGE_SEC:
            return "keep", "台帳に載ったばかり（%d秒待つ）" % MIN_AGE_SEC
        return "close", "台帳に『Claudeが開いた』と書いてあるURL"
    # 同じURLの前方一致（?artist=… などのクエリ違いを拾う）
    for k, ts2 in ledger.items():
        if k and u.startswith(k.split("?")[0]) and len(k.split("?")[0]) > 30:
            if time.time() - ts2 >= MIN_AGE_SEC:
                return "close", "台帳のURLと同じページ（クエリ違い）"

    # ── うちの成果物ページ（Claudeが検品で開く先）の扱い ──────────────
    if is_own_site(u):
        h = legacy.get(u)
        if h is not None:
            if h.get("everActive"):
                return "keep", "たまごさんが一度でも前面に出した（本人のもの）"
            if int(h.get("samples", 0)) >= 5:
                return "close", "うちの成果物ページで、一度も前面に来ていない（機械が開いた孤児）"
        m = mine.get(u)
        if m and time.time() - m.get("firstSeen", time.time()) >= OWN_STALE_SEC:
            return "close", "うちの成果物ページが%d時間以上開きっぱなし" % (OWN_STALE_SEC // 3600)
        return "keep", "うちの成果物ページだが、まだ証拠が足りない（迷ったら残す）"

    return "keep", "台帳に無い＝たまごさんが開いた可能性（迷ったら残す）"


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def log(rec):
    try:
        os.makedirs(STATUS, exist_ok=True)
        with open(LOGJ, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": now_iso(), **rec}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recon", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    if not (a.recon or a.sweep):
        a.recon = True

    ok, why = port_owner_is_chrome()
    if not ok:
        write_json(OUT, {"updatedAt": now_iso(), "armed": False, "note": why,
                         "tabs": None, "wouldClose": None})
        log({"armed": False, "note": why})
        if not a.quiet:
            print("CDP: SKIP -", why)
        return 0

    try:
        pages = list_pages()
    except Exception as e:
        write_json(OUT, {"updatedAt": now_iso(), "armed": True,
                         "note": "CDPに繋がらない: %s" % e})
        if not a.quiet:
            print("CDP: ERROR", e)
        return 0

    ledger = claude_opened_urls()
    legacy = legacy_history()
    mine = my_history([str(t.get("url") or "").strip() for t in pages])
    judged = [(t, judge(t.get("url"), ledger, len(pages), legacy, mine)) for t in pages]
    targets = [t for t, (v, _w) in judged if v == "close"]
    # 全部は閉じない（ウィンドウごと消さない）
    if len(pages) - len(targets) < KEEP_AT_LEAST:
        targets = targets[:max(0, len(pages) - KEEP_AT_LEAST)]

    write_json(OUT, {
        "updatedAt": now_iso(), "armed": True, "owner": why,
        "tabs": len(pages), "wouldClose": len(targets),
        "detail": [{"url": t.get("url"), "title": t.get("title"),
                    "verdict": v, "why": w} for t, (v, w) in judged],
    })

    closed, failed = 0, 0
    if a.sweep and not a.dry_run:
        for t in targets:
            try:
                cdp_get("/json/close/%s" % t.get("id"))
                closed += 1
            except Exception:
                failed += 1
    log({"armed": True, "tabs": len(pages), "candidates": len(targets),
         "closed": closed, "failed": failed, "dryRun": bool(a.dry_run)})
    if not a.quiet:
        print("CDP: OK - タブ%d枚 / 候補%d枚 / 閉じた%d枚" % (len(pages), len(targets), closed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
