#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
発車待ち（status/queue.json）から、空きができたら自動で次を着火する。

2026-09-04 たまごさん：
  「**まず連続して走る仕組みを優先してね。**」
  「順番に発車されるようにして、クレジットとバランスを取って、1日中回ってる状態を作るのが最優先だよ。」
  「**全部3時間縛り。もう報告ね、URLとともに報告。これがセット。**」

やること（5分おきに machine_status_push.sh から呼ばれる）:
  1. いま何本走っているかを machine.json から読む（Dispatch本体と完了済みは数えない）
  2. 空きがあるか判定：マシン（safeMax）とクレジット（週枠・5時間枠）の両方を見る
  3. 空きがあれば queue.json の先頭（優先度順）を1件だけ着火する
     - git worktree を切る
     - claude -p --session-id <新規> --model claude-sonnet-5 で起動
     - プロンプトに「3時間で切る」「1セット＝実装→main合流→Lovable公開→本番確認→URL報告」を必ず入れる
  4. 着火したら queue.json のその項目を running にして、走行中の記録を残す

安全弁:
  - Macが危険（メモリ圧=赤／スワップ増／ディスク空き5GB未満）なら着火しない
  - 週枠が stop なら着火しない（クレジットの天井に着かせない）
  - 1回の実行で着火するのは1本まで
  - Fableは使わない（no_fable.flag があるかに関わらず、ここでは常にSonnet）
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cost_risk  # noqa: E402  案件#676：お金がかかるタスクの自動判定・確認文言
import redo_guard  # noqa: E402  案件#797：やり直し合計2回でstuck化する共通ガード
import queue_store  # noqa: E402  案件#687：queue.jsonの安全な読み書き（差分マージ・世代バックアップ）
import shukan_kubun  # noqa: E402  週の作業配分：見たいもの／裏方／予備の分類
import shukan_haibun  # noqa: E402  週の作業配分：実績集計とゲート判定（裏方30%上限）
import sekisho  # noqa: E402  案件#898：関所＝報告の手前に置く機械の門（数字の主張と実測の食い違い等）
CLAUDE_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
QUEUE = os.path.join(REPO, "status", "queue.json")
MACHINE = os.path.join(REPO, "status", "machine.json")
QUOTA = os.path.join(REPO, "status", "quota.json")
PRIORITY = os.path.join(REPO, "status", "priority.json")
LOG = os.path.join(REPO, "status", "auto_launch.log")
# 797番：直近の実発車（本物・空回しテスト問わず）の時刻。genzaichi.py がこれの
# 更新間隔を見て「発車0本が10分続いていないか」を判定する（詳細はgenzaichi.py側）。
LAST_LAUNCH_STAMP = os.path.join(REPO, "status", ".last_launch_at")
# ---- 424番：どの仕事がいくら使ったか見える化（2026-09-06）----
COST_LEDGER = os.path.join(REPO, "status", "cost_by_task.json")
# 単価フォールバック（total_cost_usdが取れなかった時だけ使う）。
# 出典：Vault内に「入力$10/出力$50・100万トークンあたり」の記録は見つからなかった
#   （grep済み・2026-09-06）。依頼文に明記されたこの数値をそのままフォールバック単価として採用する。
#   実際にはほぼ全ての回でclaude -pのJSON出力に total_cost_usd（Anthropic公式単価でCLIが
#   算出済みの実額）が入っているため、フォールバックが使われるのは異常系のみの想定。
FALLBACK_PRICE_IN_PER_1M = 10.0
FALLBACK_PRICE_OUT_PER_1M = 50.0
SONNET = "claude-sonnet-5"
CLAUDE = os.path.expanduser("~/.local/bin/claude")
if not os.path.exists(CLAUDE):
    for c in ("/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if os.path.exists(c):
            CLAUDE = c
            break



# ---- 認証トークン（2026-09-05）----
# `claude setup-token` はキーチェーンに保存せず画面に出すだけなので、
# こちらで ~/.tamago/claude_token（600・git管理外）に置き、起動時に環境変数で渡す。
def claude_env():
    """CLIに渡す環境。**環境変数のトークンは原則使わない**（2026-09-05に実測）。

    `CLAUDE_CODE_OAUTH_TOKEN` はキーチェーンの正しい鍵より優先されるので、
    古い壊れたトークンが1つ残っているだけで工場全体が「期限切れ」になる。
    キーチェーンを正本にし、環境変数を使いたいときだけ ~/.tamago/use_token を置く。
    """
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    if not os.path.exists(os.path.expanduser("~/.tamago/use_token")):
        return env
    p = os.path.expanduser("~/.tamago/claude_token")
    try:
        t = io.open(p, encoding="utf-8").read().strip()
        if t:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = t
    except Exception:
        pass
    return env


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def load(p, default):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return default


def countable(s):
    if s.get("isDispatchSelf"):
        return False
    if s.get("status") in ("完了", "失敗"):
        return False
    return True


# ---- 台帳の鍵（2026-09-05／2026-09-13 queue_store.pyへ集約）----
# たまごさん「完了に入ったものもあれば、反応しないものもあります」の原因。
# 中継所（押したボタン）と心臓（着火・回収）が**同時に台帳を読み書きしていた**ため、
# 片方が1秒前に読んだ古い内容で上書きし、押した結果が消えていた（lost update）。
# 読む→書くの間ずっと鍵をかける。macOSの flock を使う（同一ファイルなので確実）。
# 2026-09-13（案件#687）：鍵とsave_queueの実体は `tools/queue_store.py` に一本化した
#   （command_ingest.py・relay_server.py等、queue.jsonに触る全プロセスで同じ実装を使うため）。
import fcntl  # noqa: F401  他コードが `import fcntl` 経由で使う可能性に配慮し残置
from contextlib import contextmanager  # noqa: F401

QUEUE_LOCK = queue_store.QUEUE_LOCK
queue_lock = queue_store.queue_lock


# ---- 発車係は同時に1つだけ（2026-09-05）----
# 実測：05:21と05:23に**同じ番号が2回発車**した（pid 30405/30494、30918/30919）。
# 心臓（15秒おき）と5分便の両方が auto_launcher を呼ぶため、走り出しが重なると
# 台帳の鍵を取り合う前に「同じ待ち行列」を見てしまう瞬間がある。
# ＝クレジットが二重に減る。**発車係そのものを1つに制限する。**
RUN_LOCK = os.path.join(REPO, "status", ".auto_launcher.lock")
_run_lock_f = None


def only_one_launcher():
    """先客がいれば False を返して静かに帰る（工場は止めない）。"""
    global _run_lock_f
    try:
        _run_lock_f = io.open(RUN_LOCK, "a+")
        fcntl.flock(_run_lock_f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except Exception:
        return False


def save_queue(q, snapshot=None, deleted_ns=None):
    """台帳を安全に書く（実体は `queue_store.save_queue`）。

    2026-09-04：直接 open(w) で書いていたため、別のプロセス（受信箱の処理・Dispatch）が
    同時に書いた瞬間に**中身が二重になって壊れた**（実測：末尾214文字が重複しJSONとして読めなくなった）。
    → 一時ファイルに書いてから置き換える（原子的）。

    2026-09-13（案件#687・777〜804番28件消失事故）：それだけでは足りなかった。
    ここは鍵を持ったまま長時間（git worktree作成・claude -p起動）`q` を抱え続け、
    最後に**丸ごと**書き戻す実装だったため、その間に command_ingest.queue_add() が
    （鍵を取らない経路＝relay_server.py等からの直接呼び出しで）新しく積んだ項目が、
    ここでの書き戻しで丸ごと消えた（777〜804番の実測消失）。
    → 差分マージ書き込み・件数減少ブロック・世代バックアップ付きの `queue_store.save_queue` に委譲する。
    `snapshot` を渡すと「自分が実際に変更した項目だけ」を正確に重ね書きできる
    （`queue_store.snapshot_items(q)` を load 直後に取っておいて渡すこと。省略時は
    自分が持っている項目を全部「自分が変更した」扱いにする＝保守的だが安全側）。
    """
    return queue_store.save_queue(q, snapshot=snapshot, deleted_ns=deleted_ns)


OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
CHECK_STATS = os.path.join(REPO, "status", "content_check_stats.json")


def _elapsed_min(started, finished):
    """startedAt〜finishedAt（"%Y-%m-%dT%H:%M:%S+09:00"形式）の差を分で返す。取れなければNone。"""
    try:
        fmt = "%Y-%m-%dT%H:%M:%S"
        t0 = datetime.strptime((started or "")[:19], fmt)
        t1 = datetime.strptime((finished or "")[:19], fmt)
        return round((t1 - t0).total_seconds() / 60.0, 1)
    except Exception:
        return None


_CUT_NOTE_RE = re.compile(r"^【中断から再開・.*?─{10,}\n\n", re.DOTALL)


def _find_transcript_by_session(session_id):
    """894番：sessionId（transcriptのファイル名）から ~/.claude/projects 配下を探す。
    見つからなくても例外を投げない（呼び出し頻度は「結果なしで切られた時」だけなので軽い）。"""
    if not session_id:
        return None
    try:
        fn = session_id + ".jsonl"
        for root, _dirs, files in os.walk(CLAUDE_PROJECTS_DIR):
            if fn in files:
                return os.path.join(root, fn)
    except Exception:
        pass
    return None


def _last_assistant_text(transcript_path, max_len=280):
    """894番：transcriptの末尾だけを読み、直近のassistant発言テキストを短く取り出す。
    全文パースは重いので末尾200KBだけ読む（切られた直後に呼ぶための軽量版）。"""
    if not transcript_path:
        return ""
    try:
        with io.open(transcript_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 200000), os.SEEK_SET)
            data = f.read().decode("utf-8", "ignore")
        text = ""
        for ln in data.splitlines():
            if '"type":"assistant"' not in ln:
                continue
            try:
                e = json.loads(ln)
            except Exception:
                continue
            c = (e.get("message") or {}).get("content")
            if isinstance(c, list):
                t = "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                if t.strip():
                    text = t.strip()
        return text[-max_len:] if text else ""
    except Exception:
        return ""


def _inject_cut_note(it, elapsed_min):
    """894番「工場が止まらない」：間引き・強制カット・クラッシュ等、理由を問わず
    『結果を残さず切られた』仕事は、次に着火する指示文（build_prompt→item["what"]）の
    先頭に「何分走って、どこまで進んでいたか」を焼き込む。
    --resume できる間（50分以内）は会話自体が残るので実害は薄いが、50分超で🧊コールドスタート
    （launch_oneが resumeFrom を捨てて新規セッションで立て直す分岐）になると会話は失われ、
    build_prompt() が item["what"] をそのまま渡すだけになる。ここで焼き込んでおけば、
    コールドスタートでも『切られた＝最初からやり直し』にならない。
    cutCountが重なってもノートが際限なく伸びないよう、既存ノートは1個だけに置き換える。
    """
    try:
        what = _CUT_NOTE_RE.sub("", it.get("what") or "", count=1)
        tail = _last_assistant_text(_find_transcript_by_session(it.get("sessionId")))
        elapsed_str = ("%d分" % elapsed_min) if elapsed_min is not None else "不明な時間"
        lines = ["【中断から再開・%s走行・%s】\n" % (elapsed_str, time.strftime("%m-%d %H:%M"))]
        lines.append("**このタスクは前回すでに%s走っています。ゼロからではなく続きとして扱ってください。**\n" % elapsed_str)
        if tail:
            lines.append("直前までの様子（前回セッション最後の発言の末尾）：\n> %s\n" % tail.replace("\n", "\n> "))
        lines.append("─" * 20 + "\n\n")
        it["what"] = "".join(lines) + what
    except Exception:
        pass  # 記録の失敗で発車自体を止めない


def short_report(it):
    """679番 たまごさん「これを直しましたのURLだけでいい位だよ」「報告とURLはセット」。
    子セッションの生の完了報告（経緯・説明・謝罪込みで長いことがある）から、
    機械で「1行目=何を直したか（20字以内）」「urlは呼び出し側でurls[0]を使う」を抜き出す。
    Dispatch向け(status/dispatch_outbox.jsonl)・進捗表向けの両方が、ここを通した短い形だけを見る。
    """
    raw = (it.get("result") or "").strip()
    what = ""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # 【完了】【問題】【判断待ち】ラベルと箇条書き記号を落として、中身の文だけ残す
        line = re.sub(r"^[【\[](完了|問題|判断待ち)[】\]][:：]?\s*", "", line)
        line = line.lstrip("・-*# 　")
        if line:
            what = line
            break
    if not what:
        what = it.get("title") or ""
    if len(what) > 20:
        what = what[:19] + "…"
    return what


def format_report_line(it):
    """short_report()の1行に、代表URL（あれば）を2行目として添えた完成形。
    経緯・技術の途中経過はここで捨てる（既存 it["result"] の生テキストは queue.json 側に残る）。
    """
    what = short_report(it)
    urls = it.get("urls") or []
    return what + ("\n" + urls[0] if urls else "")


NEW_ARRIVALS = os.path.join(REPO, "status", "new_arrivals.json")
NEW_ARRIVALS_CAP = 40


def _append_new_arrival(row):
    """732番：完了は聞かれる前に届く必要がある（たまごさん「先生（生成）が終わってるん
    だったら、ちょっと報告が欲しいよね。まだ？って言われる前に『できてますよ』って
    お知らせしてほしい」「つけ麺屋でも『何番、上がりました』って出るわけだよ」）。

    これまで dispatch_outbox.jsonl は「Dispatchが会話を始めた時に読む」ものでしかなく、
    たまごさんが毎日開く進捗表（PWA）には完了の合図が一切出ていなかった＝一番の穴。
    ここで、URL付きで成功した完了だけを軽量な別ファイルへも書き出す。進捗表(index.html)は
    こちらだけをポーリングし、「◯番 上がりました」を画面の一番上に出す。

    - 題名1行＋URLだけを持たせる（長い経緯は載せない＝queue.json側に残っている）。
    - 40件を超えたら古い方から捨てる（無限に太らせない＝軽さ優先）。
    - 「見たら消える」はクライアント側(localStorageの既読セット)の役目なので、
      ここでは常に真実の完了記録を積むだけでよい（既読管理はサーバー側に持たない）。
    """
    try:
        urls = row.get("urls") or []
        # 確認ページ（share/check/...）以外の実物URLがあれば、そちらを主URLとして優先する
        # （たまごさんが見て嬉しいのは成果物そのものであって、内部の確認記録ではないため）。
        primary = next((u for u in urls if isinstance(u, str) and "/share/check/" not in u), None) or (urls[0] if urls else None)
        if not primary:
            return
        entry = {
            "n": row.get("n"),
            "title": row.get("title"),
            "url": primary,
            "ts": row.get("ts"),
            "kind": "product" if any(isinstance(u, str) and "/share/check/" not in u for u in urls) else "check",
        }
        arrivals = load(NEW_ARRIVALS, [])
        if not isinstance(arrivals, list):
            arrivals = []
        arrivals.append(entry)
        arrivals = arrivals[-NEW_ARRIVALS_CAP:]
        tmp = NEW_ARRIVALS + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(arrivals, f, ensure_ascii=False, indent=1)
        os.replace(tmp, NEW_ARRIVALS)
    except Exception as e:
        log("new_arrivals書き込み失敗（%s番）: %s" % (row.get("n"), e))


def append_outbox(it, ok):
    """2026-09-06 新設：仕事が終わるたびに1行、status/dispatch_outbox.jsonl へ追記する。

    たまごさん「相変わらずディスパッチに報告がない。3時間で切ってるなら3時間ごとに
    3本4本、確認が来ていいはず」。これまで子セッションは queue.json（進捗表）には
    書けても、Dispatch（たまごさんと会話する側）へ届ける道が無かった。
    ここで書き出しておけば、Dispatchが会話開始時にこのファイルを読み、
    status/dispatch_reported.json（既にある「報告済み番号」の記録）と突き合わせて
    ＝前回報告した以降の分だけをまとめて出せる（読み取り側は今回の作業対象外）。

    732番：それだけだと「Dispatchが会話しているときにしか届かない」ので、成功かつ
    URL付きの完了は _append_new_arrival() で進捗表(PWA)向けの軽量フィードにも積む。
    """
    try:
        finished = it.get("finishedAt") or time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
        row = {
            "ts": finished,
            "n": it.get("n"),
            "title": it.get("title"),
            "ok": bool(ok),
            "elapsedMin": _elapsed_min(it.get("startedAt"), finished),
            "urls": it.get("urls") or [],
            "result": format_report_line(it),  # 679番：経緯を捨てて「20字+URL」だけにする
        }
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        if ok and row["urls"]:
            _append_new_arrival(row)
    except Exception as e:
        log("outbox書き込み失敗（%s番）: %s" % (it.get("n"), e))


def _append_cost_confirm_outbox(it, message):
    """案件#676：お金がかかるタスクを止めたとき、1回だけ dispatch_outbox へ確認を出す。

    通常の完了報告（n=数値）と同じ番号を使うと dispatch_reported.json の既読判定
    （n だけを見て「もう話した」扱いにする）を巻き込み、あとで本当に完了した報告が
    消えてしまう。なので n は文字列で "<番号>-cost" にして衝突させない。
    """
    try:
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "n": "%s-cost" % it.get("n"),
            "type": "cost_confirm",
            "title": it.get("title"),
            "message": message,
        }
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:
        log("cost_confirm outbox書き込み失敗（%s番）: %s" % (it.get("n"), e))


def _append_cap_limit_outbox(it):
    """案件#824：1本のタスクのcostEstimateが週予算の3%上限を超えたとき、1回だけ
    dispatch_outbox へ確認を出す（_append_cost_confirm_outboxと同じ作法。nは文字列で
    衝突を避ける）。"""
    try:
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "n": "%s-caplimit" % it.get("n"),
            "type": "cap_limit",
            "title": it.get("title") or "",
            "message": "%s番が上限に達しました。続けますか" % it.get("n"),
        }
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:
        log("cap_limit outbox書き込み失敗（%s番）: %s" % (it.get("n"), e))


def _strip_html_for_check(html):
    """タグを外してプレーンテキストにする（判定用・雑でよい）"""
    import re as _re
    html = _re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = _re.sub(r"(?s)<[^>]+>", " ", html)
    text = _re.sub(r"&nbsp;|&amp;|&lt;|&gt;|&quot;|&#39;", " ", text)
    text = _re.sub(r"\s+", " ", text).strip()
    return text


CHECK_ROOTS = (
    "https://joy-relief-station.lovable.app",
    "https://tamago2022.github.io/tamago-shinchoku",
    "https://tamago2022.github.io/tamago-shinchoku/index.html",
    "https://www.youtube.com",
    "https://youtube.com",
)


def content_check(url, timeout=10):
    """2026-09-06 新設：確認待ちに上げる直前に、確認ページを機械が実際に開いて中身を検品する。

    たまごさん「今日、確認待ちに『結果が読み取れませんでした』『URLの報告なし』が並び、
    たまごさんに『これ何を見て判断すればいいの』という状態を作った」への対策。
    既存のURL検品（JUNK/ROOTSフィルタ＝文字列だけを見る）の続きとして、
    ここでは実際にページを取りに行って中身を見る。

    弾く条件（どれか1つでも該当したら不合格）：
      ①404などページが開けない
      ②本文（タグを外した後）が200文字未満
      ③「準備中」「TODO」「調査中」しか書かれていない
      ④スクリーンショット（<img）も数字も1つも無い
      ⑤リンク先が全部トップページ

    戻り値: (ok: bool, reason: str)
    """
    import re as _re
    import socket as _socket
    import urllib.request
    import urllib.error

    # 2026-09-12（776番）：urllib.request.urlopen(timeout=...) はTCP接続・読み込みには効くが
    #   **DNS解決（getaddrinfo）自体はこのtimeoutの対象外**というPythonの既知の落とし穴がある。
    #   ネットワークが一瞬不安定になりDNSが応答しないだけで、ここが無期限にブロックし続け、
    #   auto_launcher.py全体（＝心臓）が固まる（実測：12:58〜16:49、230分停止の主因と推定）。
    #   socket.setdefaulttimeout() はDNS解決にも効く数少ない確実な手段なので、呼び出し前後で
    #   グローバル既定値を退避・復元する（他のコードの挙動を変えないため）。
    _old_timeout = _socket.getdefaulttimeout()
    try:
        _socket.setdefaulttimeout(timeout)
        req = urllib.request.Request(url, headers={"User-Agent": "tamago-content-checker/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            raw = resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return False, "ページが開けません（HTTP %s）" % e.code
    except Exception as e:
        return False, "取得に失敗しました（%s）" % e
    finally:
        _socket.setdefaulttimeout(_old_timeout)

    if code and code != 200:
        return False, "ページが%sです" % code

    text = _strip_html_for_check(raw)
    if len(text) < 200:
        return False, "本文が%d文字しかありません（200文字未満）" % len(text)

    NG_WORDS = ("準備中", "TODO", "調査中")
    if any(w in text for w in NG_WORDS):
        residual = text
        for w in NG_WORDS:
            residual = residual.replace(w, "")
        residual_core = _re.sub(r"[\s　、。・,.\-…\d]", "", residual)
        if len(residual_core) < 20:
            return False, "「準備中」「TODO」「調査中」しか書かれていません"

    has_img = bool(_re.search(r"(?is)<img\b", raw))
    has_digit = bool(_re.search(r"\d", text))
    if not has_img and not has_digit:
        return False, "スクリーンショットも数字も1つもありません"

    links = _re.findall(r'(?is)<a\s[^>]*href=["\']([^"\']+)["\']', raw)

    def _is_root(u):
        u2 = (u or "").rstrip("/")
        if not u2 or u2.startswith("#"):
            return True
        return any(u2 == r.rstrip("/") for r in CHECK_ROOTS)

    real_links = [l for l in links if l and not l.startswith("#")]
    if real_links and all(_is_root(l) for l in real_links):
        return False, "リンク先が全部トップページです"

    # ---- 2026-09-09 たまごさんの指摘で追加：**リンクを1本ずつ開いて確かめる。**----
    # たまごさんの言葉：「牛尾さんはできたんだと思ってURL2つ押したら全部404。鬼監督どうなってるんだい」
    # 実際に起きたこと（623番）：確認ページ自体は200で、中身も正しかった。**仕事は終わっていた。**
    #   だが、ページに貼ってあった2本のリンクが両方とも **private リポジトリ**（joy-relief-station）で、
    #   たまごさんが押すと GitHub が 404 を返す。**こちらからは見えて、本人には見えないリンクだった。**
    # → **「ページが開けた」だけでは合格にしない。ページの上のリンクが、たまごさん本人の目から
    #    開けるかどうかまで見る。**開けないリンクを貼るのは、証拠を渡していないのと同じ。
    checkable = [l for l in real_links
                 if l.startswith("http") and not _is_root(l)]
    # 2026-09-13（793番停止事故）：ここは上のメイン取得と違い socket.setdefaulttimeout() を
    #   かけていなかった。urlopen(timeout=...) はDNS解決（getaddrinfo）には効かないため、
    #   リンク1本のDNSが応答しないだけで無期限にブロックし、harvest()→auto_launcher.py全体
    #   （＝心臓）が45秒の見張りに毎回強制終了され、**発車が1本も出せなくなった**
    #   （実測：05:26〜05:34に8回連続で「45秒以内に終わらず強制終了」）。
    #   さらに全リンクが正常に振る舞っても 8本×8秒=64秒 で45秒予算を超えうるため、
    #   経過時間の予算（LINK_CHECK_BUDGET秒）を持たせ、超えたら残りは検品なしで打ち切る。
    LINK_CHECK_BUDGET = 20.0
    _t0 = time.time()
    for l in checkable[:8]:          # 8本まで。全部見ると遅くなるので上限を切る
        if time.time() - _t0 > LINK_CHECK_BUDGET:
            break                    # 予算超過。残りは見ずに次の判定へ進む（心臓を止めない）
        # private リポジトリは、こちらが開けてもたまごさんには 404 に見える。中身を見るまでもなく不合格。
        if "github.com/tamago2022/joy-relief-station" in l:
            return False, ("たまごさんが開けないリンクが貼ってあります（%s は非公開リポジトリで、"
                           "本人が押すと404になります）。証拠は本人が開ける場所に置いてください" % l)
        _old_timeout2 = _socket.getdefaulttimeout()
        try:
            _socket.setdefaulttimeout(8)
            req2 = urllib.request.Request(l, method="HEAD",
                                          headers={"User-Agent": "tamago-content-checker/1.0"})
            with urllib.request.urlopen(req2, timeout=8) as r2:
                if r2.getcode() not in (200, 301, 302):
                    return False, "貼ってあるリンクが開けません（%s → HTTP %s）" % (l, r2.getcode())
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410):
                return False, "貼ってあるリンクが開けません（%s → HTTP %s）" % (l, e.code)
        except Exception:
            pass                     # 回線の一時的な失敗でページ全体を落とさない
        finally:
            _socket.setdefaulttimeout(_old_timeout2)

    return True, ""


def _record_content_check(ok, reason, url, item_n=None):
    """検品の実績（何件検品して何件弾いたか）を status/content_check_stats.json へ積む。
    確認ページ側がこれをfetchして『実績』を表示する。"""
    stats = load(CHECK_STATS, {"totalChecked": 0, "totalRejected": 0, "history": []})
    stats["totalChecked"] = int(stats.get("totalChecked") or 0) + 1
    if not ok:
        stats["totalRejected"] = int(stats.get("totalRejected") or 0) + 1
    hist = stats.get("history") or []
    hist.append({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "n": item_n,
        "url": url,
        "ok": bool(ok),
        "reason": reason,
    })
    stats["history"] = hist[-50:]
    stats["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    try:
        tmp = CHECK_STATS + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CHECK_STATS)
    except Exception as e:
        log("content_check_stats書き込み失敗: %s" % e)


AI_VERIFY_STATS = os.path.join(REPO, "status", "ai_verify_stats.json")
VERIFY_MODEL = SONNET  # 2026-09-06：Verifierも今はSonnet固定。
                       # 実績（ai_verify_stats.jsonのtotalCostUsd）でコストが高いと分かったら、ここだけ差し替えれば全体に効く。
VERIFY_TIMEOUT_SEC = 600  # これを超えて生きていたら異常とみなし強制終了する安全弁


# =====================================================================
# 案件#800：検品を「読む」だけから「触る」へ。3段検品の2段目。
#
# たまごさんの言葉（2026-09-13）：
#   「間違えたものがガンガン上がってきてるんだ、もう俺に。結局、俺が見つけて
#    『違うよ』って言ってるわけじゃん。直っているものだけ見せてほしいのよ。」
#
# 原因：これまでの build_verify_prompt() は検品AIに「curlで読め・ブラウザは使うな」
#   と命じていたため、HTMLにコードさえあれば「押しても無反応」でもPASSしていた
#   （実例：コンシェルジュの「話す」ボタンが無反応でもPASSしていた）。
#
# 3段の位置づけ：
#   1段目＝機械検品(content_check)：確認ページが存在し中身があるか（既存・変更なし）
#   2段目＝触る検品(touch_check・ここ)：実際に押せる要素を headless Chrome で
#           1つずつクリックし、押しても何も変わらない要素・コンソールエラーを検出する。
#   3段目＝鬼監督(AI Verifier・start_verify/collect_verify)：たまごさんが過去に
#           言ってきた基準（oni-kantoku）に照らして中身を判断する。
#   3段すべて通ったものだけ、たまごさんの確認列（またはAI自動OK）へ進む。
#
# start_verifyと同じ設計：別プロセスをバックグラウンドで着火するだけで、
# harvest()はここで同期待ちしない（45秒watchdogを超えて心臓を止めないため）。
# =====================================================================
TOUCH_CHECK_SCRIPT = os.path.join(REPO, "tools", "verify_click.mjs")
TOUCH_CHECK_TIMEOUT_SEC = 280  # マシン高負荷時はheadless Chromeの起動に60〜90秒かかることがある実測込み
TOUCH_CHECK_STATS = os.path.join(REPO, "status", "touch_check_stats.json")
ONI_KANTOKU_LOG = os.path.join(REPO, "status", "oni_kantoku_log.jsonl")


def _find_node():
    for c in ("/opt/homebrew/bin/node", "/usr/local/bin/node", "/usr/bin/node"):
        if os.path.exists(c):
            return c
    return "node"  # PATH頼み（最終フォールバック）


def _pick_touch_target(check_url, urls):
    """触る検品の対象URLを選ぶ。確認ページ(/share/check/)自体はボタンが少ないので、
    実際に直した本物のページ（urlsのうち確認ページでないもの）を優先する。
    それが無ければ確認ページを、それも無ければNone（＝この段は素通し）を返す。"""
    for u in (urls or []):
        if u and "/share/check/" not in u and u.startswith("http"):
            return u
    if check_url and check_url.startswith("http"):
        return check_url
    return None


def start_touch_check(it, url):
    """触る検品(2段目)を別プロセスで着火する。同期待ちしない。"""
    if not url:
        return False
    new_id = str(uuid.uuid4())
    outjson = os.path.join(REPO, "status", "touchcheck-%s.json" % new_id[:8])
    logf = os.path.join(REPO, "status", "touchcheck-%s.log" % new_id[:8])
    try:
        cmd = [_find_node(), TOUCH_CHECK_SCRIPT, url, outjson]
        with open(logf, "ab") as f:
            p = subprocess.Popen(cmd, cwd=REPO, stdout=f, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception as e:
        log("触る検品の着火に失敗: %s" % e)
        return False
    it["touchPid"] = p.pid
    it["touchOutJson"] = outjson
    it["touchLog"] = logf
    it["touchStartedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    it["touchUrl"] = url
    return True


def collect_touch_check(it):
    """status="touchchecking" の項目を回収する。戻り値の形はcollect_verifyと同じ：
    None＝まだ検品中／(True/False/None, reason, report_dict)＝終了。"""
    pid = it.get("touchPid")
    alive = False
    if pid:
        try:
            os.kill(int(pid), 0)
            alive = True
        except Exception:
            alive = False
    if alive:
        try:
            started = it.get("touchStartedAt") or ""
            fmt = "%Y-%m-%dT%H:%M:%S"
            t0 = datetime.strptime(started[:19], fmt)
            now = datetime.strptime(time.strftime("%Y-%m-%dT%H:%M:%S"), fmt)
            elapsed = (now - t0).total_seconds()
        except Exception:
            elapsed = 0
        if elapsed > TOUCH_CHECK_TIMEOUT_SEC:
            try:
                os.kill(int(pid), 9)
            except Exception:
                pass
            return None, "触る検品がタイムアウトしました（%d秒超）" % TOUCH_CHECK_TIMEOUT_SEC, None
        return None
    outjson = it.get("touchOutJson") or ""
    report = None
    try:
        report = json.load(io.open(outjson, encoding="utf-8"))
    except Exception:
        pass
    if not report:
        return None, "触る検品の結果ファイルが読み取れませんでした（技術的な失敗として素通しします）", None
    no_resp = report.get("noResponse") or report.get("unresponsive") or []
    console_errs = report.get("consoleErrors") or []
    tech_error = report.get("error")
    ok = (not tech_error) and (not no_resp) and (not console_errs)
    total_clickable = report.get("totalClickable", 0)
    tested = report.get("tested", 0)
    if ok:
        reason = "無反応0件・コンソールエラー0件（%d件中%d件を実クリック）" % (total_clickable, tested)
    else:
        parts = []
        if no_resp:
            examples = "、".join("「%s」(%s)" % ((r.get("text") or "")[:20], r.get("tag") or "?")
                                 for r in no_resp[:3])
            parts.append("押しても無反応%d件%s" % (len(no_resp), "：" + examples if examples else ""))
        if console_errs:
            parts.append("コンソールエラー%d件" % len(console_errs))
        if tech_error and not parts:
            parts.append("検品自体が失敗：%s" % str(tech_error)[:150])
        reason = "、".join(parts) or "触る検品で不合格判定"
    # 技術的エラー（Chromeが開けなかった等）で押せる要素も無反応も0件のケースは、
    # 中身の問題ではなくインフラの問題として技術的エラー扱いにする（素通し対象）。
    if tech_error and not no_resp and not console_errs and tested == 0:
        return None, "触る検品が技術的に失敗しました：%s" % str(tech_error)[:150], report
    return ok, reason, report


def _record_touch_check(ok, reason, url, item_n=None, report=None):
    """実績を status/touch_check_stats.json に永続化する（他の*_stats.jsonと同じ形）。"""
    stats = load(TOUCH_CHECK_STATS, {
        "totalChecked": 0, "totalPassed": 0, "totalFailed": 0, "totalErrors": 0,
        "totalUnresponsiveElements": 0, "history": [],
    })
    stats["totalChecked"] = int(stats.get("totalChecked") or 0) + 1
    if ok is True:
        stats["totalPassed"] = int(stats.get("totalPassed") or 0) + 1
    elif ok is False:
        stats["totalFailed"] = int(stats.get("totalFailed") or 0) + 1
        no_resp = (report or {}).get("noResponse") or (report or {}).get("unresponsive") or []
        stats["totalUnresponsiveElements"] = int(stats.get("totalUnresponsiveElements") or 0) + len(no_resp)
    else:
        stats["totalErrors"] = int(stats.get("totalErrors") or 0) + 1
    hist = stats.get("history") or []
    hist.append({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "n": item_n, "url": url,
        "verdict": "pass" if ok is True else ("fail" if ok is False else "error"),
        "reason": reason,
    })
    stats["history"] = hist[-50:]
    stats["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    try:
        tmp = TOUCH_CHECK_STATS + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=1)
        os.replace(tmp, TOUCH_CHECK_STATS)
    except Exception as e:
        log("touch_check_stats書き込み失敗: %s" % e)


def _record_oni_kantoku(ok, reason, item_n, title, touch_summary=None, cost=None):
    """案件#800：鬼監督（3段目＝AI検品）が実際に動いた記録を1行ずつ残す。
    『制度は作ったが1度もパイプラインに繋がっていなかった』(684番)を繰り返さないため、
    ここへの追記が『鬼監督が実際に回っている』ことの生の証拠になる。

    既存の oni_kantoku_log.jsonl は既に実在し（443〜450番台の一括監査スクリプト群が使用）、
    tools/nikki_generator.py・tools/kenpou_check.py・tools/verify_check_pages.py が
    `n` / `title` / `reason` / `checkedAt` / `decision`（"pass"で合格集計）というキー名を
    前提に読んでいる。ここも同じキー名で書く（新しいキー名を作ると日誌・憲法点検から
    この3段目の結果が見えなくなるため）。touchCheckSummary/costUsdは追加情報として足すだけ。"""
    row = {
        "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "n": item_n,
        "title": title,
        "decision": "pass" if ok is True else ("fail" if ok is False else "error"),
        "reason": reason,
        "touchCheckSummary": touch_summary,
        "costUsd": cost,
        "task": "800-touch-verify",
    }
    try:
        with io.open(ONI_KANTOKU_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:
        log("oni_kantoku_log書き込み失敗: %s" % e)


# 鬼監督(たまごさんの分身)が積み重ねてきた関門を凝縮。全文（211行・関門0〜10）は
# たまごさんのスキル`oni-kantoku`が正本。ここには検品AIへの指示として効く最重要項目だけを抜粋する。
ONI_KANTOKU_GATES = """
【鬼監督の関門（凝縮版・正本はスキルoni-kantoku）】以下に1つでも当てはまれば不合格：
- 証拠が無い（押せる本番URL／前後スクショ／数字のいずれも無く、主張だけ）
- 頼まれた範囲を超えて余計なものを足している、または頼まれた範囲を満たしていない
  （「4件出す」等の件数指定があれば実際に数える）
- 依頼文にある要素・機能が実際の画面に見当たらない
- 同じ内容・同じ動画・同じカードが重複している
- 噂・未確認情報を事実として書いている、生年を書いている（個人のみ）等の既知の禁止事項に触れている
- 見た目が壊れている（文字が潰れる／重なる／サムネが無い箇所がある等）
- 前より重くなっている（ページが明らかに遅い）
- 「完了」と言っているのに本番URLで変化が確認できない
"""


def build_verify_prompt(it, check_url, urls):
    """AI検品(Verifier=鬼監督3段目)への指示文。渡すのは①元の依頼②作業した側の完了報告
    ③確認ページ/本番URL④すでに機械が実クリックした2段目「触る検品」の結果の4つ。
    作った側の言い分・判断理由・内部事情は一切渡さない。

    案件#800：以前は「curlで読め・ブラウザは使うな」と命じていたため、押しても無反応の
    ボタンでもHTMLにコードさえあればPASSしていた。claude-in-chrome/screencaptureは
    （許可ダイアログが出るため）引き続き禁止だが、**headless Chromeのnodeスクリプトは
    許可ダイアログを出さないので使ってよい**。すでに2段目でその結果が出ているので、
    それをそのまま判断材料として使うのが基本（自分で再実行してもよい）。"""
    target = check_url or (urls[0] if urls else "")
    touch_note = it.get("touchCheckNote") or "（このタスクでは触る検品を実行できませんでした。あなた自身が下記のnodeコマンドで確認してください）"
    node_hint = "node %s <確認したいURL>" % TOUCH_CHECK_SCRIPT
    return """【AI検品・鬼監督（Verifier）】あなたは検品専門です。この作業を行った本人ではありません。

# 元の依頼
{title}

{what}

# 作業した側の完了報告（そのまま。これを鵜呑みにせず、実際に確認すること）
{result}

# 確認すること
- 確認ページ（あれば必ず開く）: {check_url}
- 本番URL（実際に開く）: {urls}

# 2段目「触る検品」の結果（機械が実際にボタンを1つずつ押した結果。参考にすること）
{touch_note}

# やり方
- `curl` 等で実際にURLを取得して中身を読んでください。
- **claude-in-chrome・screencapture は使わないでください**（許可ダイアログが出て止まるため）。
- **`{node_hint}` はheadless Chromeで許可ダイアログを出さないので、使ってよい・むしろ推奨。**
  「押せると書いてあるのに実際は反応しない」を見つけるための唯一の手段です。
- 確認ページがあれば必ず開き、依頼内容と実際の変化が一致するか確認してください。
- 本番URLも実際に開き、確認ページの主張と食い違いがないか確認してください。
- あなたは実装しません。直しません。**見るだけです。**

{oni_gates}

# 不合格の基準（どれか1つでも該当したら不合格）
- URLが開けない
- 中身が依頼と一致しない・的外れ
- 検証可能な証拠（数字・リンク・スクショ）が無く、主張だけ
- 「直した」と書いてあるのに、実際には変化の跡が無い
- **押しても何も起きない要素がある**（触る検品の結果、またはあなた自身の確認で判明した場合）
- **コンソールにエラーが出ている**
- 依頼文が名指ししている要素・機能が実際の画面に見当たらない
- 依頼文に件数の指定（例：「4件出す」）があるのに、実際に数えると満たしていない

# 出力の最後（必ず単独の1行。この形式を厳守。パースするので変えないこと）
VERIFY_RESULT: PASS - <合格理由を一言（日本語）>
または
VERIFY_RESULT: FAIL - <不合格理由を一言（日本語・具体的に）>
""".format(
        title=it.get("title") or "",
        what=it.get("what") or "",
        result=(it.get("result") or "")[:1200],
        check_url=check_url or "（なし）",
        urls=", ".join(urls or []) or "（なし）",
        touch_note=touch_note,
        node_hint=node_hint,
        oni_gates=ONI_KANTOKU_GATES,
    ), target


def start_verify(it, check_url, urls):
    """確認待ちへ上げる前に、別プロセスのclaudeをバックグラウンドで1本だけ着火する（同期待ちしない）。
    check_url優先、無ければurls[0]。両方無ければFalseを返す（＝検品できないので呼び出し側は素通しする）。
    成功したら it に verifyPid / verifySessionId / verifyLog / verifyStartedAt / verifyUrl をセットしてTrueを返す。
    """
    target = check_url or (urls[0] if urls else None)
    if not target:
        return False
    prompt, _ = build_verify_prompt(it, check_url, urls)
    new_id = str(uuid.uuid4())
    logf = os.path.join(REPO, "status", "verify-%s.log" % new_id[:8])
    try:
        cwd = tempfile.mkdtemp(prefix="tamago-verify-")
        cmd = [CLAUDE, "-p", "--model", VERIFY_MODEL,
               "--permission-mode", "auto", "--output-format", "json", prompt]
        with open(logf, "ab") as f:
            p = subprocess.Popen(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, start_new_session=True, env=claude_env())
    except Exception as e:
        log("AI検品の着火に失敗 %s番: %s" % (it.get("n"), e))
        return False
    it["verifyPid"] = p.pid
    it["verifySessionId"] = new_id
    it["verifyLog"] = logf
    it["verifyStartedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    it["verifyUrl"] = target
    return True


def collect_verify(it):
    """status="verifying" の項目を回収する。

    戻り値：
      None                    → まだ検品中（pidが生きている）。呼び出し側は何もしない
      (True, reason, cost)    → 合格
      (False, reason, cost)   → 不合格
      (None, reason, cost)    → 技術的エラー（結果が読み取れない・タイムアウト）。呼び出し側は素通しさせる
    """
    pid = it.get("verifyPid")
    alive = False
    if pid:
        try:
            os.kill(int(pid), 0)
            alive = True
        except Exception:
            alive = False
    if alive:
        # startedAt（ローカル時刻文字列）と今の時刻を素直に比較する（タイムゾーンは両方ローカルなので揃う）。
        try:
            started = it.get("verifyStartedAt") or ""
            fmt = "%Y-%m-%dT%H:%M:%S"
            t0 = datetime.strptime(started[:19], fmt)
            now = datetime.strptime(time.strftime("%Y-%m-%dT%H:%M:%S"), fmt)
            elapsed = (now - t0).total_seconds()
        except Exception:
            elapsed = 0
        if elapsed > VERIFY_TIMEOUT_SEC:
            try:
                os.kill(int(pid), 9)
            except Exception:
                pass
            return None, "AI検品がタイムアウトしました（%d秒超）" % VERIFY_TIMEOUT_SEC, None
        return None
    # 死んでいる＝終わった
    logf = it.get("verifyLog") or ""
    raw = ""
    try:
        raw = io.open(logf, encoding="utf-8", errors="ignore").read()
    except Exception:
        pass
    cost = None
    mcost = re.search(r'"total_cost_usd"\s*:\s*([0-9.]+)', raw or "")
    if mcost:
        try:
            cost = float(mcost.group(1))
        except Exception:
            cost = None
    text = ""
    m = re.findall(r'"result"\s*:\s*"((?:[^"\\]|\\.)*)"', raw or "")
    if m:
        text = m[-1].encode("utf-8").decode("unicode_escape").encode("latin-1", "ignore").decode("utf-8", "ignore")
    mv = re.search(r"VERIFY_RESULT:\s*(PASS|FAIL)\s*-\s*(.+)", text or raw or "", re.IGNORECASE)
    if not mv:
        return None, "検品AIの結果が読み取れませんでした（技術的な失敗として素通しします）", cost
    verdict = mv.group(1).upper() == "PASS"
    reason = mv.group(2).strip().splitlines()[0][:200]
    return verdict, reason, cost


def _record_ai_verify(ok, reason, cost, url, item_n=None):
    """実績を status/ai_verify_stats.json に永続化する。_record_content_check と同じ書式（tmpファイル→os.replaceで原子的に置換）。"""
    stats = load(AI_VERIFY_STATS, {
        "totalChecked": 0, "totalPassed": 0, "totalFailed": 0, "totalErrors": 0,
        "totalCostUsd": 0.0, "reasonCounts": {}, "history": [],
    })
    stats["totalChecked"] = int(stats.get("totalChecked") or 0) + 1
    if ok is True:
        stats["totalPassed"] = int(stats.get("totalPassed") or 0) + 1
        verdict = "pass"
    elif ok is False:
        stats["totalFailed"] = int(stats.get("totalFailed") or 0) + 1
        verdict = "fail"
        rc = stats.get("reasonCounts") or {}
        key = (reason or "")[:40]
        rc[key] = int(rc.get(key) or 0) + 1
        stats["reasonCounts"] = rc
    else:
        stats["totalErrors"] = int(stats.get("totalErrors") or 0) + 1
        verdict = "error"
    if cost:
        stats["totalCostUsd"] = round(float(stats.get("totalCostUsd") or 0.0) + float(cost), 4)
    hist = stats.get("history") or []
    hist.append({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "n": item_n,
        "url": url,
        "verdict": verdict,
        "reason": reason,
        "costUsd": cost,
    })
    stats["history"] = hist[-50:]
    stats["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    try:
        tmp = AI_VERIFY_STATS + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=1)
        os.replace(tmp, AI_VERIFY_STATS)
    except Exception as e:
        log("ai_verify_stats書き込み失敗: %s" % e)


def _record_cost_by_task(n, title, cost_usd, tokens_in, tokens_out,
                          cache_read, cache_creation, model_name,
                          started_at, finished_at):
    """424番：どの仕事がいくら使ったか見える化。

    たまごさん「いまは全体の使用率しか分からず、『どの種類の仕事が高いのか』が
    分からない。だから減らしようがない」への対応。harvest() が1件終わるたびに
    ここを呼び、status/cost_by_task.json（tasks配列＝台帳）へ1行足す。
    _record_ai_verify と同じ書式（tmpファイル→os.replaceで原子的に置換）。
    """
    if cost_usd is None and (tokens_in or tokens_out):
        cost_usd = round(
            (tokens_in or 0) * FALLBACK_PRICE_IN_PER_1M / 1_000_000
            + (tokens_out or 0) * FALLBACK_PRICE_OUT_PER_1M / 1_000_000, 6)
    elapsed_min = _elapsed_min(started_at, finished_at)
    data = load(COST_LEDGER, {"tasks": []})
    tasks = data.get("tasks") or []
    tasks.append({
        "n": n,
        "title": title,
        "inputTokens": int(tokens_in or 0),
        "outputTokens": int(tokens_out or 0),
        "cacheReadTokens": int(cache_read or 0),
        "cacheCreationTokens": int(cache_creation or 0),
        "costUsd": round(float(cost_usd), 6) if cost_usd is not None else None,
        "elapsedMin": elapsed_min,
        "model": model_name or "",
        "finishedAt": finished_at,
    })
    tasks = tasks[-300:]   # 直近300件だけ持つ（台帳が無限に太らないように）
    data["tasks"] = tasks

    # ---- 今日いちばん高かった仕事トップ5（JST基準）----
    today = time.strftime("%Y-%m-%d")
    today_tasks = [t for t in tasks if (t.get("finishedAt") or "").startswith(today)
                   and t.get("costUsd") is not None]
    top5 = sorted(today_tasks, key=lambda t: t["costUsd"], reverse=True)[:5]
    data["todayTop5"] = top5
    data["todayTotalCostUsd"] = round(sum(t.get("costUsd") or 0 for t in today_tasks), 4)
    data["todayTaskCount"] = len(today_tasks)
    data["priceSourceNote"] = (
        "推定コストは基本 claude -p --output-format json の total_cost_usd をそのまま採用"
        "（Anthropic公式単価でCLIが算出済みの実額）。それが取れない場合だけ、"
        "入力$%.0f／出力$%.0f（100万トークンあたり・依頼文に指定された数値。"
        "Vault内に出典記録は見つからなかったためフォールバックとして採用）で概算する。"
        % (FALLBACK_PRICE_IN_PER_1M, FALLBACK_PRICE_OUT_PER_1M))
    data["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    try:
        tmp = COST_LEDGER + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, COST_LEDGER)
    except Exception as e:
        log("cost_by_task書き込み失敗 %s番: %s" % (n, e))


SPLIT_DIR = os.path.join(REPO, "status", "split")
SPLIT_BATCH_SIZE = 10


def split_big_job(it, q, urls):
    """2026-09-06 423番：大きい仕事の1本目（一覧作成）が終わったら、
    status/split/{n}-list.json を読んで10件ずつの小分けタスクを自動で発車待ちへ積む。

    たまごさん「いま『サイト全体の◯◯を直す』のような仕事が1本で積まれ、3時間で切られて
    中途半端に終わっている」への対策。一覧が無い／空なら『失敗』ではなく
    『一覧作成をやり直す』として2回まで自動で列に戻し、それでもダメなら人の目へ回す
    （既存のURLなし自動やり直しと同じ考え方＝無限ループを作らない）。

    戻り値：Trueなら it の状態確定済み（confirm待ちへ回してよい）。呼び出し側で
    append_outbox() するかどうかの判断に使う。
    """
    n = it.get("n")
    list_path = os.path.join(SPLIT_DIR, "%d-list.json" % n)
    data = load(list_path, {})
    targets = [str(t).strip() for t in (data.get("items") or []) if str(t).strip()]
    if not targets:
        tries = int(it.get("splitRetryCount") or 0)
        if tries < 2:
            it["splitRetryCount"] = tries + 1
            it["status"] = "hold" if it.get("holdNote") else "waiting"
            it["priority"] = it.get("priority") or 2
            it["what"] = (it.get("what") or "") + (
                "\n\n【自動やり直し・一覧が見つかりません・%s】"
                "`status/split/%d-list.json` が無いか空でした。"
                "`{\"items\": [\"対象1\", \"対象2\", ...]}` の形で必ず保存してください。"
                % (time.strftime("%m-%d %H:%M"), n))
            for k in ("finishedAt", "result", "urls", "sessionId", "startedAt"):
                it.pop(k, None)
            log("↩︎ 一覧ファイルなしのため自動やり直し %d番「%s」（%d回目）"
                % (n, it.get("title"), tries + 1))
            return False
        it["result"] = (it.get("result") or "") + (
            "\n\n【自動分割：2回試みても一覧ファイルが作れませんでした。人の目に回します】"
            "対象 status/split/%d-list.json" % n)
        it["status"] = "awaiting_check"
        log("⚠️ 大きい仕事の一覧作成が2回失敗 %d番「%s」→ 人の目へ" % (n, it.get("title")))
        return True

    items = q.get("items") or []
    next_n = max([int(x.get("n") or 0) for x in items] or [0])
    orig_title = (it.get("originalTitle") or it.get("title") or "").replace("【一覧作成】", "").strip()
    orig_what = it.get("originalWhat") or ""
    chunks = [targets[i:i + SPLIT_BATCH_SIZE] for i in range(0, len(targets), SPLIT_BATCH_SIZE)]
    added = []
    for i, chunk in enumerate(chunks, 1):
        next_n += 1
        batch_what = (
            "# 元の依頼\n---\n%s\n---\n\n"
            "# ★この仕事は自動分割の一部です（%d/%d本目）\n"
            "元は大きすぎたため、機械が対象を一覧化したうえで10件ずつに割っています。"
            "**今回はここに書かれた対象だけ**を扱ってください（他の対象には手を出さない）。\n\n"
            "対象一覧（%d件）：\n%s\n\n"
            "1件ごとに直しては終わり、ではなく、このバッチ内で1本の完了報告にまとめてよい。"
            "ただし完了条件（本番反映・URL報告）は通常の仕事と同じです。"
        ) % (orig_what, i, len(chunks), len(chunk), "\n".join("- %s" % t for t in chunk))
        items.append({
            "n": next_n,
            # 797番：カウンタを末尾の全角括弧「（1/4）」から先頭の半角「(1/4)」へ移した。
            # たまごさん「順番待ちに同じ名前のタスクが3つ並んだりすんなよ」への対応。
            # 進捗表の題名は横幅で省略される（CSS text-overflow:ellipsis）ため、区別点が
            # 長い共通の題名の末尾にあると省略部分に隠れて同じ名前に見えてしまっていた。
            "title": "(%d/%d) %s" % (i, len(chunks), orig_title or it.get("title") or ("%d番" % n)),
            "why": "大きい仕事の自動分割（元は%d番）" % n,
            "what": batch_what,
            "status": "waiting",
            "limitMin": 180,
            "model": "claude-sonnet-5",
            "priority": it.get("priority") or 3,
            "splitFrom": n,
            "splitIndex": i,
            "splitTotal": len(chunks),
            # 2026-09-06(453/455番) 分割元の origin をそのまま引き継ぐ（大きい仕事の中身は
            # たまごさんが言ったことの分割にすぎない）。分割元にも印が無ければ既定は"user"。
            "origin": it.get("origin") if it.get("origin") in ("user", "factory") else "user",
        })
        added.append(next_n)
    q["items"] = items
    it["status"] = "awaiting_check"
    it["result"] = (it.get("result") or "") + (
        "\n\n【自動分割完了】対象%d件を%d本（%d件ずつ）の発車待ちに積みました→%s番"
        % (len(targets), len(chunks), SPLIT_BATCH_SIZE, "・".join(str(x) for x in added)))
    log("✂︎ 大きい仕事を自動分割 %d番「%s」→ 対象%d件を%d本へ（%s番）"
        % (n, it.get("title"), len(targets), len(chunks), "・".join(str(x) for x in added)))
    return True


def harvest(q):
    """2026-09-04 たまごさん「作業が終わって、終わったんであれば、そこは俺の確認待ちだよ。
    確認待ちでOKって言ったら初めて完了に入る。ダメだったらもう一回順番待ちに並ぶ」
    「終わったら報告。Dispatchにも進捗表にもリンクが貼られてあること。何時何分に完了したかも」

    claude -p は1回きりの実行で、終わると結果をログに吐いて死ぬ。
    これまでその結果を誰も読んでいなかった（＝「どっか行っちゃってる」の正体）。
    ここで、死んだプロセスのログから結果とURLを拾い、status を awaiting_check（たまごさんの確認待ち）にする。
    """
    import re
    changed = False

    # ---- 3時間で切る（2026-09-15・たまごさん「全部3時間で切っちゃってください」）----
    #   これまで limitMin は項目に書かれているだけで、**実際に切る処理がどこにも無かった。**
    #   （34番「3時間を超えたセッションを自動で切る」は2026-09-04に完了扱いになっていたが実体が無い）
    #   実害：たまごさん「20何時間もダラダラやらせないで。3時間やって進まなかったセッションは、
    #        もう3時間やらせても大して進まない。できていなかったらスパッと新しい人に引き継いで」
    #   ここで kill するだけでよい。死んだプロセスは、この下の既存の回収処理が
    #   ログから結果とURLを拾って awaiting_check か waiting へ自動で振り分ける。
    #   **列へ戻す判断は既存のまま。二重課金を増やす新しい経路は作らない。**
    for it in q.get("items", []):
        if it.get("status") != "running":
            continue
        pid = it.get("pid")
        started = it.get("startedAt")
        if not pid or not started:
            continue
        try:
            st = time.mktime(time.strptime(started[:19], "%Y-%m-%dT%H:%M:%S"))
        except Exception:
            continue
        limit_min = it.get("limitMin") or 180
        try:
            limit_min = min(int(limit_min), 180)   # 上限は常に3時間
        except Exception:
            limit_min = 180
        elapsed_min = (time.time() - st) / 60.0
        if elapsed_min <= limit_min:
            continue
        try:
            os.kill(int(pid), 0)          # 生きているか
        except Exception:
            continue                       # 既に死んでいる＝下の回収に任せる
        try:
            os.kill(int(pid), 15)          # まず行儀よく
            time.sleep(2)
            try:
                os.kill(int(pid), 0)
                os.kill(int(pid), 9)       # 残っていたら強制
            except Exception:
                pass
            it["cutAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
            it["cutReason"] = "%d分で3時間ルールにより打ち切り（次の担当へ引き継ぐ）" % int(elapsed_min)
            changed = True
            log("⏱ 3時間で切りました %s番「%s」（%d分）" % (it.get("n"), it.get("title"), int(elapsed_min)))
        except Exception as e:
            log("3時間カットに失敗 %s番: %s" % (it.get("n"), e))
    # 2026-09-13（793番停止事故）：確認待ちが複数件重なると、1件ずつのcontent_check
    #   （実URLを開く・最大30秒程度）が積み重なって合計45秒を超えうる。
    #   全体にも時間予算を持たせ、超えたら残りは次回のharvest()に回す（心臓を止めない）。
    HARVEST_BUDGET = 25.0
    _harvest_t0 = time.time()
    for it in q.get("items", []):
        if time.time() - _harvest_t0 > HARVEST_BUDGET:
            log("⏳ harvest予算(%d秒)超過。残りは次の周回へ" % int(HARVEST_BUDGET))
            break
        if it.get("status") != "running":
            continue
        pid = it.get("pid")
        alive = False
        if pid:
            try:
                os.kill(int(pid), 0)
                alive = True
            except Exception:
                alive = False
        if alive:
            continue
        # 死んでいる＝終わった。ログから結果を拾う
        sid = (it.get("sessionId") or "")[:8]
        logf = os.path.join(REPO, "status", "auto-launch-%s.log" % sid)
        result, urls = "", []
        raw = ""
        # 424番：どの仕事がいくら使ったか見える化用（cost_usdが無ければNoneのまま）
        cost_usd, tok_in, tok_out, tok_cache_read, tok_cache_creation, model_name = (
            None, 0, 0, 0, 0, "")
        try:
            raw = io.open(logf, encoding="utf-8", errors="ignore").read()
            for _line in raw.splitlines():
                _line = _line.strip()
                if not _line or '"total_cost_usd"' not in _line:
                    continue
                try:
                    _j = json.loads(_line)
                except Exception:
                    continue
                cost_usd = _j.get("total_cost_usd")
                _u = _j.get("usage") or {}
                tok_in = int(_u.get("input_tokens") or 0)
                tok_out = int(_u.get("output_tokens") or 0)
                tok_cache_read = int(_u.get("cache_read_input_tokens") or 0)
                tok_cache_creation = int(_u.get("cache_creation_input_tokens") or 0)
                _mu = _j.get("modelUsage") or {}
                if _mu:
                    model_name = "+".join(_mu.keys())
                break
            m = re.findall(r'"result"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
            if m:
                # 2026-09-04 文字化け修正：unicode_escape は日本語を latin-1 として壊す。
                #   \uXXXX を解いたあと latin-1→utf-8 で戻す。
                result = m[-1].encode("utf-8").decode("unicode_escape").encode("latin-1", "ignore").decode("utf-8", "ignore")
            # URLに混ざるゴミ（\n、全角括弧、バックスラッシュ）を落とす
            # 2026-09-04 修正：joy-relief-station.lovable.app 固定だと、成果物が
            #   別リポジトリ（tamago-shinchoku＝GitHub Pages等）の時にURLを一切拾えなかった
            #   （実例：20番「自動発車」自身がそれだった）。result本文（たまごさんへの完了報告文）
            #   から任意のhttps URLを拾う方式へ一般化する。
            # 2026-09-09修正（668番）：終端文字に全角『開き』括弧（）が抜けていたため、
            #   "https://...html（この道具自身が生成したページ" のように、閉じ括弧の無い
            #   日本語の説明文がURLへそのまま連結される記録ミスが繰り返し発生していた
            #   （420番実例。verify_check_pages.pyのhttp_get()がそのままurlopenして
            #   UnicodeEncodeError→誤って「404」とVerifierに報告される実害まで発生した）。
            #   全角開き括弧「（」・バッククォート「`」・全角スペースも終端文字に追加する。
            cand = re.findall(r"https://[^\s\"'（）)、。`　]*", result or raw)
            # 2026-09-04 たまごさん「確認のURLをくれるのはいいけど、**全く見当違いなところに連れて行く**
            #   からそれもやめて。**確認してからこっちに上げて。**時間の無駄だから」
            #   → 「直ったところ」を指していないURLを証拠として数えない。
            #     ここで弾かれると、この仕事はURLなし扱いになり自動でやり直しの列へ戻る。
            JUNK = (
                "example.com", "youtube.com/oembed", "youtube.com/results",
                "youtube.com/watch", "youtu.be/", "github.com/", "docs.", "localhost",
                "trycloudflare.com",
            )
            ROOTS = (
                "https://joy-relief-station.lovable.app",
                "https://tamago2022.github.io/tamago-shinchoku",
                "https://www.youtube.com", "https://youtube.com",
            )
            clean = []
            for u in cand:
                u = u.split("\\")[0].rstrip("/.,:;")
                if not u or u in clean or len(u) <= len("https://a.co"):
                    continue
                if any(j in u for j in JUNK):
                    continue
                if u in ROOTS:          # トップページだけ貼るのは「どこを見ればいいか分からない」
                    continue
                clean.append(u)
            urls = clean[:5]
        except Exception:
            pass
        # ---- 認証切れの検知（2026-09-05・実害あり）----
        # 実測：05:25〜05:28に10本以上が1〜3秒で死に、ログには
        #   "Failed to authenticate: OAuth session expired and could not be refreshed"
        # だけが残っていた。これはこちらでは直せない（たまごさんが claude にログインし直すしかない）。
        # 気づかずに回すと、**同じ失敗を何十本も量産して台帳が汚れるだけ**なので、見つけたら発車を止める。
        if "Failed to authenticate" in (raw or "") or "OAuth session expired" in (raw or ""):
            flag = os.path.join(REPO, "status", "no_launch.flag")
            if not os.path.exists(flag):
                io.open(flag, "w", encoding="utf-8").write(
                    "Claudeのログインが切れています（OAuth session expired）。"
                    "たまごさんが claude にログインし直すまで発車を止めます。%s\n"
                    % time.strftime("%Y-%m-%d %H:%M"))
            io.open(os.path.join(REPO, "status", "auth_expired.flag"), "w", encoding="utf-8").write(
                time.strftime("%Y-%m-%d %H:%M"))
            it["status"] = "waiting"      # 失敗ではないので、そのまま列に戻す（やり直し回数も数えない）
            for k in ("finishedAt", "result", "urls", "sessionId", "startedAt"):
                it.pop(k, None)
            it.pop("pid", None)
            changed = True
            log("🔑 ログインが切れています。%d番は列に戻し、発車を止めました" % it.get("n"))
            continue
        # ---- 週次利用上限の検知（2026-09-15・874番・実害あり）----
        # 実測：2026-09-14 16:12〜2026-09-15 18:00の約26時間、"claude -p"の起動が
        #   "You've hit your weekly limit · resets 6pm (Asia/Tokyo)" を1〜3秒で返し続けていた。
        #   これが上の認証切れと同じ「仕事の中身の問題ではない」ケースなのに扱いが無かったため、
        #   59件の正常な仕事が「URLが1本も無いまま終了」という通常失敗としてredo_guardに数えられ、
        #   そのままstuckへ落ちた。副作用として鬼監督(AI検品)・Lovable公開等、複数の仕組みの
        #   生死表が「dead」と誤検知した（実際に壊れていたのはコードではなく上限そのもの）。
        # 認証切れと同じ思想：失敗として数えず列に静かに戻す。ただし週次上限は"人が動かなくても
        #   時間が経てば直る"ので、resets時刻を読み取れれば自動再開する（読めなければ60分後に再試行、
        #   まだ上限中ならこのブロックがまた検知して再セットする＝自己修復）。
        if "weekly limit" in (raw or "").lower() or "weekly limit" in (result or "").lower():
            _wl_resume = None
            _wl_m = re.search(r"resets\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", raw or result or "", re.IGNORECASE)
            if _wl_m:
                try:
                    hh = int(_wl_m.group(1)) % 12
                    if (_wl_m.group(3) or "").lower() == "pm":
                        hh += 12
                    mm = int(_wl_m.group(2) or 0)
                    _now = datetime.now()
                    _cand = _now.replace(hour=hh, minute=mm, second=0, microsecond=0)
                    if _cand <= _now:
                        _cand += timedelta(days=1)
                    _wl_resume = _cand.strftime("%Y-%m-%dT%H:%M:%S+09:00")
                except Exception:
                    _wl_resume = None
            if not _wl_resume:
                _wl_resume = (datetime.now() + timedelta(minutes=60)).strftime("%Y-%m-%dT%H:%M:%S+09:00")
            flag = os.path.join(REPO, "status", "no_launch.flag")
            io.open(flag, "w", encoding="utf-8").write(
                "Claudeの週次利用上限に達しています（weekly limit）。"
                "resumeAt=%s まで新規発車を止めます。検知時刻:%s\n"
                % (_wl_resume, time.strftime("%Y-%m-%d %H:%M")))
            io.open(os.path.join(REPO, "status", "weekly_limit.flag"), "w", encoding="utf-8").write(
                json.dumps({"detectedAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                            "resumeAt": _wl_resume}, ensure_ascii=False))
            it["status"] = "waiting"      # 失敗ではないので、そのまま列に戻す（やり直し回数も数えない）
            for k in ("finishedAt", "result", "urls", "sessionId", "startedAt"):
                it.pop(k, None)
            it.pop("pid", None)
            changed = True
            log("⏳ 週次利用上限を検知。%d番は列に戻し、発車を%sまで止めます" % (it.get("n"), _wl_resume))
            continue
        # 2026-09-05 たまごさん「何も動いてない状態は作らないで。クレジット消費最小で」
        #   → 空回し（keepalive）は終わったら台帳から静かに消す。
        #     確認待ちに積むと、判定するものが増えるだけで意味がない（今日それで29件溜めた）。
        if it.get("keepalive"):
            it["_drop"] = True
            changed = True
            log("♻︎ 空回し %d番が終わりました（台帳からは消します）" % it.get("n"))
            continue
        # ---- 途中で切られたものを「終わった」にしない（2026-09-05）----
        # たまごさんに「結果が読み取れませんでした・URLの報告なし」を見せてしまった件の原因。
        # `claude -p --output-format json` は**終わるときに1行のJSONを吐く。**それが1文字も無い
        # ということは、途中で外から止められた（見張り番がマシンの重さで間引いた＝sheds、
        # 3時間の強制カット、こちらのpkillの巻き添え等）ということ。**仕事が失敗したのではない。**
        # 失敗として確認待ちに積むと、たまごさんが「これ何を見ればいいの」と確認だけさせられる。
        # → **続きから再開**する形で列に戻す。やり直しではないので、そこまでの作業は無駄にならない。
        # ---- 「来ない通知を待って終わっている」を、終わったことにしない（2026-09-08・653番）----
        # 2026-09-08に確認待ち28件を洗ったら、**証拠が1本も無い11件のうち10件がこれだった。**
        #   「バックグラウンドの完了通知を待ちます」「ビルド完了通知を待っています」
        #   「3件の完了を待機しています」——**その通知は永遠に来ない。**
        #   `claude -p` は一発実行なので、バックグラウンドに投げた時点で待ち受ける口が無い。
        #   セッションはそう言い残して終わり、台帳には「終わった」として確認待ちへ積まれ、
        #   **たまごさんの列に「何を見ればいいのか分からないもの」として溜まっていた。**
        #   中身（605=商売の芯、635=独自ドメイン、609=あめちゃん等）は、どれも途中で止まっている。
        # → 待ちの言葉で終わっていて、証拠URLが1本も無いものは、**列に戻す。**
        _r = (result or "").strip()
        _waiting_words = ("完了通知を待", "完了を待", "通知を待", "待機しています", "待っています",
                          "待ちます", "完了するまで待", "結果が読み取れませんでした")
        if (_r and not urls and len(_r) < 400
                and any(w in _r for w in _waiting_words)):
            stallc = int(it.get("bgWaitCount") or 0) + 1
            it["bgWaitCount"] = stallc
            it["status"] = "hold" if it.get("holdNote") else "waiting"
            it["priority"] = it.get("priority") or 2
            it["what"] = (it.get("what") or "") + (
                "\n\n【来ない通知を待って終わっていました・%d回目・%s】\n"
                "前回このタスクは「%s」と言い残して終わっています。**その通知は来ません。**\n"
                "`claude -p` は一発実行なので、バックグラウンドに投げた処理の完了通知を"
                "受け取る口が構造的にありません。\n"
                "**バックグラウンド実行（& や run_in_background）を使わないでください。**\n"
                "外部コマンドは必ず `timeout` を付けて前で待つ。ビルドやlintは同期で回す。\n"
                "mainへのpushが環境の安全装置で弾かれる場合は、"
                "`status/inbox/` に `{\"id\":\"...\",\"action\":\"git_push\",\"target\":\"\"}` を1本置けば"
                "ホスト側が押します（2026-09-08新設）。"
                % (stallc, time.strftime("%m-%d %H:%M"), _r[:120]))
            for k in ("finishedAt", "result", "urls", "sessionId", "startedAt"):
                it.pop(k, None)
            it.pop("pid", None)
            changed = True
            log("⏳ 来ない通知を待って終わっていたので列に戻す %d番「%s」（%d回目）"
                % (it.get("n"), it.get("title"), stallc))
            continue

        if not (result or "").strip() and '"result"' not in (raw or ""):
            cut = int(it.get("cutCount") or 0)
            if cut < 5:
                # 894番：この時点でelapsed_minとsessionIdをまだ持っているうちに記録する
                #   （下のfor文でstartedAtを消してしまうため、消す前に計算する）
                elapsed_min = _elapsed_min(it.get("startedAt"), time.strftime("%Y-%m-%dT%H:%M:%S+09:00"))
                it["cutCount"] = cut + 1
                it["status"] = "hold" if it.get("holdNote") else "waiting"
                if it.get("sessionId"):
                    it["resumeFrom"] = it["sessionId"]   # 続きから起こす
                    # 切られた時刻を残す。1時間放置すると起こすほうが高くつくため（下の🧊）
                    it["cutAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
                _inject_cut_note(it, elapsed_min)  # 894番：「切られた＝最初からやり直し」を無くす
                it["priority"] = it.get("priority") or 2
                for k in ("finishedAt", "result", "urls", "startedAt"):
                    it.pop(k, None)
                it.pop("pid", None)
                changed = True
                log("✂︎ 途中で切られたので続きから再開へ %d番「%s」（%d回目・%s分走行）"
                    % (it.get("n"), it.get("title"), cut + 1, elapsed_min if elapsed_min is not None else "?"))
                continue
            # 5回続けて切られるなら、切られ方そのものがおかしい。人の目に回す。
            it["result"] = ("【5回続けて途中で切られました】仕事の中身の問題ではなく、"
                            "走っている途中で外から止められています。マシンの重さで間引かれた"
                            "（見張り番のsheds）か、3時間の強制カットの可能性があります。")
            it["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
            it["urls"] = []
            it.pop("pid", None)
            it["status"] = "awaiting_check"
            changed = True
            append_outbox(it, False)
            log("⚠️ 5回続けて途中で切られた %d番「%s」→ 確認待ち" % (it.get("n"), it.get("title")))
            continue
        it["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
        it["result"] = (result or "（結果が読み取れませんでした）")[:1200]
        it["urls"] = urls
        # 424番：どの仕事がいくら使ったか見える化（結果の良し悪しに関わらず、使った分は記録する）
        try:
            _record_cost_by_task(it.get("n"), it.get("title"), cost_usd, tok_in, tok_out,
                                  tok_cache_read, tok_cache_creation, model_name,
                                  it.get("startedAt"), it["finishedAt"])
        except Exception as e:
            log("cost_by_task記録失敗 %s番: %s" % (it.get("n"), e))
        it.pop("pid", None)
        changed = True

        # ---- 大きい仕事の自動分割（2026-09-06 423番）----
        # command_ingest.py の queue_add() で『全ページ』『◯◯件』等を検知した仕事は、
        # 本体ではなく「対象の一覧を作るだけ」の1本目として積まれている（bigJob/phase=list）。
        # ここでその一覧作成が終わったのを検知し、status/split/{n}-list.json を読んで
        # 10件ずつの小分けタスクへ機械的に割り、発車待ちの末尾へ積む。
        if it.get("bigJob") and it.get("phase") == "list":
            if split_big_job(it, q, urls):
                append_outbox(it, bool(urls))
            continue

        # 2026-09-04 たまごさん「画面が変わって初めて完了。画面が変わって、なおかつ報告。
        #   Dispatchに報告。URLとともに。」
        #   → **URLが1本も無いものを確認待ちに入れない。**入れると、たまごさんが
        #     「これ何を見て判断すればいいの」と確認だけさせられる（＝水くみ）。
        #     URLが無い＝完了ではないので、こちらで黙って列に戻す。2回までは自動でやり直し、
        #     3回目は確認待ちへ回して人の目で見てもらう（無限ループを作らない）。
        tries = int(it.get("redoCount") or 0)
        if not urls and tries < 2:
            it["redoCount"] = tries + 1
            redo_guard.note_fail_reason(it, "URLが1本も無いまま終了")
            # 797番：3つのカウンタ合計が2に達したら、やり直しに戻さずここでstuck化する
            if redo_guard.should_stuck(it):
                redo_guard.mark_stuck(it, log)
                changed = True
                continue
            # 止める指示が出ている案件は、やり直しでも列に戻さない（戻すと勝手に再発車してしまう）
            it["status"] = "hold" if it.get("holdNote") else "waiting"
            it["priority"] = it.get("priority") or 2
            it["what"] = (it.get("what") or "") + (
                "\n\n【自動やり直し・%s】前回はURLを1本も出さずに終わりました。"
                "たまごさんの決まり：**画面が変わって、本番のURLを報告して、はじめて完了。**"
                "本番に出したページのURLを必ず報告に含めること。"
                "どうしても出せない事情があるなら、その理由を1行だけ書くこと。"
                % time.strftime("%m-%d %H:%M"))
            for k in ("finishedAt", "result", "urls", "sessionId", "startedAt"):
                it.pop(k, None)
            log("↩︎ URLなしのため自動やり直し %d番「%s」（%d回目）" % (it.get("n"), it.get("title"), tries + 1))
        else:
            # 679番：2回やり直してもURLが1本も出なかった場合、確認待ちへ渡す理由を1行だけ残す
            #   （たまごさんが「これ何を見ればいいの」とならないよう、URL無しの事実を明記する）。
            if not urls:
                it["result"] = (it.get("result") or "") + (
                    "\n\n【理由】本番URLが1本も出せませんでした（2回やり直し済み）。人の目で判断してください。")
            # 2026-09-06 新設：確認待ちに上げる直前に、確認ページの中身を機械が検品する。
            #   「結果が読み取れませんでした」「URLの報告なし」の次に多かった事故が
            #   「URLはあるが、開いても中身が無い確認ページ」だった。
            #   urlsの中から確認ページ（/share/check/を含むURL）を探し、実際に開いて中身を見る。
            check_url = next((u for u in urls if "/share/check/" in u), None)
            if check_url:
                ok, reason = content_check(check_url)
                _record_content_check(ok, reason, check_url, it.get("n"))
                if not ok:
                    fails = int(it.get("contentCheckFailCount") or 0) + 1
                    it["contentCheckFailCount"] = fails
                    if fails < 3:
                        it["status"] = "hold" if it.get("holdNote") else "waiting"
                        it["priority"] = it.get("priority") or 2
                        it["what"] = (it.get("what") or "") + (
                            "\n\n【確認ページの機械検品ではねられました・%d回目・%s】"
                            "理由：%s。確認ページ %s の中身を作り直してください。"
                            "①何を直したか1行 ②数字（何件中何件） ③押せるリンク一覧 "
                            "④可能なら前後のスクリーンショット、の4つを必ず入れること。"
                            % (fails, time.strftime("%m-%d %H:%M"), reason, check_url))
                        for k in ("finishedAt", "result", "urls", "sessionId", "startedAt"):
                            it.pop(k, None)
                        changed = True
                        log("🚫 確認ページ検品NG %d番「%s」→ 列に戻す（%d回目・理由:%s）"
                            % (it.get("n"), it.get("title"), fails, reason))
                        continue
                    else:
                        it["result"] = (it.get("result") or "") + (
                            "\n\n【確認ページの機械検品：3回連続ではねられたため人の目に回します】理由：%s"
                            % reason)
                        it["status"] = "awaiting_check"
                        append_outbox(it, bool(urls))
                        log("⚠️ 確認ページ検品3回連続NG %d番「%s」→ 人の目へ（理由:%s）"
                            % (it.get("n"), it.get("title"), reason))
                        continue
                log("✅ 確認ページ検品OK %d番「%s」（%s）" % (it.get("n"), it.get("title"), check_url))
            # 898番：関所(sekisho)。書かれている数字（px/%）が実測の跡と食い違っていないかを
            #   ここで機械が見る（2026-09-16の事故：「上17px」と書いたが実測は9.6pxだった、への対策）。
            #   ブラウザを使わない軽い判定なのでharvest()の時間予算内で同期実行してよい。
            if check_url:
                sek_ok, sek_reason = sekisho.check_number_claims_for_url(check_url, it.get("result") or "")
                sekisho.record_result(it.get("n"), sek_ok, [] if sek_ok else [sek_reason])
                if not sek_ok:
                    fails = int(it.get("sekishoFailCount") or 0) + 1
                    it["sekishoFailCount"] = fails
                    if fails < 3:
                        it["status"] = "hold" if it.get("holdNote") else "waiting"
                        it["priority"] = it.get("priority") or 2
                        it["what"] = (it.get("what") or "") + (
                            "\n\n【関所(sekisho)ではねられました・%d回目・%s】理由：%s\n"
                            "書いてある数字が、実測した跡と食い違っています。"
                            "実際に測り直し、測った生の数字（「実測: ...」や<pre>）を確認ページに残してください。"
                            % (fails, time.strftime("%m-%d %H:%M"), sek_reason))
                        for k in ("finishedAt", "result", "urls", "sessionId", "startedAt"):
                            it.pop(k, None)
                        changed = True
                        log("🚫 関所(sekisho)NG %d番「%s」→ 列に戻す（%d回目・理由:%s）"
                            % (it.get("n"), it.get("title"), fails, sek_reason))
                        continue
                    else:
                        it["result"] = (it.get("result") or "") + (
                            "\n\n【関所(sekisho)：3回連続ではねられたため人の目に回します】理由：%s" % sek_reason)
                        it["status"] = "awaiting_check"
                        append_outbox(it, bool(urls))
                        log("⚠️ 関所(sekisho)3回連続NG %d番「%s」→ 人の目へ（理由:%s）"
                            % (it.get("n"), it.get("title"), sek_reason))
                        continue
                else:
                    log("✅ 関所(sekisho)OK %d番「%s」" % (it.get("n"), it.get("title")))
            # 案件#800：3段検品の2段目「触る検品」。確認ページの中身が正しくても、
            # 実際にボタンを押すと無反応、という事故を機械が先に見つける。
            # ここもharvest()の45秒watchdogを超えないよう、別プロセスで着火するだけで同期待ちしない。
            touch_target = _pick_touch_target(check_url, urls)
            if touch_target and start_touch_check(it, touch_target):
                it["status"] = "touchchecking"
                changed = True
                log("👆 触る検品へ回す %d番「%s」（%s）" % (it.get("n"), it.get("title"), touch_target))
            # 2026-09-06 新設（416番）：確認待ちに上げる前に、別プロセスのclaude(Sonnet)を1本だけ
            # バックグラウンドで着火してAI検品(Verifier=鬼監督3段目)させる。harvest()は15秒おきに
            # 軽く回る前提（heartbeat.sh）なので、ここでは絶対に同期待ちしない。
            # 触る検品の対象URLが無かった／着火に失敗した場合は、従来どおり3段目へ直接進む。
            elif start_verify(it, check_url, urls):
                it["status"] = "verifying"
                changed = True
                log("🔎 AI検品(鬼監督)へ回す %d番「%s」" % (it.get("n"), it.get("title")))
            else:
                it["status"] = "awaiting_check"      # たまごさんの確認待ち（検品できないので素通し）
                append_outbox(it, bool(urls))
                log("✅ 終了を回収 %d番「%s」→ 確認待ち（URL %d本・検品は対象外）"
                    % (it.get("n"), it.get("title"), len(urls)))

    # ---- 触る検品（2段目）の回収（案件#800新設）----
    # 上のループでstatus="touchchecking"にした項目を、別のループでバックグラウンドから回収する。
    # PASS → 3段目(AI検品/鬼監督)へ進める。FAIL → 797番のredo_guardへ合流してやり直し。
    # 技術的エラー(None) → この段は素通しして3段目へ直接進める（インフラの都合で仕事を止めない）。
    for it in q.get("items", []):
        if it.get("status") != "touchchecking":
            continue
        touch_outcome = collect_touch_check(it)
        if touch_outcome is None:
            continue  # まだ検品中。次回また見る
        t_ok, t_reason, t_report = touch_outcome
        t_url = it.get("touchUrl") or ""
        _record_touch_check(t_ok, t_reason, t_url, it.get("n"), t_report)
        for k in ("touchPid", "touchOutJson", "touchLog", "touchStartedAt"):
            it.pop(k, None)
        if t_ok is False:
            fails = int(it.get("touchCheckFailCount") or 0) + 1
            it["touchCheckFailCount"] = fails
            redo_guard.note_fail_reason(it, "触る検品NG：%s" % t_reason)
            if redo_guard.should_stuck(it):
                redo_guard.mark_stuck(it, log)
                changed = True
                log("🛑 触る検品NG→797番のstuck化に合流 %d番「%s」（理由:%s）"
                    % (it.get("n"), it.get("title"), t_reason))
                continue
            it["status"] = "hold" if it.get("holdNote") else "waiting"
            it["priority"] = it.get("priority") or 2
            it["what"] = (it.get("what") or "") + (
                "\n\n【触る検品(2段目)ではねられました・%d回目・%s】理由：%s\n"
                "実際に押しても反応しない要素があります。curlで読めても、押して動くかを"
                "`node %s <URL>` で自分でも確認してから直してください。"
                % (fails, time.strftime("%m-%d %H:%M"), t_reason, TOUCH_CHECK_SCRIPT))
            for k in ("finishedAt", "result", "urls", "sessionId", "startedAt"):
                it.pop(k, None)
            it.pop("touchUrl", None)
            changed = True
            log("🚫 触る検品NG %d番「%s」→ 列に戻す（%d回目・理由:%s）"
                % (it.get("n"), it.get("title"), fails, t_reason))
            continue
        # PASS または 技術的エラー(None) → 3段目(鬼監督)へ進める。
        # 技術的エラーの場合でも、その旨をtouchCheckNoteへ書き、鬼監督自身が
        # 必要なら自分でnode検品を実行できるようにする（build_verify_promptが埋め込む）。
        check_url2 = next((u for u in (it.get("urls") or []) if "/share/check/" in u), None)
        it["touchCheckNote"] = (
            ("押した結果：%s（対象: %s）" % (t_reason, t_url)) if t_url else "（触る検品は未実施）"
        )
        changed = True
        if start_verify(it, check_url2, it.get("urls") or []):
            it["status"] = "verifying"
            log("🔎 触る検品%s→AI検品(鬼監督)へ %d番「%s」（理由:%s）"
                % ("PASS" if t_ok else "技術的エラー", it.get("n"), it.get("title"), t_reason))
        else:
            it["status"] = "awaiting_check"
            append_outbox(it, bool(it.get("urls")))
            log("✅ 触る検品%s→検品対象外のため確認待ち %d番「%s」"
                % ("PASS" if t_ok else "技術的エラー", it.get("n"), it.get("title")))

    # ---- AI検品（Verifier=鬼監督3段目）の回収（2026-09-06新設・416番／2026-09-13案件#800で鬼監督化）----
    # 上のループでstatus="verifying"にした項目を、別のループでバックグラウンドから回収する。
    # ここも同期待ちしない：まだ生きていれば次回のharvest()にそのまま持ち越す。
    for it in q.get("items", []):
        if it.get("status") != "verifying":
            continue
        outcome = collect_verify(it)
        if outcome is None:
            continue  # まだ検品中。次回また見る
        ok, reason, cost = outcome
        target = it.get("verifyUrl") or ""
        _record_oni_kantoku(ok, reason, it.get("n"), it.get("title"), it.get("touchCheckNote"), cost)
        it.pop("touchCheckNote", None)
        _record_ai_verify(ok, reason, cost, target, it.get("n"))
        for k in ("verifyPid", "verifySessionId", "verifyLog", "verifyStartedAt", "verifyUrl"):
            it.pop(k, None)
        if ok is False:
            fails = int(it.get("aiVerifyFailCount") or 0) + 1
            it["aiVerifyFailCount"] = fails
            redo_guard.note_fail_reason(it, reason or "(AI検品の理由が空でした)")
            # 797番：3つのカウンタ合計が2に達したら、3回目を待たずここでstuck化する
            if redo_guard.should_stuck(it):
                redo_guard.mark_stuck(it, log)
                changed = True
                continue
            if fails < 3:
                it["status"] = "hold" if it.get("holdNote") else "waiting"
                it["priority"] = it.get("priority") or 2
                it["what"] = (it.get("what") or "") + (
                    "\n\n【AI検品(Verifier)ではねられました・%d回目・%s】理由：%s。"
                    "依頼内容と実際の変化が一致するよう、報告と確認ページを作り直してください。"
                    % (fails, time.strftime("%m-%d %H:%M"), reason))
                for k in ("finishedAt", "result", "urls", "sessionId", "startedAt"):
                    it.pop(k, None)
                changed = True
                log("🚫 AI検品NG %d番「%s」→ 列に戻す（%d回目・理由:%s・$%.3f）"
                    % (it.get("n"), it.get("title"), fails, reason, cost or 0))
                continue
            it["result"] = (it.get("result") or "") + (
                "\n\n【AI検品(Verifier)：3回連続で不合格のため人の目に回します】理由：%s" % reason)
            it["status"] = "awaiting_check"
            append_outbox(it, bool(it.get("urls")))
            changed = True
            log("⚠️ AI検品3回連続NG %d番「%s」→ 人の目へ（理由:%s）" % (it.get("n"), it.get("title"), reason))
            continue
        # 2026-09-06 443番：確認待ちをAI検品で自動OKにする（たまごさん本人の権限譲渡・07:00）。
        # 「鬼監督が判定してよい。合格→そのまま完了（たまごさんに見せない）。
        #  上げてよいのは鬼監督が判断できなかったものだけ」に対応。
        # PASS → 人の確認を待たず status=done（queue_ok と同じ形）。
        # None（技術的エラー・判断できない）→ 従来どおり awaiting_check（人の目）へ。
        if ok is None:
            it["result"] = (it.get("result") or "") + ("\n\n【AI検品：%s】" % reason)
            it["status"] = "awaiting_check"
            append_outbox(it, bool(it.get("urls")))
            log("… AI検品：判断できないため人の目へ %d番「%s」・理由:%s" % (it.get("n"), it.get("title"), reason))
        else:
            it["status"] = "done"
            it["checkedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            it["okBy"] = "ai-verifier-auto"
            it["okNote"] = "鬼監督AI検品PASS：%s" % reason
            append_outbox(it, True)
            log("✅ AI検品OK→自動完了（人の確認スキップ） %d番「%s」・理由:%s・$%.3f"
                % (it.get("n"), it.get("title"), reason, cost or 0))
            # 616番：自動OKもたまごさんがOKを押すのと同じ「完了」。棚へ自動登録。
            # 759番：新しく作った／直した、どちらも同じ棚（消えない）へrecord_done()で積む。
            try:
                if HERE not in sys.path:
                    sys.path.insert(0, HERE)
                import dekimono_lib
                dekimono_lib.record_done(it.get("n"), it.get("title"), it.get("result"), it.get("urls"))
            except Exception:
                pass
        changed = True

    # ---- 溜まった確認待ちを鬼監督に順番に見せる（2026-09-08新設・650番）----
    # たまごさんの言葉：「まじで大量に間違われて、そっちが勝手に間違えて、
    #   全部確認してくれって言われるのは無理ゲーです」「82件を1個ずつ見るのは無理」。
    # 鬼監督への権限譲渡（2026-09-06）でこの先の新しい分は自動判定されるようになったが、
    # **その前に溜まった分は誰も見ないまま確認待ちに残り続けていた**（2026-09-08時点で35件）。
    # ここで、確認ページを持っていてまだ一度も検品されていないものを、
    # 1回のharvestにつき1本だけ、静かに検品へ回す。合格すれば自動で完了になり、
    # たまごさんの列から消える。判断できなかったものだけが確認待ちに残る。
    #
    # 1本ずつなのは意図的：機械の負荷とクレジットを跳ねさせない。15秒おきに回るので、
    # 検品が空いていれば数時間で列が溶ける。急がないことが軽さを守る。
    try:
        verifying_now = len([x for x in q.get("items", [])
                             if x.get("status") == "verifying"])
        if verifying_now < 2:
            for it in q.get("items", []):
                if it.get("status") != "awaiting_check":
                    continue
                if it.get("backlogVerified") or it.get("aiVerifyFailCount"):
                    continue
                # 証拠ページが開けなかったものは、3時間おきにもう一度だけ見に行く。
                # 復旧のpushがまだ本番に届いていないだけ、ということがあるため。
                # 2026-09-12（776番）：回線が一時的に繋がらなかっただけの時は、_contentCheckCooldownMin
                #   （既定1分）だけ待てば十分。3時間固定だと、たまたま繋がらなかった1回で3時間も
                #   検品の順番から外れてしまう（＝人には見えない形でその項目だけ止まる）。
                _ec = it.get("evidenceCheckedAt")
                if _ec:
                    _cooldown_sec = float(it.get("_contentCheckCooldownMin") or 180) * 60
                    try:
                        if (time.time() - time.mktime(
                                time.strptime(_ec[:19], "%Y-%m-%dT%H:%M:%S"))) < _cooldown_sec:
                            continue
                        it.pop("_contentCheckCooldownMin", None)
                    except Exception:
                        pass
                urls = it.get("urls") or []
                check_url = next((u for u in urls if "/share/check/" in u), None)
                if not check_url and not urls:
                    continue          # 証拠が1本も無いものは検品しようがない。人の目へ残す
                it["backlogVerified"] = True   # 二度と同じものを着火しない印
                # ---- 2026-09-08 17:28 すぐ見つかった穴。ここで止める。----
                # 645番の容量確保で share/check の古いページ256件を外付けへ退避した。
                # その結果、**昔の確認ページURLは軒並み404になっている**。
                # 何も考えず検品へ回すと、鬼監督は「ページが開けない」で全部を不合格にし、
                # **すでに終わっている仕事30件が列に戻って作り直しになる**（実測：45番・48番）。
                # 仕事そのものが悪かったわけではなく、証拠の置き場所をこちらが動かしただけ。
                # → 開けないものは検品にかけない。証拠が消えた印だけ付けて、人の目へ残す。
                if check_url:
                    alive, why = content_check(check_url)
                    if not alive and "取得に失敗" in (why or ""):
                        # 回線の一時的な失敗。今日は見送って、次の巡回でまた見る。
                        # 2026-09-12（776番）：以前はここで即座にbacklogVerifiedを外していたため、
                        #   ネットワークが数分単位で不調な間、同じ番号を15秒おきに無限リトライし続けた。
                        #   socket.setdefaulttimeout()でハング自体は防いだが、多重防御として
                        #   1分間のクールダウンを入れ、詰まりかけても他のitemの検品を止めない。
                        it.pop("backlogVerified", None)
                        it["evidenceCheckedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
                        it["_contentCheckCooldownMin"] = 1
                        log("… 確認ページに繋がらないので次回へ %d番（%s）" % (it.get("n"), why))
                        break
                    if not alive and ("HTTP" in (why or "") or "開け" in (why or "")):
                        it["evidenceGone"] = True
                        it["evidenceCheckedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
                        it.pop("backlogVerified", None)   # 復旧したら3時間後にもう一度見る
                        it["result"] = (it.get("result") or "") + (
                            "\n\n【証拠ページが見当たりません】%s が開けません（%s）。"
                            "645番の容量確保で古い確認ページを外付けへ退避したためです。"
                            "仕事のやり直しは不要。証拠だけが行方不明です。" % (check_url, why))
                        changed = True
                        log("📄 証拠ページが消えている %d番「%s」→ 検品にかけない"
                            % (it.get("n"), it.get("title")))
                        break
                # 案件#800：バックログ掃き出し経路にも触る検品(2段目)を通す。
                touch_target = _pick_touch_target(check_url, urls)
                if touch_target and start_touch_check(it, touch_target):
                    it["status"] = "touchchecking"
                    changed = True
                    log("👆 溜まっていた確認待ちを触る検品へ %d番「%s」（%s）"
                        % (it.get("n"), it.get("title"), touch_target))
                elif start_verify(it, check_url, urls):
                    it["status"] = "verifying"
                    changed = True
                    log("🔎 溜まっていた確認待ちを検品へ %d番「%s」"
                        % (it.get("n"), it.get("title")))
                break
    except Exception as e:
        log("確認待ちの掃き出しで失敗（本流は止めない）: %s" % e)

    _dropped_ns = [x.get("n") for x in q.get("items", []) if x.get("_drop")]
    if _dropped_ns:
        q["items"] = [x for x in q["items"] if not x.get("_drop")]
        q["_pendingDeletedNs"] = sorted(set(q.get("_pendingDeletedNs") or []) | set(_dropped_ns))
    return changed


PROMPT_RULES_DIR = os.path.join(HERE, "prompt_rules")
PROMPT_INDEX = os.path.join(PROMPT_RULES_DIR, "INDEX.json")


def _load_rule_file(name):
    """tools/prompt_rules/<name>.md を読む。無ければ空文字（発車自体は止めない）。"""
    path = os.path.join(PROMPT_RULES_DIR, "%s.md" % name)
    try:
        return io.open(path, encoding="utf-8").read().rstrip("\n")
    except Exception as e:
        log("prompt_rules読み込み失敗 %s: %s" % (name, e))
        return ""


SESSION_PREAMBLE = os.path.join(HERE, "session_preamble.md")


def _load_session_preamble():
    """tools/session_preamble.md を指示文のいちばん先頭に入れるために読む（2026-09-18・939番）。

    たまごさんの言葉（そのまま）：
    「まずは間違いを繰り返さないってことかな。何回も言わせないようにする仕組み作りからかな。」

    これまでDispatchが子セッションを立てるとき、禁止事項（たまごさんに確認を出さない／
    computer-useを使わない／Chromeのタブを増やさない 等）を**毎回手で書いていた**。
    書いた回は事故が起きず、書き忘れた回だけ同じ事故が起きた＝人の記憶が単一障害点だった。

    ここで機械側に寄せる。INDEX.jsonのalwaysリストに足す形は採らない：
    **索引から足し忘れる余地を残したくない**ため、ファイルの存在だけで必ず先頭に入る形にした
    （INDEX.jsonを1行も触らずに効く）。読めなければ空文字を返して発車自体は止めない。
    """
    try:
        return io.open(SESSION_PREAMBLE, encoding="utf-8").read().rstrip("\n")
    except Exception as e:
        log("session_preamble読み込み失敗: %s" % e)
        return ""


def _prompt_topic_matches(text, keywords):
    t = (text or "").lower()
    return any((k or "").lower() in t for k in (keywords or []))


def build_prompt(item):
    """着火用の指示文。

    2026-09-07（628番・深津さんの指摘対応）：
    「監督AIが大計画.mdを読んでissueを作り、実務AIが『大計画に沿ってるか』を確認して作る……
     AGENTS.mdを全員が読める形で肥大化させること自体がいけない」という指摘が、この工場の
     build_prompt()そのものに直撃していた（固定テンプレートだけでUTF-8で約23,000バイト＝
     Dispatch実測「24,237文字」相当が、案件の中身と無関係に毎回全タスクへ注入されていた）。

    対応：固定文言を tools/prompt_rules/*.md へ1件1ファイルで分割し、
    tools/prompt_rules/INDEX.json を索引にした。
      - always … 毎回必ず渡す薄い核（報告の形・証拠・時間・進め方・禁止など）
      - topics … タイトル・本文にkeywordsのどれかが含まれる時だけ差し込む状況別ルール
        （ブラウザ操作／動画・音声／コピー・タイトル執筆／おすすめ導線／falのみ該当）
    内容は元のbase templateから完全一致で抽出したもので、1文字も削っていない
    （分割時に sum(chunks) == 元の長さ を実測して確認済み）。置き場所を変えただけ。
    """
    n = item.get("n")
    title = item.get("title") or ""
    what = item.get("what") or ""
    header = """【自動発車】発車待ちの{n}番です。

# やること
**{title}**

{what}

# 完了条件（この1行が満たされたら完了）
**{title} が本番に反映され、その本番URLがDispatchに届いている。**

# 1セットの定義（これ未満は成果ゼロ）
① 実装 → ② main合流 → ③ **Lovableの「公開」を押す**（聞かずに押す。エージェント・チャット・ビルド・コード編集は絶対に使わない、公開ボタンだけ）→ ④ **本番URLを開いて自分の目で確認** → ⑤ **DispatchへURL報告**

**main合流だけでは成果ゼロです。**本番で確認せずに「直しました」と言わないでください。

**注意：報告の中にhttpsで始まる本番URLが1本も無い場合、この仕事は自動的にやり直しの列へ戻されます**（たまごさんに見せる前に機械が弾きます）。URLを出せない事情があるなら、その理由を1行だけ書いてください。

**たまごさんの言葉（2026-09-04）：**
> 「**pushを完了と言ってしまう。これはダメだね。画面が変わって初めて完了。画面が変わって、なおかつ報告。Dispatchに報告。URLとともに。**セッションの中で完了したとか言って、それはもう完了してない。**報告しないのはダメ。**」
""".format(n=n, title=title, what=what)

    idx = load(PROMPT_INDEX, {"always": [], "topics": []})
    # 939番：共通の枷はヘッダーより前＝指示文のいちばん先頭に置く。
    # 後ろに置くと、長い依頼文(what)で埋まった時に読み飛ばされる実測があったため。
    parts = []
    preamble = _load_session_preamble()
    if preamble:
        parts.append(preamble)
    parts.append(header)
    for name in idx.get("always") or []:
        text = _load_rule_file(name)
        if text:
            parts.append(text)
    match_text = "%s %s" % (title, what)
    for topic in idx.get("topics") or []:
        if _prompt_topic_matches(match_text, topic.get("keywords")):
            text = _load_rule_file(topic.get("file"))
            if text:
                parts.append(text)
    return "\n\n".join(parts)


# ---- 進捗表の軽量化（2026-09-10）----
#   queue.json（1.4MB超・大半はwhat本文）を進捗表アプリが毎回丸ごと運んで重かったため、
#   what/resultを抜いた軽量版 status/queue_light.json を別途作る（build_queue_light.py）。
#   queue.jsonが更新される（＝着火・回収・確認処理のどれかがsave_queueを呼ぶ）たびに
#   作り直せば十分なので、mtimeが前回チェック時から変わっていた時だけ再生成する。
#   失敗しても発車判定（本体処理）は絶対に止めない＝try/exceptで必ず囲む。
QUEUE_LIGHT_MTIME_STATE = os.path.join(REPO, "status", ".queue_light_mtime")


def _maybe_rebuild_queue_light():
    try:
        mtime = os.path.getmtime(QUEUE)
    except Exception:
        return
    last = None
    try:
        last = float(io.open(QUEUE_LIGHT_MTIME_STATE, encoding="utf-8").read().strip())
    except Exception:
        last = None
    if last is not None and mtime <= last:
        return
    try:
        sys.path.insert(0, HERE)
        import build_queue_light
        build_queue_light.build()
        with io.open(QUEUE_LIGHT_MTIME_STATE, "w", encoding="utf-8") as f:
            f.write(str(mtime))
    except Exception as e:
        log("queue_light再生成に失敗（本体は継続）: %s" % e)


def effective_priority(it, prio):
    """発車待ち1件の「実効優先度」を返す。item自身が持つpriorityを最優先し、
    無ければ古い priority.json の Qキー方式（prio辞書）へフォールバック。どちらも無指定なら9（最後）。
    793番（2026-09-14）：_main_impl()内のネスト関数だったものをテスト可能な形でここへ切り出した
    （動作は元のコードと完全に同一。tools/test_urgent_lane.py から直接呼べるようにするため）。"""
    p = it.get("priority") or (prio or {}).get("Q%d" % it.get("n"))
    return int(p) if p else 9


def queue_rank_key(it, prio):
    """発車待ちの並び替えキー。auto_launcher._main_impl()（実際の発車順）と
    tools/test_urgent_lane.py（回帰テスト）の両方がこの1つの規則だけを見る。

    並び：① urgent（すぐ見たい）が最優先 → ② 優先度（A=1〜E=5・空き枠F=6） →
         ③ 手で並べ替えた順（order） → ④ 番号。

    2026-09-13 たまごさん「すぐ見たいやつ、ちょっと別枠にしてくんないかな？
    俺の中で優先順位全然違うから。1週間後でいいよってのもあれば、明日にでも見たいってのもある」
    → urgent:true（すぐ見たい）は priority より強い。旗を立てるのはDispatchかたまごさんだけ
    （command_ingest.queue_urgent／自動では立たない）。理由は urgentReason に入れる。"""
    p = effective_priority(it, prio)
    o = it.get("order")
    u = 0 if it.get("urgent") else 1
    return (u, p, int(o) if isinstance(o, int) else 10 ** 6, it.get("n") or 99)


def _main_impl():
  # 2026-09-13（793番停止事故）：以前はここで harvest()（確認ページのURLを1本ずつ実際に
  #   開いて検品する content_check を含む・重い/ネットワーク待ちが起こりうる）を発車判定より
  #   **先に**呼んでいた。content_check がDNS応答待ちなどで詰まると、発車判定にすら
  #   たどり着けず「45秒以内に終わらず強制終了」が延々続き、**1本も発車できなくなった**
  #   （実測：05:26〜05:34に8回連続）。
  #   → harvest は main() 側で発車の**あと**に回す（下記コメント参照）。「発車は必ず先にやる」。
  #   room計算に使う alive/queue_alive は元々 pid の生死を直接見て出しているので、
  #   harvest を先に呼ばなくても発車の可否判定は正しく動く。
  with queue_lock():
      q = load(QUEUE, {})
      items = q.get("items") or []
      if not items:
          return 0
      # 案件#687：この時点の中身を控えておき、save_queue()へ渡す。
      #   自分が「実際に変更した項目」だけを正確に見分けて重ね書きするため
      #   （渡さないと保守的に「持っている項目は全部変更した」扱いになる）。
      _snap = queue_store.snapshot_items(q)
      # 2026-09-04 たまごさん「ガソリンが切れる。家にたどり着かないよ」（火曜まで残り14%）
      #   → status/no_launch.flag があるあいだは**1本も発車させない**。
      #     回収（終わったものを確認待ちへ）と受信箱は動かすので、判定と繰り上げの練習はできる。
      #     再開はこのファイルを消すだけ。
      # 2026-09-05 ログイン切れで止めているだけのときは、**Claudeを使わない空回しは通す。**
      #   本物は出せないが、工場が死んだ状態にはしない（たまごさん「止まるのはNG。半永久装置」）。
      _flag = os.path.join(REPO, "status", "no_launch.flag")
      auth_only = False
      if os.path.exists(_flag):
          try:
              _flag_text = io.open(_flag, encoding="utf-8").read()
          except Exception:
              _flag_text = ""
          auth_only = "ログインが切れています" in _flag_text
          # 2026-09-15（874番）：週次利用上限で止めているだけなら、resumeAtを過ぎた時点で
          #   自分で気づいて自動解除する（認証切れと違い、人が動かなくても時間が経てば直るため）。
          if "週次利用上限" in _flag_text:
              _wl = load(os.path.join(REPO, "status", "weekly_limit.flag"), {}) or {}
              _resume_at = _wl.get("resumeAt") or ""
              _past = False
              if _resume_at:
                  try:
                      _past = datetime.strptime(_resume_at[:19], "%Y-%m-%dT%H:%M:%S") <= datetime.now()
                  except Exception:
                      _past = False
              if _past:
                  for _f in (_flag, os.path.join(REPO, "status", "weekly_limit.flag")):
                      try:
                          os.remove(_f)
                      except Exception:
                          pass
                  log("⏳ 週次利用上限のresumeAtを過ぎたので発車を再開します")
              else:
                  return 0
          elif not auth_only:
              return 0
      m = load(MACHINE, {})
      quota = load(QUOTA, {})

      # ---- 安全弁：マシン ----
      # 2026-09-05 17:25 **スワップが増えているだけでは止めない。**
      #   たまごさんの言葉：「**多少間違えたとしても、ちゃんと3時間ずっと走り続けて
      #   進捗が報告されるんだったら、そっちの方がよっぽど良い。承認しないと進まないよりよっぽど良い。**」
      #   実測：メモリはgreen（余裕あり）なのに swapIncreasing=True だけで**1本も出せず全停止**していた。
      #   スワップは平常時でも増えることがある。止めるのは本当に危ないとき——
      #   メモリ圧が赤、ディスクが5GB未満、またはメモリが黄色でかつスワップも増えているとき——だけにする。
      mem = m.get("memPressure")
      swap_up = bool(m.get("swapIncreasing"))
      really_bad = (mem == "red") or ((m.get("diskFreeGB") or 99) < 5) or (mem == "yellow" and swap_up)
      # 計測が10分以上古いときは、その判断を信じない（古い「危険」で工場が止まり続けるのを防ぐ）
      try:
          import datetime as _dt
          _t = m.get("measuredAt")
          if _t and (time.time() - _dt.datetime.strptime(_t[:19], "%Y-%m-%dT%H:%M:%S").timestamp()) > 600:
              really_bad = False
      except Exception:
          pass
      if really_bad:
          log("見送り: Macが危険（mem=%s swapUp=%s disk=%s）" % (m.get("memPressure"), m.get("swapIncreasing"), m.get("diskFreeGB")))
          return 0
      # ---- 安全弁：クレジット ----
      #   テスト用のカラ発車（"test": true）はClaudeを起動しない＝クレジットを1円も使わないので、
      #   週枠が上限でも通す。ここで一緒に止めていると、枠が苦しいときほど動作確認ができなくなる。
      credit_stop = (quota.get("allLevel") == "stop") or auth_only
      # 2026-09-05 たまごさん「ループシステムを作ってるんだから。**止まるのはNG。半永久装置。**」
      #   週枠が上限でも、**1本も走っていないなら、ここで止めない。**
      #   下で「空回し（Claudeを起動しない＝クレジット0）」を1本入れて、工場が回っている状態を保つ。
      _running_any = any(it.get("status") == "running" for it in items)
      _test_waiting = any(it.get("status") == "waiting" and it.get("test") for it in items)
      if credit_stop and _running_any and not _test_waiting:
          # ★2026-09-19：ここは長らく理由を取り違えて書いていた。credit_stop は
          #   「週枠が上限」だけでなく「Claudeのログインが切れている(auth_only)」でも立つ。
          #   実際 09-18 03:19 からログイン切れで本物が1本も出ていないのに、ログには
          #   「週枠が上限（all=None%）」とだけ出続け、読んだ人が枠の問題だと誤診していた。
          #   止まっている本当の理由を、そのまま書く。
          if auth_only:
              log("見送り: Claudeのログインが切れています（status/no_launch.flag。"
                  "claude にログインし直すまで本物は1本も出せません。戻れば auth_watch.py が自動で再開します）")
          else:
              log("見送り: 週枠が上限（all=%s%%）" % quota.get("allPct"))
          return 0

      # 2026-09-04 machine.json は重い計測（27秒〜）でしか書き変わらないので、最大5分ぶん古い。
      #   そのままだと「もう死んでいるセッション」を走行中として数え、空きが出ても繰り上がらなかった。
      #   ここで pid の生死をその場で見て、死んでいるぶんを除く（数百マイクロ秒で終わる）。
      def _pid_alive(pid):
          try:
              os.kill(int(pid), 0)
              return True
          except Exception:
              return False

      alive = len([s for s in (m.get("sessionList") or [])
                   if countable(s) and (not s.get("pid") or _pid_alive(s.get("pid")))])
      # 2026-09-04 テストで見つけた穴：machine.json は「Claudeのセッション」しか載せていないので、
      #   そこに現れないものを走らせると **走行0本と数えて上限を無視して発車し続ける**（実測：上限3本なのに6本出た）。
      #   台帳側で running になっていて、まだ生きているものも必ず数える。
      #   本物のセッションでも、計測が遅れて載っていない瞬間に同じことが起きる＝クレジットの垂れ流しになる。
      queue_alive = len([it for it in items
                         if it.get("status") == "running" and it.get("pid") and _pid_alive(it.get("pid"))])
      alive = max(alive, queue_alive)
      safe_max = m.get("safeMax")
      if safe_max is None:
          # 2026-09-16：「測れないから止まる」は工場を丸ごと止める最も損な止まり方。
          # machine.jsonが古い/壊れている間も、安全な既定値3本で発車自体は続ける。
          safe_max = 3
          log("safeMaxが取れないため既定値3本で発車を続けます")
      # たまごさんが進捗表で決めた「同時に走る本数」。マシンの安全上限より小さい方を採る。
      cap = (load(os.path.join(REPO, "status", "launch_cap.json"), {}) or {}).get("cap")
      if isinstance(cap, int):
          safe_max = min(safe_max, cap)
      # 2026-09-05：発車待ちがテスト（Claudeを起動しない・眠るだけ）しか無いときは、
      #   マシンの安全上限（Claudeセッションを何本まで抱えられるか）に縛られる意味がない。
      #   たまごさんの指定本数（cap）だけを見る。実処理はsleepなので負荷はほぼゼロ。
      only_tests = all(it.get("test") for it in items if it.get("status") == "waiting")
      if only_tests and isinstance(cap, int):
          safe_max = cap
      if alive >= safe_max:
          log("見送り: 走行%d本／上限%d本（空きなし）" % (alive, safe_max))
          return 0

      # ---- 優先度順に並べる。たまごさんがPWAで付けたPが最優先、次に元の番号 ----
      # 682番（2026-09-09）画面表示は A〜E（＋空き枠F）の文字だが、中身の数字(1〜6)は変えていない。
      #   A=1 今すぐ／B=2 早めに／C=3 普通／D=4 後回し／E=5 いつでも／F=6 空き枠（安全弁だけ）。
      #   この規則は昔からある数字のままなので壊れない。
      # 793番（2026-09-14）：並べ替えキー本体は queue_rank_key()（モジュール直下・テスト可能）へ
      #   切り出した。ここでは prio 辞書を渡すだけの薄いラッパーに変える（動作は完全に同一）。
      prio = (load(PRIORITY, {}).get("priority") or {})

      def _effective_priority(it):
          return effective_priority(it, prio)

      def rank(it):
          return queue_rank_key(it, prio)

      # 2026-09-05 たまごさん「何も動いてない状態は作らないで。何かしら回しといて。クレジット消費最小で」
      #   本物が出せない（週枠が上限・発車を止めている等）ときでも、工場は回っている状態を保つ。
      #   空回しは Claude を起動しないのでクレジットは1円も使わない。終われば静かに消える。
      running_now = [it for it in items if it.get("status") == "running"]
      launchable = [it for it in items if it.get("status") == "waiting"
                    and (not credit_stop or it.get("test"))]
      if not running_now and not launchable:
          nxt = max([int(x.get("n") or 0) for x in items] or [0]) + 1
          items.append({
              "n": nxt, "priority": 9, "test": True, "keepalive": True, "testSeconds": 120,
              "title": "【空回し】工場を止めないための2分の空タスク",
              "why": "本物が出せない間も、止まっている状態を作らないため（クレジットは使いません）",
              "what": "Claudeを起動しない空のタスクです。2分で終わり、台帳からは静かに消えます。",
              "status": "waiting", "limitMin": 10, "model": "claude-sonnet-5",
          })
          log("♻︎ 空回しを1本入れました（%d番・本物が出せないため）" % nxt)
          save_queue(q, snapshot=_snap)
          _snap = queue_store.snapshot_items(q)

      waiting = sorted([it for it in items if it.get("status") == "waiting"], key=rank)

      # ---- 759番3回目の重複発車を機に追加した恒久ガード（案件#759・2026-09-13）----
      #   status/failures.md #15：759番は実装・本番push・Dispatch完了報告まで全部終わっていたのに
      #   queue.json側のstatusが"running"のまま取り残され、auto_launcherに2回目・3回目の
      #   重複発車をされた。harvest()やAI検品の自動PASS経路を通らずに終わったケースが原因で、
      #   queue.json側の状態だけを見ていては再発する。
      #   ここでは「dispatch_outbox.jsonlにok:trueの完了報告が既にあるn」を外から機械的に見つけ、
      #   発車直前でその場でdoneへ戻して除外する（queue.json側の巻き戻り経路を完全解明できなくても、
      #   症状そのものを塞ぐ最終防波堤）。
      #
      #   ---- 店長のセルフレビューによる修正（同日・2026-09-13）----
      #   上のガードだけだと command_ingest.py の queue_redo()（正規の「まだ直ってないよ、
      #   やり直して」機構・680番）と衝突する。queue_redo() は再オープン時に item の status を
      #   waiting へ戻すだけで、過去の outbox の ok:true 行は一切消さない設計。そのため
      #   「nが一致してok:trueがあるか」だけで判定すると、やり直し要求で再オープンされた項目まで
      #   「もう完了報告済み」と誤判定してその場でdoneへ戻してしまい、やり直し機構そのものを
      #   永久に無効化する（元の3重発火バグより悪い機能停止の回帰）。
      #   そこで「そのnについて最後に確認できた事実（outboxのok:true）が、queue_redo()が
      #   セットするcheckedAt（＝正当な理由での再オープン時刻）より古いかどうか」で判定し直す。
      #   checkedAtがoutboxのtsより新しければ「完了報告のあとに正当な再オープンが起きた」ので
      #   除外しない。checkedAtが無い・outbox以下ならこれまで通り巻き戻りバグとして除外する。
      def _cmp_key(ts):
          """ISO8601風の日時文字列から年月日時分秒だけを取り出す（先頭19文字）。
          checkedAt（%Y-%m-%dT%H:%M:%S%z 例:+0900）と
          outboxのts（%Y-%m-%dT%H:%M:%S+09:00 例:+09:00）はタイムゾーン表記の桁数が違うが、
          本システムは常にJST単一タイムゾーンで動くため、末尾のオフセット部分を切り捨てて
          年月日時分秒部分（先頭19文字）だけを文字列比較すれば安全に新旧判定できる。"""
          s = str(ts or "")
          return s[:19]

      def _outbox_reported_ns():
          """nごとの「最新のok:true行のts」を返す（n → ts の dict）。
          同じnに複数回のok:true行があり得る（やり直し後に再度完了した場合等）ため、
          setではなくdictにして一番新しいtsを保持する。"""
          reported = {}
          try:
              with io.open(OUTBOX, encoding="utf-8") as f:
                  for line in f:
                      line = line.strip()
                      if not line:
                          continue
                      try:
                          row = json.loads(line)
                      except Exception:
                          continue
                      if row.get("ok") and row.get("n") is not None:
                          n = row.get("n")
                          ts = row.get("ts") or ""
                          prev = reported.get(n)
                          if prev is None or _cmp_key(ts) >= _cmp_key(prev):
                              reported[n] = ts
          except Exception:
              pass
          return reported

      _reported_ns = _outbox_reported_ns()

      def _is_stale_completion(it):
          """このwaiting項目が「理由なく巻き戻ったdoneの残骸」かどうかを判定する。
          checkedAt（queue_redoが再オープン時にセットする＝正当なやり直し要求の時刻）が
          outboxの最新ok:true報告より新しければ、やり直し要求のほうが後に起きているので
          正当な再オープン＝発車対象として残す（False）。それ以外はTrue（除外対象）。"""
          n = it.get("n")
          outbox_ts = _reported_ns.get(n)
          if outbox_ts is None:
              return False
          checked_at = it.get("checkedAt")
          if checked_at and _cmp_key(checked_at) > _cmp_key(outbox_ts):
              return False
          return True

      _dup_waiting = [it for it in waiting if _is_stale_completion(it)]
      if _dup_waiting:
          _dup_fresh_q = load(QUEUE, {})
          _dup_fresh_snap = queue_store.snapshot_items(_dup_fresh_q)
          _dup_fresh_items = {it2.get("n"): it2 for it2 in (_dup_fresh_q.get("items") or [])
                               if it2.get("n") is not None}
          for it in _dup_waiting:
              n = it.get("n")
              target = _dup_fresh_items.get(n)
              if not target:
                  continue
              _old_note = (target.get("note") or "").rstrip()
              _add_note = ("759番の重複発火（3回目）を機に追加した恒久ガードにより、"
                           "dispatch_outbox.jsonlに完了記録があったため再発車せず自動クローズ")
              target["note"] = (_old_note + "\n" + _add_note) if _old_note else _add_note
              target["status"] = "done"
              log("♻︎ 重複発車を防止しdoneへ戻しました %s番「%s」" % (n, target.get("title")))
          save_queue(_dup_fresh_q, snapshot=_dup_fresh_snap)
          _dup_ns = set(it.get("n") for it in _dup_waiting)
          waiting = [it for it in waiting if it.get("n") not in _dup_ns]
      if not waiting:
          log("見送り: 発車待ちが空（重複発車ガードで全て除外）")
          return 0

      if credit_stop:
          # 週枠が上限のあいだは、クレジットを使わないテストだけ通す
          waiting = [it for it in waiting if it.get("test")]
      if not waiting:
          log("見送り: 発車待ちが空" if not credit_stop else
              "見送り: 週枠が上限（all=%s%%）" % quota.get("allPct"))
          return 0

      # 682番（2026-09-09）F（空き枠タスク）＝「やってほしいが今は枠を使いたくない」もの。
      #   たまごさん「本当にどうでもいい、やってはほしいけど今は容量を使いたくないってやつ」
      #   「他にタスクが空いたときに入ればいいよ」。
      #   A〜E（優先度1〜5・未設定9）が発車待ちに1本でも残っていれば、Fは絶対に対象へ入れない。
      has_non_f_waiting = any(_effective_priority(it) != 6 for it in waiting)
      if has_non_f_waiting:
          waiting = [it for it in waiting if _effective_priority(it) != 6]

      # ---- お金の確認ゲート（案件#676・2026-09-08にfalで15ドル溶けた事故のガード）----
      #   costsMoney が立っていて、たまごさんがまだOKを押していない（costApproved が無い）ものは
      #   絶対に自動発車しない。列の先頭に来た最初の1回だけ dispatch_outbox へ確認を出し、
      #   以後は costAskedAt があるので黙って足止めする（同じ問いを連呼しない）。
      #   進捗表の💴ボタン（queue_cost_ok）でOKが押されると costApproved が立ち、次の周回で発車する。
      asked_now = False
      cost_ok_waiting = []
      for it in waiting:
          if it.get("costsMoney") and not it.get("costApproved"):
              if not it.get("costAskedAt"):
                  msg = cost_risk.confirm_message(it)
                  _append_cost_confirm_outbox(it, msg)
                  it["costAskedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
                  asked_now = True
                  log("💰 発車を止めて確認を出しました %d番「%s」" % (it.get("n"), it.get("title")))
              continue
          cost_ok_waiting.append(it)
      if asked_now:
          q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
          save_queue(q, snapshot=_snap)
          _snap = queue_store.snapshot_items(q)
      waiting = cost_ok_waiting
      if not waiting:
          log("見送り: 発車待ちは全部お金の確認待ち")
          return 0

      # ---- 週の作業配分ゲート（案件#824・見たいもの60%／裏方30%／予備10%）----
      #   裏方が枠(30%)を使い切った・曜日ルールでNGな日は、裏方タスクの新規発車を止める。
      #   1本のコストが週予算の3%を超えるタスクも、上限確認が済むまで発車しない。
      haibun = shukan_haibun.build_haibun()
      blocked = shukan_haibun.urakata_blocked(haibun)
      _haibun_gated = False
      _haibun_gate_waiting = []
      for it in waiting:
          if blocked and shukan_kubun.classify_item(it) == "urakata":
              if not it.get("urakataBlockedAt"):
                  log("🚧 裏方の枠が上限のため発車を止めました %s番「%s」" % (it.get("n"), it.get("title")))
                  it["urakataBlockedAt"] = time.strftime("%Y-%m-%d %H:%M:%S+09:00")
                  _haibun_gated = True
              continue
          cost_estimate = it.get("costEstimate")
          if isinstance(cost_estimate, (int, float)) and shukan_haibun.single_task_over_limit(cost_estimate, haibun):
              if not it.get("capLimitAskedAt"):
                  _append_cap_limit_outbox(it)
                  it["capLimitAskedAt"] = time.strftime("%Y-%m-%d %H:%M:%S+09:00")
                  _haibun_gated = True
                  log("🚧 上限超えのため発車を止めました %s番「%s」" % (it.get("n"), it.get("title")))
              continue
          _haibun_gate_waiting.append(it)
      if _haibun_gated:
          q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
          save_queue(q, snapshot=_snap)
          _snap = queue_store.snapshot_items(q)
      waiting = _haibun_gate_waiting
      if not waiting:
          log("見送り: 発車待ちは全部週の配分ゲート待ち")
          return 0

      # 2026-09-04 たまごさん「今イパネマしかしてないから、そこを4本にして」
      #   1回の実行で1本だけだと、5分×3回で3本になるまで15分かかる。空いているぶんを一度に埋める。
      room = safe_max - alive
      to_launch = waiting[:room]

  # ---- ここから先は鍵を離す（案件#687・要件④：鍵を持ったまま重い処理をしない）----
  #   git worktree作成・claude -p起動は数秒〜数十秒（まれに300秒timeout）かかることがあり、
  #   鍵を持ったままこれを行うと、その間 command_ingest.queue_add() 等（別プロセス）の
  #   書き込みを長時間ブロックする。以前はブロックした挙げ句、無鍵の経路（relay_server.py等の
  #   直接呼び出し）に割り込まれて丸ごと上書きが起きた（777〜804番28件消失・案件#687）。
  #   着火1本ごとに save_queue()（差分マージ・短時間だけ鍵を取り直す）で都度保存するので、
  #   45秒killに遭ってもそこまでの着火分は失われない。
  launched = 0
  for item in to_launch:
      if launch_one(item, q, alive + launched, safe_max):
          launched += 1
          q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
          save_queue(q, snapshot=_snap)
          _snap = queue_store.snapshot_items(q)
          # 797番：genzaichi.pyが「発車0本が10分続いていないか」を見るための実測点。
          try:
              with io.open(LAST_LAUNCH_STAMP, "w", encoding="utf-8") as f:
                  f.write(time.strftime("%Y-%m-%dT%H:%M:%S+09:00"))
          except Exception:
              pass
  return 0


def launch_one(item, q, alive, safe_max):
    # 2026-09-05 二重発車の防止（実測：05:21に同じ番号が2回出てクレジットが二重に減った）。
    #   鍵の取り合いに負けた側が古い台帳で走らないよう、着火の直前にもう一度いまの状態を見る。
    fresh = load(QUEUE, {})
    for _x in (fresh.get("items") or []):
        if _x.get("n") == item.get("n") and _x.get("status") != "waiting":
            log("二重発車を止めました %s番（いまの状態=%s）" % (item.get("n"), _x.get("status")))
            return False

    # ---- テスト用のカラ発車（クレジットを1円も使わない）----
    # 2026-09-04 たまごさん「3分で終わるセッションをくるくる回してテストしたい。
    #   中身はなんでもいい。3分で終わって完了報告がDispatchに来る、最低限の動作確認」
    #   → item に "test": true があれば、Claudeを起動せず、指定秒だけ眠って
    #     本物と同じ形の結果ログ（result と URL）を書くだけのプロセスを走らせる。
    #     回収・確認待ち・判定・繰り上げは本物とまったく同じ道を通る。
    if item.get("test"):
        new_id = str(uuid.uuid4())
        logf = os.path.join(REPO, "status", "auto-launch-%s.log" % new_id[:8])
        secs = int(item.get("testSeconds") or 180)
        url = "https://tamago2022.github.io/tamago-shinchoku/share/check/test-%d.html" % item.get("n")
        result = "【完了】%s（テスト・%d秒で終わりました）\\n確認ページ: %s" % (item.get("title"), secs, url)
        payload = '{"result": "%s"}' % result
        try:
            f = io.open(logf, "a", encoding="utf-8")
            p = subprocess.Popen(
                ["bash", "-c", "sleep %d; cat <<'EOF'\n%s\nEOF" % (secs, payload)],
                stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        except Exception as e:
            log("テスト発車に失敗 %s: %s" % (item.get("n"), e))
            return False
        item["status"] = "running"
        item["startedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
        item["sessionId"] = new_id
        item["pid"] = p.pid
        log("🧪 テスト発車 %d番「%s」→ pid %d（%d秒で終わります・走行%d本→%d本・上限%d本）"
            % (item.get("n"), item.get("title"), p.pid, secs, alive, alive + 1, safe_max))
        return True

    # ---- worktree を切る ----
    # 2026-09-16：タスクごとに作業リポジトリを選べるようにした。
    #   理由：進捗表(tamago-shinchoku)だけを直すタスクにも joy-relief-station の worktree を
    #   切ろうとして、`git worktree add` が300秒×3回タイムアウトし、**15分待って発車失敗**
    #   していた（882番・883番が実際にこれで出せなかった）。joy-relief-station は
    #   .git 320MB＋登録済みworktree 77件で、切るのに時間がかかりすぎる。
    #   触るのが tamago-shinchoku だけのタスクは item["repo"] でこちらを指す。
    repo = item.get("repo") or q.get("repo") or "/Users/mac/Desktop/joy-relief-station"
    wt_name = item.get("worktree") or ("q%02d-0904" % item.get("n"))
    # 2026-09-06：作業場をリポジトリの外へ出した。
    #   たまごさんの言葉：「ChatGPT（Codex）の一覧にこっちのタスクが出てくる。
    #   一覧が汚れて、あっちのセッションが見つけられないのよ。だからあっちに積まないで」
    #   リポジトリ配下の .worktrees は他のAIツールから「プロジェクト」として拾われていた。
    #   ドット始まりの、どのツールの索引にも入らない場所へ移す。
    WT_BASE = "/Users/mac/Documents/AI作業/.worktrees"
    try:
        os.makedirs(WT_BASE, exist_ok=True)
    except Exception:
        WT_BASE = os.path.join(repo, ".worktrees")
    wt = os.path.join(WT_BASE, wt_name)
    # 2026-09-04：Cowork側のサンドボックスからマウント越しにgitを叩くと .lock が消せずに残り、
    #   以後ホスト側の worktree add が exit 128 で失敗し続ける（実際に15番以降が着火できなくなった）。
    #   5分以上前の置き去りロックだけ掃除する（実行中のgitは巻き添えにしない）。
    try:
        subprocess.run(["bash", "-c",
                        # 2026-09-04 修正：-mmin +5 だと、Cowork側が直前に作ったロックが消せず
                        #   着火が exit 128 で失敗し続けた（q15〜q33が全滅）。ここは自分しかgitを使っていない
                        #   タイミング（5分おき・二重起動はロックで防止済み）なので、無条件で掃除する。
                        "find '%s/.git' -name '*.lock' -delete 2>/dev/null; "
                        "find '%s/.git/refs' -name '*.lock' -delete 2>/dev/null; "
                        "find '%s/.git/worktrees' -name 'locked' -delete 2>/dev/null; true" % (repo, repo, repo)],
                       capture_output=True, timeout=20)
        # 797番：ここに以前あった「worktree一覧を列挙し30分経過したものを強制削除する」処理は
        # 撤去した。理由は2つ。
        #   ①重い：git worktree list --porcelain / remove --force に最大120〜180秒のtimeoutを
        #     許していたため、worktreeの登録が増えるほど（実測：joy-relief-station側で32件）
        #     着火1回のたびにここで時間を食い、heartbeat.sh側の45秒killに巻き込まれて
        #     「発車そのもの」が止まる原因になっていた（2026-09-13 05:26〜05:42に14回連続で発生）。
        #   ②危険：ここは「30分経過しただけ」で強制削除しており、未コミットの変更や
        #     origin/main未合流かどうかを見ていなかった。既存の tools/worktree_reaper.py が
        #     heartbeat.shに相乗りして15秒おきに同じ掃除を行っており、こちらは
        #     「running中でない・git statusが空・origin/mainに合流済み・2時間以上放置」の
        #     4条件を全部満たした時だけ消す、より安全な実装。重複していたので片方（安全な方）だけ残す。
        # 着火の直前に必要なのは「今から作る自分のworktree名の場所が空いているか」だけなので、
        # 軽い prune（stale参照の整理）だけ残す。
        subprocess.run(["git", "-C", repo, "worktree", "prune"], capture_output=True, timeout=20)
    except Exception:
        pass
    # 2026-09-16：300秒×3回（最大15分）待って初めて失敗が分かる作りだったため、
    #   worktree1本の発車失敗が丸ごと15分の空白になっていた（882/883/884/874番で実際に発生）。
    #   ここで長く粘っても次の周回でどのみち再挑戦するだけなので、短く見切って次へ回す方が損が小さい。
    WT_ADD_TIMEOUT = 90
    if not os.path.isdir(wt):
        try:
            subprocess.run(["git", "-C", repo, "worktree", "add", wt,
                            "-b", "claude/" + wt_name],
                           check=True, capture_output=True, timeout=WT_ADD_TIMEOUT)
        except Exception:
            # 2026-09-04：ブランチが既にある等で失敗する（exit 128）。既存ブランチに繋ぐ形で作り直す。
            try:
                subprocess.run(["git", "-C", repo, "worktree", "add", wt,
                                "claude/" + wt_name],
                               check=True, capture_output=True, timeout=WT_ADD_TIMEOUT)
            except Exception:
                # それでもダメなら名前を変えて切る。ここで止まらない（止まると工場が止まる）
                wt_name = wt_name + "-" + time.strftime("%H%M%S")
                wt = os.path.join(WT_BASE, wt_name)
                try:
                    subprocess.run(["git", "-C", repo, "worktree", "add", wt,
                                    "-b", "claude/" + wt_name],
                                   check=True, capture_output=True, timeout=WT_ADD_TIMEOUT)
                except subprocess.CalledProcessError as e3:
                    err = (e3.stderr or b"").decode("utf-8", "ignore")[:300] if isinstance(e3.stderr, bytes) else str(e3.stderr)[:300]
                    log("worktree作成に失敗（3回試した） %s: %s" % (wt_name, err.replace("\n", " ")))
                    return False
                except Exception as e3:
                    log("worktree作成に失敗（3回試した） %s: %s" % (wt_name, e3))
                    return False

    # ---- 着火 ----
    new_id = str(uuid.uuid4())
    prompt = build_prompt(item)
    # 2026-09-05 たまごさん「割り込みもあり。緊急で入るから。途中で止めても、**続きから再開できるように**」
    #   → 引っ込めた（一時停止した）ものは、新しいセッションを立てずに前のセッションを再開する。
    #     やり直しになっていないので、そこまでの作業が無駄にならない。
    resume_id = item.get("resumeFrom")
    # ---- 2026-09-08：**1時間放置したものを起こすと、10倍高くつく。**----
    # むなかたさんの解説（note n595ea66ba734）で分かったこと：
    #   サブスク枠のキャッシュは**最後に使ってから1時間で切れる。**
    #   キャッシュが効いていれば過去のやり取りの読み直しは1/10（Fable5.1は1/40）で済むが、
    #   切れた後に --resume で起こすと、**それまでの会話を全部「定価」で読み直す。**
    #   うちは止まったセッションを何時間も後に叩き起こしていた（実測：8時間放置のセッション）。
    #   → 50分より長く放置されたものは、起こさずに**新しいセッションで立て直す。**
    #     続きの情報は指示文（build_prompt）に入っているので、やり直しにはならない。
    cut_at = item.get("cutAt") or item.get("resumeFromAt")
    if resume_id and cut_at:
        try:
            gap = (time.time() - time.mktime(time.strptime(cut_at[:19], "%Y-%m-%dT%H:%M:%S"))) / 60.0
            if gap > 50:
                log("🧊 %d番は%d分放置。キャッシュが切れているので起こさず立て直す（そのほうが安い）"
                    % (item.get("n"), gap))
                resume_id = None
                item.pop("resumeFrom", None)
        except Exception:
            pass
    if resume_id:
        new_id = resume_id
        logf = os.path.join(REPO, "status", "auto-launch-%s.log" % new_id[:8])
        cmd = [CLAUDE, "-p", "--resume", resume_id, "--model", SONNET,
               "--permission-mode", "auto", "--output-format", "json",
               "【再開】たまごさんが緊急の割り込みのために一度止めた仕事です。"
               "**前回の続きから**進めてください。最初からやり直さないこと。\n\n" + prompt]
        item.pop("resumeFrom", None)
    else:
        logf = os.path.join(REPO, "status", "auto-launch-%s.log" % new_id[:8])
        cmd = [CLAUDE, "-p", "--session-id", new_id, "--model", SONNET,
               "--permission-mode", "auto", "--output-format", "json", prompt]
    try:
        with open(logf, "ab") as f:
            f.write(("\n=== %s 自動発車: %s\n" % (time.strftime("%F %T"), item.get("title"))).encode())
            p = subprocess.Popen(cmd, cwd=wt, stdout=f, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, start_new_session=True, env=claude_env())
        pid = p.pid
    except Exception as e:
        log("着火に失敗 %s: %s" % (item.get("title"), e))
        return False

    item["status"] = "running"
    item["startedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    item["sessionId"] = new_id
    item["pid"] = pid
    log("🚀 自動発車 %d番「%s」→ pid %s / session %s（走行%d本→%d本・上限%d本）"
        % (item.get("n"), item.get("title"), pid, new_id[:8], alive, alive + 1, safe_max))
    print("自動発車: %s" % item.get("title"))
    return True


def _harvest_pass():
    """2026-09-13（793番停止事故）新設：終わった仕事の回収（content_checkの実URL検品含む）を
    発車判定とは切り離した、独立の遅い工程として最後に回す。

    ここが詰まって45秒の見張りに強制終了されても、その時点で**発車はもう終わって
    queue.jsonに保存済み**なので、工場が0本のまま止まることはない。
    """
    with queue_lock():
        q = load(QUEUE, {})
        if not q.get("items"):
            return
        _snap = queue_store.snapshot_items(q)
        if harvest(q):
            q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
            _deleted_ns = q.pop("_pendingDeletedNs", None)
            save_queue(q, snapshot=_snap, deleted_ns=_deleted_ns)


def main():
    # 途中のどの見送り（return 0）・例外で抜けても、queue.jsonが動いていたら
    # queue_light.jsonを必ず作り直す（PWA側が軽量版を読むため）。本体の発車判定は絶対に止めない。
    try:
        if not only_one_launcher():
            return 0      # 先客がいる。二重発車を作らない
        rc = _main_impl()
        # 2026-09-13：発車（上）が終わったあとに、遅くなりうる回収作業（下）を回す。
        #   「発車は必ず先にやる」。ここで例外・タイムアウトが起きても発車済みの分は失われない。
        try:
            _harvest_pass()
        except RuntimeError:
            pass          # 鍵が取れなかっただけ。次回また拾う
        except Exception as e:
            log("harvestパス（発車のあと）に失敗: %s" % e)
        return rc
    finally:
        try:
            _maybe_rebuild_queue_light()
        except Exception as e:
            log("queue_light再生成（main終端）に失敗: %s" % e)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError:
        # 鍵が取れなかっただけ。次の15秒後にまた来る（工場は止めない）
        sys.exit(0)
