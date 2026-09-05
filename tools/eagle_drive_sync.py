#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eagleライブラリ → Google Drive を自動で「同じ中身」にする。

たまごさんの要望（2026-09-05）：
  「Eagleに1枚追加したら自動的にDriveにも複製される。
   フォルダの関係性（Eagleのフォルダ構成）もDrive側で同じになる」

方式：
  Google Drive デスクトップアプリは実際に起動しており（ps確認済み）、
  ~/Library/CloudStorage/GoogleDrive-<mail>/マイドライブ は書き込み可能な
  マウントポイントとして機能している（書き込みテスト済み）。
  rclone や Drive API のOAuth設定は不要で、このマウント配下へ普通に
  ファイルをコピーするだけでGoogle Drive側へ同期される。

やること（5分おきに呼ばれる想定・差分のみ処理）：
  1. Eagleライブラリの metadata.json から「フォルダID → 親/子パス」を作る
     （eagle_gallery.py の folder_names() と同じロジックを再利用）
  2. images/*.info を全部走査し、各画像がどのフォルダに属すか解決する
     （複数フォルダに属す画像は、Eagle上の実態どおり全フォルダへコピーする）
  3. Google Drive 側に「フォルダ名の階層」でディレクトリを作り、実ファイルをコピーする
     （サムネイル(_thumbnail.*)は対象外。本物の画像だけ）
  4. 前回と中身（サイズ+mtime）が変わっていないファイルはコピーし直さない（差分同期）
  5. フォルダ移動があった場合は、古いコピー先を削除し新しい場所へコピーし直す
  6. Eagle側で完全削除されたアイテムのDrive側ファイルの削除は、今回は対象外
     （誤爆事故を避けるため。必要になったら別途スコープを切って足す）

状態ファイル: status/eagle_drive_sync_state.json
ログ: status/eagle_drive_sync.log
"""
import io
import json
import os
import shutil
import sys
import time

LIB = "/Volumes/iMac HDD/Eagle_Library_2026-09-02/eagle AI 画像整理.library"
DRIVE_ROOT = os.path.expanduser(
    "~/Library/CloudStorage/GoogleDrive-eggypop2010@gmail.com/マイドライブ/Eagle同期_AI画像整理"
)
UNSORTED_NAME = "_フォルダ未所属"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATE_PATH = os.path.join(REPO, "status", "eagle_drive_sync_state.json")
LOG_PATH = os.path.join(REPO, "status", "eagle_drive_sync.log")


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with io.open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def folder_names(lib):
    """フォルダIDから「親 / 子」形式の名前を引く表（eagle_gallery.pyと同じロジック）"""
    out = {}
    try:
        md = json.load(io.open(os.path.join(lib, "metadata.json"), encoding="utf-8"))
    except Exception as e:
        log("metadata.json 読み込み失敗: %s" % e)
        return out

    def walk(fs, path_parts=None):
        path_parts = path_parts or []
        for f in fs or []:
            name = (f.get("name") or "").strip() or "無題フォルダ"
            parts = path_parts + [name]
            out[f.get("id")] = parts
            walk(f.get("children"), parts)

    walk(md.get("folders"))
    return out


def find_original(p):
    """サムネ(_thumbnail.*)ではなく、本物のファイルを探す"""
    try:
        entries = os.listdir(p)
    except Exception:
        return None
    for f in entries:
        if f == "metadata.json" or f.startswith("."):
            continue
        if "_thumbnail." in f:
            continue
        return os.path.join(p, f)
    return None


def sanitize(name):
    """ファイル名・フォルダ名に使えない文字だけ避ける（macOS/Driveどちらでも安全な最小限）"""
    bad = "/:\0"
    out = "".join(("_" if c in bad else c) for c in name)
    return out.strip() or "無題"


def signature(path):
    try:
        st = os.stat(path)
        return "%d_%d" % (st.st_size, int(st.st_mtime))
    except Exception:
        return None


def load_state():
    try:
        return json.load(io.open(STATE_PATH, encoding="utf-8"))
    except Exception:
        return {"items": {}}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    os.replace(tmp, STATE_PATH)


def dest_dirs_for(folder_ids, folders_map):
    """1アイテムが属す全フォルダの、Drive側ディレクトリパス一覧を返す"""
    if not folder_ids:
        return [os.path.join(DRIVE_ROOT, UNSORTED_NAME)]
    dirs = []
    for fid in folder_ids:
        parts = folders_map.get(fid)
        if not parts:
            continue
        safe_parts = [sanitize(p) for p in parts]
        dirs.append(os.path.join(DRIVE_ROOT, *safe_parts))
    return dirs or [os.path.join(DRIVE_ROOT, UNSORTED_NAME)]


def main():
    if not os.path.isdir(LIB):
        log("Eagleライブラリが見つからない（外付けHDDが外れている？）: %s" % LIB)
        return 1
    if not os.path.isdir(os.path.dirname(os.path.dirname(DRIVE_ROOT))):
        log("Google Driveのマウントが見つからない（デスクトップアプリが止まっている？）")
        return 1
    os.makedirs(DRIVE_ROOT, exist_ok=True)

    folders_map = folder_names(LIB)
    state = load_state()
    items_state = state.get("items", {})

    imgs_dir = os.path.join(LIB, "images")
    if not os.path.isdir(imgs_dir):
        log("images フォルダが見つからない: %s" % imgs_dir)
        return 1

    copied = updated = unchanged = errors = 0
    seen_ids = set()

    for d in sorted(os.listdir(imgs_dir)):
        if not d.endswith(".info"):
            continue
        p = os.path.join(imgs_dir, d)
        iid = d[:-5]
        seen_ids.add(iid)
        meta_path = os.path.join(p, "metadata.json")
        try:
            m = json.load(io.open(meta_path, encoding="utf-8"))
        except Exception as e:
            errors += 1
            log("メタデータ読み込み失敗 %s: %s" % (iid, e))
            continue

        orig = find_original(p)
        if orig is None:
            continue
        sig = signature(orig)
        if sig is None:
            errors += 1
            continue

        folder_ids = m.get("folders") or []
        dest_dirs = dest_dirs_for(folder_ids, folders_map)
        base_name = sanitize(m.get("name") or iid) + os.path.splitext(orig)[1]

        prev = items_state.get(iid)
        new_dst_paths = []
        item_changed = False

        for dd in dest_dirs:
            try:
                os.makedirs(dd, exist_ok=True)
            except Exception as e:
                errors += 1
                log("フォルダ作成失敗 %s: %s" % (dd, e))
                continue
            dst = os.path.join(dd, base_name)
            new_dst_paths.append(dst)
            need_copy = True
            if prev and prev.get("sig") == sig and dst in (prev.get("dst_paths") or []):
                if os.path.exists(dst):
                    need_copy = False
            if need_copy:
                try:
                    shutil.copy2(orig, dst)
                    item_changed = True
                except Exception as e:
                    errors += 1
                    log("コピー失敗 %s -> %s: %s" % (orig, dst, e))

        # フォルダ移動などで不要になった旧コピー先を削除
        if prev:
            for old_dst in (prev.get("dst_paths") or []):
                if old_dst not in new_dst_paths and os.path.exists(old_dst):
                    try:
                        os.remove(old_dst)
                        item_changed = True
                    except Exception:
                        pass

        if prev is None:
            copied += 1
        elif item_changed:
            updated += 1
        else:
            unchanged += 1

        items_state[iid] = {"sig": sig, "dst_paths": new_dst_paths}

    # Eagle側から消えたアイテムはstateから外す（Drive側の実ファイル削除は今回スコープ外）
    stale = [k for k in list(items_state.keys()) if k not in seen_ids]
    for k in stale:
        items_state.pop(k, None)

    state["items"] = items_state
    state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
    state["counts"] = {"copied": copied, "updated": updated, "unchanged": unchanged,
                        "errors": errors, "total": len(seen_ids), "stale_removed": len(stale)}
    save_state(state)

    if copied or updated or errors:
        log("同期: 新規%d / 更新%d / 変化なし%d / エラー%d / 合計%d件" %
            (copied, updated, unchanged, errors, len(seen_ids)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
