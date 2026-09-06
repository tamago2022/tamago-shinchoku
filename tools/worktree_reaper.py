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

# 2026-09-07（620番・容量急減の原因調査で発覚）：
#   並行して走るセッションの多くが `/private/tmp/<名前>` に joy-relief-station の
#   git worktree を作っている。ここは元々この掃除係の対象外で、実測7GB・29個が
#   野放しになっていた（disk_guardian.py の監視範囲にも入っていない）。
#   ここも対象に加える。`/private/tmp` は無関係なファイルだらけなので、
#   「.git ファイルがあり、その中身が joy-relief-station を指す」ものだけを拾う。
PRIVATE_TMP = "/private/tmp"

# 2026-09-07：`.worktrees` 配下には、joy-relief-station 本体の `.git/worktrees/<名前>`
# という登録自体が既に消えている「幽霊」ディレクトリが多数ある（他セッションが
# `git worktree remove` を素通りする形で片づけた/壊した名残）。この場合
# `git status` は "not a git repository" で失敗し、reaperはずっと
# 「状態が読めない」として片づけられずに残し続けてしまう（実例：26件中の大半）。
# 幽霊と分かったものは、未コミット差分の有無を確認しようが無いため、
# **rmではなくゴミ箱へ退避するだけ**にとどめる（店主が後で拾えるように）。
GHOST_TRASH = os.path.join(os.path.expanduser("~"), ".Trash", "worktree_reaper_ghosts")
GHOST_MIN_AGE_SEC = 3 * 86400  # 3日以上さわられていない幽霊だけ対象


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


def is_ghost(path):
    """joy-relief-station本体側の`.git/worktrees/<名前>`登録が既に消えている「幽霊」か。
    （他セッションの操作の巻き添え等で、実体だけ残り登録が無いケース。2026-09-07発見）"""
    r = git(["rev-parse", "--git-dir"], cwd=path, timeout=15)
    if r is None:
        return False
    return r.returncode != 0 and "not a git repository" in (r.stderr or "")


def rescue_ghost(path, name):
    """幽霊は git worktree remove が使えない（登録が無いので）。rmはせず、
    店主が後で拾えるようゴミ箱へ退避するだけにとどめる。"""
    try:
        os.makedirs(GHOST_TRASH, exist_ok=True)
        import shutil
        dest = os.path.join(GHOST_TRASH, "%s_%d" % (name, int(time.time())))
        shutil.move(path, dest)
        return True
    except Exception as e:
        log("幽霊の退避に失敗 %s: %s" % (path, e))
        return False


def sweep_node_modules(wt_dir, guard):
    """node_modulesだけ先に消す（2026-09-05・容量の主犯。bun/npm installで作り直せる）。"""
    freed = []
    for name in sorted(os.listdir(wt_dir)):
        path = os.path.join(wt_dir, name)
        nm = os.path.join(path, "node_modules")
        if not os.path.isdir(nm):
            continue
        if name in guard or any(name.startswith(g + "-") for g in guard):
            continue
        try:
            if time.time() - os.path.getmtime(path) < MIN_AGE_SEC:
                continue
        except Exception:
            continue
        try:
            import shutil
            shutil.rmtree(nm, ignore_errors=True)
            if not os.path.isdir(nm):
                freed.append(name)
        except Exception:
            pass
    if freed:
        log("📦 [%s] node_modules を消しました %d件（bun installで作り直せます）: %s"
            % (wt_dir, len(freed), ", ".join(freed[:12])))


def sweep_worktrees(wt_dir, guard):
    """本体4条件（走行中でない・2時間以上経過・未コミット無し・origin/mainに取込済み）
    を満たすものだけ `git worktree remove`。幽霊（登録が既に消えている）は別扱い。"""
    removed, rescued, kept = [], [], []
    for name in sorted(os.listdir(wt_dir)):
        path = os.path.join(wt_dir, name)
        if not os.path.isdir(path):
            continue
        if name in guard or any(name.startswith(g + "-") for g in guard):
            kept.append((name, "走行中"))
            continue
        try:
            age = time.time() - os.path.getmtime(path)
        except Exception:
            continue
        if age < MIN_AGE_SEC:
            kept.append((name, "まだ新しい"))
            continue

        if is_ghost(path):
            # 2026-09-07：登録が無いので git worktree remove は使えない。
            # 3日以上放置されている幽霊だけ、rmではなくゴミ箱へ退避する。
            if age >= GHOST_MIN_AGE_SEC:
                if rescue_ghost(path, name):
                    rescued.append(name)
                else:
                    kept.append((name, "幽霊・退避失敗"))
            else:
                kept.append((name, "幽霊だがまだ3日未満"))
            continue

        st = git(["status", "--porcelain"], cwd=path)
        if st is None or st.returncode != 0:
            kept.append((name, "状態が読めない"))
            continue
        if (st.stdout or "").strip():
            kept.append((name, "未保存の変更あり"))
            continue
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
        log("🧹 [%s] 片づけた作業場 %d件: %s" % (wt_dir, len(removed), ", ".join(removed[:10])))
    if rescued:
        log("👻 [%s] 幽霊をゴミ箱へ退避 %d件（%sに残っています）: %s"
            % (wt_dir, len(rescued), GHOST_TRASH, ", ".join(rescued[:10])))
    if kept:
        log("残した %d件（理由つき）: %s" % (
            len(kept), ", ".join("%s(%s)" % (n, why) for n, why in kept[:8])))


def private_tmp_targets():
    """/private/tmp配下で、.gitファイルの中身がjoy-relief-stationを指すものだけ拾う。
    2026-09-07発見：ここに並行セッションの作業用worktreeが実測7GB・29個溜まっていたが
    reaper・disk_guardianどちらの監視対象にも入っていなかった。"""
    out = []
    try:
        names = os.listdir(PRIVATE_TMP)
    except Exception:
        return out
    for name in names:
        path = os.path.join(PRIVATE_TMP, name)
        gitfile = os.path.join(path, ".git")
        if not os.path.isfile(gitfile):
            continue
        try:
            content = io.open(gitfile, encoding="utf-8").read()
        except Exception:
            continue
        if "joy-relief-station" in content:
            out.append(name)
    return out


def main():
    try:
        if time.time() - os.path.getmtime(STAMP) < INTERVAL:
            return 0
    except Exception:
        pass
    io.open(STAMP, "w").write(str(int(time.time())))

    # 重いときは何もしない（掃除でMacを重くしない）
    try:
        if os.getloadavg()[0] > 15:
            return 0
    except Exception:
        pass

    guard = running_paths()

    if os.path.isdir(WT_DIR):
        sweep_node_modules(WT_DIR, guard)
        sweep_worktrees(WT_DIR, guard)

    # 2026-09-07追加：/private/tmp配下のjoy-relief-station worktreeも同じ4条件で片づける。
    # /private/tmpは実在ディレクトリの集合ではなく個別名の集合なので、専用ループにする。
    pt_names = private_tmp_targets()
    if pt_names:
        removed, kept = [], []
        for name in sorted(pt_names):
            path = os.path.join(PRIVATE_TMP, name)
            if name in guard or any(name.startswith(g + "-") for g in guard):
                kept.append((name, "走行中"))
                continue
            try:
                age = time.time() - os.path.getmtime(path)
            except Exception:
                continue
            if age < MIN_AGE_SEC:
                kept.append((name, "まだ新しい"))
                continue
            st = git(["status", "--porcelain"], cwd=path)
            if st is None or st.returncode != 0:
                kept.append((name, "状態が読めない"))
                continue
            if (st.stdout or "").strip():
                kept.append((name, "未保存の変更あり"))
                continue
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
            log("🧹 [/private/tmp] 片づけた作業場 %d件: %s" % (len(removed), ", ".join(removed[:10])))
        if kept:
            log("[/private/tmp] 残した %d件（理由つき）: %s" % (
                len(kept), ", ".join("%s(%s)" % (n, why) for n, why in kept[:8])))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
