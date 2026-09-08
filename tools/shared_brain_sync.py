#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared Brain 双方向同期（671番・「スマホでもshared-brainを読めるようにする」）

背景：
  666番でGitHub↔Obsidianの配管をsymlinkで通した
  （Vault内 shared-brain → ~/Desktop/tamago-shinchoku/shared-brain）。
  しかしVaultはiCloud Driveの中にあり、iCloudはsymlinkの「先の実体」を
  同期しない（このMac以外の場所からは空か存在しないように見える）。
  スマホのObsidianはiCloudの中身しか見えないため、symlinkのままでは
  スマホで読めない。

方式変更（671番）：
  symlinkをやめ、Vault側に「実体のフォルダ」を作る（既に本スクリプト実行前に
  1回だけ手動で置き換え済み）。以後はこのスクリプトが両側の中身を
  双方向にコピーして同じ状態に保つ。

  - repo → vault：GitHub側（AIがcommitしたもの）をVaultへ反映
  - vault → repo：たまごさんや別AIがVaultで直接編集・追加したものをGitHubへ反映
  - 一方向にしない。

安全設計（絶対に守る）：
  1. 既存ノートを壊さない・消さない。削除は一切伝播しない
     （どちらかにしか無いファイルは「まだ広まっていないだけ」として単純にコピーする）。
  2. 同名ファイルで中身が違う場合は上書きしない。
     両方をそのまま残し、負けた側のコピーを
     「<元のファイル名>__conflict_from_<repo|vault>_<timestamp>.md」として
     相手側フォルダに追加保存する（オリジナルはどちらも変更しない）。
  3. 走査対象は shared-brain/ 配下のみ。Vault全体・iCloud Drive全体を
     舐めるような os.walk は書かない（過去のGoogleドライブ全件走査事故と同じ轍を踏まない）。
  4. 同期後、repo側に変更があれば git add / commit / push まで自動で行う
     （店主指示：既存ルールに沿い、確認は求めず自律実行）。

状態ファイル: status/shared_brain_sync_state.json（前回同期時の各ファイルの中身ハッシュ）
ログ: status/shared_brain_sync.log
"""
import hashlib
import json
import os
import shutil
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REPO_SB = os.path.join(REPO, "shared-brain")
VAULT_SB = (
    "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/"
    "tamago_brain/shared-brain"
)
STATE_PATH = os.path.join(REPO, "status", "shared_brain_sync_state.json")
LOG_PATH = os.path.join(REPO, "status", "shared_brain_sync.log")

IGNORE_NAMES = {".DS_Store"}


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with io_open(LOG_PATH) as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def io_open(path):
    return open(path, "a", encoding="utf-8")


def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)


def sha1_of(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def list_files(root):
    """root配下の全ファイルを相対パスで返す（shared-brain配下のみ・浅い範囲）"""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn in IGNORE_NAMES:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            out[rel] = full
    return out


def conflict_name(rel, loser_side):
    ts = time.strftime("%Y%m%d_%H%M%S")
    base, ext = os.path.splitext(rel)
    return "%s__conflict_from_%s_%s%s" % (base, loser_side, ts, ext)


def sync():
    if not os.path.isdir(REPO_SB):
        log("ERROR: repo側 shared-brain が見つからない: %s" % REPO_SB)
        return False
    if not os.path.isdir(VAULT_SB):
        log("ERROR: vault側 shared-brain が見つからない（symlinkのまま？）: %s" % VAULT_SB)
        return False

    state = load_state()
    changed_repo = False
    changed_vault = False

    repo_files = list_files(REPO_SB)
    vault_files = list_files(VAULT_SB)
    all_rels = sorted(set(repo_files) | set(vault_files))

    for rel in all_rels:
        repo_path = os.path.join(REPO_SB, rel)
        vault_path = os.path.join(VAULT_SB, rel)
        in_repo = rel in repo_files
        in_vault = rel in vault_files
        prev_hash = state.get(rel)

        if in_repo and not in_vault:
            # repoにしか無い → vaultへコピー（新規展開。削除の伝播はしない）
            os.makedirs(os.path.dirname(vault_path), exist_ok=True)
            shutil.copy2(repo_path, vault_path)
            h = sha1_of(repo_path)
            state[rel] = h
            changed_vault = True
            log("repo→vault コピー: %s" % rel)
            continue

        if in_vault and not in_repo:
            # vaultにしか無い → repoへコピー
            os.makedirs(os.path.dirname(repo_path), exist_ok=True)
            shutil.copy2(vault_path, repo_path)
            h = sha1_of(vault_path)
            state[rel] = h
            changed_repo = True
            log("vault→repo コピー: %s" % rel)
            continue

        # 両方に存在する
        repo_hash = sha1_of(repo_path)
        vault_hash = sha1_of(vault_path)
        if repo_hash == vault_hash:
            state[rel] = repo_hash
            continue

        # 内容が違う → 誰が動かしたかを前回状態と比べて判定
        if prev_hash == repo_hash and prev_hash != vault_hash:
            # 前回からrepo側は変わっておらず、vault側だけ更新された → vault優位、repoへ反映
            shutil.copy2(vault_path, repo_path)
            state[rel] = vault_hash
            changed_repo = True
            log("vault更新をrepoへ反映: %s" % rel)
        elif prev_hash == vault_hash and prev_hash != repo_hash:
            # repo側だけ更新された → repo優位、vaultへ反映
            shutil.copy2(repo_path, vault_path)
            state[rel] = repo_hash
            changed_vault = True
            log("repo更新をvaultへ反映: %s" % rel)
        else:
            # 両方が前回から動いている（真の衝突）→ 上書きしない。両方残す
            cname_for_repo = conflict_name(rel, "vault")
            cname_for_vault = conflict_name(rel, "repo")
            repo_conflict_path = os.path.join(REPO_SB, cname_for_repo)
            vault_conflict_path = os.path.join(VAULT_SB, cname_for_vault)
            shutil.copy2(vault_path, repo_conflict_path)
            shutil.copy2(repo_path, vault_conflict_path)
            state[cname_for_repo] = vault_hash
            state[cname_for_vault] = repo_hash
            changed_repo = True
            changed_vault = True
            log(
                "衝突検知・両方保存（上書きしない）: %s → repo側に%s / vault側に%s"
                % (rel, cname_for_repo, cname_for_vault)
            )
            # オリジナルの状態も更新（次回また衝突扱いにしないよう、現状のハッシュを記録）
            state[rel] = repo_hash  # repo版を暫定の基準として記録（どちらも消していない）

    save_state(state)

    if changed_repo:
        push_repo()
    if changed_vault:
        log("vault側を更新済み（iCloudが自動でスマホへ同期する）")

    if not changed_repo and not changed_vault:
        log("差分なし")

    return True


def push_repo():
    try:
        subprocess.run(
            ["git", "add", "shared-brain", "status/shared_brain_sync_state.json"],
            cwd=REPO,
            check=True,
        )
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=REPO
        )
        if diff.returncode == 0:
            log("git: ステージ後に差分なし（コミット省略）")
            return
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                "shared-brain: 671番 双方向同期（vault↔repo自動反映）",
            ],
            cwd=REPO,
            check=True,
        )
        push = subprocess.run(
            ["git", "push", "origin", "main"], cwd=REPO, capture_output=True, text=True
        )
        if push.returncode == 0:
            log("git push 成功")
        else:
            log("git push 失敗: %s" % push.stderr.strip()[:300])
    except subprocess.CalledProcessError as e:
        log("git操作失敗: %s" % e)


if __name__ == "__main__":
    ok = sync()
    if not ok:
        raise SystemExit(1)
