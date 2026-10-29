#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工場（tamago-shinchoku）の変更が GitHub の main に毎日上がっているかの見張り（2026-10-29・たまごさん指示）

なぜ要るか（実測 2026-10-29）：
  自動で commit・push する係（tools/machine_status_push.sh の hakobu）はあったが、
  ①工場の作業場が 10-22 から作業の枝（fix-1987-push）に乗ったままで、係はその枝に commit し続けた。
  ②係の push は `git push origin main`（＝手元の main。10-21 のまま）なので、何も上がらなかった。
  ③係の pull は衝突（台帳 tools/jidou_daicho.json・確認ページ）で毎回やめて元に戻していた（黙って）。
  ④README.md・CLAUDE.md・AGENTS.md は係の git add の対象外で、書き換えても commit されなかった。
  → GitHub の main は 10-28 から止まり、x_memo・db_grant_kanmon などが 1 週間上がらなかった。

何をするか（心臓 top_status から。中で 1 時間に 1 回に間引く）：
  1. 作業場が main 以外の枝にいたら：その枝が origin/main と手元の main を両方含むなら main をそこへ進めて main に戻す
     （中身は1文字も変わらない）。含まないなら触らずに Dispatch へ1行。
  2. 係の対象外の「工場の決まりの文書」（README.md・CLAUDE.md・AGENTS.md・.githooks・.github）に
     commit されていない変更が 1 時間以上あれば commit する（push は係がする）。
  3. 上がっていない commit が 3 時間以上たまっていたら：origin/main を取り込めるか確かめ（git merge-tree・作業場は触らない）、
     ぶつかるファイルの名前を Dispatch へ1行（12時間に1回まで）。ぶつからないのに上がっていなければそれも1行。
  結果：status/public/kojo_push_mihari.json（進捗表から読む）。
使い方：
  python3 tools/kojo_push_mihari.py --tick     心臓から（1時間に1回）
  python3 tools/kojo_push_mihari.py --now      今すぐ
  python3 tools/kojo_push_mihari.py --self-test
安全：push はしない（係 hakobu の仕事）。merge・rebase・reset はしない。消すものは無い。一時ファイルを作らない。課金0。
台帳：tools/jidou_daicho.json の "kojo_push_mihari.py"
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUT = os.path.join(ST, "public", "kojo_push_mihari.json")
STAMP = os.path.join(ST, ".kojo_push_mihari_at")
TSUUCHI = os.path.join(ST, ".kojo_push_mihari_tsuuchi")
LOCK = os.path.join(ST, ".machine_status_push.lock")
JST = timezone(timedelta(hours=9))
KIMARI = ["README.md", "CLAUDE.md", "AGENTS.md", ".githooks", ".github"]
TAMARI_H = 3
TSUUCHI_GAP = 12 * 3600


def g(*a, check=False, timeout=90):
    p = subprocess.run(["git", "-C", REPO] + list(a), capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError("git %s: %s" % (a[0], p.stderr.strip()[:300]))
    return p


def out(*a):
    return g(*a).stdout.strip()


def is_anc(a, b):
    return g("merge-base", "--is-ancestor", a, b).returncode == 0


def kakari_ugoiteru():
    try:
        pid = int(open(LOCK).read().split()[0])
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def hantei_eda(branch, main_in, om_in):
    """枝の判定（純粋関数・逆テスト用）。返り値：'ok'／'modosu'／'tsuuchi'"""
    if branch == "main":
        return "ok"
    if branch and main_in and om_in:
        return "modosu"
    return "tsuuchi"


def dispatch(title, msg, doc):
    try:
        last = os.path.getmtime(TSUUCHI)
        if time.time() - last < TSUUCHI_GAP:
            doc["kiroku"].append("通知は12時間に1回まで（今回は控えた）")
            return
    except OSError:
        pass
    line = {"ts": datetime.now(JST).isoformat(timespec="seconds"), "n": "kojo-push-" + datetime.now(JST).strftime("%m%d%H"),
            "type": "kojo_push", "title": title, "message": msg + "。詳しくは status/public/kojo_push_mihari.json"}
    with open(os.path.join(ST, "dispatch_outbox.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    open(TSUUCHI, "w").close()
    doc["kiroku"].append("Dispatchへ1行：" + title)


def mimawari():
    doc = {"at": datetime.now(JST).isoformat(timespec="seconds"), "label": "工場の変更が GitHub の main に上がっているか", "kiroku": []}
    if kakari_ugoiteru():
        doc["kiroku"].append("自動pushの係が動いている最中なので、次の回に見る")
        return save(doc, None)
    g("fetch", "-q", "origin", "main", timeout=90)
    branch = out("branch", "--show-current")
    doc["eda"] = branch or "(枝なし)"
    # 1. 枝
    h = hantei_eda(branch, is_anc("main", "HEAD"), is_anc("origin/main", "HEAD"))
    if h == "modosu":
        if g("branch", "-f", "main", "HEAD").returncode == 0 and g("checkout", "-q", "main").returncode == 0:
            doc["kiroku"].append("作業場が「%s」に乗っていたので main をそこまで進めて main に戻した（中身は同じ）" % branch)
            branch = "main"
        else:
            doc["kiroku"].append("main に戻せなかった")
    elif h == "tsuuchi":
        dispatch("工場の作業場が main 以外（%s）にいる" % (branch or "枝なし"),
                 "自動pushが main に届かない状態。手元の main・GitHub の main を含んでいないので自動では戻していない", doc)
    # 2. 決まりの文書
    if branch == "main":
        henko = [l[3:] for l in out("status", "--porcelain", "--", *KIMARI).splitlines() if l[:2] in (" M", "M ", "MM")]
        furui = [f for f in henko if os.path.exists(os.path.join(REPO, f)) and time.time() - os.path.getmtime(os.path.join(REPO, f)) > 3600]
        if furui:
            g("add", "--", *furui)
            r = g("-c", "user.name=kojo-push-mihari", "-c", "user.email=kojo@local", "commit", "-q", "-m",
                  "工場の決まりの文書を記録（%s）" % "・".join(furui[:5]), "--", *furui)
            doc["kiroku"].append(("記録した：" if r.returncode == 0 else "記録できなかった：") + "・".join(furui))
    # 3. たまり
    mie = out("rev-list", "--count", "origin/main..HEAD")
    doc["agattenai"] = int(mie or 0)
    oldest = out("log", "--reverse", "--format=%ct", "origin/main..HEAD").splitlines()[:1]
    hours = (time.time() - int(oldest[0])) / 3600 if oldest else 0
    doc["furui_jikan"] = round(hours, 1)
    doc["main_saigo"] = out("log", "-1", "--format=%ci", "origin/main")
    if doc["agattenai"] and hours >= TAMARI_H:
        mt = g("merge-tree", "--write-tree", "--name-only", "HEAD", "origin/main")
        if mt.returncode == 0:
            dispatch("工場の変更 %d 件が %d 時間 GitHub に上がっていない" % (doc["agattenai"], hours),
                     "取り込みはぶつからない。自動pushの係（machine_status_push.sh）が止まっていないか見る", doc)
        else:
            lines = mt.stdout.splitlines()
            butsukaru = [l for l in lines[1:] if l and not l.startswith(("Auto-merging", "CONFLICT"))][:8]
            doc["butsukaru"] = butsukaru
            dispatch("工場の変更 %d 件が %d 時間 GitHub に上がっていない（ぶつかり %d）" % (doc["agattenai"], hours, len(butsukaru)),
                     "ぶつかるファイル：" + "・".join(butsukaru[:5]) + "。台帳は両方残す・確認ページは新しい方で解く", doc)
    ok = branch == "main" and not (doc["agattenai"] and hours >= TAMARI_H)
    return save(doc, ok)


def save(doc, ok):
    doc["ok"] = ok
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("KOJO_PUSH_MIHARI: %s 枝=%s 上がっていない=%s（%s時間）%s" % (
        {True: "OK", False: "赤", None: "見送り"}[ok], doc.get("eda"), doc.get("agattenai"), doc.get("furui_jikan"), "／".join(doc["kiroku"])))
    return 0 if ok is not False else 2


def self_test():
    assert hantei_eda("main", False, False) == "ok"
    assert hantei_eda("fix-1987-push", True, True) == "modosu"
    assert hantei_eda("fix-1987-push", True, False) == "tsuuchi"
    assert hantei_eda("fix-1987-push", False, True) == "tsuuchi"
    assert hantei_eda("", True, True) == "tsuuchi"
    print("kojo_push_mihari self-test OK")
    return 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    if "--tick" in argv:
        try:
            if time.time() - os.path.getmtime(STAMP) < 3600:
                return 0
        except OSError:
            pass
        open(STAMP, "w").close()
    return mimawari()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
