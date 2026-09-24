#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""975番・Claudeの鍵の扱いを**1か所**に集めた係（2026-09-25）

たまごさん：「直しました、じゃなくて『もう起きません。◯◯を1か所にしたから』と言い切れること。」

ここに集める前は claude_env() が auto_launcher / command_ingest / auth_watch /
gaibu_copy_naoshi の**4か所に別々にコピーされていた。**直すたびに1か所ずつずれる。
だからこのファイルが正本で、ほかは全部ここを呼ぶだけにする。

--------------------------------------------------------------------
実測で分かった「なぜ切れるのか」（2026-09-25）
--------------------------------------------------------------------
キーチェーン "Claude Code-credentials" の中身の**形だけ**を測った：
    claudeAiOauth.accessToken   長さ0
    claudeAiOauth.refreshToken  長さ0     ← 更新用の鍵まで空
    refreshTokenExpiresAt       2026-10-04頃（まだ先）

期限切れではない。**同時起動の競合で消えた。**
`/login` のOAuthの refreshToken は1回しか使えず、使うと新しい対に入れ替わる。
この工場は `claude` を同時に十数本走らせている（実測：17プロセス）。
2本が同時に更新へ走ると、負けた側が invalid_grant を受け取り、
**その「空っぽの結果」をキーチェーンへ書き戻して勝った側の鍵を消す。**
（同じ現象の報告：anthropics/claude-code #79685 / #81937 / #93521）

→ **`/login` のOAuthを無人の工場で使うこと自体が設計ミス。**
   何回ログインし直しても、同時起動をやめない限り必ずまた消える。

--------------------------------------------------------------------
だから替えたパイプ
--------------------------------------------------------------------
`claude setup-token` が出す**1年もつ固定のトークン**を正本にする。
固定＝作り替え（rotate）が起きない＝**何本同時に走らせても取り合いにならない。**
Max契約のまま使えるので課金の形は変わらない（追加0円）。

置き場   ~/.tamago/claude_token（600）
発行日   ~/.tamago/claude_token.minted
使う合図 ~/.tamago/use_token（**実際に通ることを確かめた鍵にだけ立てる**）

入れ直しは tools/975_login_1pon.py（たまごさんは1行貼ってEnterするだけ）。
"""
import io
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")

AUTH_FLAG = os.path.join(STATUS, "auth_expired.flag")
NO_LAUNCH = os.path.join(STATUS, "no_launch.flag")

TOKEN_PATH = os.path.expanduser("~/.tamago/claude_token")
MINTED_PATH = os.path.expanduser("~/.tamago/claude_token.minted")
USE_TOKEN = os.path.expanduser("~/.tamago/use_token")

# たまごさんに出す1行（文言はここだけ。あちこちで書き分けない）
NAOSHIKATA = "ログインが切れています。status/LOGIN.md の1行を貼ってEnterしてください"


def claude_bin():
    p = os.path.expanduser("~/.local/bin/claude")
    if os.path.exists(p):
        return p
    for c in ("/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if os.path.exists(c):
            return c
    return "claude"


def claude_env(base=None):
    """`claude` に渡す環境を作る。正本は「生きていると確かめた1年トークン」。

    ~/.tamago/use_token が立っているときだけ環境変数で渡す。
    立っていなければキーチェーン（短命・競合で消える形）に任せる。
    死んだトークンを立てっぱなしにしないのは auth_keeper の仕事。
    """
    env = dict(base if base is not None else os.environ)
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    if not os.path.exists(USE_TOKEN):
        return env
    try:
        t = io.open(TOKEN_PATH, encoding="utf-8").read().strip()
        if t.startswith("sk-ant-"):
            env["CLAUDE_CODE_OAUTH_TOKEN"] = t
    except Exception:
        pass
    return env


def login_ng():
    """ログインが切れているなら理由（文字列）、生きているなら None。

    **claude を叩く前に必ずこれを通す。**
    切れているのに叩くと、1件あたり150秒を捨てたうえで「失敗」が量産される。
    切れているあいだは叩かずに「待ち」へ戻すのが正しい（やり直し回数に数えない）。
    """
    try:
        if os.path.exists(AUTH_FLAG):
            return "ログイン切れ"
        if os.path.exists(NO_LAUNCH):
            txt = io.open(NO_LAUNCH, encoding="utf-8").read()
            if "ログイン" in txt or "OAuth" in txt:
                return "ログイン切れ"
    except Exception:
        pass
    return None


def token_days_left(lifetime_days=365):
    """1年トークンの残り日数。分からなければ None。"""
    try:
        minted = float(io.open(MINTED_PATH, encoding="utf-8").read().strip())
    except Exception:
        try:
            minted = os.path.getmtime(TOKEN_PATH)
        except Exception:
            return None
    return int((minted + lifetime_days * 86400 - time.time()) // 86400)


def kirenai_katachi():
    """いま「切れない形」で動いているか（1年トークンが正本か）。"""
    return os.path.exists(USE_TOKEN) and os.path.exists(TOKEN_PATH)
