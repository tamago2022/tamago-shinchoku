#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""975番・ログインを「1本のコマンド」で終わらせる係（2026-09-25）

たまごさんがやることは、これ1行を貼って Enter を押すだけ。
そのあとは画面の指示どおりにブラウザで「許可」を押して、出たコードを貼るだけ。
（パスワードはこちらでは一切扱わない。入力するのは必ずたまごさん本人。）

------------------------------------------------------------------
なぜこの形にしたか（2026-09-25 実測。推測ではない）
------------------------------------------------------------------
キーチェーン "Claude Code-credentials" の中身を測った：

    claudeAiOauth.accessToken           長さ0
    claudeAiOauth.refreshToken          長さ0      ← 更新用の鍵まで空
    claudeAiOauth.refreshTokenExpiresAt 1790992399718（2026-10-04頃）

箱は残っているのに鍵が2本とも空。だから CLI は自力で作り直せない。
原因は「期限切れ」ではなく**同時起動の競合**：
`/login` のOAuthの refreshToken は**1回しか使えない**（使うと新しい対に入れ替わる）。
この工場は `claude -p` を同時に何本も出す。2本が同時に更新へ走ると、
負けた側が invalid_grant を受け取り、**その「空っぽの結果」をキーチェーンへ書き戻す。**
勝った側の新しい鍵が上書きで消える。これが 09-20 04:30 に起きたこと。
（同じ現象の報告：anthropics/claude-code #79685・#81937・#93521）

→ **穴を塞ぐ（またログインし直す）では必ず再発する。パイプごと替える。**

替えたパイプ：
  `claude setup-token` が出す**1年もつトークン**を正本にする。
  これは更新（rotate）が起きない**固定の鍵**なので、何本同時に走らせても
  取り合いにならない＝**構造的に競合で消えない。**Max契約のまま使える（課金は変わらない）。

この係が1回で全部やる：
  ① setup-token を端末付きで起動して、たまごさんの承認を受ける
  ② 出てきた鍵を ~/.tamago/claude_token（600）へ保存し、発行日を控える
  ③ 実際に1回叩いて、本当に通ることを確かめる
  ④ 通ったときだけ ~/.tamago/use_token を立てる（死んだ鍵を立てっぱなしにしない）
  ⑤ auth_expired.flag / no_launch.flag を外す → 工場が自動で発車を再開する

鍵の中身は画面にも log にも出さない（長さと生死だけ扱う）。
"""
import io
import os
import pty
import re
import select
import subprocess
import sys
import time

# ---- 2026-09-26：承認画面をこれ以上出さないための止め札 ----
# たまごさんの画面にログイン/承認画面が出続けた実害があったため、
# status/ninshou_stop.flag があるあいだは認証を取りに行かない。
# 解除はこのファイルを消すだけ。
import os as _os_stop, sys as _sys_stop
_STOPF = _os_stop.path.join(_os_stop.path.dirname(_os_stop.path.dirname(
    _os_stop.path.abspath(__file__))), "status", "ninshou_stop.flag")
if _os_stop.path.exists(_STOPF):
    _sys_stop.stderr.write(
        "認証の取り直しは止まっています（status/ninshou_stop.flag）。"
        "解除するにはこのファイルを消してください。\n")
    _sys_stop.exit(0)


HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
AUTH_FLAG = os.path.join(STATUS, "auth_expired.flag")
NO_LAUNCH = os.path.join(STATUS, "no_launch.flag")
LOG = os.path.join(STATUS, "auth_keeper.log")

TAMAGO = os.path.expanduser("~/.tamago")
TOKEN_PATH = os.path.join(TAMAGO, "claude_token")
MINTED_PATH = os.path.join(TAMAGO, "claude_token.minted")
USE_TOKEN = os.path.join(TAMAGO, "use_token")

CLAUDE = os.path.expanduser("~/.local/bin/claude")
if not os.path.exists(CLAUDE):
    for c in ("/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if os.path.exists(c):
            CLAUDE = c
            break

TOKEN_RE = re.compile(r"sk-ant-oat01-[A-Za-z0-9_\-]{20,}")
LIMIT = 900  # 15分で諦める


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s [1pon] %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass


def say(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def strip_ansi(s):
    s = re.sub(r"\x1b\][0-9;]*;;?", "", s)
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", s)


def run_setup_token():
    """端末を与えて `claude setup-token` を回し、出てきた鍵を拾う。

    画面はそのまま素通しする（たまごさんがブラウザで承認してコードを貼れるように）。
    戻り値：鍵の文字列（拾えなければ ""）
    """
    buf = ""
    pid, fd = pty.fork()
    if pid == 0:
        env = dict(os.environ)
        # 古い鍵が残っていると setup-token がそれを見に行くので、必ず外して始める
        env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        os.execve(CLAUDE, [CLAUDE, "setup-token"], env)
    start = time.time()
    try:
        while True:
            if time.time() - start > LIMIT:
                say("\n[15分たったので終わります。もう一度貼り直してください]")
                break
            r, _, _ = select.select([fd, sys.stdin], [], [], 0.2)
            if fd in r:
                try:
                    chunk = os.read(fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                text = chunk.decode("utf-8", "replace")
                sys.stdout.write(text)
                sys.stdout.flush()
                buf += strip_ansi(text)
                if len(buf) > 200000:
                    buf = buf[-100000:]
            if sys.stdin in r:
                line = os.read(sys.stdin.fileno(), 4096)
                if line:
                    os.write(fd, line)
    finally:
        try:
            os.close(fd)
        except Exception:
            pass
        try:
            os.waitpid(pid, 0)
        except Exception:
            pass
    m = TOKEN_RE.findall(buf.replace("\n", "").replace(" ", ""))
    return m[-1] if m else ""


def probe(token):
    """本当に通るかを1回だけ確かめる。鍵の中身は返さない。"""
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    try:
        r = subprocess.run([CLAUDE, "-p", "--model", "claude-sonnet-5",
                            "--output-format", "json", "1+1は？数字だけ"],
                           capture_output=True, text=True, timeout=180, env=env)
    except Exception as e:
        return False, "叩けなかった(%s)" % type(e).__name__
    out = (r.stdout or "") + (r.stderr or "")
    if "OAuth" in out and "invalid" in out:
        return False, "鍵が無効"
    if "Failed to authenticate" in out:
        return False, "認証に失敗"
    if '"result"' in out:
        return True, "ok"
    return False, "応答が読めない"


def clear_flags():
    for p in (AUTH_FLAG, NO_LAUNCH):
        try:
            if not os.path.exists(p):
                continue
            if p == NO_LAUNCH:
                txt = io.open(p, encoding="utf-8").read()
                if "ログイン" not in txt and "OAuth" not in txt:
                    continue  # 週次上限など別の理由で止まっているときは触らない
            os.remove(p)
        except Exception:
            pass


def main():
    say("")
    say("──────────────────────────────────────────")
    say(" Claudeのログインを『1年もつ形』にし直します")
    say(" これから画面にURLが出ます。ブラウザで『許可』を押して、")
    say(" 出てきたコードをこの画面に貼って Enter を押してください。")
    say(" （パスワードはこちらでは扱いません。入力するのはたまごさんだけです）")
    say("──────────────────────────────────────────")
    say("")

    if not os.path.exists(CLAUDE):
        say("✗ claude が見つかりません（%s）。" % CLAUDE)
        return 2

    token = run_setup_token()
    if not token:
        say("")
        say("✗ 鍵を受け取れませんでした。もう一度同じコマンドを貼ってください。")
        log("失敗：鍵を拾えなかった")
        return 1

    say("")
    say("・鍵を受け取りました（長さ%d）。本当に通るか1回だけ確かめます…" % len(token))
    ok, why = probe(token)
    if not ok:
        say("✗ 受け取った鍵で通りませんでした（%s）。もう一度貼ってください。" % why)
        log("失敗：新しい鍵で通らない（%s）" % why)
        return 1

    os.makedirs(TAMAGO, exist_ok=True)
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token + "\n")
    io.open(MINTED_PATH, "w", encoding="utf-8").write("%d\n" % int(time.time()))
    io.open(USE_TOKEN, "w", encoding="utf-8").write(
        "975番・1本コマンドが『実際に通ること』を確かめて立てた合図 %s\n" % time.strftime("%F %T"))
    clear_flags()

    log("成功：1年もつ鍵に入れ替えました（長さ%d）" % len(token))
    say("")
    say("✅ 終わりました。")
    say("   ・この鍵は1年もちます（次は 2027年%s頃）" % time.strftime("%-m月", time.localtime(time.time() + 365 * 86400)))
    say("   ・同時に何本走らせても取り合いになりません＝もう勝手に切れません")
    say("   ・工場は数十秒以内に自分で発車を再開します。何もしなくて大丈夫です。")
    say("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
