#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1160番【タブ掃除係】AIが開いたタブを、AIが閉じる。

■ なぜ要るか（たまごさん・2026-09-26。同じ指摘は10回目）
  「タブを使ったら閉じろ」と何度も言われている。毎回『今回は気をつけます』で
  終わっていたので、また増えた（Braveに4枚、Chromeに大量）。
  憲法第20条：仕組みにするまでが対応。だから常駐させる。

■ 何を閉じて、何を閉じないか（ここが事故の分かれ目）
  閉じる：
    ・Brave のタブは全部（たまごさん指示「Braveは常に0枚に戻す」。触って良いのは閉じる時だけ）
    ・Chrome のうち「作業用の住所」に当たるタブで、一定時間さわられていないもの
  閉じない：
    ・Chrome で今まさに見ているタブ（各ウィンドウの active）
    ・作業用の住所に当たらないタブ＝たまごさんが自分で開いたもの
  見分け方を住所で決めているのは、AppleScriptからは「誰が開いたか」が見えないため。
  迷うものは閉じない側に倒す。

■ 記録
  status/public/tabs.json … 今の枚数（進捗表がこれを出す）
  status/tabs_souji.log   … 閉じた住所を全部残す（後から目で見られる）
"""
import io
import json
import os
import re
import subprocess
import time

HOME = os.path.expanduser("~")
REPO = os.path.join(HOME, "Desktop", "tamago-shinchoku")
ST = os.path.join(REPO, "status")
SEEN = os.path.join(ST, ".tabs_seen.json")
OUT = os.path.join(ST, "public", "tabs.json")
LOG = os.path.join(ST, "tabs_souji.log")
IDLE_SEC = 300          # 5分さわられていない作業タブは閉じる

# 作業用＝AIが開く住所。ここに当たるものだけ閉じる。
WORK = [
    r"tamago2022\.github\.io",
    r"github\.com/tamago2022",
    r"supabase\.(com|co)",
    r"trycloudflare\.com",
    r"\.lhr\.life",
    r"localhost:\d+", r"127\.0\.0\.1:\d+",
    r"r\.jina\.ai",
    r"lovable\.(app|dev)",
    r"^about:blank$", r"^chrome://newtab",
]
WORK_RE = re.compile("|".join(WORK))


def log(m):
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%F %T"), m))


def osa(script, timeout=45):
    try:
        p = subprocess.run(["osascript", "-e", script], capture_output=True,
                           text=True, timeout=timeout)
        return p.stdout.strip(), p.stderr.strip()
    except Exception as e:
        return "", str(e)


def running(app):
    # System Events 経由は重い時に30秒でも返らなかった（実測）。pgrep で見る。
    try:
        r = subprocess.run(["pgrep", "-x", app], capture_output=True, text=True, timeout=10)
        return bool(r.stdout.strip())
    except Exception:
        return False


def list_tabs(app):
    """[(window_index, tab_index, url, is_active)] を返す"""
    s = '''
    tell application "%s"
      set outp to ""
      set wi to 0
      repeat with w in windows
        set wi to wi + 1
        set ai to active tab index of w
        set ti to 0
        repeat with t in tabs of w
          set ti to ti + 1
          set outp to outp & wi & "\t" & ti & "\t" & (ai as string) & "\t" & (URL of t) & "\n"
        end repeat
      end repeat
      return outp
    end tell''' % app
    out, err = osa(s)
    rows = []
    for ln in out.split("\n"):
        parts = ln.split("\t")
        if len(parts) < 4:
            continue
        try:
            rows.append((int(parts[0]), int(parts[1]), parts[3], int(parts[2]) == int(parts[1])))
        except Exception:
            pass
    return rows, err


def close_tab(app, wi, ti):
    osa('tell application "%s" to close tab %d of window %d' % (app, ti, wi))


def load_seen():
    try:
        return json.load(io.open(SEEN, encoding="utf-8"))
    except Exception:
        return {}


def main():
    now = time.time()
    seen = load_seen()
    closed = []

    # --- Brave は 0 枚に戻す（たまごさん指示） ---
    brave_left = 0
    if running("Brave Browser"):
        rows, _ = list_tabs("Brave Browser")
        for wi, ti, url, _a in sorted(rows, key=lambda r: (-r[0], -r[1])):
            closed.append(("Brave", url))
            close_tab("Brave Browser", wi, ti)
        rows2, _ = list_tabs("Brave Browser")
        brave_left = len(rows2)

    # --- Chrome は「作業用の住所 × さわられていない」だけ閉じる ---
    chrome_left = 0
    if running("Google Chrome"):
        rows, _ = list_tabs("Google Chrome")
        keep = {}
        for wi, ti, url, active in sorted(rows, key=lambda r: (-r[0], -r[1])):
            key = url
            if active:
                seen[key] = now                      # 見ている間は時計を戻す
                continue
            if not WORK_RE.search(url or ""):
                continue                              # たまごさんのタブは触らない
            first = seen.get(key)
            if first is None:
                seen[key] = now
                continue
            if now - first >= IDLE_SEC:
                closed.append(("Chrome", url))
                close_tab("Google Chrome", wi, ti)
                seen.pop(key, None)
        rows2, _ = list_tabs("Google Chrome")
        chrome_left = len(rows2)
        for _wi, _ti, url, active in rows2:
            if active:
                seen[url] = now
        keep = keep  # noqa

    # 覚え書きは1日で捨てる
    seen = {k: v for k, v in seen.items() if now - v < 86400}
    os.makedirs(os.path.dirname(SEEN), exist_ok=True)
    json.dump(seen, io.open(SEEN, "w", encoding="utf-8"), ensure_ascii=False)

    today = time.strftime("%F")
    prev = {}
    try:
        prev = json.load(io.open(OUT, encoding="utf-8"))
    except Exception:
        pass
    total_today = (prev.get("closedToday", 0) if prev.get("day") == today else 0) + len(closed)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"day": today, "chrome": chrome_left, "brave": brave_left,
               "closedToday": total_today, "closedNow": len(closed),
               "at": time.strftime("%F %T")},
              io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    if closed:
        for app, url in closed:
            log("閉じた %s %s" % (app, (url or "")[:120]))
        log("残り Chrome=%d Brave=%d（今日 %d枚閉じた）" % (chrome_left, brave_left, total_today))
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("こけた: %s" % e)
