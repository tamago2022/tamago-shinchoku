#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
715番：憲法の遵守点検（毎日1回・自動）。

たまごさんの言葉（2026-09-10）：「たまごが言ったルールが引き継がれてないっていうのが、
だから困るんだよね。だからそれを仕組みにして」「これも失敗の一つ。これがもう起きないように、
一つずつ潰していって、確実に。鬼監督が寝てるだとか、そういうのも潰していって」

背景（今日出た2つの実例。どちらも「書いてあるのに守られていない。しかも誰も気づかない」）：
  - CLAUDE.md／AGENTS.mdに「1M context／extended contextは使わず標準コンテキストで進める」と
    明記されているのに、直近の子セッションの大半が1Mコンテキストで走っていた（714番）。
  - 「鬼監督（oni_kantoku）は完了ごとに毎回チェックする」はずが、実際には自動フックとして
    機能しておらず、直近24時間の完了に1件も記録が付いていなかった（684番）。

このスクリプトは、文章のルールのうち機械で測れるものを毎日チェックし、
status/kenpou_check.json へ結果を書く（index.htmlがこれを読んで進捗表に赤/緑で出す）。
赤が出た項目は、既存の command_ingest.queue_add() を使って直すタスクを発車待ちへ積む
（このスクリプト自身が新しい発車の仕組みを作るのではなく、既存の道に乗せるだけ）。

冪等・繰り返し実行OK：
  - 同じ赤項目を、まだ片付いていない間に何度も積まない（kenpouCheckKey で自分が積んだ
    未完了の項目を追跡し、既にあれば積み直さない）。
  - 714番・684番のように、たまごさん自身が既に同じ内容を発車待ちへ積んでいる場合は、
    重複して積まずスキップした旨だけ記録する。

実行:
  python3 tools/kenpou_check.py            # 点検して status/kenpou_check.json を書く
  python3 tools/kenpou_check.py --push     # 書いた後 git add/commit/push まで行う
  python3 tools/kenpou_check.py --no-queue # 赤が出ても発車待みへは積まない（動作確認用）
"""
import argparse
import glob
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import auto_launcher as al  # noqa: E402
import command_ingest as ci  # noqa: E402
from verify_check_pages import http_get  # noqa: E402

REPO = al.REPO
QUEUE = al.QUEUE
DELETED = os.path.join(REPO, "status", "deleted.json")
ONI_LOG = os.path.join(REPO, "status", "oni_kantoku_log.jsonl")
AUTO_LOG = os.path.join(REPO, "status", "auto_launch.log")
LAUNCH_CAP = os.path.join(REPO, "status", "launch_cap.json")
NO_LAUNCH_FLAG = os.path.join(REPO, "status", "no_launch.flag")
STATE = os.path.join(REPO, "status", "kenpou_check_state.json")
RESULT = os.path.join(REPO, "status", "kenpou_check.json")
HIST = os.path.join(REPO, "status", "kenpou_check_log.jsonl")

BIG_FILE_LIMIT = 1_000_000  # 1MB


def load(p, default):
    return al.load(p, default)


def now_jst_str():
    return time.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def to_epoch(ts):
    if not ts:
        return None
    try:
        t = time.strptime(str(ts)[:19], "%Y-%m-%dT%H:%M:%S")
        return time.mktime(t)
    except Exception:
        return None


# ───────────────────────── ①②：子セッションのモデル・コンテキスト窓 ─────────────────────────
# データ源：status/auto-launch-<sessionId8>.log の最終行（`claude -p --output-format json` の
# 実行結果サマリ）。modelUsage.<model>.contextWindow に、そのモデルが実際に使ったコンテキスト
# 窓の大きさ（200000=標準／1000000=拡張）がCLI自身によって記録されている。これは各行のusageとは
# 別で、cost_by_task.json にも今まで記録していなかった値（714番で新たに発見した数値）。

def _extract_final_json(logf):
    try:
        raw = io.open(logf, encoding="utf-8", errors="ignore").read()
    except Exception:
        return None
    for line in raw.splitlines():
        line = line.strip()
        if not line or '"total_cost_usd"' not in line:
            continue
        try:
            return json.loads(line)
        except Exception:
            continue
    return None


def check_context_and_model(sample=25):
    files = sorted(
        glob.glob(os.path.join(REPO, "status", "auto-launch-*.log")),
        key=lambda p: os.path.getmtime(p), reverse=True,
    )
    checked = 0
    bad_ctx = []
    bad_model = []
    for f in files:
        j = _extract_final_json(f)
        if not j:
            continue
        mu = j.get("modelUsage") or {}
        if not mu:
            continue
        checked += 1
        max_ctx = max([int(v.get("contextWindow") or 0) for v in mu.values()] or [0])
        if max_ctx > 200000:
            bad_ctx.append((os.path.basename(f), max_ctx))
        fable_models = [k for k in mu.keys() if "fable" in k.lower()]
        if fable_models:
            bad_model.append((os.path.basename(f), fable_models))
        if checked >= sample:
            break

    ctx_item = {
        "key": "ctx_1m",
        "label": "1Mコンテキストで走った子セッション",
        "color": "red" if bad_ctx else "green",
        "count": len(bad_ctx),
        "sample": checked,
        "detail": (
            "直近%d本の子セッション中%d本が標準200kを超えるコンテキスト窓（実測1M）で走っていた"
            "（CLAUDE.md/AGENTS.mdの『1M context/extended contextは使わない』に違反）"
            % (checked, len(bad_ctx))
        ) if bad_ctx else ("直近%d本はすべて標準200kコンテキストで走っていた" % checked),
    }
    fable_item = {
        "key": "fable_model",
        "label": "Fableモデルの混入（Sonnet固定違反）",
        "color": "red" if bad_model else "green",
        "count": len(bad_model),
        "sample": checked,
        "detail": (
            "直近%d本中%d本にFableモデルが混じっていた（モデルはSonnet固定のはず）"
            % (checked, len(bad_model))
        ) if bad_model else ("直近%d本はすべてSonnet固定で走っていた" % checked),
    }
    return ctx_item, fable_item


# ───────────────────────── ③：鬼監督が完了ごとに自動で動いているか ─────────────────────────
# 単純な「最終記録が24時間以内か」だけだと、684番の実例では見逃す（過去の一件だけ手動で
# 再チェックされていて『24時間以内』を満たしてしまうが、それは新しい完了への自動フックが
# 動いた証拠ではない）。なので、直近24時間に完了した仕事のうち、実際に鬼監督の記録
# （oni_kantoku_log.jsonl の n）が付いているものが何割あるかを数える「カバー率」を主指標にする。

def check_oni_kantoku():
    last_ts = None
    entries_by_n = {}
    try:
        with io.open(ONI_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                ts = e.get("checkedAt")
                if ts and (not last_ts or ts > last_ts):
                    last_ts = ts
                n = e.get("n")
                if n is not None:
                    entries_by_n.setdefault(n, []).append(ts)
    except FileNotFoundError:
        pass

    now = time.time()
    last_epoch = to_epoch(last_ts) if last_ts else None
    hours_since_last = (now - last_epoch) / 3600.0 if last_epoch else None

    q = load(QUEUE, {"items": []})
    recent = []
    for it in q.get("items", []):
        if it.get("status") not in ("done", "awaiting_check", "verifying"):
            continue
        e = to_epoch(it.get("finishedAt"))
        if e and now - e < 24 * 3600:
            recent.append(it.get("n"))
    covered = [n for n in recent if n in entries_by_n]
    coverage_ratio = (len(covered) / len(recent)) if recent else None

    stale = (hours_since_last is None) or (hours_since_last > 24)
    low_coverage = (coverage_ratio is not None and len(recent) >= 3 and coverage_ratio < 0.5)
    red = stale or low_coverage

    last_desc = "記録が1件も無い" if hours_since_last is None else (
        "最終記録から約%.1f時間経過（%s）" % (hours_since_last, last_ts)
    )
    if recent:
        cov_desc = "直近24時間の完了%d件中、鬼監督の記録が付いているのは%d件" % (len(recent), len(covered))
    else:
        cov_desc = "直近24時間に完了した仕事なし（カバー率は計測できず）"

    detail = last_desc + "／" + cov_desc
    if low_coverage:
        detail += "（自動フックが完了のたびに動いていない疑い＝684番と同じ症状）"
    elif stale and hours_since_last is not None:
        detail += "（24時間ルールに抵触）"

    return {
        "key": "oni_kantoku_alive",
        "label": "鬼監督が完了のたびに自動で動いているか",
        "color": "red" if red else "green",
        "count": (len(recent) - len(covered)) if recent else (1 if stale else 0),
        "detail": detail,
    }


# ───────────────────────── ④：完了報告にURLが入っているか ─────────────────────────

def check_done_missing_url(window_hours=24):
    q = load(QUEUE, {"items": []})
    now = time.time()
    missing = []
    for it in q.get("items", []):
        if it.get("status") != "done":
            continue
        e = to_epoch(it.get("finishedAt"))
        if e and now - e < window_hours * 3600:
            if not (it.get("urls") or []):
                missing.append(it.get("n"))
    return {
        "key": "done_missing_url",
        "label": "URL無しで完了(done)になった仕事",
        "color": "red" if missing else "green",
        "count": len(missing),
        "detail": (
            "直近%d時間で完了した仕事のうちURLが空のもの：%s"
            % (window_hours, "、".join("#%s" % n for n in missing))
        ) if missing else ("直近%d時間の完了はすべてURL付き" % window_hours),
    }


# ───────────────────────── ⑤：発車が止まっていないか（工場停止） ─────────────────────────

def check_factory_stall(stall_hours=3):
    cap = (load(LAUNCH_CAP, {}) or {}).get("cap") or 3
    q = load(QUEUE, {"items": []})
    items = q.get("items", [])
    running = [it for it in items if it.get("status") == "running"]
    waiting = [it for it in items if it.get("status") == "waiting"]
    eligible_waiting = [it for it in waiting if not (it.get("costsMoney") and not it.get("costApproved"))]
    paused = os.path.exists(NO_LAUNCH_FLAG)

    last_launch_ts = None
    try:
        with io.open(AUTO_LOG, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "🚀 自動発車" not in line:
                    continue
                m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                if m:
                    try:
                        t = time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                        last_launch_ts = time.mktime(t)
                    except Exception:
                        pass
    except FileNotFoundError:
        pass

    now = time.time()
    hours_since = (now - last_launch_ts) / 3600.0 if last_launch_ts else None
    has_capacity = len(running) < cap
    stalled = (not paused) and has_capacity and bool(eligible_waiting) and (
        hours_since is None or hours_since > stall_hours
    )

    if paused:
        detail = "意図的な一時停止中（status/no_launch.flag）なので工場停止としては扱わない"
    elif not has_capacity:
        detail = "走行%d本／上限%d本（枠が埋まっているだけ・正常）" % (len(running), cap)
    elif not eligible_waiting:
        detail = "発車待ちが無い（またはお金の確認待ちのみ）・正常"
    elif hours_since is None:
        detail = "発車の記録が見つからない・発車待ち%d件・空き%d枠" % (len(eligible_waiting), cap - len(running))
    else:
        detail = "最終発車から%.1f時間・発車待ち%d件・空き%d枠あり" % (hours_since, len(eligible_waiting), cap - len(running))

    return {
        "key": "factory_stalled",
        "label": "工場が止まったまま放置されていないか",
        "color": "red" if stalled else "green",
        "count": len(eligible_waiting) if stalled else 0,
        "detail": detail,
    }


# ───────────────────────── ⑥：queue.jsonの最大番号が減っていないか ─────────────────────────

def check_queue_max_regression():
    q = load(QUEUE, {"items": []})
    d = load(DELETED, {"items": []})
    cur_max = max(
        [int(it.get("n") or 0) for it in q.get("items", [])]
        + [int(it.get("n") or 0) for it in d.get("items", [])],
        default=0,
    )
    state = load(STATE, {})
    prev_max = state.get("maxNSeen")
    regressed = prev_max is not None and cur_max < prev_max
    state["maxNSeen"] = max(cur_max, prev_max or 0)
    state["lastMaxCheckedAt"] = now_jst_str()
    ci.save_json(STATE, state)

    if prev_max is None:
        detail = "初回計測：最大番号 %d を基準として記録した（次回以降これより減っていないか比べる）" % cur_max
    elif regressed:
        detail = "前回%d番 → 今回%d番（減少＝タスクが消えた疑い）" % (prev_max, cur_max)
    else:
        detail = "前回%d番 → 今回%d番（減少なし）" % (prev_max, cur_max)

    return {
        "key": "queue_max_regression",
        "label": "queue.jsonの最大番号が前回より減っていないか",
        "color": "red" if regressed else "green",
        "count": (prev_max - cur_max) if regressed else 0,
        "detail": detail,
    }


# ───────────────────────── ⑦：公開リポジトリに1MB超のファイルが無いか ─────────────────────────

def check_big_files(limit_bytes=BIG_FILE_LIMIT):
    try:
        r = subprocess.run(
            ["git", "ls-tree", "-r", "-l", "HEAD"], cwd=REPO,
            capture_output=True, text=True, timeout=180,
        )
        lines = r.stdout.splitlines()
    except Exception as e:
        return {
            "key": "big_files", "label": "公開リポジトリの1MB超ファイル",
            "color": "gray", "count": 0, "detail": "計測に失敗した: %s" % e,
        }
    big = []
    for line in lines:
        m = re.match(r"^\S+\s+\S+\s+\S+\s+(\d+|-)\t(.+)$", line)
        if not m:
            continue
        size_s, path = m.group(1), m.group(2)
        if size_s == "-":
            continue
        size = int(size_s)
        if size > limit_bytes:
            big.append((path, size))
    big.sort(key=lambda x: -x[1])
    return {
        "key": "big_files",
        "label": "公開リポジトリの1MB超ファイル",
        "color": "red" if big else "green",
        "count": len(big),
        "detail": (
            "、".join("%s(%.1fMB)" % (p, s / 1e6) for p, s in big[:5])
        ) if big else "1MB超のファイルは無い",
    }


# ───────────────────────── ⑧：渡し済みの確認ページURLが404になっていないか ─────────────────────────

def check_check_pages(sample=15, timeout=10):
    q = load(QUEUE, {"items": []})
    items = sorted(
        [it for it in q.get("items", []) if it.get("status") == "done" and it.get("urls")],
        key=lambda it: it.get("finishedAt") or "", reverse=True,
    )
    checked = 0
    bad = []
    for it in items:
        urls = it.get("urls") or []
        url = next((u for u in urls if isinstance(u, str) and u.startswith("https://tamago2022.github.io/")), None)
        if not url:
            continue
        code, _ = http_get(url, timeout=timeout)
        checked += 1
        if code != 200:
            bad.append((it.get("n"), url, code))
        if checked >= sample:
            break
    return {
        "key": "check_page_404",
        "label": "渡し済みの確認ページURLが404になっていないか",
        "color": "red" if bad else "green",
        "count": len(bad),
        "sample": checked,
        "detail": (
            "直近%d件の確認ページのうち%d件が200以外だった：%s"
            % (checked, len(bad), "、".join("#%s=%s" % (n, c) for n, _, c in bad[:5]))
        ) if bad else ("直近%d件の確認ページはすべて200だった" % checked) if checked else "確認できるURLが無かった",
    }


# ───────────────────────── ⑩：リポジトリ内のworktree（作業場）が増えすぎていないか ─────────────────────────
# 720番（2026-09-10）：ChatGPT/Codexのアプリのプロジェクト一覧に、うちが作ったgit worktreeが
# 300件近く出て「増える一方」と店主から2回目の指摘。原因はjoy-relief-station配下の
# `.worktrees`/`.claude/worktrees`等に作業場が溜まり続けること。worktree_reaper.py（30分おき、
# heartbeat.sh経由）が片づけ役だが、機能していても新規作成の速度に追いつかず増え続けることがある
# ので、件数そのものを毎日点検して赤にする。しきい値は店主の体感（300件は明確に多すぎ）を踏まえ
# 100件を境にした（reaperが健全なら通常は数十件程度に収まる想定）。

WORKTREE_TARGET = "/Users/mac/Desktop/joy-relief-station"
WORKTREE_COUNT_LIMIT = 100


def check_worktree_count(limit=WORKTREE_COUNT_LIMIT):
    try:
        r = subprocess.run(
            ["git", "-C", WORKTREE_TARGET, "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=60,
        )
        count = len([l for l in r.stdout.splitlines() if l.startswith("worktree ")])
    except Exception as e:
        return {
            "key": "worktree_count", "label": "リポジトリ内のworktree（作業場）件数",
            "color": "gray", "count": 0, "detail": "計測に失敗した: %s" % e,
        }
    over = count > limit
    return {
        "key": "worktree_count",
        "label": "リポジトリ内のworktree（作業場）件数",
        "color": "red" if over else "green",
        "count": count,
        "detail": (
            "%d件（しきい値%d件を超過。ChatGPT/Codexのプロジェクト一覧を汚す＝720番と同じ症状。"
            "worktree_reaper.pyが動いているか確認し、片づけを進めること）" % (count, limit)
        ) if over else ("%d件（しきい値%d件以内）" % (count, limit)),
    }


# ───────────────────────── ⑨：対話待ち・放置されたセッション ─────────────────────────

def check_orphan_sessions(stuck_factor=2.0, abs_stuck_hours=6):
    q = load(QUEUE, {"items": []})
    now = time.time()
    dead_pid = []
    stuck = []
    for it in q.get("items", []):
        if it.get("status") != "running":
            continue
        n = it.get("n")
        pid = it.get("pid")
        started = to_epoch(it.get("startedAt"))
        limit_min = it.get("limitMin") or 180
        # harvest()が「プロセス終了→status更新」するまでに数十秒のポーリング間隔があるため、
        # 発車直後すぐの誤検知を避ける猶予（5分）を置く。
        grace_ok = started is None or (now - started) > 300
        if pid and grace_ok:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                dead_pid.append(n)
            except Exception:
                pass
        if started:
            elapsed_min = (now - started) / 60.0
            if elapsed_min > max(limit_min * stuck_factor, abs_stuck_hours * 60):
                stuck.append((n, round(elapsed_min)))
    parts = []
    if dead_pid:
        parts.append("プロセスが既に無いのにrunning扱いのまま：%s" % "、".join("#%s" % n for n in dead_pid))
    if stuck:
        parts.append("制限時間を大幅に超えて走行中：%s" % "、".join("#%s(%d分)" % (n, m) for n, m in stuck))
    return {
        "key": "orphan_sessions",
        "label": "対話待ち・放置されたセッション",
        "color": "red" if (dead_pid or stuck) else "green",
        "count": len(dead_pid) + len(stuck),
        "detail": "／".join(parts) if parts else "放置されたセッションは無い",
    }


# ───────────────────────── まとめて実行 ─────────────────────────

# 既にたまごさん自身が同じ内容を発車待ちへ積んでいる場合、二重に積まずスキップする
# （2026-09-10時点：714番=1Mコンテキスト、684番=鬼監督の復活、が既に列にある）。
EXISTING_TASK_HINTS = {
    "ctx_1m": ["1Mコンテキスト"],
    "fable_model": ["1Mコンテキスト", "Fable"],
    "oni_kantoku_alive": ["鬼監督"],
}


def _already_open(hints, exclude_n=None):
    """タイトルだけを見る（what本文には全タスク共通の定型指示文が入っており、
    そこに『鬼監督』等の一般語が混じるため、本文まで見ると無関係なタスクへ
    誤って重複判定してしまう＝705番で実際に発生した誤検知）。"""
    q = load(QUEUE, {"items": []})
    for it in q.get("items", []):
        if it.get("status") not in ("waiting", "running"):
            continue
        if exclude_n is not None and it.get("n") == exclude_n:
            continue
        title = it.get("title") or ""
        if any(h in title for h in hints):
            return it.get("n")
    return None


def _already_tagged_open(key):
    q = load(QUEUE, {"items": []})
    for it in q.get("items", []):
        if it.get("kenpouCheckKey") == key and it.get("status") in ("waiting", "running", "awaiting_check", "verifying", "hold"):
            return it.get("n")
    return None


def auto_queue_fix(item, do_queue=True):
    if item["color"] != "red":
        return None
    key = item["key"]
    if not do_queue:
        return {"key": key, "skipped": "--no-queue指定のため積んでいない"}

    existing_n = _already_tagged_open(key)
    if existing_n:
        return {"key": key, "skipped": "既にこの点検が積んだ%d番が未解決のため積み直さない" % existing_n}

    hints = EXISTING_TASK_HINTS.get(key)
    if hints:
        owner_n = _already_open(hints)
        if owner_n:
            return {"key": key, "skipped": "既存の%d番と同じ内容のためスキップ" % owner_n}

    label = "憲法点検：%s" % item["label"]
    text = (
        "【自動検知・715番の日次憲法点検】次の項目が赤でした。\n\n"
        "・項目：%s\n・件数：%s\n・詳細：%s\n\n"
        "この項目は毎日再点検されます。直したら次回の点検（status/kenpou_check.json）で"
        "緑になっていることを確認してください。" % (item["label"], item.get("count"), item.get("detail"))
    )
    status, msg = ci.queue_add(text, priority=2, label=label, origin="factory")
    result = {"key": key, "status": status, "message": msg}
    if status == "done":
        m = re.search(r"(\d+)番として", msg)
        if m:
            n = int(m.group(1))
            with ci.queue_lock():
                q2 = ci._load_queue()
                for it in q2.get("items", []):
                    if it.get("n") == n:
                        it["kenpouCheckKey"] = key
                        break
                ci._save_queue(q2)
            result["n"] = n
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true", help="実行後、変更をgit push origin mainする")
    ap.add_argument("--no-queue", action="store_true", help="赤が出ても発車待ちへは積まない（動作確認用）")
    args = ap.parse_args()

    ctx_item, fable_item = check_context_and_model()
    items = [
        ctx_item,
        fable_item,
        check_oni_kantoku(),
        check_done_missing_url(),
        check_factory_stall(),
        check_queue_max_regression(),
        check_big_files(),
        check_check_pages(),
        check_orphan_sessions(),
        check_worktree_count(),
    ]

    queued = []
    for it in items:
        r = auto_queue_fix(it, do_queue=not args.no_queue)
        if r:
            queued.append(r)

    red_items = [it for it in items if it["color"] == "red"]
    result = {
        "checkedAt": now_jst_str(),
        "overallColor": "red" if red_items else "green",
        "redCount": len(red_items),
        "items": items,
        "queuedFixes": queued,
    }
    ci.save_json(RESULT, result)

    try:
        with io.open(HIST, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "checkedAt": result["checkedAt"],
                "overallColor": result["overallColor"],
                "redCount": result["redCount"],
                "redKeys": [it["key"] for it in red_items],
            }, ensure_ascii=False) + "\n")
    except Exception as e:
        print("履歴の追記に失敗（続行）: %s" % e)

    print("憲法点検 完了：%d項目中%d件が赤" % (len(items), len(red_items)))
    for it in items:
        mark = "🔴" if it["color"] == "red" else ("⚪" if it["color"] == "gray" else "🟢")
        print("  %s %s：%s" % (mark, it["label"], it["detail"]))
    if queued:
        print("---- 自動で積んだ/スキップした結果 ----")
        for q in queued:
            print("  %s: %s" % (q["key"], q.get("message") or q.get("skipped")))

    if args.push:
        _push()

    return 0


def _run(args, timeout=None):
    try:
        r = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or ""), (r.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "", "timeout after %ss" % timeout
    except OSError as e:
        return -1, "", str(e)


def _push(paths=("status/kenpou_check.json", "status/kenpou_check_state.json",
                  "status/kenpou_check_log.jsonl", "status/queue.json"), retries=5, wait_sec=8):
    for attempt in range(1, retries + 1):
        rc, out, err = _run(["git", "add"] + list(paths))
        if rc != 0:
            print("add失敗(試行%d): %s" % (attempt, (out + err).strip()[:300]))
            time.sleep(wait_sec)
            continue
        diff_rc, _, _ = _run(["git", "diff", "--cached", "--quiet"])
        if diff_rc != 0:
            rc, out, err = _run(["git", "commit", "-m", "kenpou-check: 憲法遵守点検 自動更新 %s" % time.strftime("%Y-%m-%d %H:%M")])
            if rc != 0:
                print("commit失敗(試行%d): %s" % (attempt, (out + err).strip()[:300]))
                time.sleep(wait_sec)
                continue
        ahead_rc, ahead_out, _ = _run(["git", "rev-list", "--count", "HEAD", "^origin/main"])
        if ahead_rc != 0 or ahead_out.strip() in ("", "0"):
            print("git: pushすべき新規コミットなし")
            return True
        rc, out, err = _run(["git", "push", "origin", "main"], timeout=60)
        if rc == 0:
            print("git push 成功")
            return True
        print("push失敗(試行%d): %s" % (attempt, (out + err).strip()[:300]))
        time.sleep(wait_sec)
    print("push断念（%d回試行）" % retries)
    return False


if __name__ == "__main__":
    sys.exit(main())
