#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
931番の作業中に踏んだ穴：**取り残された .git のロックが工場のgitを丸ごと止める。**

何が起きたか（2026-09-18・実測）：
  サンドボックス側（Cowork）のセッションが `git commit` の途中でタイムアウト打ち切りされ、
  `.git/index.lock`（424,056バイト）と `.git/next-index-20.lock` が取り残された。
  以後このリポジトリの **git add / commit が全て `rc=128` で失敗する**。
  `machine_status_push.sh` の5分便も `auto_launcher` も、gitを使う工程が全部止まる。
  しかもサンドボックスのマウント越しには `unlink` が許されておらず（Operation not permitted）、
  **ロックを作った本人が自分で片付けられない。**

たまごさんの言葉（そのまま）：
> 「食い散らかして『あと片付けておいてください』って言ってるようなもんだよ。」

→ **片付けはMac側（この工場）が自分でやる。**セッションが落ちても最後は必ず戻る形にする。
   `worktree_reaper.py`（使い終わった作業場の片付け）と同じ役割・同じ置き場所。

安全側の条件（両方を満たしたロックだけ消す。1つでも欠けたら触らない）：
  1. **ロックのmtimeが `STALE_SECONDS` 秒より古い**（＝今まさに書いている最中ではない）
  2. **git のプロセスが1本も走っていない**（走っていれば、そのロックは生きている可能性がある）

使い方:
  python3 tools/git_lock_reaper.py            # 条件を満たすロックだけ消す
  python3 tools/git_lock_reaper.py --dry-run  # 消さずに判定だけ
"""
import argparse
import glob
import os
import subprocess
import sys
import time
import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GITDIR = os.path.join(REPO, ".git")
LOG = os.path.join(REPO, "status", "git_rebase_incidents.log")  # 既存のgit事故ログへ相乗り

STALE_SECONDS = 300  # 5分。`git add` が巨大ファイルを掴んでいる可能性を考えて長めに取る

# 消してよいロックだけを名指しする。**ワイルドカードで .git 配下を舐めない。**
LOCK_PATTERNS = (
    os.path.join(GITDIR, "index.lock"),
    os.path.join(GITDIR, "next-index-*.lock"),
    os.path.join(GITDIR, "HEAD.lock"),
    os.path.join(GITDIR, "ORIG_HEAD.lock"),
    os.path.join(GITDIR, "shallow.lock"),
    os.path.join(GITDIR, "config.lock"),
    os.path.join(GITDIR, "packed-refs.lock"),
    os.path.join(GITDIR, "refs", "heads", "*.lock"),
    os.path.join(GITDIR, "refs", "remotes", "*", "*.lock"),
)


def git_is_running():
    """git のプロセスが1本でも居るか。居るなら何も触らない（生きたロックかもしれない）。"""
    try:
        r = subprocess.run(["pgrep", "-x", "git"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return True
    except Exception:
        # 判定できない時は「走っている」側に倒す＝触らない（安全側）
        return True
    return False


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (datetime.datetime.now().strftime("%F %T"), msg))
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    found = []
    now = time.time()
    for pat in LOCK_PATTERNS:
        for p in glob.glob(pat):
            try:
                age = now - os.path.getmtime(p)
            except OSError:
                continue
            found.append((p, age))

    if not found:
        if not args.quiet:
            print("LOCK_REAPER: OK - 取り残されたロックはありません")
        return 0

    stale = [(p, a) for p, a in found if a >= STALE_SECONDS]
    if not stale:
        if not args.quiet:
            print("LOCK_REAPER: SKIP - ロックはあるがまだ新しい（%d件）" % len(found))
        return 0

    if git_is_running():
        if not args.quiet:
            print("LOCK_REAPER: SKIP - gitが走っているので触りません（%d件）" % len(stale))
        return 0

    removed = 0
    for p, age in stale:
        if args.dry_run:
            if not args.quiet:
                print("LOCK_REAPER: DRYRUN - %s（%d分放置）" % (p, age // 60))
            continue
        try:
            os.remove(p)
            removed += 1
            log("🧹 取り残された git ロックを片付けました: %s（%d分放置・gitプロセスなし）"
                % (os.path.relpath(p, REPO), age // 60))
        except OSError as e:
            log("⚠️ git ロックを消せませんでした: %s（%s）" % (os.path.relpath(p, REPO), e))

    if not args.quiet:
        print("LOCK_REAPER: OK - %d件のロックを片付けました" % removed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
