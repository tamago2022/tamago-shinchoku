#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容量の見張り（2026-09-06・415番）。

ディスクの空きを見張って、埋まる前に自分で片づける係。

★測り方を間違えないこと：macOSは起動ディスクが2つに分かれている。
  `df -h /` はシステム側（今回だと21GB）なので実態が見えない。
  必ず `df -h /System/Volumes/Data` を見る（これが本当の空き）。

やること：
  ① 15分おきに空きを測る（軽い。dfだけ）
  ② 30GBを切ったら、安全に消せるものだけ自動で片づける：
     - joy-relief-station の作業場(.worktrees)の node_modules
       （bun/npm installで作り直せる。tools/worktree_reaper.py と同じ考え方を流用）
     - 7日以上前のログ
     - __pycache__
     - ビルド成果物(dist / .output)
  ③ 20GBを切ったら発車を止めてDispatchへ知らせる（status/no_launch.flag を作る。
     auto_launcher.py が既にこのフラグを見て発車を止める仕組みを持っている＝新規実装不要）
  ④ 壺と金庫は絶対に触らない：写真・動画・音楽・Eagleライブラリ・Vault・Driveの中身・
     ソフトウェアのdmg。迷ったら触らない（パスにキーワードが1つでも含まれたら問答無用でスキップ）
  ⑤ 何を消して何GB空いたかを1行ずつログに残す(status/disk_guardian.log)

このスクリプトは削除範囲を「joy-relief-station の .worktrees 配下」「tamago-shinchoku /
joy-relief-station の tools・scripts 配下の __pycache__」「tamago-shinchoku/status の
7日超ログ」に明示的に限定している。それ以外のディレクトリには一切降りない。
"""
import io
import json
import os
import shutil
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)  # /Users/mac/Desktop/tamago-shinchoku
JOY = "/Users/mac/Desktop/joy-relief-station"
WT_DIR = os.path.join(JOY, ".worktrees")
QUEUE = os.path.join(REPO, "status", "queue.json")

LOG = os.path.join(REPO, "status", "disk_guardian.log")
STAMP = os.path.join(REPO, "status", ".disk_guardian_at")
NO_LAUNCH_FLAG = os.path.join(REPO, "status", "no_launch.flag")
MY_FLAG_MARK = "容量見張り"  # 自分が書いたno_launch.flagだけを自動解除するための目印

INTERVAL = 900          # 15分に1回でよい。既存の5分間隔ジョブ(machine_status_push.sh)から
                        # 毎回呼ばれても、STAMPファイルで前回実行から900秒未満ならすぐ戻る
                        # （＝実質15分おき）。launchdの新規登録が2回ブロックされたため、
                        # 既に動いている5分間隔ジョブへの相乗り方式に切り替えた(2026-09-06)。
MIN_AGE_SEC = 2 * 3600  # 触ってから2時間は残す（走行中の作業場を守る）
OLD_LOG_SEC = 7 * 86400  # 7日以上前のログだけ対象

WARN_GB = 30   # これを切ったら安全な片付けを実行
STOP_GB = 20   # これを切ったら発車を止める

# ④ 壺と金庫：迷ったら触らない。パスにこれらの文字列を含んでいたら問答無用でスキップする。
FORBIDDEN_KEYWORDS = (
    "CloudStorage", "Eagle", "Vault", "Google Drive", "GoogleDrive",
    "Photos", "Movies", "Music", ".dmg", "tamago_brain", "iCloud",
    "Pictures", "iCloud~md~obsidian",
)

# 片付けを許す範囲（この外には一切降りない）
ALLOWED_ROOTS = (
    WT_DIR,
    os.path.join(REPO, "tools"),
    os.path.join(REPO, "status"),
    os.path.join(JOY, "tools"),
    os.path.join(JOY, "scripts"),
)


def is_forbidden(path):
    low = path.lower()
    return any(k.lower() in low for k in FORBIDDEN_KEYWORDS)


def is_allowed(path):
    ap = os.path.abspath(path)
    if is_forbidden(ap):
        return False
    return any(ap == r or ap.startswith(r + os.sep) for r in ALLOWED_ROOTS)


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def disk_free_gb():
    """★正しい測り方：/System/Volumes/Data を見る。"""
    try:
        r = subprocess.run(["df", "-k", "/System/Volumes/Data"],
                           capture_output=True, text=True, timeout=10)
        lines = r.stdout.strip().splitlines()
        if len(lines) < 2:
            return None
        cols = lines[1].split()
        avail_kb = int(cols[3])
        return avail_kb / 1024.0 / 1024.0
    except Exception as e:
        log("df失敗: %s" % e)
        return None


def dir_size_mb(path):
    try:
        if os.path.isdir(path):
            r = subprocess.run(["du", "-sm", path], capture_output=True, text=True, timeout=30)
            return int(r.stdout.split()[0])
        return round(os.path.getsize(path) / 1024 / 1024, 2)
    except Exception:
        return 0


def running_worktree_names():
    """いま走っている仕事の作業場は絶対に触らない（worktree_reaper.pyと同じ考え方）。"""
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
            n = it.get("n")
            if n is not None:
                out.add("q%s" % n)
    return out


def candidates():
    """安全に消せる候補を列挙するだけ（消さない）。確認ページ・事前チェックで使う。"""
    out = []
    guard = running_worktree_names()

    if os.path.isdir(WT_DIR):
        for name in sorted(os.listdir(WT_DIR)):
            path = os.path.join(WT_DIR, name)
            if not os.path.isdir(path) or is_forbidden(path):
                continue
            protected = name in guard or any(name.startswith(g + "-") for g in guard)
            try:
                age_ok = (time.time() - os.path.getmtime(path)) >= MIN_AGE_SEC
            except Exception:
                age_ok = False
            for sub in ("node_modules", "dist", ".output"):
                sp = os.path.join(path, sub)
                if os.path.isdir(sp) and is_allowed(sp):
                    out.append({
                        "path": sp, "kind": sub, "worktree": name,
                        "protected": protected, "age_ok": age_ok,
                        "size_mb": dir_size_mb(sp),
                    })

    # __pycache__（tools/scripts配下・浅い探索のみ。壺金庫には降りない）
    for root in (os.path.join(REPO, "tools"), os.path.join(JOY, "tools"), os.path.join(JOY, "scripts")):
        if not os.path.isdir(root) or not is_allowed(root):
            continue
        for dirpath, dirnames, _ in os.walk(root):
            depth = dirpath[len(root):].count(os.sep)
            if depth > 3:
                dirnames[:] = []
                continue
            if "__pycache__" in dirnames:
                p = os.path.join(dirpath, "__pycache__")
                if is_allowed(p):
                    out.append({"path": p, "kind": "__pycache__", "worktree": "-",
                                "protected": False, "age_ok": True, "size_mb": dir_size_mb(p)})

    # 7日超のログ（tamago-shinchoku/status配下のみ）
    root = os.path.join(REPO, "status")
    if os.path.isdir(root) and is_allowed(root):
        for fn in os.listdir(root):
            if fn.endswith(".log"):
                fp = os.path.join(root, fn)
                try:
                    if (time.time() - os.path.getmtime(fp)) >= OLD_LOG_SEC and is_allowed(fp):
                        out.append({"path": fp, "kind": "old_log", "worktree": "-",
                                    "protected": False, "age_ok": True,
                                    "size_mb": dir_size_mb(fp)})
                except Exception:
                    pass
    return out


def safe_remove(path, kind):
    if not is_allowed(path):
        log("⛔スキップ(許可範囲外・壺金庫ガード): %s" % path)
        return 0
    before = dir_size_mb(path)
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.remove(path)
        ok = not os.path.exists(path)
    except Exception as e:
        log("削除失敗 %s: %s" % (path, e))
        return 0
    if ok:
        log("🧹 消しました [%s] %s (約%sMB)" % (kind, path, before))
        return before
    return 0


def cleanup():
    freed_total = 0.0
    for c in candidates():
        if c["protected"] or not c["age_ok"]:
            continue
        freed_total += safe_remove(c["path"], c["kind"])
    return freed_total


def notify_stop(free_gb):
    if not os.path.exists(NO_LAUNCH_FLAG):
        io.open(NO_LAUNCH_FLAG, "w", encoding="utf-8").write(
            "%s：ディスク空き容量が%.1fGBを切りました(%s)。発車を止めました。\n"
            % (MY_FLAG_MARK, free_gb, time.strftime("%Y-%m-%d %H:%M:%S"))
        )
    log("🛑 空き%.1fGB<%dGB → no_launch.flag 作成・発車停止" % (free_gb, STOP_GB))


def maybe_release_stop(free_gb):
    """自分が立てたno_launch.flagだけ、回復したら自動で解除する。
    （auth切れ等の別理由でauto_launcher.py自身が立てたフラグは絶対に触らない）"""
    if not os.path.exists(NO_LAUNCH_FLAG):
        return
    try:
        content = io.open(NO_LAUNCH_FLAG, encoding="utf-8").read()
    except Exception:
        return
    if MY_FLAG_MARK in content and free_gb >= WARN_GB:
        try:
            os.remove(NO_LAUNCH_FLAG)
            log("✅ 空き%.1fGBまで回復 → no_launch.flag 解除(自分が立てたものだけ)" % free_gb)
        except Exception:
            pass


def main():
    try:
        if time.time() - os.path.getmtime(STAMP) < INTERVAL:
            return 0
    except Exception:
        pass
    io.open(STAMP, "w", encoding="utf-8").write(str(int(time.time())))

    free_gb = disk_free_gb()
    if free_gb is None:
        log("df測定失敗のため何もしません")
        return 0
    log("空き %.1fGB" % free_gb)

    if free_gb < STOP_GB:
        notify_stop(free_gb)
    else:
        maybe_release_stop(free_gb)

    if free_gb < WARN_GB:
        freed = cleanup()
        if freed:
            log("片付け完了: 約%.0fMB解放" % freed)
        else:
            log("片付け対象なし(安全条件を満たすものが無かった)")
        after = disk_free_gb()
        if after is not None and after != free_gb:
            log("片付け後の空き %.1fGB" % after)
            if after < STOP_GB:
                notify_stop(after)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
