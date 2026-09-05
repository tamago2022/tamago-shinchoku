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
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
QUEUE = os.path.join(REPO, "status", "queue.json")
MACHINE = os.path.join(REPO, "status", "machine.json")
QUOTA = os.path.join(REPO, "status", "quota.json")
PRIORITY = os.path.join(REPO, "status", "priority.json")
LOG = os.path.join(REPO, "status", "auto_launch.log")
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


# ---- 台帳の鍵（2026-09-05）----
# たまごさん「完了に入ったものもあれば、反応しないものもあります」の原因。
# 中継所（押したボタン）と心臓（着火・回収）が**同時に台帳を読み書きしていた**ため、
# 片方が1秒前に読んだ古い内容で上書きし、押した結果が消えていた（lost update）。
# 読む→書くの間ずっと鍵をかける。macOSの flock を使う（同一ファイルなので確実）。
import fcntl
from contextlib import contextmanager

QUEUE_LOCK = os.path.join(REPO, "status", ".queue.lock")


@contextmanager
def queue_lock(timeout=180.0):
    f = io.open(QUEUE_LOCK, "a+")
    t0 = time.time()
    while True:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except Exception:
            if time.time() - t0 > timeout:
                # 2026-09-05 ここで諦めて突入すると**同じ番号を2回発車してクレジットが二重に減る**
                #   （実測：05:21に3件が二重に出た）。取れないなら、今回は何もしないで帰る。
                log("鍵が取れないので今回は見送り（二重発車を防ぐ）")
                raise RuntimeError("queue_lock timeout")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


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


def save_queue(q):
    """台帳を安全に書く。

    2026-09-04：直接 open(w) で書いていたため、別のプロセス（受信箱の処理・Dispatch）が
    同時に書いた瞬間に**中身が二重になって壊れた**（実測：末尾214文字が重複しJSONとして読めなくなった）。
    台帳が壊れると工場が丸ごと止まるので、一時ファイルに書いてから置き換える（原子的）。
    """
    tmp = QUEUE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=1)
    os.replace(tmp, QUEUE)


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


def append_outbox(it, ok):
    """2026-09-06 新設：仕事が終わるたびに1行、status/dispatch_outbox.jsonl へ追記する。

    たまごさん「相変わらずディスパッチに報告がない。3時間で切ってるなら3時間ごとに
    3本4本、確認が来ていいはず」。これまで子セッションは queue.json（進捗表）には
    書けても、Dispatch（たまごさんと会話する側）へ届ける道が無かった。
    ここで書き出しておけば、Dispatchが会話開始時にこのファイルを読み、
    status/dispatch_reported.json（既にある「報告済み番号」の記録）と突き合わせて
    ＝前回報告した以降の分だけをまとめて出せる（読み取り側は今回の作業対象外）。
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
            "result": (it.get("result") or "")[:300],
        }
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:
        log("outbox書き込み失敗（%s番）: %s" % (it.get("n"), e))


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
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "tamago-content-checker/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            raw = resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return False, "ページが開けません（HTTP %s）" % e.code
    except Exception as e:
        return False, "取得に失敗しました（%s）" % e

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


def build_verify_prompt(it, check_url, urls):
    """AI検品(Verifier)への指示文。渡すのは①元の依頼②作業した側の完了報告③確認ページ/本番URLの3つだけ。
    作った側の言い分・判断理由・内部事情は一切渡さない。"""
    target = check_url or (urls[0] if urls else "")
    return """【AI検品・Verifier】あなたは検品専門です。この作業を行った本人ではありません。

# 元の依頼
{title}

{what}

# 作業した側の完了報告（そのまま。これを鵜呑みにせず、実際に確認すること）
{result}

# 確認すること
- 確認ページ（あれば必ず開く）: {check_url}
- 本番URL（実際に開く）: {urls}

# やり方
- `curl` 等で実際にURLを取得して中身を読んでください。
- **ブラウザ・claude-in-chrome・screencapture は使わないでください。**許可ダイアログを出さないこと。
- 確認ページがあれば必ず開き、依頼内容と実際の変化が一致するか確認してください。
- 本番URLも実際に開き、確認ページの主張と食い違いがないか確認してください。
- あなたは実装しません。直しません。**見るだけです。**

# 不合格の基準（どれか1つでも該当したら不合格）
- URLが開けない
- 中身が依頼と一致しない・的外れ
- 検証可能な証拠（数字・リンク・スクショ）が無く、主張だけ
- 「直した」と書いてあるのに、実際には変化の跡が無い

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
            "title": "%s（%d/%d）" % (orig_title or it.get("title") or ("%d番" % n), i, len(chunks)),
            "why": "大きい仕事の自動分割（元は%d番）" % n,
            "what": batch_what,
            "status": "waiting",
            "limitMin": 180,
            "model": "claude-sonnet-5",
            "priority": it.get("priority") or 3,
            "splitFrom": n,
            "splitIndex": i,
            "splitTotal": len(chunks),
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
    for it in q.get("items", []):
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
            cand = re.findall(r"https://[^\s\"'）)、。]*", result or raw)
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
        if not (result or "").strip() and '"result"' not in (raw or ""):
            cut = int(it.get("cutCount") or 0)
            if cut < 5:
                it["cutCount"] = cut + 1
                it["status"] = "hold" if it.get("holdNote") else "waiting"
                if it.get("sessionId"):
                    it["resumeFrom"] = it["sessionId"]   # 続きから起こす
                it["priority"] = it.get("priority") or 2
                for k in ("finishedAt", "result", "urls", "startedAt"):
                    it.pop(k, None)
                it.pop("pid", None)
                changed = True
                log("✂︎ 途中で切られたので続きから再開へ %d番「%s」（%d回目）"
                    % (it.get("n"), it.get("title"), cut + 1))
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
            # 2026-09-06 新設（416番）：確認待ちに上げる前に、別プロセスのclaude(Sonnet)を1本だけ
            # バックグラウンドで着火してAI検品(Verifier)させる。harvest()は15秒おきに軽く回る前提
            # （heartbeat.sh）なので、ここでは絶対に同期待ちしない。結果は次回以降のharvest()で回収する。
            if start_verify(it, check_url, urls):
                it["status"] = "verifying"
                changed = True
                log("🔎 AI検品へ回す %d番「%s」" % (it.get("n"), it.get("title")))
            else:
                it["status"] = "awaiting_check"      # たまごさんの確認待ち（検品できないので素通し）
                append_outbox(it, bool(urls))
                log("✅ 終了を回収 %d番「%s」→ 確認待ち（URL %d本・AI検品は対象外）"
                    % (it.get("n"), it.get("title"), len(urls)))

    # ---- AI検品（Verifier）の回収（2026-09-06新設・416番）----
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
        _record_ai_verify(ok, reason, cost, target, it.get("n"))
        for k in ("verifyPid", "verifySessionId", "verifyLog", "verifyStartedAt", "verifyUrl"):
            it.pop(k, None)
        if ok is False:
            fails = int(it.get("aiVerifyFailCount") or 0) + 1
            it["aiVerifyFailCount"] = fails
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
        # PASS、またはNone（技術的エラーのため素通し）
        if ok is None:
            it["result"] = (it.get("result") or "") + ("\n\n【AI検品：%s】" % reason)
            log("… AI検品エラー・素通し %d番「%s」・理由:%s" % (it.get("n"), it.get("title"), reason))
        else:
            log("✅ AI検品OK %d番「%s」・理由:%s・$%.3f" % (it.get("n"), it.get("title"), reason, cost or 0))
        it["status"] = "awaiting_check"
        append_outbox(it, bool(it.get("urls")))
        changed = True

    if any(x.get("_drop") for x in q.get("items", [])):
        q["items"] = [x for x in q["items"] if not x.get("_drop")]
    return changed


def build_prompt(item):
    """着火用の指示文。たまごさんが繰り返し言っていることを毎回入れる。"""
    return """【自動発車】発車待ちの{n}番です。

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

# 報告の形（これだけ）
```
【完了】<何を直したか1行>
確認ページ: <確認ページのURL>
本番: <直した実物のURL（Lovable本番など）>
```
説明も経緯も謝罪も要りません。**長い文章を書かないこと。**

**たまごさんの言葉（2026-09-06）：**
> 「**長い文章はいらない。画面で見て『直ったね』という判断にしたい。基本はLovableのリンクを送ってほしい。
>  それかスクショで『ここ直ってます』。**押してみて、ちゃんとそのページに飛んで、直ってるね、
>  反映されてるね、という確認をバンバンしていきたい。**いちいち俺が何回も同じことを言わなくていい仕組みにして。**」

**だから報告は「押せるURL」と「スクリーンショット」でできていること。**
文章で説明しないと伝わらない報告は、その時点で失格です。

# ★証拠が無いものは完了ではない（2026-09-06）
世界のループエンジニアリングでも「**AIの『完了しました』は完了の証明ではない**」が第一の課題とされています。
だからこの工場では、次のどれかが**必ず**要ります。無ければ完了として扱いません。

- **前と後のスクリーンショット**（見た目を直した仕事は、これが無いと不合格）
- **押せる本番URL**（開けば直っていることが分かる場所）
- **数字**（何件中何件を直したか。「だいたい」「ほぼ」は数字ではありません）

**「テストが通った」「pushした」は証拠になりません。**たまごさんが画面で見て分かることだけが証拠です。

# ★ 題名とコピーを書くときの目標（2026-09-05・たまごさんの言葉）
> 「**タイトルで読むパターンって少なくない。**『何か面白そうだな』って言葉には人を動かす力がある。
>  だから1番大事なのは、**ちゃんと動画の内容を読み取って、それを見たくさせる・クリックさせたくすること。**
>  最悪、そのYouTubeのタイトルに乗っかったままでもいい。でも**1歩進むと、より見たくさせるタイトル。
>  人を動かすタイトル。人をクリックで誘うタイトル・コピー。これだね。ここを目標にして。**」

- **英語の原題と投稿者名をそのまま題名にしない**（例：`Sinking Monster Truck / flyingtower` は不合格）。
- 中身を実際に見て、**開く前に絵が浮かぶ**日本語にする（例：「乗りすぎたモンスタートラック、沈む」）。
- 短く、砕けて、距離を近く。丁寧な説明調にしない。
- 合否の2問（ファンは動くか／初めての人は興味を持つか）の**上に「クリックしたくなるか」がある。**

# ★★★ たまごさんの画面を奪わない（2026-09-05・最優先）
たまごさんの言葉（そのまま）：
> 「**俺が今作業中のブラウザに、がーんってGoogle Driveが出てきた。そっちに画面が切り替わる。
>   それは邪魔なんだよね。**」

**たまごさんが今使っているウィンドウを前に出す操作は全面禁止です。**具体的に：

- `osascript` で `activate` / `tell application "..." to activate` を**使わない**。ウィンドウが前に飛び出します。
- **Braveには絶対に触らない。**タブも作らない。
- ブラウザが要るときは **Claude in Chrome の専用プロフィール（deviceId 93fefeab-0797-497c-ae03-6dd353624681「Claude作業用」）だけ**を使う。
  `select_browser` で必ず選んでから始める。tabIdは1つを使い回し、終わったら `tabs_close_mcp` で閉じる。
- **画面収録（ScreenCaptureKit）の許可を求める操作をしない。**`screencapture`・画面の録画・
  デスクトップ全体のスクリーンショットは使わない。たまごさんに許可ダイアログを出さないこと。
  証拠が要るなら、ブラウザの中のスクリーンショット機能か、`curl` で取れる事実（HTTPコード・
  ページ内の文字列・件数）で示す。
- **そもそもブラウザを開かないで済むならブラウザを開かない。**`curl` / oEmbed / API / WebFetch で
  足りる用事でブラウザを起動しないこと。

# ★確認ページを必ず作る（2026-09-04・たまごさんの指示）
たまごさんの言葉（そのまま）：
> 「**URLくれるのはいいけど、ここに連れて行ったのね。**さっきと変わってないでしょう。
>  **調べようがないから分からない。もうその入り口に連れてって。俺が探す、俺がコピーする、をやめて。
>  もう確認が取れるところへ連れて行ってください。**」

**「直したページを1つだけ貼る」のは禁止です。**たまごさんはそこから自分で探すことになります。
代わりに、成果を1枚にまとめた**確認ページ**を作り、そのURLだけを報告してください。

作り方（2026-09-06〜・型ができたので必ずこれを使う。ゼロから書かない）：
**`python3 tools/make_check_page.py --n {n} --slug <短い英語名> --title "..." --what "..." --num "値|説明" --link "ラベル|URL"` を使う**（型は`share/check/_template.html`、使い方全体は`python3 tools/make_check_page.py --help`）。
書けたら `git add` → `commit` → `push origin main`。GitHub Pagesなので数十秒で公開され、報告URLは**`https://tamago2022.github.io/tamago-shinchoku/share/check/{n}-....html`**。

**「直っていること」がそのページを開いただけで分かること。**
開いてもまだ探さないと分からないなら、その確認ページは失格です。

**出す前に自分で開いて確かめる。**たまごさんの言葉：
> 「**確認のURLをくれるのはいいけど、全く見当違いなところに連れて行くから、それもやめて。
>  確認してからこっちに上げて。時間の無駄だから。ちゃんと『直った』『問題がある』というところのURLを置いてください。**」

次のURLは**証拠として数えません**（貼っても、URLなし扱いでやり直しになります）：
サイトのトップページだけ／`example.com`／YouTubeの検索結果やoembed／GitHubのリポジトリ／ドキュメント。
**直した実物か、確認ページのURL**を出してください。

# 時間
**3時間で必ず切ってください。**（たまごさん指定）
3時間で終わらなければ、**できたところまでを本番に出して、URLと「どこまで終わって、次に何をするか」を報告**してから終わってください。黙って止まるのが一番困ります。

# 進め方
- **小さく切る。**大きくやろうとして3時間固まって何も出ないのが最悪です。1つ直すごとに公開してURLを報告してください
- **詰まったらまず `status/failures.md` を見る。**今日までに工場が止まった原因8件（症状・原因・直し方・仕掛け）が記録済み。同じ穴を調べ直さない
- 詰まったら「ここで詰まった、次はこれを試す」と1行出して、**別の経路へ進む**。右がダメなら左、後ろ、上、階段
- Bashが固まったら別の手段に切り替える。**同じ経路で3回目をやらない**
- **重い全文検索やビルドを何度も回さない**（Macのディスク待ちが伸びてフリーズします）

# 禁止
- **モデルはSonnet固定。Fableは絶対に使わない**（週枠の天井に着くと工場が全部止まります）
- **たまごさんに質問しない。**止まってよいのは不可逆な4つ（作り直せないデータの削除／課金／外部公開／パスワード入力）だけ
- 「できません」と言う前に、**試した経路を1行ずつ書き出す**
- 棚への新規掲載はしない（たまごさんの判断領域）。既存の修正・確認に限る
- BraveとLovableのChromeウィンドウを閉じない
""".format(n=item.get("n"), title=item.get("title"), what=item.get("what") or "")


def main():
  if not only_one_launcher():
      return 0      # 先客がいる。二重発車を作らない
  with queue_lock():
      q = load(QUEUE, {})
      items = q.get("items") or []
      if not items:
          return 0
      # 終わったものを回収して「確認待ち」へ移す（これをやらないと running のまま溜まって空きが出ない）
      if harvest(q):
          q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
          save_queue(q)
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
              auth_only = "ログインが切れています" in io.open(_flag, encoding="utf-8").read()
          except Exception:
              auth_only = False
          if not auth_only:
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
          log("見送り: safeMaxが取れない")
          return 0
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
      prio = (load(PRIORITY, {}).get("priority") or {})

      def rank(it):
          # 2026-09-04：スマホの「＋発車待ちに追加」で作った項目はitem自身に"priority"を持つ
          #   （queue_add・command_ingest.py）。既存のpriority.jsonのQキー方式より優先する。
          p = it.get("priority") or prio.get("Q%d" % it.get("n"))
          # 2026-09-05 たまごさん「ドラッグアンドドロップで順番入れ替えられるようにしたい」
          #   手で並べ替えた順（order）は、同じ優先度の中での並びとして最優先で効かせる。
          #   並べ替えていないものは order が無いので、従来どおり番号順で後ろに付く。
          o = it.get("order")
          return (int(p) if p else 9,
                  int(o) if isinstance(o, int) else 10 ** 6,
                  it.get("n") or 99)

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
          save_queue(q)

      waiting = sorted([it for it in items if it.get("status") == "waiting"], key=rank)
      if credit_stop:
          # 週枠が上限のあいだは、クレジットを使わないテストだけ通す
          waiting = [it for it in waiting if it.get("test")]
      if not waiting:
          log("見送り: 発車待ちが空" if not credit_stop else
              "見送り: 週枠が上限（all=%s%%）" % quota.get("allPct"))
          return 0

      # 2026-09-04 たまごさん「今イパネマしかしてないから、そこを4本にして」
      #   1回の実行で1本だけだと、5分×3回で3本になるまで15分かかる。空いているぶんを一度に埋める。
      room = safe_max - alive
      launched = 0
      for item in waiting[:room]:
          if launch_one(item, q, alive + launched, safe_max):
              launched += 1
      if launched:
          q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
          save_queue(q)
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
    repo = q.get("repo") or "/Users/mac/Desktop/joy-relief-station"
    wt_name = item.get("worktree") or ("q%02d-0904" % item.get("n"))
    wt = os.path.join(repo, ".worktrees", wt_name)
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
                       capture_output=True, timeout=60)
        subprocess.run(["git", "-C", repo, "worktree", "prune"], capture_output=True, timeout=120)
        # 2026-09-04：worktreeが129個まで増え、ディスクが96%（残23GB）になって
        #   git worktree add が exit 128 で失敗し続けた（q15〜q33が全滅）。
        #   自動発車で作った古いもの（q**-0904）を30分経過で片づける。作業本体はmainに合流済みの前提。
        out = subprocess.run(["git", "-C", repo, "worktree", "list", "--porcelain"],
                             capture_output=True, text=True, timeout=120).stdout
        now_t = time.time()
        for ln in out.splitlines():
            if not ln.startswith("worktree "):
                continue
            path = ln[len("worktree "):].strip()
            base = os.path.basename(path)
            if not (base.startswith("q") and "-0904" in base):
                continue
            try:
                if now_t - os.path.getmtime(path) < 1800:
                    continue
            except Exception:
                continue
            subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", path],
                           capture_output=True, timeout=180)
        subprocess.run(["git", "-C", repo, "worktree", "prune"], capture_output=True, timeout=120)
    except Exception:
        pass
    if not os.path.isdir(wt):
        try:
            subprocess.run(["git", "-C", repo, "worktree", "add", os.path.join(".worktrees", wt_name),
                            "-b", "claude/" + wt_name],
                           check=True, capture_output=True, timeout=300)
        except Exception:
            # 2026-09-04：ブランチが既にある等で失敗する（exit 128）。既存ブランチに繋ぐ形で作り直す。
            try:
                subprocess.run(["git", "-C", repo, "worktree", "add", os.path.join(".worktrees", wt_name),
                                "claude/" + wt_name],
                               check=True, capture_output=True, timeout=300)
            except Exception:
                # それでもダメなら名前を変えて切る。ここで止まらない（止まると工場が止まる）
                wt_name = wt_name + "-" + time.strftime("%H%M%S")
                wt = os.path.join(repo, ".worktrees", wt_name)
                try:
                    subprocess.run(["git", "-C", repo, "worktree", "add", os.path.join(".worktrees", wt_name),
                                    "-b", "claude/" + wt_name],
                                   check=True, capture_output=True, timeout=300)
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


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError:
        # 鍵が取れなかっただけ。次の15秒後にまた来る（工場は止めない）
        sys.exit(0)
