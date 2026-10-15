#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""鍵を渡し忘れられない口を作る係（2026-09-27・1161番の続き）

■ 何が起きていたか（実測）
  1年もつ鍵は ~/.tamago/claude_token にあり、合図（use_token）も立っていた。
  それでも 2026-09-27、子セッションの起動が
    `Failed to authenticate: OAuth session expired and could not be refreshed`
  で落ちた。この文言は**キーチェーン側の短命OAuth**が出すもので、
  ＝**その呼び出しには鍵が渡っていなかった。**
  鍵を渡す正本は tools/claude_auth.py の claude_env() だが、
  それを通さずに `~/.local/bin/claude` を直に叩く口が残っていれば、
  その口だけが今日と同じ形で落ちる。**呼ぶ側を全部直す作戦は、必ず1本忘れる。**

■ だから口を1つにする（穴に段ボールを貼らない）
  `~/.local/bin/claude` 自体を、鍵を入れてから本体へ渡す小さな包みに替える。
  以後、**どの口から叩いても**鍵が入る（渡し忘れが物理的に起きない）。
    ・`setup-token` / `login` / `logout` のときは入れない（作り直しの邪魔をしない）
    ・呼ぶ側が既に鍵を渡しているときは触らない
    ・合図（use_token）が立っていないときは何もしない＝今までどおりキーチェーン
  本体の在り処は ~/.tamago/claude_real に控える。claudeの自動更新で包みが
  消えても、5分便がこの係を毎回呼ぶので次の便で戻る（自己修復）。

■ 安全側
  ・包みを置いたあと必ず `claude --version` を実測する。通らなければ**元に戻す。**
  ・鍵の中身は読まない（形だけ見る）。ログにも出さない。
  ・元がシンボリックリンク（claude公式の形）でないときは何もしない。
"""
import io
import os
import stat
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LOG = os.path.join(REPO, "status", "auth_keeper.log")
BIN = os.path.expanduser("~/.local/bin/claude")
REALF = os.path.expanduser("~/.tamago/claude_real")
VERSIONS = os.path.expanduser("~/.local/share/claude/versions")
MARK = "# tamago-claude-kuchi v1"

WRAPPER = """#!/bin/sh
%s  ★自動生成（tools/claude_kuchi_install.py）。手で書き換えない。
# 鍵を渡し忘れられない口。どの呼び出しでも1年もつ鍵を入れてから本体へ渡す。
R=""
[ -n "${CLAUDE_REAL_BIN:-}" ] && R="$CLAUDE_REAL_BIN"
if [ -z "$R" ] && [ -f "$HOME/.tamago/claude_real" ]; then
  R="$(cat "$HOME/.tamago/claude_real" 2>/dev/null)"
fi
if [ -z "$R" ] || [ ! -x "$R" ]; then
  R="$(ls -t "$HOME/.local/share/claude/versions/"* 2>/dev/null | head -1)"
fi
[ -x "$R" ] || { echo "claude本体が見つかりません" >&2; exit 127; }
# 鍵を作り直すときは鍵を入れない（入れると作り直しが始まらない）
case "${1:-}" in
  setup-token|login|logout) exec "$R" "$@" ;;
esac
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && [ -e "$HOME/.tamago/use_token" ]; then
  T="$(tr -d '\\n' < "$HOME/.tamago/claude_token" 2>/dev/null || true)"
  case "$T" in
    sk-ant-*)
      if [ "${#T}" -ge 90 ]; then CLAUDE_CODE_OAUTH_TOKEN="$T"; export CLAUDE_CODE_OAUTH_TOKEN; fi
      ;;
  esac
fi
exec "$R" "$@"
""" % MARK


def log(m):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s [口] %s\n" % (time.strftime("%F %T"), m))
    except Exception:
        pass


def newest_version():
    try:
        cands = [os.path.join(VERSIONS, n) for n in os.listdir(VERSIONS)]
        cands = [p for p in cands if os.path.isfile(p) and os.access(p, os.X_OK)]
        cands.sort(key=os.path.getmtime, reverse=True)
        return cands[0] if cands else ""
    except Exception:
        return ""


def is_kuchi(path):
    try:
        if os.path.islink(path):
            return False
        return MARK in io.open(path, encoding="utf-8", errors="ignore").read(400)
    except Exception:
        return False


def real_from(path):
    """いまの ~/.local/bin/claude から本体の在り処を割り出す。"""
    if os.path.islink(path):
        t = os.path.realpath(path)
        return t if os.path.exists(t) else ""
    if is_kuchi(path):
        try:
            t = io.open(REALF, encoding="utf-8").read().strip()
            if t and os.access(t, os.X_OK):
                return t
        except Exception:
            pass
        return newest_version()
    return ""


def verify():
    try:
        p = subprocess.run([BIN, "--version"], capture_output=True, text=True, timeout=60)
        return p.returncode == 0 and "Claude" in ((p.stdout or "") + (p.stderr or ""))
    except Exception:
        return False


def main():
    if not os.path.exists(BIN):
        log("claude が %s に無い。何もしない" % BIN)
        return 0
    was_link = os.path.islink(BIN)
    old_target = os.path.realpath(BIN) if was_link else ""
    real = real_from(BIN)
    if not real:
        log("本体の在り処が読めない（包みも張らない）: %s" % BIN)
        return 1

    # 本体の控えは毎回書き直す（更新で版が変わってもここが正本）
    try:
        os.makedirs(os.path.dirname(REALF), exist_ok=True)
        io.open(REALF, "w", encoding="utf-8").write(real + "\n")
    except Exception:
        pass

    if is_kuchi(BIN):
        cur = io.open(BIN, encoding="utf-8", errors="ignore").read()
        if cur == WRAPPER:
            if "--quiet" not in sys.argv:
                print("すでに口は張られています（本体 %s）" % real)
            return 0

    tmp = BIN + ".kuchi.tmp"
    try:
        io.open(tmp, "w", encoding="utf-8").write(WRAPPER)
        os.chmod(tmp, 0o755)
        os.replace(tmp, BIN)
    except Exception as e:
        log("包みを張れなかった（%s）" % type(e).__name__)
        try:
            os.remove(tmp)
        except Exception:
            pass
        return 1

    if verify():
        log("鍵を渡し忘れられない口を張りました（本体 %s）" % os.path.basename(real))
        print("張りました（本体 %s）" % real)
        return 0

    # ★通らなければ必ず元へ戻す（工場を止めない）
    try:
        os.remove(BIN)
        if was_link and old_target:
            os.symlink(old_target, BIN)
        else:
            os.symlink(real, BIN)
        log("包みが通らなかったので元へ戻しました")
    except Exception as e:
        log("戻せませんでした（%s）★手当てが必要" % type(e).__name__)
    print("通らなかったので元へ戻しました")
    return 2


if __name__ == "__main__":
    sys.exit(main())
