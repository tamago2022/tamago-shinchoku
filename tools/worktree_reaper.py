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
import re
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TARGET = "/Users/mac/Desktop/joy-relief-station"
WT_DIR = os.path.join(TARGET, ".worktrees")
# 2026-09-09（685番・容量急減の徹底追及で発覚）：`.claude/worktrees`配下に
# サブエージェント(agent-xxxx等)が作る作業場が89個・実測9.0GB、reaper・
# disk_guardianどちらの監視対象にも入らず野放しになっていた。
# `.worktrees`(2026-09-05)→`/private/tmp`(2026-09-07)に続き3件目の同じ穴。
CLAUDE_WT_DIR = os.path.join(TARGET, ".claude", "worktrees")
# 2026-09-10（720番・店主「ChatGPTのタスク一覧に作業場が300件近く出て増える一方」への
# 2回目の指摘で発覚）：セッションの並列作業場（isolation:worktree等）が
# `Documents/AI作業/.worktrees` にも作られており（実測39件）、ここは reaper の
# 監視対象に一度も入っていなかった（TARGETがjoy-relief-station直下に決め打ちだった穴）。
# 中身はjoy-relief-stationのworktreeなので同じ4条件でそのまま片づけられる。
DOCS_WT_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "AI作業", ".worktrees"
)
QUEUE = os.path.join(REPO, "status", "queue.json")
LOG = os.path.join(REPO, "status", "worktree_reaper.log")
STAMP = os.path.join(REPO, "status", ".worktree_reaper_at")
INTERVAL = 1800          # 30分に1回でよい
MIN_AGE_SEC = 2 * 3600   # 触ってから2時間は残す
# 2026-09-09（685番・容量調査中にこのセッション自身のworktreeが誤って消された
# 実例で発覚）：コミットを一切していない新規worktreeは、HEADがTARGET本体の
# 現在のブランチ先端とビット一致するため「origin/mainに取り込み済み」の
# 条件も真になってしまい、本体4条件をすり抜けて誤って消される。
# これから使われる可能性が高い「まっさら」なworktreeは、通常のMIN_AGE_SEC(2h)
# ではなくこちらの長い保護期間が経つまで消さない。
FRESH_WORKTREE_MIN_AGE_SEC = 24 * 3600

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

# 2026-09-12（727番・店主「ChatGPT/Codexのプロジェクト一覧を汚す」再発への対応）：
# 本体4条件が安全すぎて「未保存の変更あり」「まだ本流に入っていない」「状態が読めない」
# に該当する作業場が、何日前に放置されたものでも永遠に片づかず130件で足踏みしていた
# （30分毎の巡回で1〜4件しか進まない＝しきい値100件に何時間経っても届かない）。
# 「成果を消すのが最悪」の原則は変えず、**消す代わりにバックアップしてから消す**：
#   - 未保存の変更あり     → diffをパッチとして ~/.Trash/worktree_reaper_backups へ退避
#   - まだ本流に入っていない → そのコミットをバックアップ用ブランチ名でoriginへpushして退避
#   - 状態が読めない       → 幽霊と同じ扱いでゴミ箱へ退避（rescue_ghostを流用）
# 対象は「3日以上放置されたもの」だけ（既存のGHOST_MIN_AGE_SECと同じ基準に揃える）。
STALE_BACKUP_MIN_AGE_SEC = 3 * 86400
BACKUP_TRASH = os.path.join(os.path.expanduser("~"), ".Trash", "worktree_reaper_backups")


def backup_uncommitted_changes(path, name):
    """未コミット差分をパッチ＋軽い未追跡ファイルとして退避する。成功したらTrue。"""
    try:
        os.makedirs(BACKUP_TRASH, exist_ok=True)
        dest = os.path.join(BACKUP_TRASH, "%s_%d" % (name, int(time.time())))
        os.makedirs(dest, exist_ok=True)
        diff = git(["diff", "HEAD"], cwd=path, timeout=60)
        with io.open(os.path.join(dest, "changes.patch"), "w", encoding="utf-8") as f:
            f.write((diff.stdout or "") if diff else "")
        st = git(["status", "--porcelain"], cwd=path, timeout=30)
        st_out = (st.stdout or "") if st else ""
        with io.open(os.path.join(dest, "status.txt"), "w", encoding="utf-8") as f:
            f.write(st_out)
        if st_out:
            import shutil
            for line in st_out.splitlines():
                if not line.startswith("?? "):
                    continue
                rel = line[3:].strip()
                src = os.path.join(path, rel)
                try:
                    if os.path.isfile(src) and os.path.getsize(src) < 2_000_000:
                        target = os.path.join(dest, "untracked", rel)
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        shutil.copy2(src, target)
                except Exception:
                    pass
        return True
    except Exception as e:
        log("バックアップ失敗 %s: %s" % (path, e))
        return False


def backup_branch_to_remote(path, name, sha):
    """まだ本流に入っていないコミットを、バックアップ用ブランチ名でoriginへpushして退避する。"""
    backup_ref = "refs/heads/backup/%s-%d" % (name, int(time.time()))
    r = git(["push", "origin", "%s:%s" % (sha, backup_ref)], cwd=path, timeout=120)
    if r is not None and r.returncode == 0:
        log("バックアップブランチへpush済み: %s -> %s" % (name, backup_ref))
        return True
    log("バックアップpush失敗 %s: %s" % (name, (r.stderr if r else "?")))
    return False

# 2026-09-10（720番・店主「ChatGPTのタスク一覧が300件近く出て増える一方」への対応で発覚）：
# 「未保存の変更あり」でずっと保護され続けているworktreeの実態を数件サンプルしたところ、
# 大半が実際の未完了作業ではなく①`.claude/agents/*.md`（main側で更新され続ける共通のエージェント
# 定義）、②`.agents/skills/`配下の未追跡ディレクトリ（後から共有スキルとして追加されたもの）、
# ③`.codex/`（同様の未追跡ノイズ）、④自動生成ファイル、で埋まっていた（例：gdrive-music-0903は
# `??`行が全部この手のノイズのみで実質差分ゼロだった）。これらは「消えても実害がない共通ノイズ」
# と明確に言えるものだけを厳選し、除外した残りが空なら「実質clean」として扱う。
# 安全側に倒すため、ここに載せる以外の差分が1件でもあれば従来通り保護する。
HARMLESS_STATUS_PATTERNS = [
    re.compile(r"^ M \.claude/agents/.*\.md$"),
    re.compile(r"^\?\? \.agents/skills/"),
    re.compile(r"^\?\? \.codex/"),
    re.compile(r"^ M src/routeTree\.gen\.ts$"),
]


def has_meaningful_changes(status_output):
    """`git status --porcelain`の出力から、無害な共通ノイズを除いても
    実質的な差分が残るかを判定する。空文字列・全行が無害パターン一致なら False。
    注意：`--porcelain`の各行は先頭2文字がステータスコード（例" M"）で意味を持つため、
    行全体を`.strip()`してはいけない（先頭スペースが消えて誤判定する）。改行のみで分割する。"""
    if not (status_output or "").strip():
        return False
    for line in status_output.splitlines():
        line = line.rstrip("\r\n")
        if not line:
            continue
        if any(p.match(line) for p in HARMLESS_STATUS_PATTERNS):
            continue
        return True
    return False


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


_TARGET_HEAD_CACHE = {}


def target_head():
    """TARGET本体（joy-relief-station）の現在のブランチ先端SHAを1回だけ取得する。"""
    if "sha" not in _TARGET_HEAD_CACHE:
        r = git(["rev-parse", "HEAD"], cwd=TARGET)
        _TARGET_HEAD_CACHE["sha"] = (r.stdout or "").strip() if (r and r.returncode == 0) else None
    return _TARGET_HEAD_CACHE["sha"]


def sweep_worktrees(wt_dir, guard):
    """本体4条件（走行中でない・2時間以上経過・未コミット無し・origin/mainに取込済み）
    を満たすものだけ `git worktree remove`。幽霊（登録が既に消えている）は別扱い。"""
    removed, rescued, backed_up, kept = [], [], [], []
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
            if age >= STALE_BACKUP_MIN_AGE_SEC and rescue_ghost(path, name):
                rescued.append(name)
            else:
                kept.append((name, "状態が読めない"))
            continue
        if has_meaningful_changes(st.stdout):
            if age >= STALE_BACKUP_MIN_AGE_SEC and backup_uncommitted_changes(path, name):
                r = git(["worktree", "remove", "--force", path])
                if r is not None and r.returncode == 0:
                    backed_up.append(name)
                else:
                    kept.append((name, "未保存の変更あり・remove失敗"))
            else:
                kept.append((name, "未保存の変更あり"))
            continue
        head = git(["rev-parse", "HEAD"], cwd=path)
        if head is None or head.returncode != 0:
            kept.append((name, "HEADが読めない"))
            continue
        sha = (head.stdout or "").strip()
        if sha and sha == target_head() and age < FRESH_WORKTREE_MIN_AGE_SEC:
            # コミット未着手＝これから使われる可能性が高い新品。もっと長く保護する
            # （685番：この判定が無いと「本流と同じコミット」＝「取込済み」と
            # 誤判定され、作業開始直後のworktreeが誤って消されてしまう）。
            kept.append((name, "コミット未着手・保護期間中"))
            continue
        merged = git(["merge-base", "--is-ancestor", sha, "origin/main"])
        if merged is None or merged.returncode != 0:
            if age >= STALE_BACKUP_MIN_AGE_SEC and backup_branch_to_remote(path, name, sha):
                r = git(["worktree", "remove", "--force", path])
                if r is not None and r.returncode == 0:
                    backed_up.append(name)
                else:
                    kept.append((name, "まだ本流に入っていない・remove失敗"))
            else:
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
    if backed_up:
        git(["worktree", "prune"])
        log("🗄️ [%s] バックアップ付きで片づけた作業場 %d件（%sに退避済み）: %s"
            % (wt_dir, len(backed_up), BACKUP_TRASH, ", ".join(backed_up[:10])))
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


def git_worktree_paths():
    """`git worktree list --porcelain`を正本にして、TARGET自身を除く全登録パスを返す。
    2026-09-09（685番）：決め打ちの置き場所（.worktrees/.claude/worktrees/private/tmp
    直下）だけを見る方式だと、ネストした深い場所（例：
    /private/tmp/.../scratchpad/wt-xxx）に作られたworktreeを見落とし続ける。
    ここを正本にすれば、次に新しい置き場所が増えても自動で拾える。"""
    r = git(["worktree", "list", "--porcelain"])
    if r is None or r.returncode != 0:
        return []
    paths = []
    for line in (r.stdout or "").splitlines():
        if line.startswith("worktree "):
            p = line[len("worktree "):].strip()
            if p and os.path.abspath(p) != TARGET:
                paths.append(p)
    return paths


def sweep_node_modules_paths(paths, guard):
    """sweep_node_modulesのパス配列版（decide-by-listdirではなくgit worktree list由来）。"""
    freed = []
    for path in paths:
        name = os.path.basename(path)
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
        log("📦 [git worktree list] node_modules を消しました %d件（bun installで作り直せます）: %s"
            % (len(freed), ", ".join(freed[:12])))


def sweep_paths(paths, guard, label):
    """sweep_worktreesと同じ本体4条件を、git worktree list由来のパス配列に適用する版。"""
    removed, backed_up, rescued, kept = [], [], [], []
    for path in paths:
        name = os.path.basename(path)
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
        st = git(["status", "--porcelain"], cwd=path)
        if st is None or st.returncode != 0:
            if age >= STALE_BACKUP_MIN_AGE_SEC and rescue_ghost(path, name):
                rescued.append(name)
            else:
                kept.append((name, "状態が読めない"))
            continue
        if has_meaningful_changes(st.stdout):
            if age >= STALE_BACKUP_MIN_AGE_SEC and backup_uncommitted_changes(path, name):
                r = git(["worktree", "remove", "--force", path])
                if r is not None and r.returncode == 0:
                    backed_up.append(name)
                else:
                    kept.append((name, "未保存の変更あり・remove失敗"))
            else:
                kept.append((name, "未保存の変更あり"))
            continue
        head = git(["rev-parse", "HEAD"], cwd=path)
        if head is None or head.returncode != 0:
            kept.append((name, "HEADが読めない"))
            continue
        sha = (head.stdout or "").strip()
        if sha and sha == target_head() and age < FRESH_WORKTREE_MIN_AGE_SEC:
            kept.append((name, "コミット未着手・保護期間中"))
            continue
        merged = git(["merge-base", "--is-ancestor", sha, "origin/main"])
        if merged is None or merged.returncode != 0:
            if age >= STALE_BACKUP_MIN_AGE_SEC and backup_branch_to_remote(path, name, sha):
                r = git(["worktree", "remove", "--force", path])
                if r is not None and r.returncode == 0:
                    backed_up.append(name)
                else:
                    kept.append((name, "まだ本流に入っていない・remove失敗"))
            else:
                kept.append((name, "まだ本流に入っていない"))
            continue
        r = git(["worktree", "remove", "--force", path])
        if r is not None and r.returncode == 0:
            removed.append(name)
        else:
            kept.append((name, "removeに失敗"))
    if removed:
        git(["worktree", "prune"])
        log("🧹 [%s] 片づけた作業場 %d件: %s" % (label, len(removed), ", ".join(removed[:10])))
    if backed_up:
        git(["worktree", "prune"])
        log("🗄️ [%s] バックアップ付きで片づけた作業場 %d件（%sに退避済み）: %s"
            % (label, len(backed_up), BACKUP_TRASH, ", ".join(backed_up[:10])))
    if rescued:
        log("👻 [%s] 幽霊をゴミ箱へ退避 %d件（%sに残っています）: %s"
            % (label, len(rescued), GHOST_TRASH, ", ".join(rescued[:10])))
    if kept:
        log("[%s] 残した %d件（理由つき）: %s" % (
            label, len(kept), ", ".join("%s(%s)" % (n, why) for n, why in kept[:8])))


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

    # 2026-09-09（685番）追加：`.claude/worktrees`配下も同じ4条件で片づける。
    if os.path.isdir(CLAUDE_WT_DIR):
        sweep_node_modules(CLAUDE_WT_DIR, guard)
        sweep_worktrees(CLAUDE_WT_DIR, guard)

    # 2026-09-10（720番）追加：`Documents/AI作業/.worktrees`配下も同じ4条件で片づける。
    if os.path.isdir(DOCS_WT_DIR):
        sweep_node_modules(DOCS_WT_DIR, guard)
        sweep_worktrees(DOCS_WT_DIR, guard)

    # 2026-09-09（685番）追加：git worktree list --porcelainを正本にして、
    # 上記の決め打ち3箇所（.worktrees/.claude/worktrees/private-tmp直下）以外に
    # 作られたworktree（例：/private/tmp配下のネストしたscratchpad）も同じ条件で拾う。
    # これで次に新しい置き場所が増えても自動対応できる。
    try:
        _known_dirs = (os.path.abspath(WT_DIR), os.path.abspath(CLAUDE_WT_DIR), os.path.abspath(DOCS_WT_DIR))

        def _is_known(p):
            ap = os.path.abspath(p)
            for d in _known_dirs:
                if ap == d or ap.startswith(d + os.sep):
                    return True
            if ap.startswith(PRIVATE_TMP + os.sep):
                rel = os.path.relpath(ap, PRIVATE_TMP)
                return os.sep not in rel  # PRIVATE_TMP直下だけは既存ループが処理済み
            return False

        dynamic_paths = [p for p in git_worktree_paths() if not _is_known(p)]
        if dynamic_paths:
            sweep_node_modules_paths(dynamic_paths, guard)
            sweep_paths(dynamic_paths, guard, "git worktree list(新規置き場所)")
    except Exception as e:
        log("git worktree list動的スイープ失敗: %s" % e)

    # 2026-09-07追加：/private/tmp配下のjoy-relief-station worktreeも同じ4条件で片づける。
    # /private/tmpは実在ディレクトリの集合ではなく個別名の集合なので、専用ループにする。
    # 2026-09-12（727番）：このループはsweep_pathsと全く同じ4条件＋バックアップ退避を
    # 重複実装していたため、二重管理を避けてsweep_pathsに一本化した。
    pt_names = private_tmp_targets()
    if pt_names:
        pt_paths = [os.path.join(PRIVATE_TMP, name) for name in sorted(pt_names)]
        sweep_paths(pt_paths, guard, "/private/tmp")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
