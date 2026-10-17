#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【投稿済み曲の見回り】SNSに出した曲の台帳を毎日作り、曲ページの5点を点検し、落ちた曲は直す仕事を積む。

たまごさん（2026-10-17・優先順位1位「SNSで発信したもの周りのページ品質」）：
  「もう投稿したもの（X・TikTok・YouTubeショート）をちゃんと把握して。世の中に出した曲からページを濃くしていく。
    検索で出ない、関連が2曲しかない、はおかしい。80点以上は基本中の基本」
  実例：X投稿 2108437452188762302 の布袋寅泰「Dancing with the Moonlight」。サイトで「ダンス」「ダンシング」で
        検索しても出ない。曲ページの関連は布袋の曲2曲だけ。

━━ 1日1回（心臓 top_status.py の相乗り・中で20時間に1回に間引く）━━
  ① 台帳を作る（集める）  → status/public/toukou_daicho.json
       X（予約）   : status/buffer_queue/dashita.jsonl（Bufferに入れた控え＝正本）。予定時刻を過ぎたもの
       X（手で出した）: tools/x_toukou.py の取り出し（0円・鍵なし・GETだけ）。本文の自サイトURLから曲を引く
       サイトの投稿ログ: joy-relief-station docs/operations/sns-post-log.json の status=posted
       TikTok      : 公開プロフィール @joyreliefstation を Mac の curl で1回（0円）。取れなければ「取れない」と書く
       YouTubeショート: status/toukou_daicho_config.json の youtube_channel_id があれば公開RSS（0円）。無ければ「未登録」
       ★有料APIは使わない。ブラウザを開かない。投稿・いいね・削除は一切しない。
  ② 点検する              → status/public/toukou_tenken.json
       joy-relief-station の最新 main を一時の作業場に出し、scripts/patrol/check-posted-songs.mts を走らせる
       （①検索 ②関連4本以上 ③メモと出典 ④マガジンへの入口 ⑤動画の生死＝oEmbed）。作業場は終わったら自分で消す。
  ③ 直す仕事を積む         → status/queue.json（command_ingest.queue_add・origin=factory・sonnet）
       落ちた曲があれば、その日1件だけ「直して本番まで」の仕事を積む。台帳が変わった日も、台帳の写しを
       サイトへ入れる仕事として同じ1件に含める（検索で「SNSで紹介した曲」を少し先に出すのに使う）。

使い方:
  python3 tools/toukou_mimawari.py --daily        # 心臓から（20時間に1回）
  python3 tools/toukou_mimawari.py --collect      # 台帳だけ作る（サンドボックスからでも動く・TikTok等は飛ばす）
  python3 tools/toukou_mimawari.py --check        # 点検だけ（Macで）
  python3 tools/toukou_mimawari.py --self-test
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

JST = _dt.timezone(_dt.timedelta(hours=9))
DASHITA = os.path.join(REPO, "status", "buffer_queue", "dashita.jsonl")
X_LIVE = os.path.join(REPO, "status", "1075_x", "toukou_oasisjoyrelief.json")
CONFIG = os.path.join(REPO, "status", "toukou_daicho_config.json")
DAICHO = os.path.join(REPO, "status", "public", "toukou_daicho.json")
TENKEN = os.path.join(REPO, "status", "public", "toukou_tenken.json")
STAMP = os.path.join(REPO, "status", ".toukou_mimawari_at")
LOG = os.path.join(REPO, "status", "toukou_mimawari.log")
JRS = os.path.expanduser(os.environ.get("TOUKOU_JRS", "~/tamago/jrs_fix"))
GH_TOKEN_FILE = os.path.expanduser("~/tamago/gh_token")
SITE = "https://joy-relief-station.lovable.app"
TIKTOK = "joyreliefstation"
GATE_HOURS = 20


def _now():
    return _dt.datetime.now(JST)


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (_now().strftime("%F %T"), msg))
    except Exception:
        pass


def _read_json(p, default):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


# ────────────────────────── ① 集める ──────────────────────────
SONG_URL = re.compile(r"/cover-guide\?([^\s\"'<>)]+)")


def song_key_from_text(text):
    """本文の自サイトURL（/cover-guide?artist=..&song=..）から曲キーを取る。"""
    for m in SONG_URL.finditer(text or ""):
        q = urllib.parse.parse_qs(m.group(1).replace("&amp;", "&"))
        a = (q.get("artist") or [""])[0]
        s = (q.get("song") or [""])[0]
        if a and s:
            return "%s/%s" % (a, s)
    return None


def from_buffer(now_utc):
    """Buffer に入れた控え（正本）。予定時刻を過ぎたもの＝もう出たもの。"""
    out = []
    try:
        lines = io.open(DASHITA, encoding="utf-8").read().splitlines()
    except Exception:
        return out, "dashita.jsonl が読めない"
    for ln in lines:
        try:
            r = json.loads(ln)
        except Exception:
            continue
        where = r.get("where") or ""
        due = r.get("due_utc") or ""
        m = re.search(r"\((\d{4}-\d\d-\d\dT[\d:.]+Z)\)", where)
        if not due and m:
            due = m.group(1)
        manual = "手でXに投稿" in where
        if due and due > now_utc and not manual:
            continue  # まだ予定（出ていない）
        key = r.get("song_key")
        out.append({
            "platform": "x",
            "via": "buffer" if not manual else "manual",
            "at": due or r.get("at") or "",
            "url": ("https://x.com/oasisjoyrelief (Buffer %s)" % r.get("post_id")) if r.get("post_id") else "",
            "songKey": urllib.parse.unquote(key) if key else None,
            "text": (r.get("head") or "")[:200],
            "id": "buffer:%s" % (r.get("post_id") or r.get("text_key") or due),
        })
    return out, ""


def from_x_live():
    d = _read_json(X_LIVE, {})
    out = []
    for t in d.get("toukou") or []:
        body = t.get("honbun") or ""
        out.append({
            "platform": "x",
            "via": "x",
            "at": t.get("itsu") or "",
            "url": t.get("url") or "",
            "songKey": song_key_from_text(body),
            "text": body[:200],
            "id": "x:%s" % t.get("id"),
        })
    return out, ("" if out else "x_toukou の取り出しが空（%s）" % (d.get("at") or "未実行"))


def from_sns_log(jrs_dir):
    p = os.path.join(jrs_dir, "docs", "operations", "sns-post-log.json")
    d = _read_json(p, {})
    out = []
    for e in d.get("posts") or []:
        if e.get("status") != "posted":
            continue
        out.append({
            "platform": "x",
            "via": "sns-post-log",
            "at": e.get("date") or "",
            "url": e.get("postedUrl") or "",
            "songKey": song_key_from_text(e.get("pageUrl") or ""),
            "text": "%s %s" % (e.get("artist") or "", e.get("songTitle") or ""),
            "id": "x:%s" % ((e.get("postedUrl") or "").rsplit("/", 1)[-1] or e.get("id")),
        })
    return out, ""


def _curl(url, timeout=30):
    """Mac の curl（0円・鍵なし）。サンドボックスでは届かないことがある。"""
    try:
        r = subprocess.run(["curl", "-sL", "-m", str(timeout), "-A",
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
                            url], capture_output=True, timeout=timeout + 5)
        return r.stdout.decode("utf-8", "ignore")
    except Exception:
        return ""


def from_tiktok():
    html = _curl("https://www.tiktok.com/@%s" % TIKTOK)
    if not html:
        return [], "TikTok に届かない（curl 空）"
    m = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', html, re.S)
    items = []
    if m:
        try:
            data = json.loads(m.group(1))
            scope = data.get("__DEFAULT_SCOPE__") or {}
            for k, v in scope.items():
                if "item" in k.lower() and isinstance(v, dict):
                    for it in (v.get("itemList") or []):
                        items.append(it)
        except Exception:
            pass
    out = []
    for it in items:
        vid = str(it.get("id") or "")
        desc = it.get("desc") or ""
        ts = it.get("createTime")
        out.append({
            "platform": "tiktok",
            "via": "tiktok",
            "at": _dt.datetime.fromtimestamp(int(ts), JST).isoformat() if ts else "",
            "url": "https://www.tiktok.com/@%s/video/%s" % (TIKTOK, vid),
            "songKey": song_key_from_text(desc),
            "text": desc[:200],
            "id": "tiktok:%s" % vid,
        })
    if not out:
        return [], "TikTok の公開ページから投稿一覧が取れない（ログイン無しでは一覧を返さない形）"
    return out, ""


def from_youtube():
    cfg = _read_json(CONFIG, {})
    ch = cfg.get("youtube_channel_id")
    if not ch:
        return [], "YouTubeショートのチャンネルIDが未登録（status/toukou_daicho_config.json の youtube_channel_id）"
    xml = _curl("https://www.youtube.com/feeds/videos.xml?channel_id=%s" % ch)
    out = []
    for e in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        vid = (re.search(r"<yt:videoId>([^<]+)", e) or [None, ""])[1]
        title = (re.search(r"<title>([^<]*)", e) or [None, ""])[1]
        desc = (re.search(r"<media:description>([^<]*)", e, re.S) or [None, ""])[1]
        pub = (re.search(r"<published>([^<]+)", e) or [None, ""])[1]
        out.append({
            "platform": "youtube",
            "via": "youtube-rss",
            "at": pub,
            "url": "https://www.youtube.com/shorts/%s" % vid,
            "songKey": song_key_from_text(desc),
            "text": ("%s %s" % (title, desc))[:200],
            "id": "yt:%s" % vid,
        })
    return out, ("" if out else "YouTube の公開RSSが空")


def collect(jrs_dir=None, net=True):
    now_utc = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    old = _read_json(DAICHO, {})
    posts = {p["id"]: p for p in old.get("posts") or [] if p.get("id")}
    sources = {}
    getters = [("x_buffer", lambda: from_buffer(now_utc)), ("x_live", from_x_live)]
    if jrs_dir:
        getters.append(("sns_post_log", lambda: from_sns_log(jrs_dir)))
    if net:
        getters += [("tiktok", from_tiktok), ("youtube_shorts", from_youtube)]
    else:
        sources["tiktok"] = {"n": 0, "why": "このときは見ていない（--collect をネット無しで実行）"}
        sources["youtube_shorts"] = {"n": 0, "why": "このときは見ていない"}
    for name, fn in getters:
        try:
            got, why = fn()
        except Exception as e:  # 1つ落ちても他は続ける
            got, why = [], "失敗：%s" % e
        for p in got:
            prev = posts.get(p["id"])
            if prev and prev.get("songKey") and not p.get("songKey"):
                p["songKey"] = prev["songKey"]
            posts[p["id"]] = p
        sources[name] = {"n": len(got), "why": why}
    rows = sorted(posts.values(), key=lambda p: p.get("at") or "")
    daicho = {
        "updatedAt": _now().isoformat(),
        "what": "ごきげん補給所のアカウント（X @oasisjoyrelief・TikTok @joyreliefstation・YouTubeショート）に出た投稿の台帳。tools/toukou_mimawari.py が毎日作る。",
        "sources": sources,
        "songs": len({p["songKey"] for p in rows if p.get("songKey")}),
        "posts": rows,
    }
    _write_json(DAICHO, daicho)
    log("台帳 %d件（曲 %d）%s" % (len(rows), daicho["songs"],
                                 " ".join("%s=%s" % (k, v["n"]) for k, v in sources.items())))
    return daicho


# ────────────────────────── ② 点検 ──────────────────────────
def _git(args, cwd, timeout=300):
    env = dict(os.environ)
    cmd = ["git"]
    try:
        tok = io.open(GH_TOKEN_FILE).read().strip()
        if tok:
            import base64
            b = base64.b64encode(("x-access-token:%s" % tok).encode()).decode()
            cmd += ["-c", "http.extraheader=Authorization: Basic %s" % b]
    except Exception:
        pass
    return subprocess.run(cmd + args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def check():
    """joy-relief-station の最新 main を一時の作業場に出して点検する。作業場は終わったら必ず消す。"""
    if not os.path.isdir(os.path.join(JRS, ".git")):
        return {"ok": False, "why": "joy-relief-station の手元の複製が無い（%s）" % JRS}
    log("点検 開始（%s）" % JRS)
    r = _git(["fetch", "-q", "origin", "main"], JRS)
    if r.returncode != 0:
        log("fetch 失敗：%s" % (r.stderr or "")[:200])
    wt = tempfile.mkdtemp(prefix="toukou_wt_", dir="/private/tmp" if os.path.isdir("/private/tmp") else None)
    try:
        r = _git(["worktree", "add", "--detach", "-f", wt, "origin/main"], JRS)
        if r.returncode != 0:
            return {"ok": False, "why": "作業場を作れない：%s" % (r.stderr or "")[:200]}
        nm = os.path.join(JRS, "node_modules")
        if os.path.isdir(nm):
            os.symlink(nm, os.path.join(wt, "node_modules"))
        ledger_in = os.path.join(wt, "docs", "operations", "posted-songs.json")
        shutil.copyfile(DAICHO, ledger_in)
        log("作業場 %s で点検を走らせる" % wt)
        out = os.path.join(REPO, "status", "public", "toukou_tenken.json.tmp")
        r = subprocess.run(["npx", "tsx", "--import", "./scripts/_asset-stub.mjs",
                            "scripts/patrol/check-posted-songs.mts", "--ledger", ledger_in,
                            "--json", out, "--oembed"], cwd=wt, capture_output=True, text=True, timeout=1500)
        if not os.path.exists(out):
            return {"ok": False, "why": "点検が結果を出さなかった：%s" % ((r.stderr or r.stdout or "")[-300:])}
        os.replace(out, TENKEN)
        res = _read_json(TENKEN, {})
        log("点検 曲%s 合格%s 不合格%s" % (res.get("songs"), res.get("pass"), res.get("fail")))
        # 台帳がサイトの写しと違うか（違えば、直す仕事に「写しを入れる」も含める）
        site_copy = _git(["show", "origin/main:docs/operations/posted-songs.json"], JRS).stdout
        res["_ledger_changed"] = _ledger_keys(site_copy) != _ledger_keys(io.open(DAICHO, encoding="utf-8").read())
        return {"ok": True, "result": res}
    finally:
        # 使ったらしまう：作業場は自分で消す（worktree_taihi も拾う）
        try:
            _git(["worktree", "remove", "--force", wt], JRS, timeout=120)
        except Exception:
            pass
        shutil.rmtree(wt, ignore_errors=True)
        try:
            _git(["worktree", "prune"], JRS, timeout=60)
        except Exception:
            pass


def _ledger_keys(text):
    try:
        d = json.loads(text or "{}")
    except Exception:
        return set()
    return {p.get("songKey") for p in d.get("posts") or [] if p.get("songKey")}


# ────────────────────────── ③ 直す仕事を積む ──────────────────────────
def build_job(res, today):
    ng = [it for it in res.get("items") or [] if not it.get("ok")]
    lines = []
    for it in ng[:40]:
        lines.append("- %s「%s」 %s ：%s" % (it.get("artist"), it.get("title"), it.get("url"), " ／ ".join(it.get("fails") or [])))
    more = "" if len(ng) <= 40 else "\n（ほか%d曲。全部は status/public/toukou_tenken.json）" % (len(ng) - 40)
    unm = res.get("unmatchedPosts") or []
    text = (
        "【タスク】SNSに出した曲の曲ページを、5点（検索・関連4本以上・メモと出典・マガジンへの入口・動画）を満たすまで直して本番に出す（%s の見回り）\n"
        "【落ちた曲】%d曲\n%s%s\n"
        "【台帳】tamago-shinchoku/status/public/toukou_daicho.json を joy-relief-station の docs/operations/posted-songs.json に写す（%s）\n"
        "【直し方】関連は理由の言えるものだけ（src/lib/relatedReason.ts・shelfPicks.ts の手書き・moodThreads.ts の気分の糸・coverGuide.ts の relatedProjects）。"
        "メモは sekisho-jijitsu-shutten の関所を通し、出典を src に入れる。検索で出ないものは src/lib/searchCards.ts／searchVariants.ts を直す（曲だけの手当てで済ませない）。"
        "新しい日本語は src/i18n/overlay の4言語に訳を足す。見た目は変えない。\n"
        "【点検】npx tsx --import ./scripts/_asset-stub.mjs scripts/patrol/check-posted-songs.mts --oembed で全曲合格\n"
        "【公開】prebuild の関所を全部通して push → Lovable の deploy_project → tools/koukai_kakunin.py で本番が変わったことまで\n"
        "【曲に結べなかった投稿】%d件（本文に曲名とアーティスト名が無い）。分かるものは台帳の songKey を埋める。\n"
        "【報告】完了/問題/判断待ち、3行以内。たまごさんに質問しない。"
    ) % (today, len(ng), "\n".join(lines), more,
         "変わっている" if res.get("_ledger_changed") else "変わっていなければ不要", len(unm))
    return text, len(ng)


def enqueue(res):
    today = _now().strftime("%Y-%m-%d")
    ng_n = sum(1 for it in res.get("items") or [] if not it.get("ok"))
    if ng_n == 0 and not res.get("_ledger_changed"):
        log("落ちた曲0・台帳変化なし → 積まない")
        return None
    text, n = build_job(res, today)
    try:
        import command_ingest
        r = command_ingest.queue_add(text, priority=2,
                                     label="投稿済み曲のページを直す %s（%d曲）" % (today, n),
                                     origin="factory", model="claude-sonnet-5")
        log("仕事を積んだ：%s" % (r,))
        return r
    except Exception as e:
        log("仕事を積めなかった：%s" % e)
        return None


# ────────────────────────── 入口 ──────────────────────────
def daily(force=False):
    if not force:
        try:
            if time.time() - os.path.getmtime(STAMP) < GATE_HOURS * 3600:
                return "skip"
        except OSError:
            pass
        if _now().hour < 6:
            return "skip"
    io.open(STAMP, "w").write(_now().isoformat())
    # X の手で出した分も拾えるよう、取り出し係を先に1回（0円・GETだけ）
    try:
        subprocess.run(["python3", os.path.join(HERE, "x_toukou.py")], capture_output=True, timeout=180)
    except Exception:
        pass
    collect(jrs_dir=JRS, net=True)
    try:
        c = check()
    except Exception as e:  # 落ちた理由を必ず残す（黙って死なない）
        c = {"ok": False, "why": "点検の途中で落ちた：%r" % (e,)}
    if not c.get("ok"):
        log("点検できず：%s" % c.get("why"))
        _write_json(TENKEN, {"at": _now().isoformat(), "error": c.get("why")})
        return "check-failed"
    enqueue(c["result"])
    return "done"


def self_test():
    assert song_key_from_text("見て https://joy-relief-station.lovable.app/cover-guide?artist=hotei-tomoyasu&song=dancing-with-the-moonlight #布袋") == "hotei-tomoyasu/dancing-with-the-moonlight"
    assert song_key_from_text("リンク無し") is None
    assert _ledger_keys('{"posts":[{"songKey":"a/b"},{"songKey":null}]}') == {"a/b"}
    text, n = build_job({"items": [{"ok": False, "artist": "A", "title": "T", "url": "u", "fails": ["関連が2本"]},
                                   {"ok": True}], "_ledger_changed": True}, "2026-10-17")
    assert n == 1 and "関連が2本" in text and "変わっている" in text
    print("SELF-TEST OK")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        self_test()
    elif "--collect" in a:
        d = collect(jrs_dir=JRS if os.path.isdir(JRS) else None, net="--no-net" not in a)
        print("台帳 %d件 曲%d" % (len(d["posts"]), d["songs"]))
    elif "--check" in a:
        c = check()
        print(json.dumps({k: v for k, v in c.items() if k != "result"}, ensure_ascii=False),
              (c.get("result") or {}).get("pass"), (c.get("result") or {}).get("fail"))
    else:
        print(daily(force="--force" in a))
