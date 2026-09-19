#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""969番【拾い口】トーキングアバターの調査依頼Issueに来た返事を、
そのまま（要約せず）961番のページへ並べる。

たまごさん（2026-09-20・原文）:
  「返事が来たら、要約せずそのまま 961-talking-avatar-jirei.html に追記する。
    6時間待ってもいい。待っている間、このセッションは待たない。」

■ 何をするか
  1. status/969/issue.json に書いてある Issue番号のコメントを GitHub から読む
  2. まだ載せていないコメントだけを、**本文を1文字も削らずに**
     share/check/961-talking-avatar-jirei.html の「外部AIからの返事」欄へ足す
  3. 載せたコメントのidを status/969/seen.json に記録する（二度載せない）

■ 無害であること
  - 読むのは api.github.com の joy-relief-station の Issue だけ。GETのみ。
  - 書くのは share/check/961-talking-avatar-jirei.html と status/969/ だけ。
  - **お金は1円もかからない**（GitHub REST APIは無料）。
  - 返事が0件なら、条件付きGET1本で終わる（ETagが効くのでレート消費も0）。
  - 工場自身の書き込み（本文に <!-- tamago-factory --> を含むもの）は拾わない
    ＝自分の書き込みを自分で拾う無限増殖を止める。

■ 呼ばれ方
  tools/machine_status_push.sh（5分おきに launchd から必ず走る便）に相乗り。
  新しい常駐は増やさない＝この工場の決まり。
"""
import html
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import github_watch  # noqa: E402  ★トークンの取り方はここに1本化されている

REPO_SLUG = "tamago2022/joy-relief-station"
API = "https://api.github.com"
WORK = os.path.join(REPO, "status", "969")
ISSUE_JSON = os.path.join(WORK, "issue.json")
SEEN_JSON = os.path.join(WORK, "seen.json")
LOG = os.path.join(WORK, "pickup.log")
PAGE = os.path.join(REPO, "share", "check", "961-talking-avatar-jirei.html")
MARK = "<!-- 969:返事ここまで -->"


def _log(msg):
    try:
        import time
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass


def _load(path, default):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default


def _get(url, token, etag=None, timeout=25):
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer %s" % token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "tamago-969-pickup")
    if etag:
        req.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), json.loads(r.read().decode("utf-8", "ignore") or "null"), \
                r.headers.get("ETag")
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return 304, None, etag
        raise


def _linkify(text):
    """本文はそのまま。URLだけ押せるようにする（憲法8条・リンクを必ず付ける）。"""
    out = []
    for part in re.split(r"(https?://[^\s<>\"'）」】]+)", text):
        if part.startswith("http"):
            u = html.escape(part, quote=True)
            out.append('<a href="%s" target="_blank" rel="noopener">%s</a>' % (u, u))
        else:
            out.append(html.escape(part))
    return "".join(out).replace("\n", "<br>")


def _block(c):
    who = (c.get("user") or {}).get("login") or "?"
    at = (c.get("created_at") or "").replace("T", " ").replace("Z", " UTC")
    return (
        '\n<div class="panel reply" data-cid="%s">\n'
        '  <h2>%s からの返事<small>%s ／ 本文は1文字も直していません（原文のまま）</small></h2>\n'
        '  <div class="raw">%s</div>\n'
        '</div>\n' % (c.get("id"), html.escape(who), html.escape(at),
                      _linkify(c.get("body") or ""))
    )


def main():
    issue = _load(ISSUE_JSON, {})
    number = issue.get("number")
    if not number:
        return 0  # まだIssueが立っていない＝何もしない（無害）

    token = github_watch.gh_token()
    if not token:
        _log("トークンが取れませんでした")
        return 0

    state = _load(SEEN_JSON, {})
    seen = set(state.get("ids") or [])
    etag = state.get("etag")

    url = "%s/repos/%s/issues/%s/comments?per_page=100" % (API, REPO_SLUG, number)
    try:
        code, data, new_etag = _get(url, token, etag)
    except Exception as e:
        _log("読めませんでした: %s" % (e,))
        return 0
    if code == 304 or not data:
        return 0

    fresh = [c for c in data
             if c.get("id") not in seen
             and "<!-- tamago-factory -->" not in (c.get("body") or "")]
    if not fresh:
        state["etag"] = new_etag
        state["ids"] = sorted(seen)
        io.open(SEEN_JSON, "w", encoding="utf-8").write(
            json.dumps(state, ensure_ascii=False, indent=1))
        return 0

    try:
        page = io.open(PAGE, encoding="utf-8").read()
    except Exception as e:
        _log("ページが読めません: %s" % (e,))
        return 0
    if MARK not in page:
        _log("目印がありません: %s" % MARK)
        return 0

    add = "".join(_block(c) for c in fresh)
    page = page.replace(MARK, add + MARK)
    # 1件でも来たら「返事待ちです」の札を外す
    page = re.sub(r'\n\s*<div class="machi" id="machi969">.*?</div>\n', "\n", page,
                  flags=re.S)
    io.open(PAGE, "w", encoding="utf-8").write(page)

    seen.update(c.get("id") for c in fresh)
    io.open(SEEN_JSON, "w", encoding="utf-8").write(json.dumps(
        {"ids": sorted(seen), "etag": new_etag}, ensure_ascii=False, indent=1))
    _log("%d件をページに足しました（Issue #%s）" % (len(fresh), number))
    return len(fresh)


if __name__ == "__main__":
    os.makedirs(WORK, exist_ok=True)
    n = main()
    print(json.dumps({"added": n}, ensure_ascii=False))
