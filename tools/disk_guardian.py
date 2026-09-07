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
     - joy-relief-station の作業場(.worktrees・.claude/worktrees の両方)の node_modules
       （bun/npm installで作り直せる。tools/worktree_reaper.py と同じ考え方を流用）
     - 7日以上前のログ
     - __pycache__
     - ビルド成果物(dist / .output)
  ③ 20GBを切ったら発車を止めてDispatchへ知らせる（status/no_launch.flag を作る。
     auto_launcher.py が既にこのフラグを見て発車を止める仕組みを持っている＝新規実装不要）
  ④ 壺と金庫は絶対に触らない：写真・動画・音楽・Eagleライブラリ・Vault・Driveの中身・
     ソフトウェアのdmg。迷ったら触らない（パスにキーワードが1つでも含まれたら問答無用でスキップ）
  ⑤ 何を消して何GB空いたかを1行ずつログに残す(status/disk_guardian.log)

このスクリプトは削除範囲を「joy-relief-station の .worktrees 配下・.claude/worktrees 配下」
「tamago-shinchoku / joy-relief-station の tools・scripts 配下の __pycache__」
「tamago-shinchoku/status の7日超ログ」に明示的に限定している。それ以外のディレクトリには
一切降りない。
"""
import glob
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
# 2026-09-06（430番）：作業場は `.worktrees` だけでなく `.claude/worktrees` にも
# 大量にできる（Claude Codeのworktreeエージェント機能）。ここは元々見張り対象に
# 入っておらず、実測で node_modules だけで約8.7GB、dist/.output で約3.4GB、
# 合計12GB超が野放しになっていた＝17GB切れの主因。以後はここも見張る。
# 2026-09-06（491番検品で発覚・追加）：同じ2026-09-06に auto_launcher.py 側が
# 「他のAIツールの索引を汚さない」対応で作業場の主置き場を
# `/Users/mac/Documents/AI作業/.worktrees` へ移設していた（joy-relief-station配下は
# フォールバックのみ）。この新しい主置き場を見ておらず実測21件・約1.6GBが野放しに
# なっていたため追加した。
AI_WORK_WT = "/Users/mac/Documents/AI作業/.worktrees"
WT_DIRS = (WT_DIR, os.path.join(JOY, ".claude", "worktrees"), AI_WORK_WT)
QUEUE = os.path.join(REPO, "status", "queue.json")

LOG = os.path.join(REPO, "status", "disk_guardian.log")
STAMP = os.path.join(REPO, "status", ".disk_guardian_at")
NO_LAUNCH_FLAG = os.path.join(REPO, "status", "no_launch.flag")
# 2026-09-06（491番）：確認ページに「いまの空き」「消せる候補の一覧（消さずに一覧だけ）」を
# 出せるようにするための保存先。dump_candidates() が15分おきに上書きするだけで、
# candidates() 自体のロジック（壺金庫ガード・許可範囲）には一切触らない。
CANDIDATES_JSON = os.path.join(REPO, "status", "disk_candidates.json")
MY_FLAG_MARK = "容量見張り"  # 自分が書いたno_launch.flagだけを自動解除するための目印

INTERVAL = 900          # 15分に1回でよい。既存の5分間隔ジョブ(machine_status_push.sh)から
                        # 毎回呼ばれても、STAMPファイルで前回実行から900秒未満ならすぐ戻る
                        # （＝実質15分おき）。launchdの新規登録が2回ブロックされたため、
                        # 既に動いている5分間隔ジョブへの相乗り方式に切り替えた(2026-09-06)。
MIN_AGE_SEC = 2 * 3600  # 触ってから2時間は残す（走行中の作業場を守る）
OLD_LOG_SEC = 7 * 86400  # 7日以上前のログだけ対象

# 2026-09-06 03:20 **閾値を下げた。この見張りが工場を丸ごと止めてしまったため。**
#   17.4GB残っていて発車0本・待機22本という、たまごさんが一番嫌う状態を作った。
#   たまごさんの最上位の決まりは「止まるのが最悪。何も進んでいないのが最悪」。
#   実際、コードを直す仕事なら17GBあれば何の問題もなく走る。足りなくなるのは
#   動画を作るときだけ。**容量を守るために工場を止めるのは、目的と手段が逆。**
WARN_GB = 25   # これを切ったら安全な片付けを実行
STOP_GB = 8    # 本当に危ないときだけ止める（macOSが不安定になる手前）

# ④ 壺と金庫：迷ったら触らない。パスにこれらの文字列を含んでいたら問答無用でスキップする。
FORBIDDEN_KEYWORDS = (
    "CloudStorage", "Eagle", "Vault", "Google Drive", "GoogleDrive",
    "Photos", "Movies", "Music", ".dmg", "tamago_brain", "iCloud",
    "Pictures", "iCloud~md~obsidian",
)

# 2026-09-07（620番・容量急減の原因調査）：ここまでの監視対象（作業場のnode_modules・
# __pycache__・7日超ログ）は全部合わせても数GB規模で、実際に急減の主犯だった
# 「OS/アプリの一時キャッシュ」（合計で当日8GB超・実測）が完全に監視の外だった。
# 以下はいずれもOS/アプリが自動的に作り直す一時データであり、店主の壺・金庫
# （写真・Vault・Drive実体・Eagle・Xアーカイブ・fal成果物）とは無関係。
HOME = os.path.expanduser("~")
APP_CACHE_ROOTS = (
    # iCloud(CloudKit)がアップロード時に作る一時クローン。同期のたび生成され、
    # 消しても次回同期時に再生成されるだけ（実測3.3GB・5187ファイル）。
    os.path.join(HOME, "Library/Caches/CloudKit"),
    # Sparkle(多くのMacアプリの自動更新機構)のダウンロード・インストールキャッシュ。
    # 更新後も旧バージョンのインストーラを消さずに溜め込む（Codex実測1.3GB）。
    os.path.join(HOME, "Library/Caches/com.openai.codex/org.sparkle-project.Sparkle"),
    os.path.join(HOME, "Library/Caches/com.brave.Browser/org.sparkle-project.Sparkle/PersistentDownloads"),
    os.path.join(HOME, "Library/Application Support/BraveSoftware/Brave-Browser/component_crx_cache"),
    os.path.join(HOME, "Library/Caches/notion-updater"),
    # pipのHTTPキャッシュ。再ダウンロードで作り直せる（実測439MB）。
    os.path.join(HOME, "Library/Caches/pip"),
)
APP_CACHE_MIN_AGE_SEC = 3 * 86400  # 3日以上さわられていないものだけ

# 2026-09-07（620番タスクC・監視対象の拡張）：ブラウザ自動操作プロファイル
# （鬼監督=oni-kantoku・Lovable公開便=chrome-publish）はChrome本体と同じく
# Cache/Code Cache/GPUCache配下に再生成可能な一時データを溜め込む。実測ログ
# （620番）でこの種のプロファイルキャッシュが完全に監視対象外だったと判明した。
# プロファイル名は実行のたび増える/複数並存するため固定パスでは拾えない→globで
# 都度展開する。Cookie・Login Data等の実データ（ログインセッション）には触れない。
APP_CACHE_GLOB_PATTERNS = (
    "/tmp/oni-kantoku-chrome-profile*",
    os.path.join(HOME, ".tamago", "chrome-publish"),
)
APP_CACHE_SUBDIRS = ("Default/Cache", "Default/Code Cache", "Default/GPUCache",
                      "Cache", "Code Cache", "GPUCache")


def _glob_app_cache_roots():
    """globパターンを展開し、実在するCache系サブフォルダだけを返す（毎回動的に解決）。"""
    roots = []
    for pattern in APP_CACHE_GLOB_PATTERNS:
        for base in glob.glob(pattern):
            if not os.path.isdir(base):
                continue
            for sub in APP_CACHE_SUBDIRS:
                sp = os.path.join(base, sub)
                if os.path.isdir(sp):
                    roots.append(sp)
    return tuple(roots)


# 2026-09-07：~/.claude/projects（並行セッションのtranscript・tool-results置き場、
# 実測3.3GB超）の添付出力を「候補として見せるだけ」の対象にする。transcript本体
# (.jsonl)は復旧の頼り（Remote Control運用）のため対象外、UUIDサブフォルダ配下
# だけをサイズ測定する。cleanup()からは明示的に除外し、絶対に自動では消さない。
CLAUDE_PROJECTS = os.path.join(HOME, ".claude", "projects")
CLAUDE_SESSION_MIN_AGE_SEC = 14 * 86400  # 14日以上更新の無いセッションだけ候補に出す


def allowed_roots():
    """片付けを許す範囲（この外には一切降りない）。app cacheはglob展開があるため
    毎回動的に解決する（起動時に存在しなかったプロファイルも後から拾えるように）。"""
    return WT_DIRS + APP_CACHE_ROOTS + _glob_app_cache_roots() + (
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
    return any(ap == r or ap.startswith(r + os.sep) for r in allowed_roots())


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

    for wt_dir in WT_DIRS:
        if not os.path.isdir(wt_dir):
            continue
        for name in sorted(os.listdir(wt_dir)):
            path = os.path.join(wt_dir, name)
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

    # 2026-09-07追加：OS/アプリの一時キャッシュ（中身だけ消す。ルート自体は残す＝
    # 次回そのアプリが自分で作り直せるようにする）。
    for root in APP_CACHE_ROOTS + _glob_app_cache_roots():
        if not os.path.isdir(root) or not is_allowed(root):
            continue
        try:
            entries = os.listdir(root)
        except Exception:
            continue
        for fn in entries:
            fp = os.path.join(root, fn)
            if not is_allowed(fp):
                continue
            try:
                age_ok = (time.time() - os.path.getmtime(fp)) >= APP_CACHE_MIN_AGE_SEC
            except Exception:
                age_ok = False
            out.append({"path": fp, "kind": "app_cache", "worktree": "-",
                        "protected": False, "age_ok": age_ok, "size_mb": dir_size_mb(fp)})

    # 2026-09-07（620番タスクC）：~/.claude/projects配下の古いセッションの添付出力
    # （tool-results等）をサイズ測定して候補一覧にだけ出す。transcript本体(.jsonl)は
    # 復旧の頼りのため対象にしない。**ここは常に候補表示のみ・cleanup()側で明示的に
    # 除外し、自動削除の対象条件を満たしても絶対に消さない**（迷ったら消さない方針）。
    if os.path.isdir(CLAUDE_PROJECTS):
        try:
            proj_names = os.listdir(CLAUDE_PROJECTS)
        except Exception:
            proj_names = []
        for proj in proj_names:
            proj_path = os.path.join(CLAUDE_PROJECTS, proj)
            if not os.path.isdir(proj_path):
                continue
            try:
                entries = os.listdir(proj_path)
            except Exception:
                continue
            for name in entries:
                sub = os.path.join(proj_path, name)
                if not os.path.isdir(sub):
                    continue  # .jsonl本体（transcript）はここでは対象にしない
                try:
                    age = time.time() - os.path.getmtime(sub)
                except Exception:
                    continue
                out.append({
                    "path": sub, "kind": "claude_session_attachments", "worktree": "-",
                    "protected": False, "age_ok": age >= CLAUDE_SESSION_MIN_AGE_SEC,
                    "size_mb": dir_size_mb(sub),
                })

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
        # 2026-09-07：~/.claude/projects の添付出力は候補一覧に見せるだけの対象。
        # age_ok条件を満たしても、ここで明示的に弾いて自動削除しない（人の目待ち）。
        if c["kind"] == "claude_session_attachments":
            continue
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
    # 2026-09-06 03:20 **自分で止めたのに、自分で外せない条件になっていた。**
    #   止める線(20GB)より外す線(30GB)の方が高かったので、17GBのまま永久に止まり続けた。
    #   走行0本・待機22本という最悪の状態を作った。**外す線は止める線より少しだけ上にする。**
    if MY_FLAG_MARK in content and free_gb >= STOP_GB + 2:
        try:
            os.remove(NO_LAUNCH_FLAG)
            log("✅ 空き%.1fGBまで回復 → no_launch.flag 解除(自分が立てたものだけ)" % free_gb)
        except Exception:
            pass


def dump_candidates(free_gb):
    """いまの空きと消せる候補の一覧を確認ページ用に保存するだけ（ここでは何も消さない）。"""
    try:
        cs = sorted(candidates(), key=lambda c: -c.get("size_mb", 0))
        data = {
            "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "free_gb": round(free_gb, 1),
            "warn_gb": WARN_GB,
            "stop_gb": STOP_GB,
            "candidates": cs,
        }
        with io.open(CANDIDATES_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log("候補一覧の保存に失敗: %s" % e)


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
    dump_candidates(free_gb)

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
