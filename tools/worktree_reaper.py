#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""使い終わった作業場（git worktree）を片づける（2026-09-05）。

たまごさんの言葉：
  「ChatGPTの横のタスクに、Claude Codeのタスクみたいなのがフォルダで来てるんだけど、
   **もうこれどうにかしたいんだけど。すっきりさせたい。** なんでここに来るの。来る意味って何なの。」

正体：`auto_launcher.py` が1件ごとに `joy-relief-station/.worktrees/<名前>` を切っている。
仕事が終わっても**片づけていなかった**ので51個溜まり、ChatGPT(Codex)がそれを
1つずつ「プロジェクト」として拾って一覧に並べていた。たまごさんの画面が汚れた。

ここで安全に片づける。**成果を消すのが最悪**なので、次を全部満たすものだけ消す：
  1. 台帳(queue.json)で running になっていない
  2. 作業ディレクトリに未コミットの変更が無い（git status が空）
  3. そのブランチのコミットが origin/main に取り込まれている（＝成果は本流にある）
  4. 最後に触ってから2時間以上経っている

1つでも欠けたら**触らない。**判断がつかないものは残す。
"""
import io
import json
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TARGET = "/Users/mac/Desktop/joy-relief-station"
WT_DIR = os.path.join(TARGET, ".worktrees")
QUEUE = os.path.join(REPO, "status", "queue.json")
LOG = os.path.join(REPO, "status", "worktree_reaper.log")
STAMP = os.path.join(REPO, "status", ".worktree_reaper_at")
INTERVAL = 1800          # 30分に1回でよい
MIN_AGE_SEC = 2 * 3600   # 触ってから2時間は残す


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def git(args, cwd=TARGET, timeout=60):
    try:
        return subprocess.run(["git", "-C", cwd] + args, capture_output=True,
                              text=True, timeout=timeout)
    except Exception:
        return None


def running_paths():
    """いま走っている仕事が使っている作業場は絶対に触らない。"""
    try:
        q = json.load(io.open(QUEUE, encoding="utf-8"))
    except Exception:
        return set()
    out = set()
    for it in q.get("items") or []:
        if it.get("status") == "running":
            for k in ("worktree", "wt", "cwd"):
                v = it.get(k)
                if v:
                    out.add(os.path.basename(str(v)))
            # 名前の付け方（q<番号>-<日付>）からも推測して守る
            n = it.get("n")
            if n is not None:
                out.add("q%s" % n)
    return out


def main():
    try:
        if time.time() - os.path.getmtime(STAMP) < INTERVAL:
            return 0
    except Exception:
        pass
    io.open(STAMP, "w").write(str(int(time.time())))

    if not os.path.isdir(WT_DIR):
        return 0
    # 重いときは何もしない（掃除でMacを重くしない）
    try:
        if os.getloadavg()[0] > 15:
            return 0
    except Exception:
        pass

    guard = running_paths()
    removed, kept = [], []
    for name in sorted(os.listdir(WT_DIR)):
        path = os.path.join(WT_DIR, name)
        if not os.path.isdir(path):
            continue
        # ① 走行中のものは触らない（名前の前方一致でも守る）
        if name in guard or any(name.startswith(g + "-") for g in guard):
            kept.append((name, "走行中"))
            continue
        # ④ 新しいものは触らない
        try:
            if time.time() - os.path.getmtime(path) < MIN_AGE_SEC:
                kept.append((name, "まだ新しい"))
                continue
        except Exception:
            continue
        # ② 未コミットの変更があるものは触らない
        st = git(["status", "--porcelain"], cwd=path)
        if st is None or st.returncode != 0:
            kept.append((name, "状態が読めない"))
            continue
        if (st.stdout or "").strip():
            kept.append((name, "未保存の変更あり"))
            continue
        # ③ 成果が本流(origin/main)に入っているか
        head = git(["rev-parse", "HEAD"], cwd=path)
        if head is None or head.returncode != 0:
            kept.append((name, "HEADが読めない"))
            continue
        sha = (head.stdout or "").strip()
        merged = git(["merge-base", "--is-ancestor", sha, "origin/main"])
        if merged is None or merged.returncode != 0:
            kept.append((name, "まだ本流に入っていない"))
            continue
        r = git(["worktree", "remove", "--force", path])
        if r is not None and r.returncode == 0:
            removed.append(name)
        else:
            kept.append((name, "removeに失敗"))

    if removed:
        git(["worktree", "prune"])
        log("🧹 片づけた作業場 %d件: %s" % (len(removed), ", ".join(removed[:10])))
    if kept:
        log("残した %d件（理由つき）: %s" % (
            len(kept), ", ".join("%s(%s)" % (n, why) for n, why in kept[:8])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
