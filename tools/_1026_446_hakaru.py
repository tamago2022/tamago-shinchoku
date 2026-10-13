#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1026番：#446 を「起こした回数」と「返ってきた回数」を数えて台帳に書く。

★投げっぱなしにしない。起こしたなら out を、返ってきたなら in を、
  **実物のコメントを見て**書く（skill：嘘のログを書かない）。
"""
import io, json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import github_watch, ai_daicho  # noqa: E402

SLUG = "tamago2022/joy-relief-station"
NUM = 446
THREAD = "gh:%s#%d" % (SLUG, NUM)
WOKE = os.path.join(REPO, "status", "969", "woke.json")


def api(path, token):
    r = urllib.request.Request("https://api.github.com" + path)
    r.add_header("Authorization", "Bearer %s" % token)
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("User-Agent", "tamago-1026")
    with urllib.request.urlopen(r, timeout=30) as f:
        return json.loads(f.read().decode("utf-8", "ignore"))


def main():
    token = github_watch.gh_token()
    if not token:
        print("GitHubのトークンが取れない（gh auth login が要る）")
        return 1
    # ---- 起こした分（out）を台帳へ。1回だけ。
    woke = json.loads(io.open(WOKE, encoding="utf-8").read()) if os.path.exists(WOKE) else {}
    already = set()
    for row in ai_daicho.read_all():
        if row.get("dir") == "out" and row.get("thread") == THREAD:
            already.add(row.get("ai"))
    for ai, rec in (woke.get("%s#%d" % (SLUG, NUM)) or {}).items():
        ref = "https://github.com/%s/issues/%d" % (SLUG, NUM)
        if ai_daicho.ai_key(ai) in already:
            continue                      # ★二度数えない（起こしたのは1回）
        ok = bool(rec.get("code"))
        ai_daicho.append("out", ai, thread=THREAD,
                         topic="#446 を起こした（%s）" % ("jules ラベル" if ai == "jules"
                                                  else "@codex コメント"),
                         ref=ref, ok=ok, err=None if ok else rec.get("error"),
                         extra={"http": rec.get("code"), "at": rec.get("at"),
                                "by": "1026番・起こしは1回だけ"})
    # ---- 返り（in）を実物から数える
    issue = api("/repos/%s/issues/%d" % (SLUG, NUM), token)
    labels = [l["name"] for l in issue.get("labels") or []]
    comments = api("/repos/%s/issues/%d/comments?per_page=100" % (SLUG, NUM), token)
    mine, theirs = 0, []
    for c in comments:
        body = c.get("body") or ""
        who = (c.get("user") or {}).get("login") or ""
        if "<!-- tamago-factory -->" in body or body.strip().startswith("@codex"):
            mine += 1
            continue
        if who == "tamago2022":
            mine += 1
            continue
        theirs.append((c.get("created_at"), who, body[:80].replace("\n", " "),
                       c.get("html_url")))
    print("■ #446 ラベル: %s" % ("・".join(labels) or "（無し）"))
    print("■ 起こした回数: %d（jules ラベル／@codex コメント・実測HTTP）"
          % len(woke.get("%s#%d" % (SLUG, NUM)) or {}))
    print("■ コメント総数 %d ／ こちらが書いた %d ／ 外部AIが書いた %d"
          % (len(comments), mine, len(theirs)))
    for t in theirs:
        print("   ← %s %s :: %s" % (t[0], t[1], t[2]))
        if ai_daicho.already_logged_in(THREAD, t[3]):
            continue                      # ★同じ返事を二度数えない
        ai = ai_daicho.who_to_ai(t[1])
        ai_daicho.append("in", ai or t[1], thread=THREAD, ref=t[3], who=t[1],
                         topic="#446 への返事")
    if not theirs:
        print("   （まだ返りは0件。起こしたのは %s）"
              % (list((woke.get('%s#%d' % (SLUG, NUM)) or {}).values()) or "未"))
    ai_daicho.publish()
    return 0


if __name__ == "__main__":
    sys.exit(main())
