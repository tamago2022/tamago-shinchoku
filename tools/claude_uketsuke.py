#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Claude Code 受付係（claude_uketsuke）— 2026-10-17 たまごさん指示。

たまごさん：「Gensparkとの間で水汲み（仲介）は本当はしたくない」
実害：joy-relief-station #1015（【Claude Codeに頼む】月の特集）が置かれても、
  github_watch.py は「tamago2022 の『〜に頼む】』は受信箱に畳むだけ」で発車待ちに積まず、
  たまごさんが口で伝えるまで誰も着手しなかった。tamago-shinchoku はそもそも見ていなかった。

やること（5分に1回・心臓 top_status.py の相乗り）：
  ① joy-relief-station と tamago-shinchoku の open Issue のうち、
     タイトルに【Claude Codeに頼む】を含む新しいものを拾う
  ② 工場の発車待ち（status/queue.json）へ積む → auto_launcher が着火（人は押さない）
  ③ Issue に「受け付けました」をコメント（先頭に <!-- tamago-factory -->＝Gensparkへの返事はIssueで）
  ④ Dispatch へ1行（status/dispatch_outbox.jsonl, type=claude_uketsuke）
  ⑤ 30分に1回、Genspark AI Drive（gsk drive tree）の新しいファイルを拾って Dispatch へ1行
     （中身の取り込みはしない＝名前と置き場だけ知らせる。無料の一覧取得だけ使う）

作るもの：status/claude_uketsuke_state.json（覚え書き）／status/claude_uketsuke.log（300行で刈る）
         status/public/claude_uketsuke.json（進捗表用）。一時ファイルは作らない。
台帳：tools/jidou_daicho.json の "claude_uketsuke.py"
逆テスト：python3 tools/claude_uketsuke.py --self-test
手で今すぐ回す：python3 tools/claude_uketsuke.py --force
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
STATE = os.path.join(ST, "claude_uketsuke_state.json")
LOG = os.path.join(ST, "claude_uketsuke.log")
PUBLIC = os.path.join(ST, "public", "claude_uketsuke.json")
OUTBOX = os.path.join(ST, "dispatch_outbox.jsonl")
LOCK = os.path.join(ST, ".claude_uketsuke.lock")

REPOS = ["tamago2022/joy-relief-station", "tamago2022/tamago-shinchoku"]
TITLE_MARK = "【Claude Codeに頼む】"
GATE_SEC = 300            # 5分おき
DRIVE_GATE_SEC = 1800     # AI Drive は30分おき（gsk は1回が重い）
MAX_PER_RUN = 3           # 流し込み事故の防止
BOOTSTRAP_SEC = 48 * 3600 # 初回だけ48時間遡る
FACTORY_MARK = "<!-- tamago-factory -->"
PATHS = [os.path.expanduser(p) for p in ("~/.local/bin", "~/bin", "~/.npm-global/bin")] + \
        ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
ENV = dict(os.environ, PATH=":".join(PATHS + [os.environ.get("PATH", "")]))


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%F %T"), msg))
        lines = open(LOG, encoding="utf-8").read().splitlines()
        if len(lines) > 400:
            open(LOG, "w", encoding="utf-8").write("\n".join(lines[-300:]) + "\n")
    except Exception:
        pass


def load_state():
    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        st = {}
    st.setdefault("seen", [])
    st.setdefault("next", 0)
    st.setdefault("driveNext", 0)
    st.setdefault("driveSeen", None)   # None＝初回（今ある分は「新しい」と数えない）
    st.setdefault("since", time.time() - BOOTSTRAP_SEC)
    st.setdefault("stats", {"runs": 0, "picked": 0, "driveNew": 0, "errors": 0})
    return st


def save_state(st):
    st["seen"] = list(dict.fromkeys(st["seen"]))[-2000:]
    st["updatedAt"] = time.strftime("%F %T")
    tmp = "%s.%d.tmp" % (STATE, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def outbox(title, message, urls=None):
    row = {"ts": time.strftime("%F %T"), "n": "uketsuke-%d" % int(time.time() * 1000),
           "type": "claude_uketsuke", "from": "claude_uketsuke", "title": title,
           "message": message, "urls": urls or []}
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run(cmd, timeout=60):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=ENV, cwd=REPO)
    return p.returncode, p.stdout, p.stderr


def is_target(title):
    return TITLE_MARK in (title or "")


def _iso(s):
    try:
        import calendar
        return calendar.timegm(time.strptime((s or "")[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return 0


def instruction(repo, it):
    body = (it.get("body") or "")[:6000]
    return "\n".join([
        "【タスク】GitHub %s #%s「%s」を実行する（%s 経由の自動受付）" % (repo, it["number"], it["title"], TITLE_MARK),
        "【出どころ】%s ／ 投稿者: %s" % (it.get("url"), (it.get("author") or {}).get("login")),
        "【最初にやる】`gh issue view %s -R %s --comments` で全文とコメントを読む（下の抜粋は先頭だけ）。" % (it["number"], repo),
        "【守る】Issueの「触らない」「事実注意」に従う。本文は勝手にリライトしない。お金が出る操作・削除・権限変更・秘密情報の持ち出しはしない。",
        "　たまごさん（2026-10-17）「とりあえず公開して見せて。そこから調整」＝Issueが本番公開を求めていれば、関所（koutai_kanmon・unify_look・prebuild）を通したうえで公開してよい。",
        "【返事】終わったら同じIssueにコメント（本文の先頭に %s）：コミット番号＋本番URL＋未確認。Gensparkへの返事はIssueコメントで。たまごさんを仲介に使わない。" % FACTORY_MARK,
        "【報告】Dispatchへ3行（完了/問題/判断待ち）。",
        "", "---- Issue本文（先頭） ----", body,
    ])


def check_issues(st, budget):
    picked = 0
    seen = set(st["seen"])
    for repo in REPOS:
        if picked >= budget:
            break
        try:
            # 検索API（--search）は今日の実測で60秒超のタイムアウトが続いたので使わない。
            # 新しい順30件の軽い一覧だけ取り、本文は当たった号だけ取りに行く。
            rc, out, err = run(["gh", "issue", "list", "-R", repo, "--state", "open", "--limit", "30",
                                "--json", "number,title,url,createdAt,author"], timeout=90)
        except Exception as e:
            st["stats"]["errors"] += 1
            log("%s 一覧が取れない: %r" % (repo, e))
            continue
        if rc != 0:
            st["stats"]["errors"] += 1
            log("%s 一覧が取れない rc=%s %s" % (repo, rc, (err or "")[:200]))
            continue
        try:
            items = json.loads(out or "[]")
        except Exception:
            items = []
        for it in sorted(items, key=lambda x: x.get("createdAt") or ""):
            if picked >= budget:
                break
            key = "%s#%s" % (repo, it.get("number"))
            if key in seen or not is_target(it.get("title")):
                continue
            if _iso(it.get("createdAt")) < st["since"]:
                seen.add(key)   # 基準線より前の古い号は掘り返さない
                continue
            try:
                rc2, o2, _ = run(["gh", "issue", "view", str(it["number"]), "-R", repo, "--json", "body"], timeout=90)
                it["body"] = json.loads(o2).get("body") if rc2 == 0 else ""
            except Exception:
                it["body"] = ""   # 本文が取れなくても積む（着手側が gh issue view で読み直す）
            sys.path.insert(0, HERE)
            try:
                import command_ingest
                status, msg = command_ingest.queue_add(
                    instruction(repo, it), priority=1,
                    label="GH%s %s" % (it["number"], it["title"].replace(TITLE_MARK, "")[:50]),
                    origin="factory")
            except Exception as e:
                st["stats"]["errors"] += 1
                log("%s 発車待ちに積めない: %r" % (key, e))
                continue
            seen.add(key)
            picked += 1
            short = it["title"].replace(TITLE_MARK, "")[:60]
            try:
                run(["gh", "issue", "comment", str(it["number"]), "-R", repo, "--body",
                     "%s\n受け付けました。工場の発車待ちに積み、順に着手します（%s）。終わったらここにコミット番号と本番URLを書きます。"
                     % (FACTORY_MARK, msg)], timeout=40)
            except Exception as e:
                log("%s 受付コメントを書けない: %r" % (key, e))
            outbox("【受付】%s #%s %s" % (repo.split("/")[1], it["number"], short),
                   "【Claude Codeに頼む】を自動受付→発車待ちへ（%s）" % msg, [it.get("url")])
            log("%s「%s」→ 積んだ（%s）" % (key, short, msg))
    st["seen"] = list(seen)
    return picked


def _drive_files(js):
    """gsk drive tree の出力（JSONが1つ＋ゴミ）からファイルだけ取り出す。"""
    try:
        d, _ = json.JSONDecoder().raw_decode(js.strip())
        return {e["entry_id"]: e.get("name") for e in (d.get("data") or {}).get("entries", [])
                if e.get("kind") == "file"}
    except Exception:
        return None


def check_drive(st):
    try:
        rc, out, err = run(["gsk", "--no-input", "drive", "tree", "--path", "/"], timeout=150)
    except Exception as e:
        log("AI Drive が読めない: %r" % (e,))
        return 0
    files = _drive_files(out or "")
    if files is None:
        log("AI Drive の返事が読めない rc=%s %s" % (rc, (out or err or "")[:160]))
        return 0
    if st["driveSeen"] is None:
        st["driveSeen"] = sorted(files)
        log("AI Drive 初回：%d件を基準にした（通知しない）" % len(files))
        return 0
    old = set(st["driveSeen"])
    new = [(i, n) for i, n in files.items() if i not in old]
    if new:
        names = "、".join(n for _, n in new[:8])
        outbox("【AI Drive 新着】%d件" % len(new),
               "Genspark AI Drive に新しいファイル：%s（gsk drive で取れます）" % names, [])
        log("AI Drive 新着 %d件: %s" % (len(new), names))
    st["driveSeen"] = sorted(old | set(files))[-5000:]
    return len(new)


def write_public(st, picked, dnew):
    try:
        json.dump({"at": time.strftime("%F %T"), "kankaku": "5分", "repos": REPOS, "mark": TITLE_MARK,
                   "kondo": picked, "drive_kondo": dnew, "stats": st["stats"]},
                  open(PUBLIC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass


def main(force=False):
    import fcntl
    lf = open(LOCK, "a+")
    try:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        return 0
    st = load_state()
    now = time.time()
    if not force and now < st["next"]:
        return 0
    st["next"] = now + GATE_SEC
    save_state(st)               # 先に次の時刻を書く（重い回の二重起動を防ぐ）
    st["stats"]["runs"] += 1
    started = now - 10
    picked = check_issues(st, MAX_PER_RUN)
    st["stats"]["picked"] += picked
    if picked < MAX_PER_RUN:
        st["since"] = started
    dnew = 0
    if force or now >= st["driveNext"]:
        st["driveNext"] = now + DRIVE_GATE_SEC
        dnew = check_drive(st)
        st["stats"]["driveNew"] += dnew
    save_state(st)
    write_public(st, picked, dnew)
    return 0


def self_test():
    assert is_target("【Claude Codeに頼む】月の特集")
    assert not is_target("【Julesに頼む】間違い探し")
    assert not is_target("Claude Codeに頼む（括弧なし）")
    j = '{"data":{"entries":[{"entry_id":"a","kind":"file","name":"x.html"},{"entry_id":"b","kind":"directory","name":"d"}]}}\nAlarm'
    assert _drive_files(j) == {"a": "x.html"}
    assert _drive_files("fetch failed") is None
    t = instruction("tamago2022/x", {"number": 1, "title": TITLE_MARK + "t", "url": "u", "body": "b", "author": {"login": "a"}})
    assert FACTORY_MARK in t and "gh issue view 1" in t
    print("SELF-TEST OK")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(main(force="--force" in sys.argv))
