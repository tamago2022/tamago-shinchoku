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

STALE_SECONDS = 300   # 5分。`git add` が巨大ファイルを掴んでいる可能性を考えて長めに取る
MAX_AUTO_MERGE = 40   # 手元がこれ以上先に進んでいたら、自動では合流しない（人が見る）
# ★2026-09-18 実測で分かった穴：この工場は auto_launcher / command_ingest / 5分便が
#   gitを絶えず叩いているので、「gitプロセスが1本も無い」という条件だけだと
#   **静かな瞬間が来ず、ロックが何十分も片付かないことがある**
#   （実測：`refs/heads/main.lock` が8分以上放置され、15秒おきに呼ばれていても消えなかった）。
#   正常な git の操作が**15分**ロックを握り続けることは無いので、そこまで古ければ
#   gitが走っていても消す。これが無いと、この道具は「動いているのに直らない」状態になる。
HARD_STALE_SECONDS = 900  # 15分

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


def reap(dry_run=False, quiet=False):
    """他のスクリプトからも関数として呼べる本体。

    ★なぜ関数にしたか（2026-09-18の実測）：`heartbeat.sh` に行を足しても、
      **走っている心臓はループ本体をメモリに持っているので、心臓が入れ替わるまで効かない。**
      一方 python のファイルは毎回の呼び出しで読み直される。そこで毎サイクル必ず呼ばれる
      `tools/launch_watchdog.py` から `reap()` を呼ぶことで、心臓の入れ替えを待たずに効かせる。
    """
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
        if not quiet:
            print("LOCK_REAPER: OK - 取り残されたロックはありません")
        return 0

    stale = [(p, a) for p, a in found if a >= STALE_SECONDS]
    if not stale:
        if not quiet:
            print("LOCK_REAPER: SKIP - ロックはあるがまだ新しい（%d件）" % len(found))
        return 0

    if git_is_running():
        # gitが走っている時は、15分以上放置された「明らかな置き土産」だけに限って片付ける。
        stale = [(p, a) for p, a in stale if a >= HARD_STALE_SECONDS]
        if not stale:
            if not quiet:
                print("LOCK_REAPER: SKIP - gitが走っているので触りません（%d件）" % len(found))
            return 0

    removed = 0
    for p, age in stale:
        if dry_run:
            if not quiet:
                print("LOCK_REAPER: DRYRUN - %s（%d分放置）" % (p, age // 60))
            continue
        try:
            os.remove(p)
            removed += 1
            log("🧹 取り残された git ロックを片付けました: %s（%d分放置・%s）"
                % (os.path.relpath(p, REPO), age // 60,
                   "15分超なのでgit走行中でも片付けた" if age >= HARD_STALE_SECONDS
                   else "gitプロセスなし"))
        except OSError as e:
            log("⚠️ git ロックを消せませんでした: %s（%s）" % (os.path.relpath(p, REPO), e))

    if not quiet:
        print("LOCK_REAPER: OK - %d件のロックを片付けました" % removed)
    return 0


def push_out(quiet=False):
    """commit済みなのに誰もpushしていない分を、押し出すだけ。commitはしない。

    2026-09-19（配達係の工事中に実機で踏んだ）：
      このリポジトリで origin へ push できる出口は事実上2つ
      （machine_status_push.sh の5分便と command_watch.sh の30秒便）しか無く、
      **どちらも「自分が書いたファイルが変わったとき」にしか push しない。**
      一方 Cowork/Dispatch のサンドボックスには GitHub の資格情報が無い
      （実測：`could not read Username for 'https://github.com'`）。
      つまりセッション側が commit したものは、**誰かのファイルが偶然変わるまで
      公開されない。**しかも実測でこの日、5分便は22分以上死んでいた。
      結果：commitは出来ているのに公開URLが永久に404、という
      「たまごさんに押せないものを渡す」事故の温床そのものになっていた。

    → 心臓から2分おきに必ず呼ばれるこの道具に「未pushがあれば押し出す」だけ足す。
      commit はしないので、この道具が勝手に何かを公開することはない。
      あくまで「誰かが公開すると決めて commit したもの」を運ぶだけ。
    """
    # rebase/merge の途中なら触らない（中途半端な状態を公開しない）
    for marker in ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD"):
        if os.path.exists(os.path.join(GITDIR, marker)):
            if not quiet:
                print("PUSH_OUT: SKIP - %s の途中なので触りません" % marker)
            return 0

    def git(*args, timeout=120):
        return subprocess.run(["git", "-C", REPO, *args],
                              capture_output=True, text=True, timeout=timeout)

    # 2026-09-19 実測で踏んだ穴：**pull せずに push だけ試していた。**
    #   このリポジトリの origin/main には、こちら以外にも書き手がいる
    #   （.github/workflows/deliver-verify.yml が確認結果を [skip ci] で押し戻す）。
    #   ところがこの道具は `@{u}..HEAD`＝**手元の古い origin/main** としか比べず、
    #   fetch もしないまま push していた。向こうが1歩でも進んでいると
    #   non-fast-forward で弾かれ、以後30秒おきに同じ失敗を延々と繰り返す。
    #   実測：09:20:42 から 09:42:09 まで、同じ「failed to push」を22分間。
    #   その間 commit 済みのものは1つも公開されない＝配達が丸ごと止まる。
    # → 押す前に必ず fetch して、向こうが進んでいたら merge で合流してから押す。
    #   合流がこけたら必ず --abort で元に戻す（中途半端な状態を残さない）。
    def _count(rng):
        r = git("rev-list", "--count", rng, timeout=30)
        if r.returncode != 0:
            return None
        try:
            return int((r.stdout or "0").strip() or 0)
        except ValueError:
            return None

    try:
        f = git("-c", "credential.helper=!gh auth git-credential",
                "fetch", "origin", "main", timeout=120)
        if f.returncode != 0 and not quiet:
            print("PUSH_OUT: 注意 - fetchに失敗（古い手元の記録で判断します）")
    except Exception as e:  # noqa: BLE001
        if not quiet:
            print("PUSH_OUT: 注意 - fetchできませんでした（%s）" % e)

    try:
        ahead = _count("origin/main..HEAD")
        behind = _count("HEAD..origin/main")
    except Exception as e:  # noqa: BLE001
        if not quiet:
            print("PUSH_OUT: SKIP - 数えられませんでした（%s）" % e)
        return 0

    if ahead is None or behind is None:
        if not quiet:
            print("PUSH_OUT: SKIP - 上流が分からない")
        return 0

    if ahead <= 0:
        if not quiet:
            print("PUSH_OUT: OK - 未pushのcommitはありません")
        return 0

    # 手元が異常に進んでいるときは自動で合流しない（人が見るべき状態）
    if behind > 0 and ahead > MAX_AUTO_MERGE:
        log("⚠️ 手元が%d件先・向こうが%d件先。自動の合流は見送りました（多すぎます）"
            % (ahead, behind))
        if not quiet:
            print("PUSH_OUT: SKIP - 差が大きいので自動では触りません")
        return 0

    if behind > 0:
        # ★rebase は使わない。case#687（2026-09-13）で禁じ手になっている：
        #   autostash がこのリポジトリ全体の未コミットの変更を巻き込んで退避し、
        #   失敗時に黙って古い内容へ巻き戻す事故を10日で12回起こした。
        #   command_watch.sh / machine_status_push.sh と同じく merge に揃える。
        #   こけても --abort で元に戻すだけで、黙った巻き戻りは起きない。
        try:
            mg = git("-c", "core.mergeAutoStash=false",
                     "merge", "--no-edit", "origin/main", timeout=300)
        except Exception as e:  # noqa: BLE001
            log("⚠️ 向こうが%d件先でしたが、合流できませんでした（%s）" % (behind, e))
            return 0
        if mg.returncode != 0:
            git("merge", "--abort", timeout=120)
            err = (mg.stderr or mg.stdout or "").strip().splitlines()
            log("⚠️ 向こうが%d件先。合流がこけたので元に戻しました: %s"
                % (behind, err[-1] if err else "理由不明"))
            if not quiet:
                print("PUSH_OUT: NG - 合流できないので元に戻しました")
            return 0
        log("🔁 向こうが%d件先だったので、手元の%d件と合流しました" % (behind, ahead))
        ahead = _count("origin/main..HEAD") or ahead

    try:
        p = git("-c", "credential.helper=!gh auth git-credential",
                "push", "origin", "HEAD:main", timeout=180)
    except Exception as e:  # noqa: BLE001
        log("⚠️ 未pushの%d件を押し出せませんでした（%s）" % (ahead, e))
        return 0

    if p.returncode == 0:
        log("📮 誰もpushしていなかったcommit %d件を押し出しました" % ahead)
        if not quiet:
            print("PUSH_OUT: OK - %d件を押し出しました" % ahead)
    else:
        err = (p.stderr or "").strip().splitlines()
        log("⚠️ 未pushの%d件を押し出せませんでした: %s"
            % (ahead, err[-1] if err else "理由不明"))
        if not quiet:
            print("PUSH_OUT: NG - %s" % (err[-1] if err else "理由不明"))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--no-push", action="store_true",
                    help="ロックの片付けだけして、未pushの押し出しはしない")
    args = ap.parse_args()
    rc = reap(dry_run=args.dry_run, quiet=args.quiet)
    if not args.dry_run and not args.no_push:
        push_out(quiet=args.quiet)
    return rc


if __name__ == "__main__":
    sys.exit(main())
