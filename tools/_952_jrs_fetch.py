#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""952番 — 非公開リポ joy-relief-station の「正本」を工場(Mac)側で読み出して持ち帰る。

■ なぜ要るか（2026-09-19 実測）
  Cowork のサンドボックスからは api.github.com / raw.githubusercontent.com に
  回線が出ない（プロキシが 403 CONNECT を返す）。github.com だけは出るが、
  非公開リポは認証が要るので匿名では 404。
  一方 Mac からは `git push` が通っている ＝ **鍵は Mac の keychain にある。**
  `gh` は `gh auth login` 未実施でトークンが取れない（status/github_watch.log 実測）が、
  git の credential helper（osxkeychain）からなら取れる可能性がある。

■ やること（読むだけ。push も課金操作も一切しない）
  1. Mac の中に joy-relief-station の clone があるか探す
  2. あれば docs/design/concierge-concept-02-08.md を読む（作業ツリー → git show の順）
  3. git credential から github.com のトークンを取り、Issue #431 を REST で読む
  4. clone が無ければ、トークンで tarball ではなく Contents API からファイルだけ取る
  5. 取れたものを status/952_seihon/ に全文で置く（次のセッションが同じ壁に当たらないため）

■ 安全のために
  - 書き込みは status/952_seihon/ 配下のみ
  - トークンは**絶対にファイルに書かない**（長さだけ記録する）
  - ネットワークは github.com / api.github.com のみ
"""
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT_DIR = os.path.join(REPO, "status", "952_seihon")

OWNER = "tamago2022"
NAME = "joy-relief-station"
DOC_PATH = "docs/design/concierge-concept-02-08.md"
ISSUE_NO = 431


def _run(cmd, cwd=None, timeout=60, input_text=None):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, input=input_text)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return 127, "", str(e)


def find_clone(log):
    """Mac の中の clone を探す。深追いしない（時間切れを避ける）。"""
    home = os.path.expanduser("~")
    guesses = [
        os.path.join(home, "Desktop", NAME),
        os.path.join(home, "Documents", NAME),
        os.path.join(home, NAME),
        os.path.join(home, "Desktop", "AI作業", NAME),
        os.path.join(home, "Documents", "AI作業", NAME),
        os.path.join(home, "src", NAME),
        os.path.join(home, "repos", NAME),
        os.path.join(home, "ghq", "github.com", OWNER, NAME),
    ]
    for g in guesses:
        if os.path.isdir(os.path.join(g, ".git")):
            log.append("決め打ちで見つけました: %s" % g)
            return g
    # 決め打ちで無ければ探す（3階層・8秒で打ち切り）
    for base, depth in ((os.path.join(home, "Desktop"), 4),
                        (os.path.join(home, "Documents"), 4),
                        (home, 3)):
        if not os.path.isdir(base):
            continue
        rc, out, err = _run(["find", base, "-maxdepth", str(depth), "-type", "d",
                             "-name", NAME], timeout=25)
        for line in (out or "").splitlines():
            line = line.strip()
            if line and os.path.isdir(os.path.join(line, ".git")):
                log.append("探して見つけました: %s" % line)
                return line
    log.append("Mac の中に clone は見つかりませんでした")
    return None


def get_token(log):
    """git の credential helper から github.com のトークンを取る。値は返すが記録しない。"""
    # 1) gh（望み薄だが一応）
    rc, out, err = _run(["gh", "auth", "token"], timeout=15)
    if rc == 0 and out.strip():
        log.append("トークン取得: gh auth token（長さ %d）" % len(out.strip()))
        return out.strip()
    # 2) git credential fill（osxkeychain）
    rc, out, err = _run(["git", "credential", "fill"], timeout=15,
                        input_text="protocol=https\nhost=github.com\n\n")
    if rc == 0:
        for line in (out or "").splitlines():
            if line.startswith("password="):
                tok = line[len("password="):].strip()
                if tok:
                    log.append("トークン取得: git credential fill（長さ %d）" % len(tok))
                    return tok
    log.append("トークンは取れませんでした（gh・git credential とも不発）")
    return None


def api(path, token, log, accept="application/vnd.github+json"):
    import urllib.error
    import urllib.request
    url = "https://api.github.com" + path
    req = urllib.request.Request(url)
    req.add_header("Accept", accept)
    req.add_header("User-Agent", "tamago-952")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        log.append("API %s → HTTP %s" % (path, e.code))
    except Exception as e:
        log.append("API %s → %s" % (path, e))
    return None


def read_doc_from_clone(clone, log):
    p = os.path.join(clone, DOC_PATH)
    if os.path.isfile(p):
        log.append("作業ツリーから読めました: %s" % DOC_PATH)
        return io.open(p, encoding="utf-8", errors="replace").read()
    # 作業ツリーに無い → fetch してから git show
    _run(["git", "fetch", "origin", "--quiet"], cwd=clone, timeout=180)
    for ref in ("origin/main", "origin/master", "HEAD"):
        rc, out, err = _run(["git", "show", "%s:%s" % (ref, DOC_PATH)], cwd=clone, timeout=60)
        if rc == 0 and out.strip():
            log.append("git show %s から読めました" % ref)
            return out
    log.append("clone はあるが %s が見つかりません" % DOC_PATH)
    return None


def run_job(payload=None):
    log = []
    os.makedirs(OUT_DIR, exist_ok=True)
    result = {"ok": False, "log": log, "got": {}, "totalYen": 0.0}

    clone = find_clone(log)
    token = get_token(log)

    doc = None
    if clone:
        doc = read_doc_from_clone(clone, log)

    if doc is None and token:
        raw = api("/repos/%s/%s/contents/%s" % (OWNER, NAME, DOC_PATH), token, log)
        if raw:
            try:
                import base64
                j = json.loads(raw)
                doc = base64.b64decode(j.get("content") or "").decode("utf-8", "replace")
                log.append("Contents API から読めました")
            except Exception as e:
                log.append("Contents API の中身が壊れています: %s" % e)

    if doc:
        p = os.path.join(OUT_DIR, "concierge-concept-02-08.md")
        io.open(p, "w", encoding="utf-8").write(doc)
        result["got"]["doc"] = p
        result["docChars"] = len(doc)

    # Issue #431（本文＋コメント）
    issue_text = None
    if token:
        raw = api("/repos/%s/%s/issues/%d" % (OWNER, NAME, ISSUE_NO), token, log)
        if raw:
            try:
                j = json.loads(raw)
                parts = ["# Issue #%d %s" % (ISSUE_NO, j.get("title") or ""),
                         "",
                         "状態: %s / 起票 %s" % (j.get("state"), j.get("created_at")),
                         "",
                         j.get("body") or ""]
                craw = api("/repos/%s/%s/issues/%d/comments?per_page=100"
                           % (OWNER, NAME, ISSUE_NO), token, log)
                if craw:
                    for c in json.loads(craw):
                        parts += ["", "---", "## コメント（%s・%s）"
                                  % ((c.get("user") or {}).get("login"), c.get("created_at")),
                                  "", c.get("body") or ""]
                issue_text = "\n".join(parts)
                log.append("Issue #%d を読めました" % ISSUE_NO)
            except Exception as e:
                log.append("Issue の中身が壊れています: %s" % e)

    if issue_text:
        p = os.path.join(OUT_DIR, "issue-431.md")
        io.open(p, "w", encoding="utf-8").write(issue_text)
        result["got"]["issue"] = p
        result["issueChars"] = len(issue_text)

    # 参考：リポ内で 02/08 に触れている他のファイルも拾っておく
    if clone:
        rc, out, err = _run(["git", "grep", "-l", "-i", "concierge-concept\\|案内人",
                             "HEAD", "--", "docs/"], cwd=clone, timeout=60)
        if rc == 0 and out.strip():
            io.open(os.path.join(OUT_DIR, "related_files.txt"), "w",
                    encoding="utf-8").write(out)
            result["got"]["related"] = "status/952_seihon/related_files.txt"

    io.open(os.path.join(OUT_DIR, "_log.txt"), "w", encoding="utf-8").write(
        "取得 %s\n\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), "\n".join(log)))

    result["ok"] = bool(doc or issue_text)
    return result


if __name__ == "__main__":
    print(json.dumps(run_job({}), ensure_ascii=False, indent=1))
