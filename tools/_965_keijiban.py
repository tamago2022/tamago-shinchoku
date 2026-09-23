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

# ★2026-09-22（977番）：公開の掲示板 tamago2022/ai-kaigi を追加。
#   理由＝Grok / Genspark は**非公開リポが読めない**（たまごさん実測）。
#   joy-relief-station は .env が入っているので絶対に公開にしない。だから別の公開repoを掲示板にする。
#   ★ai-kaigi へ書くものは全世界から読める。秘密の混入検査は tools/nageru.py 側で機械的にやる。
ALLOW_REPO = ("tamago2022/joy-relief-station", "tamago2022/tamago-shinchoku",
              "tamago2022/ai-kaigi")
PUBLIC_REPO = ("tamago2022/ai-kaigi", "tamago2022/tamago-shinchoku")
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

    # ★2026-09-22：中身がまだ1つも無いrepo（掲示板として作っただけの ai-kaigi）は
    #   /commits が 409「Git Repository is empty.」を返す。これは異常ではない。
    #   ここで例外にすると、Issueは数えられているのに人口調査ごと失敗扱いになる。
    try:
        code, data = _req("%s/repos/%s/commits?per_page=100" % (API, repo), token)
        for c in (data or []):
            add(c.get("author"), "commits")
    except urllib.error.HTTPError as e:
        if e.code != 409:
            raise

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

        if action == "label":
            # 977番：既に立っている号にラベルを貼る（Julesの起こし方はこれ・公式ドキュメント）。
            code, d = _req("%s/repos/%s/issues/%s/labels" % (API, repo, payload["number"]),
                           token, "POST", {"labels": payload["labels"]})
            return {"ok": True, "repo": repo, "action": action,
                    "labels": [x.get("name") for x in (d or [])], "totalYen": 0.0}

        if action == "exists":
            # 977番：掲示板そのものが在るか（公開/非公開も）。GETだけ・課金0。
            try:
                code, d = _req("%s/repos/%s" % (API, repo), token)
                return {"ok": True, "repo": repo, "action": action, "exists": True,
                        "private": bool((d or {}).get("private")),
                        "url": (d or {}).get("html_url"),
                        "openIssues": (d or {}).get("open_issues_count"), "totalYen": 0.0}
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return {"ok": True, "repo": repo, "action": action, "exists": False,
                            "totalYen": 0.0}
                raise

        if action == "read":
            code, head = _req("%s/repos/%s/issues/%s" % (API, repo, payload["number"]), token)
            code, d = _req("%s/repos/%s/issues/%s/comments?per_page=100" % (API, repo, payload["number"]),
                           token)
            return {"ok": True, "repo": repo, "action": action,
                    "title": (head or {}).get("title"),
                    "bodyWho": ((head or {}).get("user") or {}).get("login"),
                    "body": ((head or {}).get("body") or "")[:6000],
                    # ★977番：id を足した。台帳（ai_daicho.py）が「同じ返事を二度数えない」
                    #   照合に使う。Issue番号で照合すると、同じ号への2通目以降が
                    #   重複扱いで消える（2026-09-19にチャッピーの返信4通が消えた事故）。
                    "comments": [{"id": c.get("id"),
                                  "who": (c.get("user") or {}).get("login"),
                                  "type": (c.get("user") or {}).get("type"),
                                  "at": c.get("created_at"),
                                  "text": (c.get("body") or "")[:4000]} for c in (d or [])],
                    "totalYen": 0.0}

        if action == "prfiles":
            code, d = _req("%s/repos/%s/pulls/%s/files?per_page=30" % (API, repo, payload["number"]), token)
            out = []
            for f in (d or []):
                out.append({"name": f.get("filename"), "add": f.get("additions"),
                            "patch": (f.get("patch") or "")[:6000]})
            return {"ok": True, "repo": repo, "action": action, "files": out, "totalYen": 0.0}

        if action == "prstate":
            # ★1027番：名指しのPRが**mainに入ったか**だけを見る。GETのみ・課金0。
            #   Jules が立てたPRは作者が tamago2022 になる（GitHub Appが持ち主の名で押すため）。
            #   だから作者で数えると Jules の分が全部たまごさんの分に混ざる。名指しで見るのはそのため。
            out = []
            for num in (payload.get("numbers") or []):
                code, p = _req("%s/repos/%s/pulls/%s" % (API, repo, num), token)
                out.append({"number": num,
                            "title": (p or {}).get("title"),
                            "author": (((p or {}).get("user") or {}).get("login")),
                            "state": (p or {}).get("state"),
                            "merged": bool((p or {}).get("merged_at")),
                            "mergedAt": (p or {}).get("merged_at"),
                            "additions": (p or {}).get("additions"),
                            "deletions": (p or {}).get("deletions"),
                            "changedFiles": (p or {}).get("changed_files"),
                            "createdAt": (p or {}).get("created_at"),
                            "url": (p or {}).get("html_url")})
            return {"ok": True, "repo": repo, "action": action, "prs": out, "totalYen": 0.0}

        if action == "prstats":
            # ★1027番：「返事を書いた数」と「本番に出た数」を分けて数えるための口。
            #   誰がPRを何本立てて、そのうち何本が**mainに入ったか**（merged）を数える。
            #   コメントの数だけ見ていると、返事が多い子＝役に立った子に見えてしまう。
            #   Devinで「15本中1本しか入らなかった（6.7%）」を見落としたのがこれ。
            #   GETのみ・課金0・白名簿repoの中だけ。
            out, page = {}, 1
            while page <= 5:
                code, d = _req("%s/repos/%s/pulls?state=all&per_page=100&page=%d" % (API, repo, page), token)
                if not d:
                    break
                for p in d:
                    who = ((p.get("user") or {}).get("login")) or "?"
                    r = out.setdefault(who, {"login": who,
                                             "type": ((p.get("user") or {}).get("type")),
                                             "opened": 0, "merged": 0, "closedUnmerged": 0, "open": 0})
                    r["opened"] += 1
                    if p.get("merged_at"):
                        r["merged"] += 1
                    elif p.get("state") == "closed":
                        r["closedUnmerged"] += 1
                    else:
                        r["open"] += 1
                if len(d) < 100:
                    break
                page += 1
            rows = sorted(out.values(), key=lambda x: -x["opened"])
            return {"ok": True, "repo": repo, "action": action, "prs": rows, "totalYen": 0.0}

        return {"ok": False, "error": "知らない action: %s" % action, "totalYen": 0.0}
    except Exception as e:
        return {"ok": False, "error": _err(e), "totalYen": 0.0}


if __name__ == "__main__":
    print(json.dumps(run_job({"action": sys.argv[1] if len(sys.argv) > 1 else "bots"}),
                     ensure_ascii=False, indent=1))
