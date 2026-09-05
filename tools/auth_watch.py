#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ログインが戻ったら、自分で気づいて工場を再開する（2026-09-05）。

たまごさんの言葉：「**俺を動かすのは本当に最終手段。**」「止まるのはNG。半永久装置。」

ログイン切れ（OAuth session expired）を検知すると auto_launcher が
`status/auth_expired.flag` と `status/no_launch.flag` を置いて本物の発車を止める。
ここは10分おきに**いちばん軽い実行を1回だけ**投げて、通るようになっていたら
自分で両方の旗を外して発車を再開する。たまごさんに「直った？」と聞かない。
"""
import io
import json
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
AUTH_FLAG = os.path.join(REPO, "status", "auth_expired.flag")
NO_LAUNCH = os.path.join(REPO, "status", "no_launch.flag")
STAMP = os.path.join(REPO, "status", ".auth_probe_at")
LOG = os.path.join(REPO, "status", "auto_launch.log")
CLAUDE = os.path.expanduser("~/.local/bin/claude")
if not os.path.exists(CLAUDE):
    for c in ("/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if os.path.exists(c):
            CLAUDE = c
            break
INTERVAL = 600  # 10分に1回だけ試す（無駄打ちしない）



# ---- 認証トークン（2026-09-05）----
# `claude setup-token` はキーチェーンに保存せず画面に出すだけなので、
# こちらで ~/.tamago/claude_token（600・git管理外）に置き、起動時に環境変数で渡す。
def claude_env():
    """環境変数のトークンは原則使わない（2026-09-05に実測して分かったこと）。

    `CLAUDE_CODE_OAUTH_TOKEN` は**キーチェーンの正しい鍵より優先される。**
    古い壊れた鍵が1つ残っているだけで、ログインが成功していても工場全体が
    「OAuth session expired」のままになる。キーチェーンを正本にする。
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


def cleanup_stale_login():
    """10分以上経ったログイン手続きの残骸を落とす（放置しても固まらないが、居座らせない）。"""
    pidf = os.path.join(REPO, "status", "auth_login.pid")
    try:
        if os.path.exists(pidf) and time.time() - os.path.getmtime(pidf) > 600:
            subprocess.run(["pkill", "-f", "setup-token"], capture_output=True, timeout=5)
            os.remove(pidf)
            log("🔑 ログイン手続きの残骸を片づけました（10分経過）")
    except Exception:
        pass


def main():
    cleanup_stale_login()
    if not os.path.exists(AUTH_FLAG):
        return 0
    try:
        if time.time() - os.path.getmtime(STAMP) < INTERVAL:
            return 0
    except Exception:
        pass
    io.open(STAMP, "w").write(str(int(time.time())))
    try:
        r = subprocess.run([CLAUDE, "-p", "--model", "claude-sonnet-5",
                            "--output-format", "json", "1+1は？"],
                           capture_output=True, text=True, timeout=90, env=claude_env())
    except Exception:
        return 0
    out = (r.stdout or "") + (r.stderr or "")
    if "Failed to authenticate" in out or "OAuth session expired" in out:
        return 0
    if '"result"' not in out:
        return 0
    # 通った。旗を外して本物の発車を再開する
    for p in (AUTH_FLAG, NO_LAUNCH):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
    log("🔑 ログインが戻ったので、発車を自動で再開しました")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
