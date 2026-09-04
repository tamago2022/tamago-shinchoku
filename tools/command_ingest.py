#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PWAの「リモコン」ボタンから来たコマンドを実行する（2026-09-03）。

流れ:
  PWA（スマホ）でボタンをタップ → obsidian://new が Vault に
  `AI出力/_ルール/コマンド_受信/<id>.md`（JSON）を作る → iCloudでMacに届く
  → このスクリプト（30秒おきのlaunchdから呼ばれる）が未処理の受信ファイルを読んで実行
     → status/commands.json に結果を追記してpush（PWAが読んで「実行しました」を表示）

対応アクション:
  resume    : 止まっているセッションを claude -p --resume で再開
  stop      : 指定pidを終了（Claudeプロセスであることを確認してから。SIGTERM）
  handoff   : 詰まっているセッションに簡易引き継ぎメッセージ付きの新セッションを立てる
  close_app : 重いアプリを終了（除外リスト＝Brave・Chromeは絶対に実行しない。未保存書類は失敗扱い）
  queue_ok    : 進捗表「たまごさんの確認待ち」で✅OKを押した番号を status/queue.json で done にする
  queue_redo  : 同じくやり直しを押した番号を waiting に戻し、items配列の先頭へ移動する（次に発車の一番手にする）

  2026-09-04 queue_ok/queue_redo 追加：進捗表の確認ボタンは、これまで押した結果が端末内
  （localStorage）にしか残らず、Mac側の status/queue.json には一切反映されていなかった
  （index.html側コメントに「Obsidian経由でMac側へ渡す」と書かれていたが実装が無かった）。
  優先度（priority_ingest.py）・リモコン（resume/stop/handoff/close_app）と同じ
  「obsidian://new → Vault → このingest → status/queue.json」の道に乗せて実装した。

受信ファイルは消さない（記録として残す）。commands.jsonに書いたidは二重実行しない。
"""
import glob
import json
import os
import re
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
VAULT = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
INBOX_DIR = os.path.join(VAULT, "AI出力", "_ルール", "コマンド_受信")
OUT = os.path.join(REPO, "status", "commands.json")
QUEUE = os.path.join(REPO, "status", "queue.json")
CLAUDE = os.environ.get("CLAUDE_BIN") or (os.path.expanduser("~/.local/bin/claude")
        if os.path.exists(os.path.expanduser("~/.local/bin/claude")) else "claude")

# 2026-09-03 たまごさん指定：絶対に閉じない（Chromeを含めるのは『Happy Place Station | Lovable』の
# ウィンドウを巻き込まないため。プロセス単位のquitではウィンドウ単位の除外ができないので全体を除外する）
EXCLUDED_APPS = {"Brave Browser", "Google Chrome"}


def run(cmd, timeout=10):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def load_json(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def close_app(app):
    if not app:
        return "failed", "対象アプリ名が無い"
    if app in EXCLUDED_APPS:
        return "skipped", "%s は除外対象のため実行しません" % app
    check = run(["pgrep", "-f", app])
    if not check or not check.stdout.strip():
        return "skipped", "%s は起動していません" % app
    r = run(["osascript", "-e", 'tell application "%s" to quit' % app.replace('"', '\\"')], timeout=8)
    if r is None:
        return "failed", "タイムアウト（保存待ちの可能性）"
    time.sleep(2)
    check2 = run(["pgrep", "-f", app])
    if check2 and check2.stdout.strip():
        return "failed", "保存待ちで閉じられませんでした（未保存の書類がある可能性）"
    return "done", "%s を閉じました" % app


def resume(cli):
    if not cli:
        return "failed", "対象セッションIDが無い"
    log = os.path.join(REPO, "status", "cmd-resume-%s.log" % cli[:8])
    cmd = [CLAUDE, "-p", "--resume", cli, "--permission-mode", "auto", "--output-format", "json",
           "【PWAリモコン】たまごさんがスマホから再開を指示。止まっていた続きを最後までやって。"]
    try:
        with open(log, "ab") as f:
            f.write(("\n=== %s resume ===\n" % time.strftime("%Y-%m-%d %H:%M:%S")).encode())
            subprocess.Popen(cmd, cwd=os.path.expanduser("~"), stdout=f, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, start_new_session=True)
        return "done", "再開コマンドを送りました"
    except Exception as e:
        return "failed", str(e)


def stop(pid):
    try:
        pid = int(pid)
    except Exception:
        return "failed", "pidが不正"
    check = run(["ps", "-p", str(pid), "-o", "command="])
    if not check or not (check.stdout or "").strip():
        return "skipped", "既に終了しています"
    if "claude" not in check.stdout.lower():
        return "failed", "Claudeのプロセスではないため安全のため止めません"
    try:
        os.kill(pid, 15)  # SIGTERM。強制終了(-9)はしない
        return "done", "止めました"
    except Exception as e:
        return "failed", str(e)


def handoff(cli):
    if not cli:
        return "failed", "対象セッションIDが無い"
    new_id = str(uuid.uuid4())
    log = os.path.join(REPO, "status", "cmd-handoff-%s.log" % new_id[:8])
    prompt = ("【PWAリモコン・引き継ぎ】たまごさんがスマホから引き継ぎを指示。前のセッション（%s）が詰まっている。"
              "止まらない工場のホワイトボード（python3 /Users/mac/Desktop/joy-relief-station/ai-brain/live/whiteboard.py next）"
              "を見て、担当を引き取り、続きを進めて。tamago-unyou-osスキルの前提に従うこと。" % cli[:8])
    cmd = [CLAUDE, "-p", "--session-id", new_id, "--permission-mode", "auto", "--output-format", "json", prompt]
    try:
        with open(log, "ab") as f:
            f.write(("\n=== %s handoff from %s ===\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), cli[:8])).encode())
            subprocess.Popen(cmd, cwd=os.path.expanduser("~"), stdout=f, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, start_new_session=True)
        return "done", "新セッション %s を起動しました" % new_id[:8]
    except Exception as e:
        return "failed", str(e)


def _load_queue():
    return load_json(QUEUE, {"items": []})


def _save_queue(q):
    save_json(QUEUE, q)


def _find_item(items, n):
    for it in items:
        if it.get("n") == n:
            return it
    return None


def queue_ok(target):
    """進捗表「✅OK・完了にする」→ status/queue.json の該当番号を done にする。"""
    try:
        n = int(target)
    except Exception:
        return "failed", "番号が不正: %r" % target
    q = _load_queue()
    items = q.get("items") or []
    it = _find_item(items, n)
    if it is None:
        return "failed", "%d番がqueue.jsonに見つかりません" % n
    if it.get("status") == "done":
        return "skipped", "%d番はすでに完了です" % n
    it["status"] = "done"
    it["checkedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    q["items"] = items
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    return "done", "%d番を完了にしました" % n


def queue_redo(target):
    """進捗表「↩︎やり直し」→ status/queue.json の該当番号を waiting に戻し、
    items配列の先頭へ移す（＝次に発車の一番手。auto_launcher.pyが次サイクルで拾う）。
    走行の残骸（sessionId/pid/startedAt/finishedAt/result/urls）は消し、新規のwaiting項目と同じ形に戻す。"""
    try:
        n = int(target)
    except Exception:
        return "failed", "番号が不正: %r" % target
    q = _load_queue()
    items = q.get("items") or []
    idx = None
    for i, it in enumerate(items):
        if it.get("n") == n:
            idx = i
            break
    if idx is None:
        return "failed", "%d番がqueue.jsonに見つかりません" % n
    it = items.pop(idx)
    it["status"] = "waiting"
    it["checkedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for k in ("finishedAt", "result", "urls", "sessionId", "pid", "startedAt"):
        it.pop(k, None)
    items.insert(0, it)
    q["items"] = items
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    return "done", "%d番を列の先頭（次に発車）へ戻しました" % n


def process(cmd):
    action = cmd.get("action")
    target = cmd.get("target")
    if action == "close_app":
        return close_app(target)
    if action == "resume":
        return resume(target)
    if action == "stop":
        return stop(target)
    if action == "handoff":
        return handoff(target)
    if action == "queue_ok":
        return queue_ok(target)
    if action == "queue_redo":
        return queue_redo(target)
    return "failed", "不明なアクション: %s" % action


def main():
    os.makedirs(INBOX_DIR, exist_ok=True)
    out = load_json(OUT, {"results": []})
    done_ids = {r.get("id") for r in out.get("results", [])}
    files = sorted(glob.glob(os.path.join(INBOX_DIR, "*.md")))
    changed = False
    for fp in files:
        try:
            txt = open(fp, encoding="utf-8").read()
        except Exception:
            continue
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            continue
        try:
            cmd = json.loads(m.group(0))
        except Exception:
            continue
        cid = cmd.get("id")
        if not cid or cid in done_ids:
            continue
        status, message = process(cmd)
        out.setdefault("results", []).append({
            "id": cid, "action": cmd.get("action"), "target": cmd.get("target"), "label": cmd.get("label"),
            "status": status, "message": message, "doneAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        done_ids.add(cid)
        changed = True
        print("%s: %s / %s -> %s (%s)" % (cid, cmd.get("action"), cmd.get("target"), status, message))
    if changed:
        out["results"] = out["results"][-200:]  # 肥やさない
        out["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        save_json(OUT, out)


if __name__ == "__main__":
    main()
