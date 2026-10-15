#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
615番: Obsidianノートの「▶ 読み上げ」リンクから来た音声化を裏で完走させる係。

command_ingest.py の action=dokudoku は、音声化(数分かかる)を待たずに
「始めました」を即座に返す（30秒おきの受信箱ループを止めないため）。
実際の処理はこのスクリプトを subprocess.Popen で切り離して行い、
終わったら status/commands.json に結果を1件追記する（PWA側の表示用）。

使い方: python3 dokudoku_worker.py <cmd_id> <ノートの絶対パス>
"""
import sys
import os
import io
import re
import json
import time
import fcntl
import subprocess
from contextlib import contextmanager

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOKUDOKU = "/Users/mac/Documents/AI作業/tools_local/dokudoku/dokudoku.py"
OUT = os.path.join(REPO, "status", "commands.json")
LOCK = os.path.join(REPO, "status", ".commands.lock")


@contextmanager
def commands_lock():
    f = open(LOCK, "a+")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()


def load_json(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def append_result(cmd_id, action_status, message):
    with commands_lock():
        data = load_json(OUT, {"results": []})
        data.setdefault("results", []).append({
            "id": cmd_id, "action": "dokudoku", "status": action_status,
            "message": message, "doneAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        data["results"] = data["results"][-200:]
        data["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        tmp = OUT + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, OUT)


def main():
    if len(sys.argv) < 3:
        print("使い方: dokudoku_worker.py <cmd_id> <ノートの絶対パス>")
        sys.exit(1)
    cmd_id, note_path = sys.argv[1], sys.argv[2]
    log_path = os.path.join(REPO, "status", "dokudoku-%s.log" % cmd_id[:8])
    try:
        r = subprocess.run([sys.executable, DOKUDOKU, note_path, "--publish"],
                            capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        append_result(cmd_id, "failed", "音声化がタイムアウトしました（30分超）")
        return
    except Exception as e:
        append_result(cmd_id, "failed", "起動できませんでした: %s" % e)
        return
    out = (r.stdout or "") + (r.stderr or "")
    io.open(log_path, "w", encoding="utf-8").write(out)
    if r.returncode != 0:
        append_result(cmd_id, "failed", "音声化に失敗しました（ログ: status/%s）" % os.path.basename(log_path))
        return
    m = re.search(r"音声URL: (\S+)", out)
    url = m.group(1) if m else ""
    append_result(cmd_id, "done", "音声化して公開しました: %s" % url)


if __name__ == "__main__":
    main()
