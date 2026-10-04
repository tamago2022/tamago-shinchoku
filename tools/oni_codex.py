#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/oni_codex.py ── 鬼監督（外の判定役＝ChatGPT/Codex）への1本道。2026-10-01

たまごさん（2026-10-01・原文）:
  「『完了しました』と言っても、俺の基準に達していなかったら差し戻す仕組み。
    自己検品ができないようなので、ChatGPTに検品してもらう仕組み。
    鬼監督システムの話を GitHub 通じてでもやり取りはしてほしいね。」

■ なぜ要るか（2026-10-01 実測）
  tools/oni_modoshi.py（機械の門）は動いている。URL200・中身・過去の指摘までは通す。
  ところが最後の鍵 status/gaibu/soto_hantei.json（外の判定）に**1件ごとの判定を書く人が居ない。**
  外への依頼は gaibu_shinsa.py が「200件まとめて1日1回」投げるだけで、1件ごとの合否は返らない。
  → 機械の門を通った成果物が全部「外待ち」で止まり、合格0のまま回り続けていた。

■ 公式の作法（そのまま使う。オリジナルの通信路は作らない）
  developers.openai.com/codex/integrations/github：
    「@codex を含むコメントで Codex が起きる。review 以外の言葉なら作業として受ける。」
  ＝工場は既にこの形で Codex と双方向◯（tools/nageru.py の codex 口・#450/#466/#481/#502 実測）。
  ★Issue本文ではなく**コメント**で起こす（本文だけでは起きない・#450 実測）。
  ★Codex のクラウドは既定でネットに出られない（#467「見られない」実測）。
    → 判定材料は**こちらで叩いた実物（HTTPコード＋本文の抜粋）をコメントに同梱**する。

■ 流れ（1件＝1往復）
  ① nage   … 成果物URLを叩き、実物の抜粋＋依頼文（＝合格条件）を鬼監督Issueに @codex で投げる
  ② hirou  … chatgpt-codex-connector[bot] の返事を拾い、1行目の「合格／差し戻し」を読む
  ③ 戻す   … 判定を status/gaibu/soto_hantei.json（完了の鍵）と台帳 status/oni_codex/hantei.jsonl に書く
             差し戻しなら command_ingest.queue_add で**作業票に自動で戻す**（たまごさんを通さない）

使い方
  python3 tools/oni_codex.py nage --url URL --title "件名" --irai "依頼文の言葉" [--key N]
  python3 tools/oni_codex.py hirou          # 心臓から毎周回（待ちが無ければ即戻る）
  python3 tools/oni_codex.py --show
"""
from __future__ import annotations

import datetime
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

GH = "/Users/mac/.local/bin/gh"
GH_REPO = "tamago2022/joy-relief-station"
DIR = os.path.join(ST, "oni_codex")
CONF = os.path.join(DIR, "issue.json")          # {"number": N}
MACHI = os.path.join(DIR, "machi.json")         # 返事待ち
HANTEI = os.path.join(DIR, "hantei.jsonl")      # ★判定の台帳（合格／差し戻し）
SOTO = os.path.join(ST, "gaibu", "soto_hantei.json")
JST = datetime.timezone(datetime.timedelta(hours=9))
BOT = "chatgpt-codex-connector"
NUKIGAKI = 3500                                  # 本文の抜粋（文字）


def now():
    return datetime.datetime.now(JST)


def stamp():
    return now().strftime("%Y-%m-%d %H:%M:%S")


def load(p, d):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def save(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def append(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with io.open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(o, ensure_ascii=False) + "\n")


def gh(args, inp=None):
    p = subprocess.run([GH] + args, input=inp, capture_output=True, text=True, timeout=90)
    if p.returncode != 0:
        raise RuntimeError("gh %s rc=%s %s" % (args[:2], p.returncode, (p.stderr or "")[-300:]))
    return p.stdout


def norm(s):
    # gaibu_shinsa.norm と同じ（完了の鍵のキーを揃える）
    return re.sub(r"[★☆*#`>【】\[\]「」『』（）()・:：,、。\.\-—–_/\\!！?？\s]", "", s or "").lower()


def tataku(url):
    """実物を叩く。Codex のクラウドはネットに出られないので、こちらの実測を同梱する。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (iPhone) oni-codex"})
        with urllib.request.urlopen(req, timeout=20) as r:
            code = r.status
            html = r.read(600000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return None, "取得失敗: %s" % type(e).__name__
    t = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", html)
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t).strip()
    head = ("<title>%s</title>\n" % title.group(1).strip()) if title else ""
    return code, head + t


def kara_ka(url, code, text):
    """画面を描いてから中身が出るページ（Lovable等）か。urllibの本文が抜け殻なら True。
    ★実測（2026-10-01 #580）：Lovableの棚は urllib だと「読み込み中」の殻しか返らず、
      Codexが「証拠が無い」で差し戻した＝中身ではなく取り方で落ちていた。"""
    if "lovable.app" in (url or ""):
        return True
    return code == 200 and (len(text or "") < 400 or "読み込み中" in (text or ""))


def egaite_miru(url, aru="", nai=()):
    """表示し終えた画面を読む。既存の tools/2210_tana_miru.mjs をそのまま使う（使い捨てheadless・使ったら殺す）。
    戻り値：(本文, 結果dict, PNGのパス)"""
    png = os.path.join(DIR, "shot-%s.png" % now().strftime("%m%d%H%M%S"))
    env = dict(os.environ, ONI_ZENBUN="1")
    try:
        p = subprocess.run(["node", os.path.join(HERE, "2210_tana_miru.mjs"), url, png, aru or ""] + list(nai),
                           capture_output=True, text=True, timeout=90, env=env, cwd=REPO)
        r = json.loads(p.stdout or "{}")
    except Exception as e:
        return "", {"error": "%s: %s" % (type(e).__name__, e)}, None
    return r.get("text") or "", r, (png if os.path.exists(png) else None)


def shot_wo_oku(png):
    """スクショを公開の置き場（gh-pages の share/oni/）に1枚だけ置いてURLを返す。
    ★git push はしない。真因13の緊急路（gh api PUT contents・単一ファイル）をそのまま使う。"""
    import base64
    import shutil
    name = "share/oni/%s" % os.path.basename(png)
    # 次の公開便（force push）で消えないよう、手元の share/oni/ にも同じ1枚を置く
    os.makedirs(os.path.join(REPO, "share", "oni"), exist_ok=True)
    shutil.copyfile(png, os.path.join(REPO, name))
    body = {"message": "鬼監督の検品スクショ %s" % os.path.basename(png), "branch": "gh-pages",
            "content": base64.b64encode(open(png, "rb").read()).decode()}
    tmp = png + ".json"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(body, f)
    try:
        gh(["api", "--method", "PUT", "repos/tamago2022/tamago-shinchoku/contents/%s" % name, "--input", tmp])
    finally:
        os.remove(tmp)
    return "https://tamago2022.github.io/tamago-shinchoku/%s" % name


def issue_no():
    c = load(CONF, {})
    if not c.get("number"):
        raise RuntimeError("鬼監督Issueの番号が未設定（status/oni_codex/issue.json）")
    return int(c["number"])


def nage(url, title, irai, key=None, aru="", nai=()):
    code, body = tataku(url)
    toriKata = "HTTPで直接取得"
    mieta, shot_url = [], None
    if kara_ka(url, code, body):
        t, r, png = egaite_miru(url, aru, nai)
        if t:
            body, toriKata = t, "iPhone幅(375×812)のheadless Chromeで表示し終えてから画面の文字を読んだ"
        else:
            toriKata = "表示し終えた画面を読めなかった（%s）。HTTPの抜け殻のまま" % (r.get("error") or "本文0字")
        if aru:
            mieta.append("- 出ているべき「%s」: **%s**" % (aru, "画面に出ている" if r.get("found") else "画面に無い"))
        for w in nai:
            mieta.append("- 出てはいけない「%s」: **%s**" % (w, "画面に出ている" if w in (r.get("foundNot") or []) else "画面に無い"))
        if png:
            try:
                shot_url = shot_wo_oku(png)
            except Exception as e:
                mieta.append("- スクショの置き場への公開に失敗（%s）" % type(e).__name__)
    nuki = (body or "")[:NUKIGAKI]
    jid = now().strftime("%m%d%H%M%S")
    text = "\n".join([
        "@codex 鬼監督の検品をお願いします（検品ID: %s）。" % jid,
        "",
        "**対象URL**: %s" % url,
        "**件名**: %s" % title,
        "**依頼文（＝合格条件。この言葉そのものが満たされているか）**:",
        "> " + (irai or "").replace("\n", "\n> "),
        "",
        "**こちらで叩いた実物**（Codexのクラウドはネットに出られないため同梱）: HTTP %s ／ 取り方：%s" % (code, toriKata),
    ] + (["**画面に出ているか（機械が画面の文字で確認）**:"] + mieta if mieta else []) + (
        ["**スクショ（iPhone幅）**: %s" % shot_url, "![screenshot](%s)" % shot_url] if shot_url else []) + [
        "<details><summary>画面の本文（%d字）</summary>\n\n```\n%s\n```\n</details>" % (len(nuki), nuki),
        "",
        "判定基準はこのIssue本文のとおり（論より証拠／依頼文の言葉そのものが合格条件／不快は悪）。",
        "**返し方：1行目に「合格」か「差し戻し」だけ。2行目に理由1行。**コードは変更しないでください。",
    ])
    out = gh(["api", "repos/%s/issues/%d/comments" % (GH_REPO, issue_no()),
              "-F", "body=@-"], inp=text)
    c = json.loads(out)
    m = load(MACHI, {})
    m[jid] = {"jid": jid, "key": key, "title": title, "url": url, "irai": irai,
              "code": code, "commentId": c.get("id"), "commentUrl": c.get("html_url"),
              "at": c.get("created_at"), "nageta": stamp()}
    save(MACHI, m)
    append(HANTEI, {"at": stamp(), "jid": jid, "st": "nageta", "key": key, "title": title,
                    "url": url, "ref": c.get("html_url")})
    return m[jid]


def yomu(body):
    """1行目（無ければ最初に出てくる語）で合否を読む。読めなければ None。"""
    lines = [l.strip(" *#>\t") for l in (body or "").splitlines() if l.strip()]
    for l in lines[:3]:
        if l.startswith("差し戻し") or l.startswith("差戻し") or l.upper().startswith("NG"):
            return False, l
        if l.startswith("合格") or l.upper().startswith("OK"):
            return True, l
    if re.search(r"差し戻し|差戻し", body or ""):
        return False, lines[0] if lines else ""
    if "合格" in (body or ""):
        return True, lines[0] if lines else ""
    return None, lines[0] if lines else ""


def riyuu(body):
    lines = [l.strip(" *#>\t") for l in (body or "").splitlines() if l.strip()]
    return (lines[1] if len(lines) > 1 else (lines[0] if lines else ""))[:200]


def sashimodosu(rec, naze, ref):
    try:
        import command_ingest
        try:
            import queue_store
            lock = queue_store.queue_lock
        except Exception:
            import contextlib
            lock = contextlib.nullcontext
        body = "\n".join([
            "【差し戻し（鬼監督＝Codex）】%s" % rec["title"],
            "【対象URL】%s" % rec["url"],
            "【依頼文（合格条件）】%s" % rec.get("irai", ""),
            "【差し戻しの理由】%s" % naze,
            "【判定の出どころ】%s" % ref,
            "直して、本番URLを報告に貼る。もう一度 tools/oni_codex.py nage で鬼監督に投げ直す。",
            "たまごさんに質問しない。",
        ])
        return command_ingest.queue_add(body, priority=1,
                                        label=("差し戻し（鬼監督）｜" + rec["title"])[:60],
                                        origin="factory")
    except Exception as e:
        return "failed", "%s: %s" % (type(e).__name__, e)



def goukaku_katazuke(rec):
    """合格済み案件に対応する鬼監督の差し戻し票を自動キャンセルし、走行中なら止める。"""
    try:
        import command_ingest
        import signal
        qpath = os.path.join(REPO, "status", "queue.json")
        q = load(qpath, {"items": []})
        base_title = str(rec.get("title") or "").strip()
        base_title = base_title.replace("・再判定", "").replace(" 再判定", "")
        base_title = re.sub(r"（再判定[^）]*）$", "", base_title).strip()
        target_url = str(rec.get("url") or "").strip()
        hit = []
        for it in q.get("items") or []:
            if it.get("status") in ("done", "cancelled"):
                continue
            title = str(it.get("title") or "")
            what = str(it.get("what") or "")
            if not title.startswith("差し戻し（鬼監督）"):
                continue
            if target_url and target_url not in what:
                continue
            if base_title and norm(base_title)[:28] not in norm(title + " " + what):
                continue
            n = int(it.get("n") or 0)
            pid = int(it.get("pid") or 0)
            st, _msg = command_ingest.queue_cancel(str(n))
            if st == "done":
                hit.append(n)
                if pid > 1:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except OSError:
                        pass
        return hit
    except Exception:
        return []

def hirou():
    # ★心臓の周回と手動の呼び出しが重なっても、同じ返事を二重に作業票へ積まない
    import fcntl
    os.makedirs(DIR, exist_ok=True)
    lf = io.open(os.path.join(DIR, ".lock"), "w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return {"skip": "別の hirou が走行中"}
    m = load(MACHI, {})
    if not m:
        return {"machi": 0}
    no = issue_no()
    out = gh(["api", "repos/%s/issues/%d/comments?per_page=100" % (GH_REPO, no), "--paginate"])
    try:
        cs = json.loads(out)
    except Exception:
        cs = []
        for chunk in re.findall(r"\[.*?\](?=\[|\s*$)", out, re.S):
            cs += json.loads(chunk)
    bot = [c for c in cs if BOT in ((c.get("user") or {}).get("login") or "")]
    soto = load(SOTO, {})
    kimatta = []
    for jid, rec in list(m.items()):
        after = [c for c in bot if int(c.get("id") or 0) > int(rec.get("commentId") or 0)]
        for c in sorted(after, key=lambda x: x.get("id")):
            ok, l1 = yomu(c.get("body") or "")
            if ok is None:
                continue          # 「👀」「作業中」などは判定ではない。次を待つ
            naze = riyuu(c.get("body") or "")
            ref = c.get("html_url")
            soto[norm(rec["title"])[:24]] = {"ok": ok, "at": stamp(), "kara": "Codex（鬼監督）",
                                             "naze": naze[:120], "ref": ref}
            row = {"at": stamp(), "jid": jid, "st": "goukaku" if ok else "sashimodoshi",
                   "key": rec.get("key"), "title": rec["title"], "url": rec["url"],
                   "naze": naze, "ichigyoume": l1, "ref": ref}
            if not ok:
                row["queue"] = "%s:%s" % sashimodosu(rec, naze, ref)
            else:
                closed = goukaku_katazuke(rec)
                if closed:
                    row["queueClosed"] = closed
            append(HANTEI, row)
            kimatta.append(row)
            m.pop(jid, None)
            break
    save(SOTO, soto)
    save(MACHI, m)
    return {"machi": len(m), "kimatta": kimatta}


def show():
    rows = []
    try:
        rows = [json.loads(l) for l in io.open(HANTEI, encoding="utf-8") if l.strip()]
    except Exception:
        pass
    lim = (now() - datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    r24 = [r for r in rows if r.get("at", "") >= lim]
    g = sum(1 for r in r24 if r.get("st") == "goukaku")
    s = sum(1 for r in r24 if r.get("st") == "sashimodoshi")
    print("鬼監督(Codex) 直近24h：判定%d件（合格%d・差し戻し%d）／返事待ち%d件"
          % (g + s, g, s, len(load(MACHI, {}))))
    for r in r24[-10:]:
        print(" ", r.get("at"), r.get("st"), r.get("title"), r.get("ref") or "")


def main():
    a = sys.argv[1:]
    if not a or a[0] == "--show":
        show()
        return 0
    if a[0] == "nage":
        def opt(k, d=""):
            return a[a.index(k) + 1] if k in a else d
        nai = [w for w in opt("--nai").split(",") if w.strip()]
        r = nage(opt("--url"), opt("--title"), opt("--irai"), opt("--key") or None,
                 aru=opt("--aru"), nai=nai)
        print("投げた", r["jid"], r["commentUrl"], "HTTP", r["code"])
        return 0
    if a[0] == "hirou":
        r = hirou()
        print(json.dumps(r, ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
