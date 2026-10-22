#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全AIへの共有メモ係（zen_ai_kyouyu）— 2026-10-22 たまごさん指示。

たまごさん：「この水汲みを俺がまだやらなきゃいけないのがしんどい」
実害：ごきげんの種（公式LINE）が工場の CLAUDE.md にしか無く、Grokボット（司令塔）が
  「公式LINEのことはGitHubのどこにも書かれていなかった」と言った。
  Grokボットは3時間ごとに GitHub の共有メモを読む。だから工場が受けた指示は、言われなくても全部そこに書く。

共有メモの正本＝joy-relief-station のラベル「店主の指示メモ」の付いた Issue（#1037 の常設ルール・Grokボットが3時間ごとに読む）。
  1企画＝1Issue（題【店主の指示メモ】<企画名>）。無ければ作る。企画名が無いもの・3時間まとめは「全体像」Issueへ。
  設定は status/zen_ai_kyouyu/config.json（repo / label / zentai＝全体像Issueの番号）の1か所だけ。
Grok など GitHub にログインできない読み手向けに、公開の写し status/public/renkei/kyouyu_memo.md も毎回作る。

使い方：
  ① どこからでも（サンドボックスの子でも）：書きたいことを待ち行列に置く（gh は使わない）
       python3 tools/zen_ai_kyouyu.py kaku --kikaku "企画名" --title "件名" --body "中身"            # 全AIへ共有
       python3 tools/zen_ai_kyouyu.py kaku --dispatch --kikaku "企画名" --title "件名" --body "指示の要約"  # Dispatchからの指示
       （--kikaku を省くと「全体像」Issueへ。--body-file でファイルから読める）
  ② Mac の心臓（top_status の相乗り・5分おき）：python3 tools/zen_ai_kyouyu.py --tick
       ・待ち行列を Issue へコメントで書く（先頭 <!-- tamago-factory -->、@メンション無し）
       ・3時間に1回、その間に工場が受けた指示（status/queue.json の新しい項目の題名）を1本にまとめて書く
       ・公開の写しを作り直す
  逆テスト：python3 tools/zen_ai_kyouyu.py --self-test

作るもの：status/zen_ai_kyouyu/{config.json,machi.jsonl,kaita.jsonl,state.json,log}／status/public/renkei/kyouyu_memo.md
         ／Genspark AI Drive /ごきげん補給所_全AI共有メモ.md（写しが変わったときだけ上書き）
台帳：tools/jidou_daicho.json の "zen_ai_kyouyu.py"（kaita.jsonl 500行・log 300行で自分で刈る）
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
D = os.path.join(REPO, "status", "zen_ai_kyouyu")
CONF = os.path.join(D, "config.json")
MACHI = os.path.join(D, "machi.jsonl")
KAITA = os.path.join(D, "kaita.jsonl")
STATE = os.path.join(D, "state.json")
LOG = os.path.join(D, "log")
PUB = os.path.join(REPO, "status", "public", "renkei", "kyouyu_memo.md")
QUEUE = os.path.join(REPO, "status", "queue.json")
MARK = "<!-- tamago-factory -->"
GATE_SEC = 300
DIGEST_SEC = 3 * 3600
DIGEST_MAX = 40
PATHS = [os.path.expanduser(p) for p in ("~/.local/bin", "~/bin", "~/.npm-global/bin")] + \
        ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
ENV = dict(os.environ, PATH=":".join(PATHS + [os.environ.get("PATH", "")]))


def exe(name):
    """心臓の PATH には gh・gsk が無いことがあるので、自分で探して絶対パスで呼ぶ。"""
    import shutil
    return shutil.which(name, path=ENV["PATH"]) or name
DEFAULT_CONF = {"repo": "tamago2022/joy-relief-station", "label": "店主の指示メモ", "zentai": None}
PREFIX = "【店主の指示メモ】"

# 鍵・個人情報を公開Issueに出さない（雑だが確実な伏せ字）
_HIMITSU = [
    (re.compile(r"(gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_\-]{20,}|xox[abpr]-[A-Za-z0-9\-]{10,}|AIza[0-9A-Za-z_\-]{30,})"), "［鍵は伏せた］"),
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "［メールは伏せた］"),
    (re.compile(r"(?i)(password|passwd|パスワード|暗証番号)\s*[:：=]\s*\S+"), r"\1: ［伏せた］"),
    (re.compile(r"@(?=[A-Za-z0-9])"), "＠"),  # @メンションにしない
]


def fusei(s):
    s = s or ""
    for rx, rep in _HIMITSU:
        s = rx.sub(rep, s)
    return s


def log(msg):
    try:
        os.makedirs(D, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%F %T"), msg))
        lines = open(LOG, encoding="utf-8").read().splitlines()
        if len(lines) > 400:
            open(LOG, "w", encoding="utf-8").write("\n".join(lines[-300:]) + "\n")
    except Exception:
        pass


def conf():
    try:
        c = json.load(open(CONF, encoding="utf-8"))
        if c.get("repo") and c.get("label"):
            return c
    except Exception:
        pass
    return dict(DEFAULT_CONF)


def load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".w"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def kaku(title, body, kind="kyouyu", who="Claude Code（工場）", kikaku=""):
    """待ち行列に1件置く。gh を使わないのでサンドボックスの子からでも呼べる。"""
    os.makedirs(D, exist_ok=True)
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "kind": kind, "who": who,
           "kikaku": (kikaku or "").strip()[:60], "title": (title or "").strip()[:120], "body": (body or "").strip()[:6000]}
    with open(MACHI, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def kakidashi(rec):
    head = {"dispatch": "【Claude Code／Dispatchからの指示】", "digest": "【Claude Code／工場が受けた指示（3時間分）】"}.get(
        rec.get("kind"), "【Claude Code／全AIへ共有】")
    return fusei("%s\n%s %s\n\n%s\n\n%s" % (MARK, head, rec.get("title", ""), rec.get("body", ""),
                                            "（%s・%s）" % (rec.get("who", ""), rec.get("at", "")[:16])))


def _gh(args):
    p = subprocess.run([exe("gh")] + args, capture_output=True, text=True, timeout=60, env=ENV)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "")[:200])
    return p.stdout.strip()


def issue_for(c, kikaku, st):
    """企画名→Issue番号。覚え書き→ラベル付きの開いたIssueの題→無ければ作る。企画名なし＝全体像。"""
    if not kikaku:
        if c.get("zentai"):
            return int(c["zentai"])
        kikaku = "全体像（全部共有・正本）"
    memo = st.setdefault("issues", {})
    if memo.get(kikaku):
        return memo[kikaku]
    out = _gh(["issue", "list", "-R", c["repo"], "--label", c["label"], "--state", "open", "--limit", "200",
               "--json", "number,title", "--jq", '.[] | "\\(.number)\\t\\(.title)"'])
    for line in out.splitlines():
        num, _, t = line.partition("\t")
        if t.strip() == PREFIX + kikaku:
            memo[kikaku] = int(num)
            return int(num)
    url = _gh(["issue", "create", "-R", c["repo"], "--label", c["label"], "--title", PREFIX + kikaku,
               "--body", "%s\n%s%s\n\n店主の指示・決まったこと・店主の入力待ち・次の作業を、この企画1本にまとめて書く場所（#1037 の常設ルール）。工場が自動で追記します。" % (MARK, PREFIX, kikaku)])
    num = int(url.rstrip("/").rsplit("/", 1)[-1])
    memo[kikaku] = num
    log("Issueを作った %s #%s" % (kikaku, num))
    return num


def gh_comment(c, body, num):
    return _gh(["api", "repos/%s/issues/%s/comments" % (c["repo"], num), "-f", "body=" + body, "--jq", ".html_url"])


def digest_body(items, since):
    rows = []
    for it in items:
        try:
            t = it.get("queuedAt") or it.get("createdAt") or ""
            if not t or t <= since:
                continue
            title = re.sub(r"\s+", " ", it.get("title") or "").strip()
            if not title:
                continue
            rows.append((t, it.get("n"), title[:90], it.get("origin") or ""))
        except Exception:
            continue
    rows.sort()
    if not rows:
        return None, since
    newest = rows[-1][0]
    shown = rows[-DIGEST_MAX:]
    lines = ["- %s｜%s番｜%s" % (t[5:16].replace("T", " "), n, ti) for t, n, ti, _ in shown]
    more = len(rows) - len(shown)
    body = "工場の受付（status/queue.json）に入った新しい指示 %d件%s。状態は進捗表 https://tamago2022.github.io/tamago-shinchoku/ で見られます。\n\n%s" % (
        len(rows), ("（古い%d件は省略）" % more) if more > 0 else "", "\n".join(lines))
    return body, newest


def kaita_lines(n=60):
    try:
        return [json.loads(l) for l in open(KAITA, encoding="utf-8").read().splitlines() if l.strip()][-n:]
    except Exception:
        return []


def shashi(c):
    """公開の写し（Grok などログインできない読み手用）。新しいものが上。"""
    recs = list(reversed(kaita_lines(60)))
    out = ["# 全AIへの共有メモ（公開の写し・自動生成）", "",
           "正本：https://github.com/%s/issues?q=label%%3A%s （ラベル「%s」の付いたIssue。1企画＝1Issue）" % (c["repo"], c["label"], c["label"]),
           "ルール：@メンションは書かない／勝手に配信しない（配信は工場の仕組みだけ）／店主に伝言をさせない。",
           "更新：%s" % time.strftime("%Y-%m-%d %H:%M"), ""]
    for r in recs:
        out += ["---", "## %s %s %s" % (r.get("at", "")[:16].replace("T", " "), ("［%s］" % r["kikaku"]) if r.get("kikaku") else "", r.get("title", "")),
                r.get("url", ""), "", fusei(r.get("body", "")), ""]
    os.makedirs(os.path.dirname(PUB), exist_ok=True)
    open(PUB, "w", encoding="utf-8").write("\n".join(out) + "\n")


def tick(force=False):
    st = load(STATE, {})
    now = time.time()
    if not force and now - st.get("last", 0) < GATE_SEC:
        return
    st["last"] = now
    c = conf()
    # ① 待ち行列を書く
    try:
        machi = [json.loads(l) for l in open(MACHI, encoding="utf-8").read().splitlines() if l.strip()]
    except Exception:
        machi = []
    # ② 3時間ごとの「工場が受けた指示」まとめ
    if now - st.get("digestAt", 0) >= DIGEST_SEC:
        since = st.get("digestSince") or time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now - DIGEST_SEC))
        try:
            q = load(QUEUE, {})
            items = q.get("items", q) if isinstance(q, dict) else q
            body, newest = digest_body(items, since)
            if body:
                machi.append({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "kind": "digest", "who": "工場の受付（自動）",
                              "title": "", "body": body})
            st["digestSince"] = newest
        except Exception as e:
            log("まとめが作れない: %r" % (e,))
        st["digestAt"] = now
    keep = []
    for rec in machi:
        try:
            url = gh_comment(c, kakidashi(rec), issue_for(c, rec.get("kikaku", ""), st))
            rec["url"] = url
            with open(KAITA, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            log("書いた %s %s" % (rec.get("title", "")[:40], url))
        except Exception as e:
            rec["tries"] = rec.get("tries", 0) + 1
            log("書けない（%d回目）: %r" % (rec["tries"], e))
            if rec["tries"] < 20:
                keep.append(rec)
    with open(MACHI + ".w", "w", encoding="utf-8") as f:
        f.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep))
    os.replace(MACHI + ".w", MACHI)
    ls = kaita_lines(10 ** 6)
    if len(ls) > 600:
        open(KAITA, "w", encoding="utf-8").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ls[-500:]))
    try:
        shashi(c)
        drive_okuru(st)
    except Exception as e:
        log("写しが作れない／AI Driveに置けない: %r" % (e,))
    save(STATE, st)


DRIVE_PATH = "/ごきげん補給所_全AI共有メモ.md"   # Genspark のチャット横断の記憶用（/tamago-inbox/ の外＝納品と取り違えない）


def drive_okuru(st):
    """公開の写しが変わったときだけ Genspark AI Drive に上書き（gsk drive upload・無料・確認なし）。"""
    import hashlib
    txt = open(PUB, encoding="utf-8").read()
    body = re.sub(r"^更新：.*$", "", txt, flags=re.M)
    h = hashlib.sha1(body.encode("utf-8")).hexdigest()
    if st.get("driveHash") == h:
        return
    p = subprocess.run([exe("gsk"), "drive", "upload", "--upload_path", DRIVE_PATH, "--file_content", txt,
                        "--overwrite", "true", "--no-input"], capture_output=True, text=True, timeout=120, env=ENV)
    if p.returncode == 0 and '"status":"ok"' in (p.stdout or "").replace(" ", ""):
        st["driveHash"] = h
        log("AI Drive に置いた %s" % DRIVE_PATH)
    else:
        log("AI Drive に置けない rc=%s %s" % (p.returncode, (p.stderr or p.stdout or "")[:160]))


def self_test():
    assert "＠codex" in fusei("@codex 見て")
    assert "［メールは伏せた］" in fusei("a.b@example.com")
    assert "［鍵は伏せた］" in fusei("ghp_" + "a" * 30)
    body, newest = digest_body([{"n": 1, "title": "古い", "queuedAt": "2026-10-01T00:00:00"},
                                {"n": 2, "title": "新しい  指示", "queuedAt": "2026-10-22T10:00:00"}], "2026-10-21T00:00:00")
    assert "2番｜新しい 指示" in body and "古い" not in body and newest == "2026-10-22T10:00:00"
    assert digest_body([], "x") == (None, "x")
    k = kakidashi({"kind": "dispatch", "title": "t", "body": "b", "who": "w", "at": "2026-10-22T10:00"})
    assert k.startswith(MARK) and "Dispatchからの指示" in k
    print("zen_ai_kyouyu self-test OK")


def main(a):
    if "--self-test" in a:
        return self_test()
    if "--tick" in a:
        return tick(force="--force" in a)
    if a and a[0] == "kaku":
        def opt(k):
            return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else ""
        body = opt("--body")
        if "--body-file" in a:
            body = open(opt("--body-file"), encoding="utf-8").read()
        rec = kaku(opt("--title"), body, "dispatch" if "--dispatch" in a else "kyouyu", kikaku=opt("--kikaku"))
        print("待ち行列に置きました（5分以内に共有メモへ）：%s" % rec["title"])
        return
    print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
