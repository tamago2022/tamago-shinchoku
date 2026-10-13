#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【できたもの】1枚。たまごさんがブックマーク1つで、今日できたものを全部見られる画面。

たまごさん（2026-09-27）
  「終わってます、っていう報告が欲しい。報告がないと俺が気づかないし、忘れてしまう」
  「わざわざ俺が見に行かなくちゃいけない、その手間を省くためにリンクを貼ってくれ」
  「もう仕組みで解決してくれ。何百回言わせるんだよ」

■ 設計（手で書かない／探しに行かせない／止まっているものを隠さない）
  1. 元は既にある記録だけ。人は1文字も書かない。
       ・git のコミット（本番に出た「見えるもの」が入ったコミット）
       ・status/dekimono.json（できたもの棚）
       ・status/dispatch_outbox.jsonl（発車の結果）
  2. 1件＝1行＋押せるURL＋時刻。説明を書かない。
  3. 出すのは「見て嬉しい成果物」だけ。
       裏方（フックを入れた／点検した／写しが止まった 等）は出さない。
       機械の判定は1つ：**開いて見えるものが出来たか**。
         → /share/check/（確認の控え）・.json・.log・github.com は成果物ではない＝載せない
  4. まだ終わっていないものも同じ画面に。走行中／止まっている（理由1行）。
  5. スマホで軽い。JS 0行・画像0枚・外部通信0回（中身は焼き込み済み）。
  6. 色は theme/tamago-dark.css（1165-hassha.html と同じ）1枚だけ。
  7. 24時間1件も載らなければ、それ自体を赤で出す。

■ 出力
  status/public/dekita.html  … これがブックマークする1枚
  status/public/dekita.json  … 同じ中身の機械用（件数の突き合わせに使う）

■ 走り方
  5分便（tools/machine_status_push.sh）から毎周呼ばれる。人は押さない。
  単体でも: python3 tools/dekita.py
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://tamago2022.github.io/tamago-shinchoku/"
OUT_HTML = os.path.join(REPO, "status", "public", "dekita.html")
OUT_JSON = os.path.join(REPO, "status", "public", "dekita.json")

DAYS = 21          # さかのぼる日数
MAX_ROWS = 80      # 出す行数（スマホで軽く保つ）

# ---- 「開いて見えるもの」か ----------------------------------------------
VIEWABLE_EXT = (".html", ".png", ".jpg", ".jpeg", ".webp", ".gif",
                ".mp4", ".mov", ".mp3", ".m4a", ".wav", ".pdf")
# 成果物ではない（＝裏方）。ここに当たったら載せない
NOT_DELIVER = (
    "/share/check/",          # 確認の控え。作ったものではない
    "github.com/", "raw.githubusercontent.com/",
    ".json", ".log", ".md", ".txt", ".jsonl",
)
# 中身が機械のかけら（読み上げの音声キャッシュ等）＝人が見るものではない
NOISE_PATH = ("share/check/", "share/zunda/", "share/tts/", "theme/", "tools/",
              "node_modules/", "share/nagekomi", "status/split/", "share/done/",
              "share/nikki/")
# 機械が毎日撒く定型コミット＝成果物ではない
NOISE_SUBJECT = re.compile(
    r"(画面・共有資料・道具の更新|maintenance-check|kenpou-check|自動更新|"
    r"nikki:|auto-commit|wip|Merge |Revert )")
# 見出しに出たら裏方（自分の生死の話）
NOISE_TITLE = re.compile(r"(【自動検知】|が動いていません|異常なし|発車0本|落ちました|"
                         r"消えました|沈黙|心臓|heartbeat|writeループ)")


def sh(args, cwd=REPO):
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                              timeout=45).stdout
    except Exception:
        return ""


def is_deliverable(url):
    if not url:
        return False
    u = url.lower()
    if any(b in u for b in NOT_DELIVER):
        return False
    if "open.spotify.com" in u or "youtube.com" in u or "youtu.be" in u:
        return True
    if u.rstrip("/").endswith(VIEWABLE_EXT):
        return True
    # 本番サイト（ごきげん補給所）のページはパスに拡張子が無い
    if "lovable.app" in u or "gokigen" in u:
        return True
    return u.endswith("/")


def clean_path(p):
    p = p.strip()
    if not p:
        return None
    if any(n in p for n in NOISE_PATH):
        return None
    if not p.lower().endswith(VIEWABLE_EXT):
        return None
    return p


# ---- ① git：本番に出た「見えるもの」が入ったコミットを1行にする -----------
def from_git():
    raw = sh(["git", "log", "--since=%d.days" % DAYS, "--diff-filter=AM",
              "--name-only", "--pretty=format:@@%ct|%s",
              "--", "*.html", "*.png", "*.jpg", "*.webp", "*.mp4", "*.mp3"])
    rows, cur = [], None
    for line in raw.splitlines():
        if line.startswith("@@"):
            if cur and cur["files"]:
                rows.append(cur)
            ts, _, subj = line[2:].partition("|")
            cur = {"ts": int(ts), "subj": subj.strip(), "files": []}
        elif cur is not None:
            f = clean_path(line)
            if f:
                cur["files"].append(f)
    if cur and cur["files"]:
        rows.append(cur)

    out = []
    for r in rows:
        if NOISE_SUBJECT.search(r["subj"]) or NOISE_TITLE.search(r["subj"]):
            continue
        files = r["files"]
        # 代表の1本を選ぶ（index より個別ページ、浅い方を優先）
        files.sort(key=lambda p: (p.endswith("index.html"), p.count("/"), p))
        url = BASE + files[0]
        extra = len(files) - 1
        out.append({
            "at": datetime.fromtimestamp(r["ts"], JST).isoformat(),
            "title": r["subj"],
            "url": url,
            "more": extra,
            "src": "git",
        })
    return out


# ---- ② できたもの棚 ------------------------------------------------------
def from_dekimono():
    p = os.path.join(REPO, "status", "dekimono.json")
    if not os.path.exists(p):
        return []
    try:
        items = json.load(open(p, encoding="utf-8")).get("items", [])
    except Exception:
        return []
    out = []
    for i in items:
        url, title = i.get("url"), (i.get("title") or "").strip()
        if not is_deliverable(url) or NOISE_TITLE.search(title):
            continue
        out.append({"at": i.get("addedAt") or "", "title": title,
                    "url": url, "more": 0, "src": "dekimono"})
    return out


# ---- ③ 発車の結果 --------------------------------------------------------
def from_outbox():
    p = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("type"):          # 通知系（落ちた・お金の確認 等）は成果物ではない
            continue
        title = str(r.get("title") or "").strip()
        if NOISE_TITLE.search(title):
            continue
        for u in (r.get("urls") or []):
            if is_deliverable(u):
                out.append({"at": r.get("ts") or "", "title": title,
                            "url": u, "more": 0, "src": "outbox"})
                break
    return out


def parse_at(s):
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=JST)
    except Exception:
        return None


# ---- ④ いま走っている／止まっている --------------------------------------
def load(path, default=None):
    try:
        return json.load(open(os.path.join(REPO, path), encoding="utf-8"))
    except Exception:
        return default


def running_and_stuck(now):
    top = load("status/top_status.json", {}) or {}
    running, stuck = [], []
    for r in (top.get("runningNow") or []):
        el = float(r.get("elapsedMin") or 0)
        lim = float(r.get("limitMin") or 180)
        row = {"n": r.get("n"), "title": r.get("label") or "",
               "min": int(el), "url": ""}
        if el > lim:
            row["why"] = "%d分走りっぱなし（上限%d分を超えている）" % (el, lim)
            stuck.append(row)
        else:
            running.append(row)

    # 現在地の赤旗（now.json）
    for f in ((load("status/now.json", {}) or {}).get("genzaichi", {}) or {}).get("redFlags", []) or []:
        f = str(f).strip()
        if f:
            stuck.append({"n": "", "title": f, "min": 0, "url": "", "why": f})

    # 直近24時間の「止まっている」通知（同じ件名は1つにまとめる）
    p = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
    seen = set()
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            t = r.get("type")
            if t not in ("stuck_escalation", "cost_confirm"):
                continue
            at = parse_at(r.get("ts"))
            if not at or (now - at) > timedelta(hours=24):
                continue
            title = str(r.get("title") or "").strip()
            key = (t, title[:40])
            if key in seen:
                continue
            seen.add(key)
            why = ("たまごさんの💴OK待ち（押すまで発車しません）"
                   if t == "cost_confirm" else "進まないまま同じ所で止まっている")
            stuck.append({"n": r.get("n") or "", "title": title,
                          "min": 0, "url": "", "why": why})
    # 赤旗の重複を落とす
    out, ks = [], set()
    for s in stuck:
        k = (str(s["title"])[:40], s["why"][:20])
        if k in ks:
            continue
        ks.add(k)
        out.append(s)
    return running, out[:12]


# ---- 組み立て ------------------------------------------------------------
def build():
    now = datetime.now(JST)
    items = from_git() + from_dekimono() + from_outbox()

    # URLで重複を落とす（新しい方を残す）
    items = [i for i in items if i["title"]]
    items.sort(key=lambda i: parse_at(i["at"]) or datetime(1970, 1, 1, tzinfo=JST),
               reverse=True)
    seen, uniq = set(), []
    for i in items:
        u = i["url"].rstrip("/")
        if u in seen:
            continue
        seen.add(u)
        at = parse_at(i["at"])
        if not at or (now - at) > timedelta(days=DAYS):
            continue
        i["_at"] = at
        uniq.append(i)
    uniq = uniq[:MAX_ROWS]

    running, stuck = running_and_stuck(now)

    newest = uniq[0]["_at"] if uniq else None
    silent_h = (now - newest).total_seconds() / 3600 if newest else 999
    today = [i for i in uniq if i["_at"].date() == now.date()]

    data = {
        "updatedAt": now.isoformat(timespec="seconds"),
        "counts": {"all": len(uniq), "today": len(today),
                   "running": len(running), "stuck": len(stuck)},
        "silentHours": round(silent_h, 1),
        "items": [{k: v for k, v in i.items() if k != "_at"} for i in uniq],
        "running": running,
        "stuck": stuck,
    }
    return data, uniq, running, stuck, now, silent_h


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def render(data, uniq, running, stuck, now, silent_h):
    c = data["counts"]
    p = []
    a = p.append
    a('<!doctype html><html lang="ja"><meta charset="utf-8">')
    a('<meta name="viewport" content="width=device-width,initial-scale=1">')
    a('<meta name="theme-color" content="#0d0f12">')
    a('<meta name="robots" content="noindex,nofollow">')
    a('<title>できたもの</title>')
    a('<link rel="stylesheet" href="../../theme/tamago-dark.css">')
    a("<style>"
      "*{box-sizing:border-box}"
      "body{margin:0;background:var(--t-bg,#0d0f12);color:var(--t-fg,#e8e6e1);"
      "font-family:-apple-system,\"Hiragino Sans\",system-ui,sans-serif;line-height:1.55;"
      "-webkit-text-size-adjust:100%}"
      ".w{max-width:760px;margin:0 auto;padding:18px 14px 64px}"
      "h1{font-size:19px;margin:0 0 2px;letter-spacing:.04em}"
      ".at{color:var(--t-dim,#7d8590);font-size:12px;margin:0 0 14px}"
      ".n{color:var(--t-mute,#9aa4ae);font-size:13px;margin:0 0 16px}"
      ".n b{color:var(--t-fg,#e8e6e1);font-variant-numeric:tabular-nums}"
      "h2{font-size:12.5px;color:var(--t-mute2,#8b949e);letter-spacing:.1em;"
      "margin:26px 0 8px;border-top:1px solid var(--t-line,#23272e);padding-top:14px}"
      "a.r{display:block;text-decoration:none;color:inherit;"
      "padding:9px 2px;border-bottom:1px solid var(--t-line2,#1d2126)}"
      "a.r:active{background:var(--t-panel,#15181d)}"
      ".d{color:var(--t-dim,#7d8590);font-size:11.5px;font-variant-numeric:tabular-nums;"
      "margin-right:8px}"
      ".t{font-size:14.5px;color:var(--t-fg2,#c9d1d9)}"
      ".go{color:var(--t-ok,#5ddba0);font-size:12px;margin-left:6px}"
      ".row{padding:9px 2px;border-bottom:1px solid var(--t-line2,#1d2126);font-size:14px}"
      ".why{display:block;color:var(--t-dim,#7d8590);font-size:12px;margin-top:2px}"
      ".red{background:#3a1416;border:1px solid var(--t-ng,#ff7b72);color:#ffd9d6;"
      "border-radius:10px;padding:12px 14px;margin:0 0 16px;font-size:14px}"
      ".em{color:var(--t-dim,#7d8590);font-size:13px;padding:8px 2px}"
      "</style>")
    a('<div class="w">')
    a("<h1>できたもの</h1>")
    a('<p class="at">%s 時点。機械が数えた実測。人は1文字も書いていない。</p>'
      % now.strftime("%Y-%m-%d %H:%M"))

    if silent_h >= 24:
        a('<div class="red">🛑 <b>%s時間、本番に何も出ていません。</b>'
          'できたものが1件も積まれていない状態が丸1日続いています。</div>'
          % (int(silent_h) if silent_h < 900 else "24以上"))

    a('<p class="n">いま <b>%d</b>件 載っている（今日 <b>%d</b>件）'
      ' ／ 走行中 <b>%d</b>本 ／ 止まっている <b>%d</b>件</p>'
      % (c["all"], c["today"], c["running"], c["stuck"]))

    a("<h2>できたもの（新しい順）</h2>")
    if not uniq:
        a('<p class="em">まだ1件も載っていません。</p>')
    last = None
    for i in uniq:
        d = i["_at"].strftime("%m/%d")
        if d != last:
            last = d
        more = ('<span class="go">+%d</span>' % i["more"]) if i.get("more") else ""
        a('<a class="r" href="%s" target="_blank" rel="noopener">'
          '<span class="d">%s %s</span><span class="t">%s</span>%s</a>'
          % (esc(i["url"]), d, i["_at"].strftime("%H:%M"), esc(i["title"]), more))

    a("<h2>いま走っている</h2>")
    if not running:
        a('<p class="em">0本。</p>')
    for r in running:
        a('<div class="row">%s%s<span class="why">%d分</span></div>'
          % (("%s番 " % r["n"]) if r["n"] else "", esc(r["title"]), r["min"]))

    a("<h2>止まっている（隠さない）</h2>")
    if not stuck:
        a('<p class="em">0件。</p>')
    for s in stuck:
        a('<div class="row">%s%s<span class="why">%s</span></div>'
          % (("%s番 " % s["n"]) if s["n"] else "", esc(s["title"]), esc(s["why"])))

    a('<h2>この画面について</h2><p class="em">'
      '5分ごとに、git のコミット・できたもの棚・発車の結果から自動で積み上がります。'
      'セッションが手で登録する必要はありません。'
      '確認の控え（/share/check/）は成果物ではないので出していません。</p>')
    a("</div>")
    return "\n".join(p)


def main():
    data, uniq, running, stuck, now, silent = build()
    html = render(data, uniq, running, stuck, now, silent)
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    # 中身が同じなら書かない（公開の道を無駄に叩かない）
    old = ""
    if os.path.exists(OUT_HTML):
        old = open(OUT_HTML, encoding="utf-8").read()
    body_old = re.sub(r"<p class=\"at\">.*?</p>", "", old, flags=re.S)
    body_new = re.sub(r"<p class=\"at\">.*?</p>", "", html, flags=re.S)
    if body_old != body_new:
        open(OUT_HTML, "w", encoding="utf-8").write(html)
        json.dump(data, open(OUT_JSON, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    c = data["counts"]
    print("dekita: %d件（今日%d）／走行%d／止まり%d → %s"
          % (c["all"], c["today"], c["running"], c["stuck"], OUT_HTML))


if __name__ == "__main__":
    main()
