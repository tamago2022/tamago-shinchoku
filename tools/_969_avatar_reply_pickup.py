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
import time
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
# 2026-09-20 追加：見張る先を増やせるようにした。
#   joy-relief-station は非公開なので、外のAI（Grok等）はIssueを読めない（実測404）。
#   同じ問いを公開リポジトリ tamago2022/ai-kaigi にも立てたので、両方を見る。
#   ★新しい常駐は増やしていない。この1本が両方を見るだけ。
TARGETS_JSON = os.path.join(WORK, "targets.json")
SEEN_JSON = os.path.join(WORK, "seen.json")
LOG = os.path.join(WORK, "pickup.log")
PAGE = os.path.join(REPO, "share", "check", "961-talking-avatar-jirei.html")
MARK = "<!-- 969:返事ここまで -->"


def _log(msg):
    try:
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


def _post(url, token, payload, timeout=25):
    """GitHubへ1回だけ書く（起こすため）。失敗は握り潰さず呼び元へ返す。"""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", "Bearer %s" % token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "tamago-969-pickup")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.getcode()


# ★2026-09-23（1026番）ここが今回の本丸。
#
#   81回走って0件だった原因は「拾い口が壊れていた」ではなく、
#   **誰も起こしていなかった**（status/969_返信0件の原因.md の実測）。
#   977番でも同じ事故が起きている＝2回目＝個人の落ち度ではなく仕組みの不在。
#
#   だから「今回の的に引き金を1回打つ」のでは直らない（＝穴を塞ぐだけ）。
#   **見張りと引き金を同じ1本にする。**この先どんな先を足しても、
#   見張り始めた瞬間に必ず起こしている。起こし方の書いていない先は見張らない。
#
#   起こし方は実測で確かめたものだけ（作法の出どころは tools/nageru.py と同じ）:
#     jules … `jules` ラベルを貼る（公式ドキュメント：jules.google/docs/running-tasks/）
#     codex … `@codex` とコメントする（本文に書いても起きない・#450で実測）
WAKE_HOW = {
    "jules": ("labels", ["jules"]),
    "codex": ("comment", "@codex 上のお題をお願いします。"),
}
WOKE_JSON = os.path.join(WORK, "woke.json")


def _ensure_woken(slug, number, wakes, token):
    """まだ起こしていない先を起こす。**1回だけ。**催促はしない（回数を増やさない）。

    戻り値: (起こし済みか, 止まっている理由)
    """
    woke = _load(WOKE_JSON, {})
    key = "%s#%s" % (slug, number)
    done = dict(woke.get(key) or {})
    todo = [w for w in (wakes or []) if w in WAKE_HOW and not done.get(w)]
    unknown = [w for w in (wakes or []) if w not in WAKE_HOW]
    if unknown:
        _log("%s：知らない起こし方 %s（実測で確かめたのは %s）"
             % (key, "・".join(unknown), "・".join(sorted(WAKE_HOW))))
    for w in todo:
        how, arg = WAKE_HOW[w]
        try:
            if how == "labels":
                code = _post("%s/repos/%s/issues/%s/labels" % (API, slug, number),
                             token, {"labels": arg})
            else:
                code = _post("%s/repos/%s/issues/%s/comments" % (API, slug, number),
                             token, {"body": arg})
            done[w] = {"at": time.strftime("%F %T"), "code": code}
            _log("%s を起こしました（%s・HTTP %s）" % (key, w, code))
        except Exception as e:                      # 握り潰さない。理由を残して赤にする
            done[w] = {"error": str(e)[:200], "at": time.strftime("%F %T")}
            _log("%s を起こせませんでした（%s）: %s" % (key, w, e))
    if todo or unknown:
        woke[key] = done
        try:
            io.open(WOKE_JSON, "w", encoding="utf-8").write(
                json.dumps(woke, ensure_ascii=False, indent=1))
        except Exception as e:
            _log("起こした記録を残せませんでした: %s" % e)
    ok = [w for w in (wakes or []) if (done.get(w) or {}).get("code")]
    if ok:
        return True, ""
    if not wakes:
        return False, "起こす引き金が書いてありません（targets.json の wake が空）"
    errs = "／".join("%s:%s" % (w, (done.get(w) or {}).get("error", "未実行"))
                    for w in wakes)
    return False, "起こせていません（%s）" % errs


def _targets():
    """見張る先の一覧。**起こす引き金があり、実際に起こせた先だけを返す。**

    戻り値: (見張る先[(slug,number)], 止めた先[(key, 理由)])
    """
    conf = {}
    for t in (_load(TARGETS_JSON, []) or []):
        try:
            conf[(t["repo"], int(t["number"]))] = t
        except Exception:
            continue
    pairs = []
    issue = _load(ISSUE_JSON, {})
    if issue.get("number"):
        pairs.append((issue.get("repo") or REPO_SLUG, int(issue["number"])))
    for pair in conf:
        if pair not in pairs:
            pairs.append(pair)

    token = github_watch.gh_token()
    watch, stopped = [], []
    for slug, number in pairs:
        key = "%s#%s" % (slug, number)
        wakes = (conf.get((slug, number)) or {}).get("wake") or []
        if isinstance(wakes, str):
            wakes = [wakes]
        if not wakes:
            # ★見張らない。見張ると「走った回数」だけが永久に増えて赤が消えない。
            stopped.append((key, (conf.get((slug, number)) or {}).get("why")
                            or "起こす引き金が書いてありません"))
            continue
        if not token:
            stopped.append((key, "GitHubのトークンが取れませんでした（gh auth login が要る）"))
            continue
        ok, why = _ensure_woken(slug, number, wakes, token)
        if ok:
            watch.append((slug, number))
        else:
            stopped.append((key, why))
    return watch, stopped


def main():
    targets, stopped = _targets()

    # ★止めた先は、黙って捨てない。state に書いて鍵台帳（hantei）の赤に出す。
    #   「走った回数だけ増えて中身が0」を作らないため、見張れる先が1つも無い日は
    #   **seen.json を書き換えない**（書き換えると mtime が進み、台帳が1回走ったと数える）。
    if stopped:
        _log("見張りません：" + "／".join("%s（%s）" % (k, w) for k, w in stopped))
    if not targets:
        why = "／".join("%s：%s" % (k, w) for k, w in stopped) or "見張る先がまだありません"
        try:
            io.open(os.path.join(WORK, "blocked.json"), "w", encoding="utf-8").write(
                json.dumps({"blocked": why, "at": time.strftime("%F %T")},
                           ensure_ascii=False, indent=1))
        except Exception:
            pass
        return 0
    try:
        os.remove(os.path.join(WORK, "blocked.json"))
    except OSError:
        pass

    token = github_watch.gh_token()
    if not token:
        _log("トークンが取れませんでした")
        return 0

    state = _load(SEEN_JSON, {})
    seen = set(state.get("ids") or [])
    etags = dict(state.get("etags") or {})
    # 旧い形（etagが1本だけ）からの引き継ぎ
    if state.get("etag") and targets:
        etags.setdefault("%s#%s" % targets[0], state["etag"])

    fresh = []
    for slug, number in targets:
        key = "%s#%s" % (slug, number)
        url = "%s/repos/%s/issues/%s/comments?per_page=100" % (API, slug, number)
        try:
            code, data, new_etag = _get(url, token, etags.get(key))
        except Exception as e:
            _log("%s を読めませんでした: %s" % (key, e))
            continue
        etags[key] = new_etag
        if code == 304 or not data:
            continue
        for c in data:
            if c.get("id") in seen:
                continue
            if "<!-- tamago-factory -->" in (c.get("body") or ""):
                continue
            c["_from"] = key
            fresh.append(c)

    def _save():
        io.open(SEEN_JSON, "w", encoding="utf-8").write(json.dumps(
            {"ids": sorted(seen), "etags": etags}, ensure_ascii=False, indent=1))

    if not fresh:
        _save()
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
    _save()
    _log("%d件をページに足しました（%s）" % (
        len(fresh), ", ".join(sorted({c["_from"] for c in fresh}))))
    return len(fresh)


if __name__ == "__main__":
    os.makedirs(WORK, exist_ok=True)
    n = main()
    print(json.dumps({"added": n}, ensure_ascii=False))
