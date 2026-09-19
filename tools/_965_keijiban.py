#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""965番【AI掲示板】GitHubのIssueを「AI同士の相談机」として使うための口。

たまごさん（2026-09-20・原文）:
  「28円かかるんだ。30円で33回やったら1000円になる。ジェミニーもGrokもやったら
    5000円いっちゃうかもしれない。GitHubにみんな自分の意見を書いて、それが
    レポートに返ってくる、そういうことではないんだ？」

★答え：そういうことです。GitHub経由なら API代は0円。
  各社の「月額の中に入っている GitHub連携」を使うので、従量課金が発生しない。

■ このファイルがやること（工場＝Mac側で走る。サンドボックスからは回線が出ない）
  action=bots    … この repo に実際に書き込んだ相手（Bot / App）を一覧にする。
                   「繋がっている」を推測ではなく**実測**で出すためのもの。
  action=issue   … 掲示板のお題を1本立てる（Issue作成）。
  action=comment … 既存のお題に1行足す。

■ 安全のための決まり
  - 行き先は api.github.com の、下の ALLOW_REPO に書いた repo だけ。
  - 鍵（トークン）の値は結果に絶対に出さない。長さも出さない。
  - 課金は1円も発生しない（GitHub REST APIは無料）。totalYen は常に 0.0。
"""
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import github_watch  # noqa: E402  ★トークンの取り方はここに1本化されている

ALLOW_REPO = ("tamago2022/joy-relief-station", "tamago2022/tamago-shinchoku")
API = "https://api.github.com"


def _req(url, token, method="GET", body=None, timeout=25):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer %s" % token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "tamago-965-keijiban")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.getcode(), json.loads(r.read().decode("utf-8", "ignore") or "null")


def _err(e):
    if isinstance(e, urllib.error.HTTPError):
        try:
            b = e.read().decode("utf-8", "ignore")
        except Exception:
            b = ""
        return "HTTP %s %s" % (e.code, b[:400])
    return "%s: %s" % (type(e).__name__, e)


def _bots(repo, token):
    """この repo に実際に書いた相手を数える。Bot（＝GitHub App）が本命。"""
    who = {}

    def add(u, where):
        if not u:
            return
        k = "%s (%s)" % (u.get("login"), u.get("type"))
        d = who.setdefault(k, {"login": u.get("login"), "type": u.get("type"),
                               "issues": 0, "comments": 0, "commits": 0})
        d[where] += 1

    for url, where in (
        ("%s/repos/%s/issues?state=all&per_page=100" % (API, repo), "issues"),
        ("%s/repos/%s/issues/comments?per_page=100&sort=created&direction=desc" % (API, repo), "comments"),
    ):
        code, data = _req(url, token)
        for it in (data or []):
            add(it.get("user"), where)

    code, data = _req("%s/repos/%s/commits?per_page=100" % (API, repo), token)
    for c in (data or []):
        add(c.get("author"), "commits")

    rows = sorted(who.values(), key=lambda d: -(d["issues"] + d["comments"] + d["commits"]))
    return rows


def run_job(payload):
    payload = payload or {}
    repo = payload.get("repo") or ALLOW_REPO[0]
    if repo not in ALLOW_REPO:
        return {"ok": False, "error": "行き先が白名簿にありません: %s" % repo, "totalYen": 0.0}

    token = github_watch.gh_token()
    if not token:
        return {"ok": False, "error": "GitHubのトークンが取れませんでした（gh auth login が要る）",
                "totalYen": 0.0}

    action = payload.get("action") or "bots"
    try:
        if action == "bots":
            return {"ok": True, "repo": repo, "action": action,
                    "writers": _bots(repo, token), "totalYen": 0.0}

        if action == "issue":
            body = {"title": payload["title"], "body": payload["body"]}
            if payload.get("labels"):
                body["labels"] = payload["labels"]
            code, d = _req("%s/repos/%s/issues" % (API, repo), token, "POST", body)
            return {"ok": True, "repo": repo, "action": action, "number": d.get("number"),
                    "url": d.get("html_url"), "totalYen": 0.0}

        if action == "comment":
            code, d = _req("%s/repos/%s/issues/%s/comments" % (API, repo, payload["number"]),
                           token, "POST", {"body": payload["body"]})
            return {"ok": True, "repo": repo, "action": action,
                    "url": d.get("html_url"), "totalYen": 0.0}

        if action == "read":
            code, d = _req("%s/repos/%s/issues/%s/comments?per_page=100" % (API, repo, payload["number"]),
                           token)
            return {"ok": True, "repo": repo, "action": action,
                    "comments": [{"who": (c.get("user") or {}).get("login"),
                                  "type": (c.get("user") or {}).get("type"),
                                  "at": c.get("created_at"),
                                  "text": (c.get("body") or "")[:4000]} for c in (d or [])],
                    "totalYen": 0.0}

        return {"ok": False, "error": "知らない action: %s" % action, "totalYen": 0.0}
    except Exception as e:
        return {"ok": False, "error": _err(e), "totalYen": 0.0}


if __name__ == "__main__":
    print(json.dumps(run_job({"action": sys.argv[1] if len(sys.argv) > 1 else "bots"}),
                     ensure_ascii=False, indent=1))
