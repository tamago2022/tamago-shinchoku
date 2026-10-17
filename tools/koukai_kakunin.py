#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公開（Lovable の deploy_project）が本当に本番に出たかを確かめ、出なければ「なぜ止まったか」まで出す。

■ なぜ要るか（2026-10-17 実測）
  10/16 16:56 の d6551f7（特集キャプションから制作メモを外した）で、prebuild の言語の関所
  （scripts/patrol/check-i18n-parity.mjs）が失敗し始めた。Lovable はビルドが落ちても deploy_project に
  「pending／受付済み」を返すだけなので、約20時間、何回公開を押しても本番が古いままだった。誰も気づけなかった。

■ やること（GETと手元のビルド前検査だけ。課金0・公開の操作はしない）
  1. 本番トップの x-deployment-id を記録し、--wait 分まで変わるのを待つ（--before で押す前のIDを渡す）
  2. 変わらなければ、~/tamago/jrs_fix（joy-relief-station の main の写し）を最新にして prebuild の関所を1本ずつ走らせ、
     落ちた関所とその出力を status/koukai_kakunin.json と status/dispatch_outbox.jsonl に1行で出す
  使い方:
    python3 tools/koukai_kakunin.py --id                 # 今の本番の deployment-id
    python3 tools/koukai_kakunin.py --before <ID> --wait 12
    python3 tools/koukai_kakunin.py --kanmon             # 本番は見ずに prebuild の関所だけ走らせる
"""
import json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
JRS = os.path.expanduser("~/tamago/jrs_fix")
SITE = "https://joy-relief-station.lovable.app/"
OUT = os.path.join(REPO, "status", "koukai_kakunin.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
ENV = dict(os.environ, PATH=os.path.expanduser("~/.bun/bin:~/.local/bin:") + "/usr/local/bin:/opt/homebrew/bin:" + os.environ.get("PATH", ""))


def dep_id():
    req = urllib.request.Request(SITE, method="HEAD", headers={"User-Agent": "tamago-koukai-kakunin", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=20) as r:
        v = r.headers.get("x-deployment-id") or ""
    return v.split(".")[1] if v.count(".") >= 1 else v


def kanmon():
    """prebuild の関所を1本ずつ走らせ、落ちたものを返す。"""
    if not os.path.isdir(os.path.join(JRS, ".git")):
        subprocess.run(["gh", "repo", "clone", "tamago2022/joy-relief-station", JRS, "--", "--depth", "50"], env=ENV, capture_output=True)
    subprocess.run(["git", "-C", JRS, "pull", "-q", "--rebase", "origin", "main"], env=ENV, capture_output=True)
    if not os.path.isdir(os.path.join(JRS, "node_modules")):
        subprocess.run(["bun", "install"], cwd=JRS, env=ENV, capture_output=True)
    pre = json.load(open(os.path.join(JRS, "package.json")))["scripts"]["prebuild"]
    ochi = []
    for c in [x.strip() for x in pre.split("&&")]:
        p = subprocess.run(c, shell=True, cwd=JRS, env=ENV, capture_output=True, text=True)
        if p.returncode != 0:
            ochi.append({"kanmon": c, "out": ((p.stdout or "") + (p.stderr or ""))[-1500:]})
    # 生成物の書き換えは元に戻す（関所が書く控え・生成ファイル）
    subprocess.run(["git", "-C", JRS, "checkout", "--", "."], env=ENV, capture_output=True)
    head = subprocess.run(["git", "-C", JRS, "log", "-1", "--format=%h %ci %s"], env=ENV, capture_output=True, text=True).stdout.strip()
    return head, ochi


def main():
    a = sys.argv[1:]
    if "--id" in a:
        print(dep_id()); return 0
    if "--kanmon" in a:
        head, ochi = kanmon()
        print(json.dumps({"main": head, "ochita": ochi}, ensure_ascii=False, indent=1)); return 1 if ochi else 0
    before = a[a.index("--before") + 1] if "--before" in a else dep_id()
    wait = float(a[a.index("--wait") + 1]) if "--wait" in a else 12
    t_end = time.time() + wait * 60
    now = before
    while time.time() < t_end:
        try:
            now = dep_id()
        except Exception:
            pass
        if now and now != before:
            r = {"ts": time.strftime("%FT%T%z"), "ok": True, "before": before, "after": now}
            json.dump(r, open(OUT, "w"), ensure_ascii=False, indent=1); print(json.dumps(r, ensure_ascii=False)); return 0
        time.sleep(30)
    head, ochi = kanmon()
    r = {"ts": time.strftime("%FT%T%z"), "ok": False, "before": before, "after": now, "main": head, "ochita": ochi}
    json.dump(r, open(OUT, "w"), ensure_ascii=False, indent=1)
    why = ochi[0]["kanmon"] if ochi else "prebuild の関所は全部通る（Lovable 側のビルド・混雑を疑う）"
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%FT%T%z"), "n": "koukai-kakunin", "type": "red",
                            "title": "公開を押したのに本番が変わっていません（%d分）" % wait,
                            "message": "main=%s ／ 止めているもの：%s" % (head, why)}, ensure_ascii=False) + "\n")
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 1


if __name__ == "__main__":
    sys.exit(main())
