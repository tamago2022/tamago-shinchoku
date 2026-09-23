#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1145番【押す】隠す表（kanseiHidden.generated.ts）だけを main に1コミットで入れる。0円。

なぜ別に作ったか：1132_dasu.py は「1132.patch が当たること」が前提。
1132番が既に main に入ったので、そのpatchはもう当たらない（実測で失敗した）。
隠す表を更新するだけなら patch は要らない。**1本のファイルを差し替えるだけ**。

データは1件も消していない。隠しているだけ。動画が戻れば次の生成で自動的に表から外れる。
"""
from __future__ import annotations
import importlib.util, io, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "status", "1140", "kanseiHidden.generated.ts")
PATH_IN_REPO = "src/lib/kanseiHidden.generated.ts"


def load_dasu():
    spec = importlib.util.spec_from_file_location("dasu", os.path.join(HERE, "1132_dasu.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_job(payload=None):
    payload = payload or {}
    m = load_dasu()
    log = []
    body = io.open(SRC, encoding="utf-8").read()
    token = m._token()
    if not token:
        return {"ok": False, "log": ["GitHubの鍵が取れませんでした"], "totalYen": 0.0}
    api, repo, br = m.API, m.GH_REPO, m.BRANCH
    head = m._req("GET", "%s/repos/%s/git/ref/heads/%s" % (api, repo, br), token)
    base = head["object"]["sha"]
    log.append("いまの main = %s" % base[:8])
    base_commit = m._req("GET", "%s/repos/%s/git/commits/%s" % (api, repo, base), token)

    # いま main に入っているものと同じなら押さない
    try:
        tree = m._req("GET", "%s/repos/%s/git/trees/%s?recursive=1"
                      % (api, repo, base_commit["tree"]["sha"]), token)
        cur = [t for t in tree.get("tree", []) if t["path"] == PATH_IN_REPO]
        if cur:
            blob = m._req("GET", "%s/repos/%s/git/blobs/%s" % (api, repo, cur[0]["sha"]), token)
            import base64
            old = base64.b64decode(blob["content"]).decode("utf-8", "ignore")
            if old.strip() == body.strip():
                log.append("main と同じでした。押しません")
                return {"ok": True, "log": log, "alreadyIn": True, "totalYen": 0.0}
            log.append("いま main にある行数 %d → 押す行数 %d"
                       % (old.count("\n"), body.count("\n")))
    except Exception as e:
        log.append("いまのものを読めませんでした（押しは続ける）: %r" % (e,))

    if payload.get("dryRun"):
        log.append("--dry-run なのでGitHubには書きません")
        return {"ok": True, "log": log, "dryRun": True, "totalYen": 0.0}

    blob = m._req("POST", "%s/repos/%s/git/blobs" % (api, repo), token,
                  {"content": body, "encoding": "utf-8"})
    new_tree = m._req("POST", "%s/repos/%s/git/trees" % (api, repo), token,
                      {"base_tree": base_commit["tree"]["sha"],
                       "tree": [{"path": PATH_IN_REPO, "mode": "100644",
                                 "type": "blob", "sha": blob["sha"]}]})
    msg = ("1145番【実物で棚卸し】動画24,005本を1本ずつ実際に叩いて、"
           "再生できないものを表から外した\n\n"
           "実測 = tools/1145_jissoku.py（YouTube oEmbed・1本ずつ・0円）\n"
           "  叩いた 24,005本 / 未実測 0本 / 生きている 23,862本 / 再生できない 143本\n"
           "  （削除・非公開 82 ／ 埋め込み禁止 34 ／ 拒否 27）\n"
           "前の便は形からの推測で57本としていた。実測すると143本だった。\n"
           "データは1件も消していない。隠しているだけ。戻れば次の生成で自動的に表から外れる。\n"
           "戻し方: src/lib/kansei.ts の KANSEI_GATE = false。")
    commit = m._req("POST", "%s/repos/%s/git/commits" % (api, repo), token,
                    {"message": msg, "tree": new_tree["sha"], "parents": [base]})
    m._req("PATCH", "%s/repos/%s/git/refs/heads/%s" % (api, repo, br), token,
           {"sha": commit["sha"], "force": False})
    log.append("★mainに入りました: %s" % commit["sha"][:8])
    return {"ok": True, "log": log, "commit": commit["sha"], "totalYen": 0.0}


if __name__ == "__main__":
    print(json.dumps(run_job({"dryRun": "--dry-run" in sys.argv}),
                     ensure_ascii=False, indent=1))
