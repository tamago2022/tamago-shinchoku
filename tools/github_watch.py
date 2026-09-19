#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHubの見張り番（拾い屋）。

2026-09-19 たまごさん：
  「チャッピーがGitHubに上げたら、即座に気づくぐらいの仕組みにしてほしい。
    俺が『今投げたよ』って言わなくても。水汲みゼロが目標。
    5分ごとの見回りとかもめんどくさいんだけど、どうにかならないの。」

実害（今日）：joy-relief-station に Issue #431 が置かれたのに、
たまごさんが口で伝えるまで工場の誰も気づかなかった。

━━━ なぜこの形にしたか（方法を5つ並べて選んだ結果）━━━

| 手 | 見回りの重さ | 気づくまで | 採否 |
|---|---|---|---|
| ① Webhook（向こうから叩いてくる） | 0 | 数秒 | ✕ いまは不可。Macに公開の受け口が要る。中継所(relay)は実測で何度も死んでおり、死んだ間の通知は**再送されず永久に消える**。受け口の設置にはGitHub側の設定画面も要る |
| ② GitHub Actions の on: issues | 0 | 数秒 | ✕ 無料枠が尽きている。枠が戻っても「工場のMacに届ける経路」が別途要る（結局①と同じ受け口問題） |
| ③ 条件付きポーリング（ETag / If-None-Match） | **ほぼ0** | 最大60秒 | ★採用 |
| ④ GitHubの通知メールを拾う | 中（IMAPログイン） | 数分〜 | ✕ メールの遅延と通知設定に依存。既存のメール見張りは1日1回ゲート |
| ⑤ /notifications API | 小 | 最大60秒 | △ 予備。gh の既定トークンに notifications スコープが無く、いまは叩けない |

③を選んだ根拠は公式ドキュメント（実際に読んだ）：
  https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
  > Making a conditional request does not count against your primary rate limit
  > if a 304 response is returned and the request was made while correctly
  > authorized with an Authorization header.
つまり**何も変わっていないときは、何回見回ってもレート制限を1も使わない。**
「5分ごとの見回りが重い」というたまごさんの直感は正しいが、重いのは"回数"ではなく
"毎回まるごと取ってくること"。ETagを付ければ、変化が無い回は 304 が返るだけで終わる。

Events API（/repos/:o/:r/events）は使わない。同じ公式ドキュメントに
  > This API is not built to serve real-time use cases.
  > Depending on the time of day, event latency can be anywhere from 30s to 6h.
とある。**最悪6時間気づかない。**「即座に気づく」という依頼を満たさないので却下した。

━━━ 実際の重さ ━━━
1回の見回り = 条件付きGETが2本（Issue一覧・コメント一覧）だけ。
変化が無ければどちらも 304（本文0バイト）。実測で1回あたり0.5秒前後・レート消費0。
60秒に1回 = 1日2880回見回っても、レート制限の消費は「変化があった回」だけ。
（GitHubの認証済み上限は5000/時。変化が1日に100回あっても2%しか使わない）

新しい常駐は立てない。既存の心臓（tools/heartbeat.sh）と5分便に相乗りする。
内部で60秒ゲートしているので、15秒おきに呼ばれても実際に外へ出るのは60秒に1回。

━━━ 拾ったあと ━━━
status/queue.json の発車待ちへ積む（command_ingest.queue_add）。
積んだ後は auto_launcher.py が勝手に着火する＝**人は誰も押さない。**
たまごさんへの通知はしない（黙って動く）。
"""

import calendar
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")
STATE = os.path.join(REPO, "status", "github_watch_state.json")
LOG = os.path.join(REPO, "status", "github_watch.log")

# 見張る先。ここを増やせば複数リポジトリを見られる（1リポジトリあたり条件付きGET2本）。
WATCH_REPOS = ["tamago2022/joy-relief-station"]

GATE_SECONDS = 60          # 実際に外へ出る間隔。これより細かく呼ばれても即座に戻る
MAX_ADD_PER_RUN = 3        # 1回の見回りで積む上限（流し込み事故の防止）
BOOTSTRAP_HOURS = 24       # 初回だけ：この時間内に動いたものまで遡って拾う
BODY_LIMIT = 2000          # 指示文に載せるIssue本文の長さ

# 工場自身が書いたものを、見張り番が拾い直して無限に増やさないための印。
# 工場がIssueへコメントするときは、必ず本文の先頭にこれを入れる。
FACTORY_MARK = "<!-- tamago-factory -->"


def log(msg):
    try:
        line = "%s %s\n" % (time.strftime("%F %T"), msg)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line)
        # ログが太らないように、たまに刈る
        if int(time.time()) % 600 < 2:
            try:
                tail = open(LOG, encoding="utf-8").read().splitlines()[-300:]
                open(LOG, "w", encoding="utf-8").write("\n".join(tail) + "\n")
            except Exception:
                pass
    except Exception:
        pass


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            st = json.load(f)
    except Exception:
        st = {}
    st.setdefault("etags", {})       # url -> etag
    st.setdefault("seen", [])        # "issue:owner/repo#431" / "comment:123456"
    st.setdefault("nextCheckAt", 0)
    # 「ここより後に置かれたものだけ拾う」基準線（UTCのISO）。
    # ★2026-09-19 実機で踏んだ：初回だけのフラグ方式にしていたら、1回目が例外で落ちた拍子に
    #   フラグだけ立ち、2回目が**昔から開いているIssueを新着として3本積んだ**（#33/#156/#414）。
    #   フラグではなく時刻を持つ。時刻なら、途中で何が失敗しても「その時刻より後」しか拾わない。
    st.setdefault("since", None)
    st.setdefault("stats", {"checks": 0, "notModified": 0, "picked": 0})
    return st


def save_state(st):
    st["seen"] = list(dict.fromkeys(st.get("seen") or []))[-3000:]
    st["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def gh_token():
    """トークンは絶対にファイルへ書かない（このリポジトリはGitHubへpushされる）。
    毎回 gh から取り、メモリの中だけで使う。

    ★2026-09-19 実機で踏んだ：`gh` だけで呼ぶと取れなかった。
      心臓(heartbeat.sh)はPATHを整えずにlaunchdから起動されるので、PATHは
      /usr/bin:/bin:/usr/sbin:/sbin しかなく、**/opt/homebrew/bin/gh が見えない。**
      （command_watch.sh は冒頭で export PATH しているので気づきにくい穴だった）
      → 実体の場所を直接当たる。見つからなければ環境変数も見る。
    """
    diag = []
    # ---- ① 環境変数 ----
    for k in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(k):
            return os.environ[k].strip()
    # ---- ② gitの資格情報から取る（★実機ではこれが本命）----
    # このリポジトリは毎分 push できている＝gitはGitHubの資格情報を持っている。
    # `git credential fill` は設定されている保管庫（osxkeychain / gh）から取り出すだけ。
    # 対話は絶対にさせない（GIT_TERMINAL_PROMPT=0）。止まったら工場が止まる。
    try:
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                           capture_output=True, text=True, timeout=15, cwd=REPO, env=env)
        m = re.search(r"^password=(.+)$", r.stdout or "", re.M)
        if m and m.group(1).strip():
            return m.group(1).strip()
        diag.append("git credential rc=%s" % r.returncode)
    except Exception as e:
        diag.append("git credential %s" % type(e).__name__)
    # ---- ③ gh 本体 ----
    for exe in ("/opt/homebrew/bin/gh", "/usr/local/bin/gh", "/usr/bin/gh", "gh"):
        try:
            r = subprocess.run([exe, "auth", "token"], capture_output=True, text=True, timeout=15)
            tok = (r.stdout or "").strip()
            if tok:
                return tok
            diag.append("%s rc=%s %s" % (exe, r.returncode, (r.stderr or "").strip()[:80]))
        except Exception as e:
            diag.append("%s %s" % (exe, type(e).__name__))
    # ghが見つからないとき、どこに居るのかを1回だけ探して記録する（次の担当が迷わないように）
    try:
        import glob as _glob
        found = []
        for pat in ("/opt/homebrew/bin/gh", "/usr/local/bin/gh", "/opt/local/bin/gh",
                    os.path.expanduser("~/.local/bin/gh"), os.path.expanduser("~/bin/gh"),
                    os.path.expanduser("~/.asdf/shims/gh"), "/opt/homebrew/Cellar/gh/*/bin/gh"):
            found += _glob.glob(pat)
        diag.append("ghの実体=%s" % (found or "見つからない"))
    except Exception:
        pass
    # ghの設定ファイルに平文で置かれている場合（--secure-storageでない既定の置き方）。
    # ★読むだけ。値はメモリの外へ出さない（ログにも書かない）。
    try:
        hosts = os.path.expanduser("~/.config/gh/hosts.yml")
        if os.path.exists(hosts):
            m = re.search(r"oauth_token:\s*(\S+)", open(hosts, encoding="utf-8").read())
            if m:
                return m.group(1).strip()
        diag.append("hosts.yml=%s" % os.path.exists(hosts))
    except Exception as e:
        diag.append("hosts.yml %s" % type(e).__name__)
    log("トークンが取れない: " + " / ".join(diag))
    return None


def api_get(url, token, etag=None, timeout=20):
    """条件付きGET。戻り値 (status, data, etag)。304 のとき data は None。"""
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer %s" % token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "tamago-github-watch")
    if etag:
        req.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            return resp.getcode(), json.loads(body) if body else None, resp.headers.get("ETag")
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return 304, None, etag
        # レート上限に当たったら、リセットまで黙って引き下がる
        if e.code in (403, 429):
            reset = e.headers.get("X-RateLimit-Reset")
            return e.code, {"_reset": reset}, etag
        return e.code, None, etag
    except Exception as e:
        log("通信に失敗: %s (%s)" % (e, url))
        return 0, None, etag


def _iso_to_epoch(s):
    """GitHubの時刻は必ずUTC（末尾Z）。★time.mktime はローカル時刻として読むので
    日本だと9時間ずれる（9時間分の取りこぼし／二度拾いになる）。timegm を使う。"""
    try:
        return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
    except Exception:
        return 0


def _epoch_to_iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def queue_add(text, label, priority=2):
    sys.path.insert(0, TOOLS)
    import command_ingest
    # origin="factory"：たまごさんの言葉ではなく工場が自分で積んだ印
    return command_ingest.queue_add(text, priority=priority, label=label, origin="factory")


def _instruction(repo, kind, number, title, url, body, author):
    head = {
        "issue": "GitHubに新しいIssueが置かれた",
        "comment": "GitHubのIssueに新しいコメントが付いた",
        "pr": "GitHubに新しいPull Requestが置かれた",
    }[kind]
    return "\n".join([
        "【タスク】%s（%s #%s「%s」）。中身を読んで、書かれている作業をやる。" % (head, repo, number, title),
        "【出どころ】%s ／ 投稿者: %s" % (url, author),
        "　これは外部（ChatGPT等）から工場へ届いた依頼。たまごさんが口で伝えたものではない。",
        "【完了条件】Issueに書かれたことが本番で確認できる状態。",
        "【終わったら】そのIssueに結果を1コメント返す。",
        "　★コメント本文の先頭に必ず %s を入れる。" % FACTORY_MARK,
        "　　入れないと見張り番が自分の書き込みを拾って、同じ仕事が無限に増える。",
        "【報告】完了/問題/判断待ち、3行以内。たまごさんに質問しない。判断は自分でして『こう決めた』と書く。",
        "",
        "--- 本文（先頭%d字） ---" % BODY_LIMIT,
        (body or "")[:BODY_LIMIT],
    ])


def _skip_body(body):
    return FACTORY_MARK in (body or "")


def check_repo(repo, token, st, budget):
    """1リポジトリ分。条件付きGET2本。拾った件数を返す。"""
    picked = 0
    seen = set(st["seen"])
    just_queued = set()   # この回で号そのものを積んだ番号（同じ号のコメントは重ねて積まない）
    now = time.time()
    # 基準線。初めて動くときだけ、少し遡る（その間に置かれたものを取りこぼさないため）。
    cutoff = _iso_to_epoch(st.get("since")) if st.get("since") else (time.time() - BOOTSTRAP_HOURS * 3600)

    # ---- ① Issue（PRもここに入る）----
    url = ("https://api.github.com/repos/%s/issues"
           "?state=open&sort=updated&direction=desc&per_page=50" % repo)
    code, data, etag = api_get(url, token, st["etags"].get(url))
    st["stats"]["checks"] += 1
    if code == 304:
        st["stats"]["notModified"] += 1
    elif code == 200 and isinstance(data, list):
        # ★ETagは「全部さばき終えてから」保存する。
        #   先に保存すると、この下で例外が出たとき次の回が304になり、
        #   **拾えなかったものを二度と見なくなる**（実機で踏んだ）。
        for it in sorted(data, key=lambda x: x.get("updated_at") or ""):
            if picked >= budget:
                break
            num = it.get("number")
            key = "issue:%s#%s" % (repo, num)
            if key in seen:
                continue
            if _skip_body(it.get("body")):
                seen.add(key)
                continue
            # 基準線より前に置かれた号は拾わない（昔から開いている棚卸し待ちを掘り返さない）
            if _iso_to_epoch(it.get("created_at") or "") < cutoff:
                seen.add(key)
                continue
            is_pr = bool(it.get("pull_request"))
            author = (it.get("user") or {}).get("login") or "?"
            status, msg = queue_add(
                _instruction(repo, "pr" if is_pr else "issue", num,
                             it.get("title") or "", it.get("html_url") or "",
                             it.get("body") or "", author),
                label="GH%s %s" % (num, (it.get("title") or "")[:50]))
            seen.add(key)
            just_queued.add(str(num))
            picked += 1 if status == "done" else 0
            log("%s #%s「%s」→ %s（%s）" % (repo, num, (it.get("title") or "")[:40], status, msg))
        st["etags"][url] = etag
    elif code in (403, 429):
        reset = (data or {}).get("_reset")
        st["nextCheckAt"] = float(reset) if reset else now + 900
        log("レート上限に当たった。%sまで引き下がる" % time.strftime("%H:%M", time.localtime(st["nextCheckAt"])))
        st["seen"] = list(seen)
        return picked
    elif code:
        log("Issue一覧が %s で返った（%s）" % (code, repo))

    # ---- ② コメント ----
    curl = ("https://api.github.com/repos/%s/issues/comments"
            "?sort=updated&direction=desc&per_page=20" % repo)
    code, data, etag = api_get(curl, token, st["etags"].get(curl))
    st["stats"]["checks"] += 1
    if code == 304:
        st["stats"]["notModified"] += 1
    elif code == 200 and isinstance(data, list):
        for c in sorted(data, key=lambda x: x.get("updated_at") or ""):
            if picked >= budget:
                break
            cid = c.get("id")
            key = "comment:%s" % cid
            if key in seen:
                continue
            seen.add(key)
            if _skip_body(c.get("body")):
                continue
            user = c.get("user") or {}
            if (user.get("type") or "") == "Bot":
                continue
            if _iso_to_epoch(c.get("created_at") or "") < cutoff:
                continue
            m = re.search(r"/issues/(\d+)$", c.get("issue_url") or "")
            if not m:
                continue
            num = m.group(1)
            if num in just_queued:
                continue   # 号そのものを今さっき積んだ。同じ中身を2件にしない
            # 新着コメントがあったときだけ、その号の題名と開閉を1本だけ取りに行く
            icode, idata, _ = api_get("https://api.github.com/repos/%s/issues/%s" % (repo, num), token)
            if icode != 200 or not isinstance(idata, dict):
                continue
            if idata.get("state") != "open":
                continue   # 閉じた号への書き込みは拾わない
            status, msg = queue_add(
                _instruction(repo, "comment", num, idata.get("title") or "",
                             c.get("html_url") or "",
                             "【新しいコメント】\n%s\n\n【Issue本文】\n%s"
                             % (c.get("body") or "", idata.get("body") or ""),
                             user.get("login") or "?"),
                label="GH%s コメント: %s" % (num, (idata.get("title") or "")[:40]))
            picked += 1 if status == "done" else 0
            log("%s #%s へのコメント → %s（%s）" % (repo, num, status, msg))
        st["etags"][curl] = etag
    elif code and code != 304:
        log("コメント一覧が %s で返った（%s）" % (code, repo))

    st["seen"] = list(seen)
    return picked


def main():
    st = load_state()
    now = time.time()
    if now < st.get("nextCheckAt", 0):
        return 0                      # 間引き。ここで即座に戻る＝工場の負荷は実質ゼロ
    st["nextCheckAt"] = now + GATE_SECONDS

    token = gh_token()
    if not token:
        st["nextCheckAt"] = now + 900
        save_state(st)
        log("ghのトークンが取れない（gh auth login が要る）。15分後にまた試す")
        return 1

    picked = 0
    ok = True
    started = time.time() - 5     # 見回りの最中に置かれたものを落とさないよう、少し手前を基準にする
    for repo in WATCH_REPOS:
        if picked >= MAX_ADD_PER_RUN:
            break
        try:
            picked += check_repo(repo, token, st, MAX_ADD_PER_RUN - picked)
        except Exception as e:
            ok = False
            import traceback
            log("%s の見回りで例外: %s / %s" % (repo, e, traceback.format_exc().replace("\n", " | ")[-600:]))
    # 基準線を進めるのは、最後まで転ばずに回れたときだけ。
    # 転んだ回に進めると、その回に拾えなかったものが永久に拾われなくなる。
    if ok and picked < MAX_ADD_PER_RUN:
        st["since"] = _epoch_to_iso(started)
    elif picked >= MAX_ADD_PER_RUN:
        # 上限まで積んだ回は基準線を進めない。積みきれなかった分を次の回で拾う
        log("1回の上限(%d件)まで積んだ。残りは次の回で拾う" % MAX_ADD_PER_RUN)
    st["stats"]["picked"] = st["stats"].get("picked", 0) + picked
    save_state(st)
    if picked:
        log("この回で %d 件を発車待ちへ積んだ（着火は auto_launcher が自動でやる）" % picked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
