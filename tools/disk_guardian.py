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
import sys
import time

# 2026-09-08（648番・「容量の減りが止まったかを24時間測って証明する」）：
# disk_trend.pyは同じtools/配下の新規モジュール。日次の推移レポート(JSON+SVGグラフ)
# と「1時間で1GB以上減った時間帯の犯人候補」を作る。失敗してもdisk_guardian.py本体の
# 安全動作（片付け・発車停止判定）を壊さないよう、import自体を例外安全にする。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import disk_trend
except Exception:
    disk_trend = None

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

# 2026-09-08（640番・128GBキャッシュ調査の副産物）：本命は
# ~/Library/CloudStorage/GoogleDrive-*/マイドライブ配下の「オフラインで利用可能」指定
# フォルダ(実測125GB)だったが、これは fileproviderctl evict が
# contentPolicy(=常に手元に置く指定)で明示的に拒否する(Error 35)ことを実機で確認済み
# ＝GUI側で「オフラインのアクセスを解除」を1回押す以外に安全な自動解除経路が無い
# （FORBIDDEN_KEYWORDSのCloudStorage/GoogleDrive/Musicにより本スクリプトは元々この
# フォルダの中には一切降りない＝正しい挙動、変更不要）。
# 代わりに実機調査で見つかった「壺金庫と無関係な安全采キャッシュ」を追加する：
#   - joy-relief-station 本体(Desktop直下・worktreeではない)のnode_modules/dist/.output
#     （bun/npm installで作り直せる。実測424MB。稼働中プロセスが無いことを確認済み）
#   - Spotify/Python/bun/node-gyp のアプリキャッシュ（いずれも実測時プロセス未実行・
#     再生成される一時データ。実測 Spotify285MB+Python173MB+bun172MB+node-gyp64MB）
MAIN_REPO_DIR = JOY  # Desktop直下の本体（.worktreesではない）
APP_CACHE_ROOTS = APP_CACHE_ROOTS + (
    os.path.join(HOME, "Library/Caches/com.spotify.client"),
    os.path.join(HOME, "Library/Caches/com.apple.python"),
    os.path.join(HOME, "Library/Caches/bun"),
    os.path.join(HOME, "Library/Caches/node-gyp"),
)

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


TRASH_DIR = os.path.join(HOME, ".Trash")
# 2026-09-09（685番・「1日20GB減る」原因追及）：ゴミ箱は店主が既に「消す」と
# 決めたものの最終置き場。実測で2020〜2023年の古いインストーラ(.dmg等)が
# 16.4GB居座っていた（Finderで「ゴミ箱を空にする」を押し忘れているだけ）。
# ただし「うっかり削除して数分後に戻したい」を守るため、7日以上経過した
# トップレベル項目だけを対象にする（直近のworktree_reaper_ghosts等は対象外）。
TRASH_MIN_AGE_SEC = 7 * 86400

def allowed_roots():
    """片付けを許す範囲（この外には一切降りない）。app cacheはglob展開があるため
    毎回動的に解決する（起動時に存在しなかったプロファイルも後から拾えるように）。"""
    return WT_DIRS + APP_CACHE_ROOTS + _glob_app_cache_roots() + (
        os.path.join(REPO, "tools"),
        os.path.join(REPO, "status"),
        os.path.join(JOY, "tools"),
        os.path.join(JOY, "scripts"),
        # 2026-09-08（640番）：本体(Desktop直下)のnode_modules/dist/.outputだけを
        # 名指しで許可。JOY全体は許可しない（srcや.git等を誤って対象化しないため）。
        os.path.join(MAIN_REPO_DIR, "node_modules"),
        os.path.join(MAIN_REPO_DIR, "dist"),
        os.path.join(MAIN_REPO_DIR, ".output"),
        # 2026-09-09（685番）：ゴミ箱トップレベル項目（7日以上経過分のみ候補化）。
        TRASH_DIR,
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

    # 2026-09-08（640番）：joy-relief-station 本体(Desktop直下・worktreeではない)の
    # node_modules/dist/.output。WT_DIRSは.worktrees配下しか見ないため、本体側は
    # 監視対象外のまま実測424MB(node_modules)が野放しだった。稼働中の開発サーバの
    # cwdと一致しないことを実行時に確認した上で追加（走行中の作業場は触らない方針を
    # MAIN_REPO_DIRでも踏襲）。
    if os.path.isdir(MAIN_REPO_DIR) and MAIN_REPO_DIR not in guard:
        for sub in ("node_modules", "dist", ".output"):
            sp = os.path.join(MAIN_REPO_DIR, sub)
            if os.path.isdir(sp) and is_allowed(sp):
                try:
                    age_ok = (time.time() - os.path.getmtime(sp)) >= MIN_AGE_SEC
                except Exception:
                    age_ok = False
                out.append({
                    "path": sp, "kind": sub, "worktree": "joy-relief-station(本体)",
                    "protected": False, "age_ok": age_ok,
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

    # 2026-09-09（685番）：ゴミ箱（~/.Trash）直下のトップレベル項目。店主が既に
    # Finderで「削除」を選んだ後の最終置き場であり、中身は既にis_forbidden()
    # （Eagle/Vault/CloudStorage/Photos等のキーワード）でも二重に守られる。
    # 7日以上ゴミ箱にあるものだけを候補にする（うっかり削除の救済期間）。
    if os.path.isdir(TRASH_DIR) and is_allowed(TRASH_DIR):
        try:
            trash_entries = os.listdir(TRASH_DIR)
        except Exception:
            trash_entries = []
        for fn in trash_entries:
            if fn in (".DS_Store",):
                continue
            fp = os.path.join(TRASH_DIR, fn)
            if is_forbidden(fp) or not is_allowed(fp):
                continue
            try:
                age_ok = (time.time() - os.path.getmtime(fp)) >= TRASH_MIN_AGE_SEC
            except Exception:
                age_ok = False
            out.append({"path": fp, "kind": "trash_old", "worktree": "-",
                        "protected": False, "age_ok": age_ok, "size_mb": dir_size_mb(fp)})
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


# 2026-09-07（620番・容量急減の主犯特定）：Google Drive「マイドライブ」直下は
# 壺金庫（FORBIDDEN_KEYWORDSに"CloudStorage"等が入っており、絶対に自動削除しない）
# だが、それゆえにここに何十GBという重複ファイルが置かれても誰も気づけなかった。
# 実例：「音楽ライブラリまるごとバックアップ_iMacHDDの控え_2026-09-02」125GB。
# Google Drive Desktopの同期方式が「ミラーリング」だと、クラウドと同じ量が
# そのままローカルディスクにも専有される（`fileproviderctl evict`で一時的に
# ローカル実体を消しても、同期デーモインが数分〜十数分で再ダウンロードし直すことを
# 620番で実測確認済み＝恒久解決にはGoogle Drive Desktopアプリの環境設定で
# 「ファイルをストリーミングする」に切り替えるか、対象フォルダを右クリックして
# 「オフラインのアクセスを解除」するGUI操作が必要。自動削除はしない、警告するだけ）。
GDRIVE_WARN_GB = 50

# 2026-09-08（642番・「工場がGoogleドライブから読むのをやめる」）：
# ★このgdrive_big_folder_warnings()自体が「Driveを読む＝容量を食う」を
#   毎回やっていた張本人だった。disk_guardian.pyはINTERVAL=900秒（15分おき）で
#   1日96回動く。そのたびに Drive の「マイドライブ」直下フォルダ全部へ
#   `du -sm`（=配下の全ファイルへstat）を実行していた＝1日96回、Driveを丸ごと
#   舐めていたことになる。たまごさんの指示「Driveを丸ごと走査しない」に反する。
# ★直し方：実測（du）は1日1回だけに制限し、それ以外の呼び出しはキャッシュ
#   （GDRIVE_CACHE_JSON）を返すだけにした。これで指示の
#   「毎日1回、Driveのローカル使用量を測って記録する」も同時に満たす。
GDRIVE_CHECK_INTERVAL_SEC = 86400  # 1日1回でよい（巨大フォルダの増減はそんなに速く動かない）
GDRIVE_STAMP = os.path.join(REPO, "status", ".gdrive_check_at")
GDRIVE_CACHE_JSON = os.path.join(REPO, "status", "gdrive_daily_usage.json")


def _gdrive_measure_now():
    """実際にduを叩いて測る（1日1回だけ呼ばれる想定。ここ以外からdu -smをDriveへ打たない）。"""
    warnings = []
    try:
        base_glob = os.path.join(HOME, "Library", "CloudStorage", "GoogleDrive-*", "マイドライブ")
        for base in glob.glob(base_glob):
            if not os.path.isdir(base):
                continue
            try:
                entries = os.listdir(base)
            except Exception:
                continue
            for name in entries:
                p = os.path.join(base, name)
                if not os.path.isdir(p):
                    continue
                size_gb = dir_size_mb(p) / 1024.0
                if size_gb >= GDRIVE_WARN_GB:
                    warnings.append({"path": p, "size_gb": round(size_gb, 1)})
    except Exception as e:
        log("Google Drive警告チェック失敗: %s" % e)
    return warnings


def gdrive_big_folder_warnings():
    """Google Driveの「マイドライブ」直下でGDRIVE_WARN_GBを超えるフォルダを
    見つけたら警告として返すだけ（壺金庫なので絶対に削除しない）。
    2026-09-08(642番)：実測(du)は1日1回だけ。それ以外は前回結果のキャッシュを返す
    （＝Driveへ触りに行かない）。"""
    now = time.time()
    try:
        last = os.path.getmtime(GDRIVE_STAMP)
    except Exception:
        last = 0
    if now - last < GDRIVE_CHECK_INTERVAL_SEC:
        try:
            cached = json.load(io.open(GDRIVE_CACHE_JSON, encoding="utf-8"))
            return cached.get("warnings", [])
        except Exception:
            return []

    warnings = _gdrive_measure_now()
    try:
        io.open(GDRIVE_STAMP, "w", encoding="utf-8").write(str(int(now)))
    except Exception:
        pass
    try:
        with io.open(GDRIVE_CACHE_JSON, "w", encoding="utf-8") as f:
            json.dump({
                "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "warnings": warnings,
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log("Google Drive日次キャッシュ保存失敗: %s" % e)
    return warnings


# 2026-09-07（620番）：tamago-shinchoku自身のshare/配下（確認ページ・Eagle共有画像）も
# 「毎回増え続けるが誰も測っていない」状態だった。ここも自動削除はせず、サイズを
# ログに残して見える化するだけに留める（確認ページの実物が消えると困るため）。
SHARE_WATCH_DIRS = ("check", "eagle-k7m2xq9p")


def share_dir_sizes():
    sizes = {}
    for name in SHARE_WATCH_DIRS:
        p = os.path.join(REPO, "share", name)
        if os.path.isdir(p):
            sizes[name] = dir_size_mb(p)
    return sizes


# 2026-09-08（645番・「二度と減らない形にする」）：空き容量に応じて同時走行本数
# (status/launch_cap.json の cap)を自動で絞る。クレジット枠管理など他の理由で
# 既に低いcapが設定されている場合はそちらを優先し、壊さない（自分が設定した分だけ
# 自動で戻す＝maybe_release_stop()と同じ「自分の後始末は自分でする」方式）。
LAUNCH_CAP_JSON = os.path.join(REPO, "status", "launch_cap.json")
LAUNCH_CAP_MARK = "容量見張り"
LAUNCH_CAP_WARN_GB = 30  # これを切ったら2本
LAUNCH_CAP_STOP_GB = 15  # これを切ったら1本


def _load_json(path, default=None):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def maybe_adjust_launch_cap(free_gb):
    if free_gb < LAUNCH_CAP_STOP_GB:
        desired = 1
    elif free_gb < LAUNCH_CAP_WARN_GB:
        desired = 2
    else:
        desired = None

    cur = _load_json(LAUNCH_CAP_JSON, {})
    is_mine = cur.get("source") == LAUNCH_CAP_MARK

    if desired is not None:
        if is_mine and cur.get("cap") == desired:
            return  # 既に自分が同じ値を設定済み
        if not is_mine and isinstance(cur.get("cap"), int) and cur.get("cap") <= desired:
            return  # 他の理由(クレジット枠等)の方が既に厳しいか同等 → 触らない
        prev_cap = cur.get("_prev_cap") if is_mine else cur.get("cap")
        prev_why = cur.get("_prev_why") if is_mine else cur.get("why")
        try:
            with io.open(LAUNCH_CAP_JSON, "w", encoding="utf-8") as f:
                json.dump({
                    "cap": desired,
                    "source": LAUNCH_CAP_MARK,
                    "_prev_cap": prev_cap,
                    "_prev_why": prev_why,
                    "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "why": "%s：空き%.1fGB<%dGBのため走行上限を%d本に制限" % (
                        LAUNCH_CAP_MARK, free_gb,
                        LAUNCH_CAP_STOP_GB if desired == 1 else LAUNCH_CAP_WARN_GB, desired),
                }, f, ensure_ascii=False, indent=1)
            log("🐢 空き%.1fGB → 走行上限を%d本に制限(launch_cap.json)" % (free_gb, desired))
        except Exception as e:
            log("launch_cap.json書き込み失敗: %s" % e)
    else:
        if is_mine:
            prev_cap = cur.get("_prev_cap")
            restored = {
                "cap": prev_cap if isinstance(prev_cap, int) else 5,
                "why": cur.get("_prev_why") or "容量見張り解除により復帰",
                "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            try:
                with io.open(LAUNCH_CAP_JSON, "w", encoding="utf-8") as f:
                    json.dump(restored, f, ensure_ascii=False, indent=1)
                log("✅ 空き%.1fGBまで回復 → 走行上限を元(%s本)に戻しました" % (free_gb, restored["cap"]))
            except Exception as e:
                log("launch_cap.json復元失敗: %s" % e)


# 2026-09-08（645番・「毎日1回、空き容量を記録。前日比-5GBを超えたら犯人を特定して報告」）：
# 1日1回だけ空き容量を履歴に積む。前日との差が-5GBを超えたら警告をログへ残す
# （犯人の自動特定まではしない＝status/history.jsonlとの突き合わせは人/Dispatch側で行う）。
DAILY_HISTORY_JSON = os.path.join(REPO, "status", "disk_daily_history.json")
DAILY_DROP_WARN_GB = 5


def maybe_record_daily(free_gb):
    today = time.strftime("%Y-%m-%d")
    hist = _load_json(DAILY_HISTORY_JSON, {"days": []})
    days = hist.get("days") or []
    if days and days[-1].get("date") == today:
        return  # 今日はもう記録済み
    prev_free = days[-1].get("free_gb") if days else None
    days.append({"date": today, "free_gb": round(free_gb, 1),
                 "measured_at": time.strftime("%Y-%m-%d %H:%M:%S")})
    days = days[-90:]  # 90日分だけ残す
    try:
        with io.open(DAILY_HISTORY_JSON, "w", encoding="utf-8") as f:
            json.dump({"days": days}, f, ensure_ascii=False, indent=1)
    except Exception as e:
        log("日次履歴の保存失敗: %s" % e)
        return
    if prev_free is not None and (prev_free - free_gb) > DAILY_DROP_WARN_GB:
        # 2026-09-08（648番）：犯人特定まで自動化する（disk_trend.find_culprits）。
        # 前回記録〜今回記録の間にhistory.jsonlへ記録されていたタスク番号を突き合わせる。
        cause = "特定できず"
        if disk_trend is not None and days and len(days) >= 2:
            try:
                t1 = time.strptime(days[-2]["measured_at"], "%Y-%m-%d %H:%M:%S")
                t2 = time.strptime(days[-1]["measured_at"], "%Y-%m-%d %H:%M:%S")
                import datetime as _dt
                nums, _titles = disk_trend.find_culprits(
                    _dt.datetime(*t1[:6]), _dt.datetime(*t2[:6]))
                if nums:
                    cause = "・".join(nums)
            except Exception:
                pass
        log("⚠️前日比-%.1fGB(前日%.1fGB→今日%.1fGB)。原因候補：%s"
            % (prev_free - free_gb, prev_free, free_gb, cause))
    elif prev_free is not None:
        log("📊 容量見張り日次：変化なし(前日%.1fGB→今日%.1fGB)" % (prev_free, free_gb))

    # 1日1回、24時間トレンドレポート(JSON+SVGグラフ)も更新する（同じ日次タイミングに相乗り。
    # 新規launchd登録はしない＝642番までの教訓と同じ理由）。
    if disk_trend is not None:
        try:
            r = disk_trend.build_report()
            stable = r.get("stable_period_since_trough")
            if stable:
                log("📈 直近の山(%s・%.1fGB)以降%sh経過、いま%.1fGB → %s"
                    % (stable["since"], stable["since_free_gb"], stable["hours"],
                       stable["now_free_gb"], stable["verdict"]))
        except Exception as e:
            log("容量トレンドレポート生成失敗: %s" % e)


# 2026-09-08（645番）：share/check・share/eagle-* に上限を設け、超えたら古いものから
# 外付け(/Volumes/iMac HDD)へ移す。GitHub Pagesの確認ページなので、直近だけ手元(=リポジトリ)
# に残し、古いものは archive フォルダへ実体を移してから git rm する（次回pushで反映）。
SHARE_CHECK_DIR = os.path.join(REPO, "share", "check")
SHARE_CHECK_KEEP = 30
# 2026-09-08 17:35 やり直し。**「件数」で捨てたのが間違いだった。**
#   645番で「直近30件だけ残す」にした結果、256件の確認ページが外付けへ出て、
#   **たまごさんに渡してきた確認URLが軒並み404になった。**
#   鬼監督に古い確認待ちを見せたら、ページが開けないという理由で
#   「すでに終わっている仕事」を次々に不合格にし、作り直しの列へ戻し始めた（実測4件）。
#   確認ページはたまごさんへの領収書であり、**リンクが死ぬこと自体が損害。**
#   重いのはページ数ではなく、中に埋め込んだ画像。258件のHTMLを全部足しても33MB。
#   → **軽いページは何件でも残す。重いページだけを、新しい方から30件残して外へ出す。**
SHARE_CHECK_BIG_KB = 500     # これを超えるものだけを「重いページ」として扱う
EXTERNAL_ARCHIVE_ROOT = "/Volumes/iMac HDD/tamago-shinchoku-archive/share-check"


def archive_old_share_check(dry_run=True):
    """share/check直下の.htmlのうち、**重いもの**（SHARE_CHECK_BIG_KB超）だけを対象に、
    更新日時が新しい順にSHARE_CHECK_KEEP件だけ残し、それ以外を外付けへ移す候補を返す。
    軽いページ（＝ほぼ全部の確認ページ）は、何件あっても動かさない。リンクを殺さないため。"""
    if not os.path.isdir(SHARE_CHECK_DIR):
        return []
    # "_"始まりはテンプレート・集計ファイル（_template.html等）。仕組みが壊れるため対象外。
    files = [f for f in os.listdir(SHARE_CHECK_DIR)
             if f.endswith(".html") and not f.startswith("_")]
    big = []
    for f in files:
        p = os.path.join(SHARE_CHECK_DIR, f)
        try:
            if os.path.getsize(p) > SHARE_CHECK_BIG_KB * 1024:
                big.append((f, os.path.getmtime(p)))
        except Exception:
            pass
    files_full = sorted(big, key=lambda x: -x[1])
    old = [f for f, _ in files_full[SHARE_CHECK_KEEP:]]
    if dry_run or not old:
        return old
    if not os.path.isdir("/Volumes/iMac HDD"):
        log("share/check整理: 外付け未接続のためスキップ")
        return []
    os.makedirs(EXTERNAL_ARCHIVE_ROOT, exist_ok=True)
    moved = []
    for f in old:
        src = os.path.join(SHARE_CHECK_DIR, f)
        dst = os.path.join(EXTERNAL_ARCHIVE_ROOT, f)
        try:
            shutil.move(src, dst)
            moved.append(f)
        except Exception as e:
            log("share/check移動失敗 %s: %s" % (f, e))
    if moved:
        log("📦 share/checkから%d件を外付けへ移動(直近%d件は保持)" % (len(moved), SHARE_CHECK_KEEP))
    return moved


def dump_candidates(free_gb):
    """いまの空きと消せる候補の一覧を確認ページ用に保存するだけ（ここでは何も消さない）。"""
    try:
        cs = sorted(candidates(), key=lambda c: -c.get("size_mb", 0))
        gdrive_warnings = gdrive_big_folder_warnings()
        share_sizes = share_dir_sizes()
        data = {
            "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "free_gb": round(free_gb, 1),
            "warn_gb": WARN_GB,
            "stop_gb": STOP_GB,
            "candidates": cs,
            "gdrive_big_folder_warnings": gdrive_warnings,
            "share_dir_sizes_mb": share_sizes,
        }
        with io.open(CANDIDATES_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        for w in gdrive_warnings:
            log("⚠️Google Drive巨大フォルダ(壺金庫のため未削除・要GUI対応): %.1fGB %s"
                % (w["size_gb"], w["path"]))
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
    maybe_record_daily(free_gb)
    maybe_adjust_launch_cap(free_gb)

    # 2026-09-08（645番）：share/checkの件数上限は「ディスクが逼迫しているか」とは
    # 無関係に常時守る（30件超がそのまま放置され続けないように、毎回チェックする）。
    # git rm・commit・pushはここでは行わない（既存の自動コミットジョブが拾う）。
    archive_old_share_check(dry_run=False)

    # 2026-09-09（685番・「ダウンロードは全部iMac HDDを使うようにしてほしい」）：
    # ~/Downloadsフォルダ自体を外付けへのシンボリックリンクに置き換える理想形は、
    # macOSのTCC保護でPermission Deniedとなり実行不可（GUI側の許可が必要・店主のみ
    # 可能な操作）と実測確認済み。次善策として、3日以上経ったダウンロードだけを
    # 自動で外付けへ退避する係をここから間借りして動かす（launchctl loadが
    # このセッションの権限では拒否されたため、既に動いているこのジョブへ相乗り）。
    try:
        sys.path.insert(0, HERE)
        import downloads_offload
        downloads_offload.main()
    except Exception as e:
        log("downloads_offload呼び出し失敗: %s" % e)

    # 2026-09-09（685番）：ゴミ箱の7日超項目は、空き容量の逼迫（WARN_GB=25）を
    # 待たずに常時片付ける。店主が既に「削除」を選んだ後の最終置き場であり、
    # 実測で2020〜2023年の古いインストーラが16.4GB居座っていた
    # （＝Finderで「空にする」を押し忘れているだけの死蔵容量）。
    try:
        trash_freed = 0.0
        for c in candidates():
            if c["kind"] == "trash_old" and c["age_ok"] and not c["protected"]:
                trash_freed += safe_remove(c["path"], c["kind"])
        if trash_freed:
            log("🗑ゴミ箱の7日超項目を片付け: 約%.0fMB解放" % trash_freed)
    except Exception as e:
        log("ゴミ箱掃除失敗: %s" % e)

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
