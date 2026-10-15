#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub Actions の月の分数を無料枠（GitHub Free＝非公開リポで月2,000分）に収めるための道具（2026-10-11）。

なぜ要るか（実測・2026-10-11）：
  joy-relief-station（非公開）だけが分を食っていた。10月は1日〜5日で約1,955分を使い切り、
  以降は「支払いが止まっている」表示でジョブが起動前に落ちていた（PR #906 もこれ）。
  公開リポ（tamago-shinchoku・ai-kaigi）は標準ランナーなら無料なので数えない。

使い方（Macで。鍵は ~/.tamago/gh_token をそのまま使う＝キーチェーンの許可ポップアップを出さない）：
  python3 tools/actions_waku.py herasu   … status/gh_actions_waku/new/ の内容で workflow を書き換える
                                           （GitHub上の今の中身が、測った時の中身と1文字でも違えばその1本は触らない）
  python3 tools/actions_waku.py modosu   … 全部、書き換える前の中身（status/gh_actions_waku/moto/）へ戻す
  python3 tools/actions_waku.py modosu tamago-manager.yml … 1本だけ戻す
  記録：status/gh_actions_waku/herashita.json
  測り直し：status/gh_actions_waku/collect2.py → collect3.py（今月の実分数をジョブ単位で数える）
"""
import base64, hashlib, json, os, sys, time, urllib.request, urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(REPO, "status", "gh_actions_waku")
FULL = "tamago2022/joy-relief-station"
TOK = open(os.path.expanduser("~/.tamago/gh_token")).read().strip()


def call(method, path, body=None):
    req = urllib.request.Request("https://api.github.com" + path, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": "Bearer " + TOK, "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"err": e.read().decode()[:300]}


def live(name):
    st, d = call("GET", "/repos/%s/contents/.github/workflows/%s?ref=main" % (FULL, name))
    if st != 200:
        return None, None
    return base64.b64decode(d["content"]).decode(), d["sha"]


def put(name, text, sha, msg):
    st, d = call("PUT", "/repos/%s/contents/.github/workflows/%s" % (FULL, name),
                 {"message": msg, "content": base64.b64encode(text.encode()).decode(), "sha": sha, "branch": "main"})
    return st, (d.get("commit") or {}).get("sha", d.get("err", ""))[:40]


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    only = set(sys.argv[2:])
    log_path = os.path.join(W, "herashita.json")
    log = json.load(open(log_path)) if os.path.exists(log_path) else []
    if cmd == "herasu":
        src, dst, msg = "moto", "new", "[skip ci] ci: GitHub Actions を無料枠（月2,000分）に収める（戻す: python3 tools/actions_waku.py modosu）"
    elif cmd == "modosu":
        src, dst, msg = "new", "moto", "[skip ci] ci: Actions 節約を元に戻す（tools/actions_waku.py modosu）"
    else:
        print(__doc__); return 1
    for name in sorted(os.listdir(os.path.join(W, dst))):
        if only and name not in only:
            continue
        want = open(os.path.join(W, dst, name)).read()
        expect = open(os.path.join(W, src, name)).read()
        cur, sha = live(name)
        if cur is None:
            r = (name, "GitHubで読めない")
        elif cur == want:
            r = (name, "既にその状態")
        elif cur != expect and cmd == "herasu":
            r = (name, "測った後に誰かが書き換えている→触らない")
        else:
            st, c = put(name, want, sha, msg)
            r = (name, "書き換えた %s %s" % (st, c))
        print(*r)
        log.append({"at": time.strftime("%F %T"), "cmd": cmd, "file": r[0], "result": r[1]})
    json.dump(log, open(log_path, "w"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
