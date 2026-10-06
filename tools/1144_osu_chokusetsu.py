#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1144番【出るまで押す】mainに入れた中身が本番に出るまで、Lovableの公開を自分で押す。

なぜ別に作るか（2026-09-25 実測）:
  tools/kohyou_osu.py は「見る係が赤にしたときだけ」押す。1144番のように
  こちらから main を動かした直後は、見る係が次の回に測るまで黄のままで、
  何分も押されない。→ たまごさん「公開は聞かずに押す」に合わない。
  この1本は、**Lovableが新しいmainを取り込んでいることを確かめてから**押す。
  （取り込む前に押すと別の中身が出るので、そこは絶対に確かめる。）

安全:
  呼ぶのは get_project と deploy_project の2つだけ（kohyou_osu.py の白名簿を使う）。
  deploy は全プラン無料＝課金0。
  出たかどうかは x-deployment-id の**UUIDの部分だけ**で見る（後ろは毎回変わる飾り）。
"""
from __future__ import annotations
import os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kohyou_osu import Lovable, MATO   # noqa: E402

NAME = "ごきげん補給所"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Safari/537.36"


def honban_uuid(url):
    """本番が今どの版を出しているか。x-deployment-id の UUID だけを返す。"""
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(r, timeout=20) as resp:
            v = resp.headers.get("x-deployment-id") or ""
    except Exception as e:
        print("本番が読めません: %r" % (e,)); return ""
    parts = v.split(".")
    return parts[1] if len(parts) > 1 else v


def motteru_kanmon(sha):
    """そのコミットに関所（src/lib/kansei.ts）が入っているか。

    ★mainは15分ごとに動くのでSHA一致では永久に合わない。
      「関所が入っている版か」で見るのが正しい（これが出したい中身の条件そのもの）。
    ★raw.githubusercontent.com で見てはいけない（2026-09-25 実測）:
      押す前の404がCDNに5分ほど残り、入った後も404を返し続ける＝永久に押せない。
      → GitHubのAPIで木（tree）を引いて、パスがあるかで見る。
    """
    import json as _json, urllib.request as _u
    sys.path.insert(0, HERE)
    import github_watch
    tok = github_watch.gh_token()
    url = ("https://api.github.com/repos/tamago2022/joy-relief-station/git/trees/%s?recursive=1"
           % sha)
    r = _u.Request(url)
    r.add_header("Authorization", "Bearer %s" % tok)
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("User-Agent", "tamago-1144")
    try:
        with _u.urlopen(r, timeout=90) as resp:
            tree = _json.loads(resp.read())
    except Exception as e:
        print("    木が読めません: %r" % (e,)); return False
    paths = {e.get("path") for e in tree.get("tree", [])}
    return "src/lib/kansei.ts" in paths and "src/lib/kanseiHidden.generated.ts" in paths


def main():
    want = (sys.argv[1] if len(sys.argv) > 1 else "").strip()[:8]
    mato = MATO[NAME]
    lv = Lovable()
    if not lv.ok():
        print("鍵がありません。押せません"); return 2
    lv.hello()
    before = honban_uuid(mato["url"])
    print("本番のいま = %s / 出したいコミット = %s" % (before or "-", want or "(指定なし)"))

    for i in range(1, 41):                      # 最大およそ20分
        o, err = lv.call("get_project", {"project_id": mato["project_id"]})
        if o is None:
            print("[%d] get_project が読めません: %s" % (i, err)); time.sleep(30); continue
        sha = (o.get("latest_commit_sha") or "")[:8]
        print("[%d] %s Lovableが持つコミット = %s" % (i, time.strftime("%H:%M:%S"), sha or "-"))
        if not sha or not motteru_kanmon(sha):
            print("    → その版に関所がまだ入っていないので押しません（待つ）")
            time.sleep(30); continue
        print("    → その版に関所が入っています。押します")
        r, err = lv.call("deploy_project", {"project_id": mato["project_id"]})
        if r is None:
            print("    deploy_project が読めません: %s" % err); time.sleep(30); continue
        print("    ★押しました status=%s id=%s" % (r.get("status"), (r.get("deployment_id") or "")[:8]))
        for j in range(20):                     # 出るまで最大10分見る
            time.sleep(30)
            now = honban_uuid(mato["url"])
            print("    確かめ%d: 本番 = %s" % (j + 1, now or "-"))
            if now and now != before:
                print("★出ました %s → %s" % (before, now))
                return 0
        print("    押しても変わりませんでした。もう一度押します")
        before = honban_uuid(mato["url"]) or before
    print("★出ませんでした（時間切れ）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
