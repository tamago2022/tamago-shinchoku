#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登録したLovable MCPが繋がるか、Mac側で1回だけ `claude mcp list` を見る。
結果は status/lovable_mcp_setup.log に足す。1回走ったら二度と走らない。"""
import os, shutil, subprocess, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAG = os.path.join(REPO, "status", ".lovable_mcp_check_done")
REPORT = os.path.join(REPO, "status", "lovable_mcp_setup.log")
CAND = ["/usr/local/bin/claude", "/opt/homebrew/bin/claude",
        os.path.expanduser("~/.local/bin/claude"),
        os.path.expanduser("~/.claude/local/claude")]


def run():
    try:
        os.close(os.open(FLAG, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
    except Exception:
        return
    out = []
    cli = shutil.which("claude") or next((c for c in CAND if os.path.isfile(c)), None)
    try:
        p = subprocess.run([cli, "mcp", "list"], capture_output=True, text=True,
                           timeout=90, cwd=REPO)
        out.append("mcp list rc=%s\n%s\n%s" % (p.returncode, (p.stdout or "")[:2000],
                                               (p.stderr or "")[:800]))
    except Exception as e:
        out.append("mcp list 失敗: %r" % (e,))
    try:
        p = subprocess.run([cli, "mcp", "get", "lovable"], capture_output=True, text=True,
                           timeout=90, cwd=REPO)
        out.append("mcp get lovable rc=%s\n%s\n%s" % (p.returncode, (p.stdout or "")[:2000],
                                                      (p.stderr or "")[:800]))
    except Exception as e:
        out.append("mcp get 失敗: %r" % (e,))
    try:
        with open(REPORT, "a", encoding="utf-8") as f:
            f.write("\n%s == 繋がるか確認 ==\n" % time.strftime("%F %T") + "\n".join(out) + "\n")
    except Exception:
        pass
