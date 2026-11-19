#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""特集（マガジン）の一覧と、新しい特集のお知らせ（2026-10-11）

━━ なぜ作ったか（たまごさん原文）━━
  「知らないところで特集（マガジン）がどんどんできるのは悪くない。公開はしていい。
    でも1個ずつさらっと確認したい」

━━ やること ━━
  ① 本番（joy-relief-station の main）にある /feature/... を全部並べる：
     題名・URL・誰が書いたか（git の履歴＋作業の記録）・公開日・曲数（動画の数）。
  ② 前回の一覧との差分を見て、新しい特集が**本番で200を返したら**
     status/public/tokushu_new.json（進捗表の一番上に出る）と status/dispatch_outbox.jsonl に1行。
  ③ 書きかけ（noindex の下書き・main に無いブランチの特集・Genspark の特集の作業）も「書きかけ」として並べる。
  ★AIを1回も呼ばない。git と curl とファイルだけ。課金0。

    python3 tools/tokushu.py            # 一覧を作り直す＋新しい特集を知らせる（心臓から）
    python3 tools/tokushu.py --self-test
"""
from __future__ import annotations

import argparse
import html
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
JST = timezone(timedelta(hours=9))
HONBAN = "https://joy-relief-station.lovable.app"
SEEN = os.path.join(STATUS, "tokushu_seen.json")
OUT_JSON = os.path.join(STATUS, "public", "tokushu.json")
NEW_JSON = os.path.join(STATUS, "public", "tokushu_new.json")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")
OUT_HTML = os.path.join(REPO, "share", "check", "tokushu-ichiran.html")
PAGE_URL = "https://tamago2022.github.io/tamago-shinchoku/share/check/tokushu-ichiran.html"
NEW_DAYS = 7  # 進捗表の一番上に出しておく日数

# joy-relief-station の置き場（上から最初にあるもの）。Mac 本体は Desktop。
JRS_CANDIDATES = [os.environ.get("JRS_DIR") or "", "/Users/mac/Desktop/joy-relief-station",
                  os.path.expanduser("~/Desktop/joy-relief-station"),
                  os.path.join(STATUS, "_pr906", "repo")]

YT = re.compile(r"""(?:_ID\s*=\s*|videoId\s*:\s*|youtubeId\s*:\s*|ytId\s*:\s*|youtu\.be/|[?&]v=|/embed/)["']?([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])""")


def _now():
    return datetime.now(JST)


def git(jrs, *args, timeout=60):
    env = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    try:
        r = subprocess.run(["git", "-C", jrs] + list(args), capture_output=True, text=True,
                           timeout=timeout, env=env)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def find_jrs():
    for c in JRS_CANDIDATES:
        if c and os.path.isdir(os.path.join(c, ".git")):
            return c
    return None


def honban_code(url):
    """本番のHTTPコード。取れなければ None（＝未確認）。Mac の curl。"""
    try:
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-L", "--max-time", "20", url],
                           capture_output=True, text=True, timeout=30)
        c = int((r.stdout or "0").strip() or 0)
        return c or None
    except Exception:
        return None


def _load(path, default):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default


def _save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _queue_index():
    """作業の記録（status/queue.json）から 番号→(モデル, 出どころ, 言われた日時)。"""
    out = {}
    q = _load(os.path.join(STATUS, "queue.json"), {})
    for it in (q.get("items") if isinstance(q, dict) else q) or []:
        n = it.get("n")
        if n is not None:
            out[str(n)] = {"model": it.get("model"), "origin": it.get("origin"), "queuedAt": it.get("queuedAt")}
    return out


def dare_kaita(author, email, msg, qidx):
    """誰が書いたか。★推測で名前を足さない。根拠（どこを見たか）を必ず添える。"""
    m = msg or ""
    co = re.findall(r"Co-Authored-By:\s*([^<\n]+)", m, re.I)
    bango = None
    mm = re.search(r"(\d{3,6})\s*(?:番|号)|案件\s*#\s*(\d+)|\((\d{3,6})\)|feat\((\d{3,6})\)|q(\d{3,6})", m)
    if mm:
        bango = next(g for g in mm.groups() if g)
    a = (author or "").lower()
    who, konkyo = None, []
    if "jules" in a:
        who = "Jules（Google）"
    elif "gpt-engineer" in a or "lovable" in a:
        who = "Lovable"
    elif re.search(r"vloy", m + a, re.I):
        who = "VloyBot"
    elif re.search(r"genspark", m, re.I):
        who = "Genspark"
    elif re.search(r"\bcodex\b", m + a, re.I):
        who = "Codex（ChatGPT）"
    elif co:
        who = "Claude（%s）" % co[0].strip().replace("Claude ", "")
    elif "fable" in a or "claude" in a:
        who = "Claude（%s）" % author
    elif a.startswith("tamago-") and "[bot]" in a:
        who = "Claudeの工場"
    if co:
        konkyo.append("Co-Authored-By: %s" % co[0].strip())
    konkyo.append("コミットの名義：%s" % author)
    if bango:
        q = qidx.get(str(bango))
        if q:
            konkyo.append("作業の記録 %s番（%s・%s）" % (bango, q.get("model") or "モデル不明",
                                                    "たまごさんの依頼" if q.get("origin") == "user" else (q.get("origin") or "")))
            if who in (None, "Claudeの工場") and q.get("model"):
                who = "Claudeの工場（%s番・%s）" % (bango, q["model"])
        elif who == "Claudeの工場":
            who = "Claudeの工場（%s番）" % bango
    if not who:
        who = "不明（%s 名義・AIの署名なし）" % author
    return who, "／".join(konkyo)


def magazine_index(jrs, ref):
    src = git(jrs, "show", "%s:src/lib/magazineFeatures.ts" % ref)
    if not src:
        p = os.path.join(jrs, "src", "lib", "magazineFeatures.ts")
        src = io.open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    consts = {}
    for m in re.finditer(r'const (\w+)\s*:\s*MagazineFeatureInfo\s*=\s*\{\s*path:\s*"([^"]+)",\s*title:\s*"([^"]+)"', src):
        consts[m.group(1)] = (m.group(2), m.group(3))
    out = {}
    body = src[src.find("MAGAZINE_INDEX"):]
    for m in re.finditer(r'\{\s*path:\s*(?:(\w+)\.path|"([^"]+)"),\s*title:\s*(?:(\w+)\.title|"([^"]+)"),\s*kicker:\s*"([^"]+)"', body):
        path = consts.get(m.group(1), (m.group(2), ""))[0] if m.group(1) else m.group(2)
        title = consts.get(m.group(3), ("", m.group(4)))[1] if m.group(3) else m.group(4)
        out[path] = {"title": title, "kicker": m.group(5)}
    for _, (p, t) in consts.items():
        out.setdefault(p, {"title": t, "kicker": ""})
    return out


def kyoku_suu(jrs, ref, src):
    ids = set(YT.findall(src or ""))
    for d, imp in re.findall(r'from\s+"@/(lib|components)/(\w+)"', src or ""):
        if not re.search(r"Songs$|^feature", imp):
            continue  # 曲の台帳（xxxSongs）と特集の部品（featureXxx）だけ見る
        s2 = ""
        for ext in (".ts", ".tsx"):
            s2 = git(jrs, "show", "%s:src/%s/%s%s" % (ref, d, imp, ext))
            if not s2:
                p = os.path.join(jrs, "src", d, imp + ext)
                s2 = io.open(p, encoding="utf-8").read() if os.path.exists(p) else ""
            if s2:
                break
        ids |= set(YT.findall(s2))
    return len(ids)


def collect(jrs, ref, check_honban=True):
    qidx = _queue_index()
    mag = magazine_index(jrs, ref)
    names = [l.strip() for l in git(jrs, "ls-tree", "--name-only", ref, "src/routes/").splitlines()]
    rows = []
    for f in names:
        m = re.match(r"src/routes/feature\.([a-z0-9-]+)\.tsx$", f)
        if not m:
            continue
        slug = m.group(1)
        path = "/feature/" + slug
        first = git(jrs, "log", ref, "--diff-filter=A", "--format=%H%x1f%cI%x1f%an%x1f%ae%x1f%B%x1e", "--", f).strip()
        recs = [r for r in first.split("\x1e") if r.strip()]
        h = date = author = email = msg = ""
        if recs:
            h, date, author, email, msg = (recs[-1].strip("\n").split("\x1f") + [""] * 5)[:5]
        who, konkyo = dare_kaita(author, email, msg, qidx)
        src = git(jrs, "show", "%s:%s" % (ref, f))
        if not src and os.path.exists(os.path.join(jrs, f)):
            src = io.open(os.path.join(jrs, f), encoding="utf-8").read()
        title = (mag.get(path) or {}).get("title")
        if not title and src:
            t = re.search(r'meta:\s*\[\s*\{\s*title:\s*[`"]([^`"]{4,160})[`"]', src)
            title = t.group(1).split("｜")[0].split(" | ")[0] if t else None
        if title and re.fullmatch(r"\$\{(\w+)\}", title) and src:
            v = re.search(r'const %s\s*=\s*[`"]([^`"]+)[`"]' % re.fullmatch(r"\$\{(\w+)\}", title).group(1), src)
            title = v.group(1) if v else None
        if not title:
            t = re.search(r"(?:特集|マガジン下書き|マガジン)「(.+?)」(?=を|\s|（|$)", msg or "", re.M)
            title = t.group(1) if t else None
        if not title and slug.endswith("-en"):
            base = (mag.get(path[:-3]) or {}).get("title")
            title = (base + "（英語版）") if base else None
        if not title:
            title = "（題名を取れず）" + ((msg or "").strip().splitlines() or [slug])[0][:60]
        jou = "公開"
        if src and "noindex" in src:
            jou = "書きかけ（noindex の下書き）"
        elif src and len(src) < 600:
            jou = "転送・別版（%dバイト）" % len(src)
        elif path not in mag:
            jou = "公開（特集一覧には未登録）"
        code = honban_code(HONBAN + path) if check_honban else None
        rows.append({"slug": slug, "path": path, "url": HONBAN + path, "title": title,
                     "kicker": (mag.get(path) or {}).get("kicker", ""),
                     "dare": who, "konkyo": konkyo, "commit": h[:8], "msg": (msg or "").strip().splitlines()[0][:140] if msg else "",
                     "koukaibi": date[:10] if date else "不明", "kyoku": kyoku_suu(jrs, ref, src) if src else None,
                     "jou": jou, "honban": code})
    rows.sort(key=lambda r: r["koukaibi"], reverse=True)
    return rows


def kakikake(jrs, main_slugs):
    out = []
    # ① main に無いブランチの特集（30日以内に動いたブランチだけ）
    refs = git(jrs, "for-each-ref", "--format=%(refname:short)\x1f%(committerdate:iso-strict)", "refs/remotes/").splitlines()
    lim = (_now() - timedelta(days=30)).isoformat()
    seen_b = set()
    for ln in refs:
        ref, _, d = ln.partition("\x1f")
        if not ref or ref.endswith("/HEAD") or ref.endswith("/main") or d < lim:
            continue
        for f in git(jrs, "ls-tree", "--name-only", ref, "src/routes/").splitlines():
            m = re.match(r"src/routes/feature\.([a-z0-9-]+)\.tsx$", f.strip())
            if m and m.group(1) not in main_slugs and m.group(1) not in seen_b:
                seen_b.add(m.group(1))
                out.append({"title": "/feature/" + m.group(1), "dare": "ブランチ %s" % ref, "url": "",
                            "at": d[:10], "doko": "joy-relief-station のブランチ（main 未合流）"})
    # ② Genspark で動かした特集の作業
    p = os.path.join(STATUS, "gsk_daicho.jsonl")
    if os.path.exists(p):
        for ln in io.open(p, encoding="utf-8", errors="ignore"):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            name = str(r.get("taskName") or r.get("shigoto") or "")
            if re.search(r"特集|マガジン|magazine", name, re.I):
                out.append({"title": name, "dare": "Genspark", "url": r.get("url") or "", "at": str(r.get("at"))[:10],
                            "doko": "Genspark（%s）" % (r.get("nani") or "作業")})
    # ③ 工場の GitHub Pages に置いた別版
    if os.path.exists(os.path.join(REPO, "share", "philippines-karaoke.html")):
        out.append({"title": "借りものの、本物 ─ フィリピンのモールで鳴った一曲から、二つの「原曲」をたどる",
                    "dare": "不明（2026-09-19 04:42 に工場の自動コミットで取り込まれた。作った作業の記録が無い）",
                    "url": "https://tamago2022.github.io/tamago-shinchoku/share/philippines-karaoke.html",
                    "at": "2026-09-19", "doko": "工場の GitHub Pages（本番の特集とは別のページ）"})
    return out


def oshirase(rows, seen, check_honban=True):
    """新しい特集を知らせる。初回（seen が空）は知らせずに覚えるだけ。"""
    new = []
    if seen.get("slugs") is None:
        return new
    for r in rows:
        if r["slug"] in seen["slugs"]:
            continue
        if r["jou"].startswith("書きかけ"):
            continue  # 下書きは「公開」になってから知らせる（seen に入れない）
        if check_honban and r["honban"] != 200:
            continue  # 本番で200になるまで待つ（次の見回りでまた見る）
        new.append(r)
    return new


def render(data):
    e = html.escape
    h = ["""<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>特集の一覧</title>
<style>body{font-family:-apple-system,"Hiragino Sans",sans-serif;margin:0;background:#faf8f3;color:#222;font-size:15px}
.w{max-width:760px;margin:0 auto;padding:14px}h1{font-size:20px}h2{font-size:16px;border-left:4px solid #b33;padding-left:8px;margin-top:22px}
.c{background:#fff;border:1px solid #e3ddd0;border-radius:10px;padding:10px 12px;margin:8px 0}
.t{font-weight:700}.k{color:#777;font-size:12px}.tag{font-size:11px;padding:1px 6px;border-radius:8px;background:#eee;margin-left:4px}
.new{background:#fde2e2}a{color:#a33;word-break:break-all}</style>
<div class="w"><p class="k"><a href="../../index.html">← 進捗表</a></p><h1>特集（マガジン）の一覧</h1>"""]
    # 2026-10-11 鬼監督§10：パス・枝名（origin/main 等）を画面に出さない（pre-pushで止まり公開が全停止した）
    h.append('<p class="k">作成 %s ／ 見た場所：サイトの最新版 ／ 本番の確認：%s</p>'
             % (e(data["generatedAt"]), "本番を直接開いて確認" if data["honbanCheck"] else "未確認（回線なし）"))
    newslugs = {n["slug"] for n in data.get("newRecent", [])}
    h.append("<h2>本番にある特集 %d本</h2>" % len(data["rows"]))
    for r in data["rows"]:
        h.append('<div class="c%s"><div class="t">%s%s</div><div><a href="%s">%s</a></div>'
                 '<div>書いた：<b>%s</b></div><div class="k">公開日 %s ／ 曲（動画）%s本 ／ 状態 %s ／ 本番 %s</div>'
                 '<div class="k">根拠：%s ／ 最初のコミット %s「%s」</div></div>'
                 % (" new" if r["slug"] in newslugs else "", e(r["title"]),
                    '<span class="tag">%s</span>' % e(r["kicker"]) if r["kicker"] else "",
                    e(r["url"]), e(r["path"]), e(r["dare"]), e(r["koukaibi"]),
                    r["kyoku"] if r["kyoku"] is not None else "不明", e(r["jou"]),
                    r["honban"] if r["honban"] else "未確認", e(r["konkyo"]), e(r["commit"]), e(r["msg"])))
    h.append("<h2>書きかけ・別の場所にあるもの %d件</h2>" % len(data["kakikake"]))
    for r in data["kakikake"]:
        h.append('<div class="c"><div class="t">%s</div><div>書いた：%s</div><div class="k">%s ／ %s</div>%s</div>'
                 % (e(r["title"]), e(r["dare"]), e(r["at"]), e(r["doko"]),
                    '<div><a href="%s">%s</a></div>' % (e(r["url"]), e(r["url"])) if r.get("url") else ""))
    h.append('<p class="k">新しい特集が本番で200を返すと、進捗表の一番上に「新しい特集」が出て、dispatch_outbox にも1行入る（心臓 tools/heartbeat.sh → tools/tokushu.py）。'
             '「誰が書いたか」はコミットの署名と作業の記録だけで決める。分からないものは「不明」。</p></div>')
    return "\n".join(h)


def run(check_honban=True, notify=True):
    jrs = find_jrs()
    data = {"generatedAt": _now().strftime("%Y-%m-%d %H:%M"), "jrs": jrs, "ref": "", "rows": [], "kakikake": [],
            "honbanCheck": check_honban, "url": PAGE_URL}
    if not jrs:
        data["error"] = "joy-relief-station の置き場が見つからない"
        return data
    if os.path.basename(jrs) == "joy-relief-station":
        git(jrs, "fetch", "-q", "origin", "main", timeout=90)
    ref = "origin/main" if git(jrs, "rev-parse", "--verify", "-q", "origin/main").strip() else "HEAD"
    data["ref"] = ref
    rows = collect(jrs, ref, check_honban)
    data["rows"] = rows
    data["kakikake"] = kakikake(jrs, {r["slug"] for r in rows}) + [
        {"title": r["title"], "dare": r["dare"], "url": r["url"], "at": r["koukaibi"], "doko": "main にあるが " + r["jou"]}
        for r in rows if r["jou"].startswith("書きかけ")]

    seen = _load(SEEN, {})
    first_time = seen.get("slugs") is None
    new = oshirase(rows, seen, check_honban) if notify else []
    known = set(seen.get("slugs") or [])
    if first_time:
        known |= {r["slug"] for r in rows if not r["jou"].startswith("書きかけ")}
    known |= {r["slug"] for r in new}
    _save(SEEN, {"slugs": sorted(known), "updatedAt": data["generatedAt"]})

    recent = _load(NEW_JSON, {}).get("items", [])
    if first_time:  # 初回だけ：直近3日に出た特集を「新しい特集」として上に出しておく（見落とし防止）
        lim3 = (_now() - timedelta(days=3)).strftime("%Y-%m-%d")
        for r in rows:
            if r["koukaibi"] >= lim3 and not r["jou"].startswith("書きかけ"):
                recent.append({"at": data["generatedAt"], "slug": r["slug"], "title": r["title"],
                               "dare": r["dare"], "url": r["url"], "note": "見張りを始めた時点で直近3日に出ていた"})
    for r in new:
        item = {"at": data["generatedAt"], "slug": r["slug"], "title": r["title"], "dare": r["dare"], "url": r["url"]}
        recent.insert(0, item)
        try:
            with io.open(OUTBOX, "a", encoding="utf-8") as f:
                f.write(json.dumps({"at": _now().isoformat(), "from": "tokushu",
                                    "text": "新しい特集：%s／%s／%s" % (r["title"], r["dare"], r["url"])},
                                   ensure_ascii=False) + "\n")
        except Exception:
            pass
    lim = (_now() - timedelta(days=NEW_DAYS)).strftime("%Y-%m-%d %H:%M")
    recent = [x for x in recent if x.get("at", "") >= lim]
    data["newRecent"] = recent
    data["newThisRun"] = [r["slug"] for r in new]
    _save(NEW_JSON, {"items": recent, "updatedAt": data["generatedAt"], "ichiran": PAGE_URL})
    _save(OUT_JSON, data)
    page = render(data)
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with io.open(OUT_HTML + ".tmp", "w", encoding="utf-8") as f:
        f.write(page)
    os.replace(OUT_HTML + ".tmp", OUT_HTML)
    return data


def self_test():
    global SEEN
    res = []
    rows = [{"slug": "a", "jou": "公開", "honban": 200}, {"slug": "b", "jou": "公開", "honban": 200},
            {"slug": "c", "jou": "書きかけ（noindex の下書き）", "honban": 200}, {"slug": "d", "jou": "公開", "honban": 404}]
    res.append(("① 初回は知らせない（覚えるだけ）", oshirase(rows, {}) == []))
    got = [r["slug"] for r in oshirase(rows, {"slugs": ["a"]})]
    res.append(("② 新しくて本番200のものだけ知らせる（b）", got == ["b"]))
    res.append(("③ 書きかけ・本番404は知らせない", "c" not in got and "d" not in got))
    w, k = dare_kaita("tamago-patrol-local[bot]", "", "wip: フィリピン×カラオケ マガジン特集ページ（1470番）",
                      {"1470": {"model": "claude-sonnet-5", "origin": "user"}})
    res.append(("④ 工場のコミット＋番号→Claudeの工場（1470番・claude-sonnet-5）", w == "Claudeの工場（1470番・claude-sonnet-5）"))
    w, _ = dare_kaita("tamago-manager[bot]", "", "x\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>", {})
    res.append(("⑤ Co-Authored-By を読む", w == "Claude（Fable 5）"))
    w, _ = dare_kaita("tamago2022", "", "新特集を追加", {})
    res.append(("⑥ 署名が無ければ『不明』と書く", w.startswith("不明")))
    res.append(("⑦ 曲数：動画IDを数える", len(set(YT.findall('const A_ID = "ahpmuikko3U"; videoId: "7pPb5fmumNo", x="https://youtu.be/ahpmuikko3U"'))) == 2))
    ng = [x for x in res if not x[1]]
    print("特集の見張り 見本試験: %d件中 %d件 想定どおり" % (len(res), len(res) - len(ng)))
    for n, ok in res:
        print("  %s %s" % ("◯" if ok else "✕", n))
    return 1 if ng else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--no-honban", action="store_true", help="本番の HTTP 確認をしない（回線が無いとき）")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    d = run(check_honban=not a.no_honban)
    print("特集 %d本・書きかけ %d件・今回の新着 %s → %s" % (len(d["rows"]), len(d["kakikake"]),
                                                    d.get("newThisRun") or "なし", PAGE_URL))
    for r in d["rows"]:
        print("  %s %s ／ %s ／ %s ／ 曲%s ／ %s" % (r["koukaibi"], r["path"], r["title"], r["dare"], r["kyoku"], r["jou"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
