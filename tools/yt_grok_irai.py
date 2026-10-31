#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YouTube の限定公開を Grokボットに頼み、返ってきたURLを台帳に残す係（2026-10-31 たまごさん）

たまごさん（10-31 夜）：「Grokボットは普通に限定公開で上げてくる」
  → tools/yt_gentei.py（自分で上げる道具）は Google の OAuth クライアントJSONが無くて止まっている（status/yt_gentei/jotai.json）。
    代わりに、GitHub の共有メモ（joy-relief-station Issue #1040）に「どの動画を・どこに・どの形で返すか」を書いて Grok に頼む。

  python3 tools/yt_grok_irai.py kaku <頼み.json>   … Mac で：Issue にコメントを書き（gh）、頼みを台帳に積む。呼び鈴（grok_tsuushin）も鳴らす
       頼み.json = {"issue":1040, "items":[{"key":"宇宙うんこv2","namae":"261031_宇宙うんこv2_滝.mp4","drive":"https://drive..."}...], "body":"本文"}
  python3 tools/yt_grok_irai.py --tick              … 心臓（top_status の相乗り・中で10分に間引く）：頼んだ後の Issue のコメントから
                                                       YouTube のURLを拾い、「名前｜URL」の行なら名前で、そうでなければ順番の記録だけ残す。
                                                       新しく取れたURLは Dispatch へ1行。全部そろうか7日たったら見に行かない
  python3 tools/yt_grok_irai.py --jotai
  python3 tools/yt_grok_irai.py --self-test

決まり：自分では上げない・公開（public）を頼まない（限定公開＝unlisted だけ）・SNSに投稿しない。gh は Mac でだけ動く。
作るもの：status/yt_gentei/grok_irai.json（台帳・status/ は公開リポに載らない）／status/dispatch_outbox.jsonl に1行
台帳：tools/jidou_daicho.json の "yt_grok_irai.py"（一時ファイル・ブラウザ・複製は作らない）
"""
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GH_REPO = "tamago2022/joy-relief-station"
DAICHO = os.path.join(REPO, "status", "yt_gentei", "grok_irai.json")
STAMP = os.path.join(REPO, "status", "yt_gentei", ".grok_irai_at")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
MAX_DAYS = 7
YT = re.compile(r"https?://(?:www\.|m\.)?(?:youtu\.be/[\w-]{6,}|youtube\.com/(?:watch\?v=|shorts/)[\w-]{6,})[^\s)>\]」）]*")


def load():
    try:
        with open(DAICHO, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"irai": []}


def save(d):
    os.makedirs(os.path.dirname(DAICHO), exist_ok=True)
    tmp = DAICHO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DAICHO)


def gh(args, timeout=60):
    """心臓の PATH には gh が無いことがあるので、共有メモ係（zen_ai_kyouyu）と同じ探し方・同じ環境で呼ぶ"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import zen_ai_kyouyu as Z
        p = subprocess.run([Z.exe("gh")] + args, capture_output=True, text=True, timeout=timeout, env=Z.ENV)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", "gh が無い"


def dispatch(what, url=""):
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.strftime("%F %T"), "from": "yt_grok_irai", "type": "yt_gentei",
                            "what": what, "url": url}, ensure_ascii=False) + "\n")


def hiroi(body, items):
    """コメント本文から (key or None, URL) を拾う。同じ行に名前（key）があれば名前で結ぶ"""
    out = []
    for ln in body.splitlines():
        for u in YT.findall(ln):
            k = next((it["key"] for it in items if it["key"] in ln or os.path.splitext(it.get("namae", ""))[0] in ln), None)
            out.append((k, u))
    return out


def kaku(path):
    req = json.load(open(path, encoding="utf-8"))
    num = int(req.get("issue", 1040))
    rc, out, err = gh(["api", "repos/%s/issues/%d/comments" % (GH_REPO, num), "-f", "body=" + req["body"],
                       "--jq", "[.html_url,.created_at]|@tsv"])
    if rc != 0:
        print("書けなかった:", err.strip()[:300]); return 1
    html, created = out.strip().split("\t")
    d = load()
    d["irai"].append({"issue": num, "comment": html, "since": created, "at": time.strftime("%F %T"),
                      "items": [dict(it, youtube="") for it in req["items"]], "hokano_url": [], "owari": ""})
    save(d)
    try:   # 呼び鈴（Reason Network が生きていれば数秒で Grok に届く。だめでも Issue は3時間おきに読まれる）
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        subprocess.run(["python3", os.path.join(REPO, "tools", "grok_tsuushin.py"), "okuru", "--title",
                        "YouTube限定公開のお願い（%d本）" % len(req["items"]), "--body",
                        "Issue #%d にリンク一覧を書きました。YouTube ＠joy-relief-station に限定公開で上げて、URLを同じIssueに返してください。" % num,
                        "--url", html], timeout=60, capture_output=True)
    except Exception:
        pass
    dispatch("Grokに YouTube 限定公開を頼んだ（%d本）｜%s" % (len(req["items"]), html), html)
    print(html)
    return 0


def tick(force=False):
    try:
        if not force and time.time() - os.path.getmtime(STAMP) < 600:
            return
    except OSError:
        pass
    os.makedirs(os.path.dirname(STAMP), exist_ok=True)
    open(STAMP, "w").close()
    d = load(); changed = False
    for r in d["irai"]:
        if r.get("owari"):
            continue
        if all(it["youtube"] for it in r["items"]):
            r["owari"] = "そろった " + time.strftime("%F %T"); changed = True; continue
        t0 = time.mktime(time.strptime(r["at"], "%Y-%m-%d %H:%M:%S"))
        if time.time() - t0 > MAX_DAYS * 86400:
            r["owari"] = "7日たった（そろわず）"; changed = True
            dispatch("Grokの限定公開、7日たってもURLがそろわない（%d/%d）｜%s" % (
                sum(1 for it in r["items"] if it["youtube"]), len(r["items"]), r["comment"]), r["comment"])
            continue
        rc, out, err = gh(["api", "repos/%s/issues/%d/comments?since=%s&per_page=100" % (GH_REPO, r["issue"], r["since"]),
                           "--jq", ".[]|[.html_url,.body]|@json"])
        if rc != 0:
            continue
        for ln in out.splitlines():
            try:
                html, body = json.loads(ln)
            except Exception:
                continue
            if html == r["comment"] or "<!-- tamago-factory -->" in body:
                continue
            for k, u in hiroi(body, r["items"]):
                it = next((x for x in r["items"] if x["key"] == k), None)
                if it and not it["youtube"]:
                    it["youtube"] = u; it["kaeshi"] = html; changed = True
                    dispatch("限定公開が返ってきた：%s｜%s" % (it["namae"], u), u)
                elif not it and u not in [x["url"] for x in r["hokano_url"]] and u not in [x["youtube"] for x in r["items"]]:
                    r["hokano_url"].append({"url": u, "kaeshi": html}); changed = True
                    dispatch("Issue #%d に名前の分からない YouTube URL：%s（どの動画か要確認）" % (r["issue"], u), u)
    if changed:
        save(d)


def jotai():
    d = load()
    for r in d["irai"]:
        print(r["at"], r["comment"], r.get("owari") or "待ち")
        for it in r["items"]:
            print("  ", it["namae"], it["youtube"] or "（まだ）")


def self_test():
    items = [{"key": "宇宙うんこv2", "namae": "261031_宇宙うんこv2_滝.mp4"}, {"key": "音ハメ_絵本", "namae": "261031_音ハメ_絵本.mp4"}]
    body = "上げました\n宇宙うんこv2｜https://youtu.be/AbCdEf12345\n- 261031_音ハメ_絵本: https://www.youtube.com/watch?v=ZZZzzz99999\nおまけ https://youtube.com/shorts/QQQqqq77777"
    got = hiroi(body, items)
    assert got[0] == ("宇宙うんこv2", "https://youtu.be/AbCdEf12345"), got
    assert got[1] == ("音ハメ_絵本", "https://www.youtube.com/watch?v=ZZZzzz99999"), got
    assert got[2][0] is None and "shorts/QQQqqq77777" in got[2][1], got
    assert not YT.findall("https://drive.google.com/file/d/xyz/view")
    print("self-test OK")
    return True


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "--jotai":
        jotai()
    elif a[0] == "kaku":
        sys.exit(kaku(a[1]))
    elif a[0] == "--tick":
        tick("--force" in a)
    elif a[0] == "--self-test":
        sys.exit(0 if self_test() else 1)
