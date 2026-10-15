#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1156番・ログインを「ブラウザで1回押すだけ」にする係（2026-09-26）

たまごさんがやることは **開いた画面の「承認」を1回押すだけ。**
コマンドを貼らない。コードを写さない。ターミナルを開かない。

------------------------------------------------------------------
なぜこの形か（2026-09-26 実測。推測ではない）
------------------------------------------------------------------
・keychain "Claude Code-credentials" の claudeAiOauth は
    accessToken 長さ0 / refreshToken 長さ0 / expiresAt 0
  ＝箱だけ残って鍵が2本とも空。CLIは自力で作り直せない。
  最後に生きていたのは 2026-09-20 04:30（auth_keeper.json の ngSince）。
・保険の ~/.tamago/claude_token（9/5発行・sk-ant-oat01…）も実測で
  `401 OAuth access token is invalid`。死んでいる。
・Claude.app 同梱の claude（Coworkが動いている実体）も同じ keychain を見るので
  `OAuth session expired and could not be refreshed`。
  → **Mac の中に、CLIが使える生きた鍵は1本も残っていない。**
    つまり「たまごさんの手なしで復旧する」道は、実測の結果ゼロ本だった。

だから残る1手を最小にする：
  `claude setup-token` を**この係が端末を与えて裏で走らせ**、
  出てきた承認URLを status/1156/state.json に置く。
  たまごさんは開いた画面で「承認」を押すだけ。
  戻ってきたコードは、この係が自分でCLIへ流し込む。

取れたトークンは1年もつ**固定の鍵**（rotateしない）なので、
何本同時に走らせても取り合いにならない＝競合で消える事故が構造的に起きない。

鍵の値は画面にもログにも state.json にも一切書かない（長さと生死だけ）。

使い方:
    python3 tools/1156_login_ichioshi.py start    # 裏で起動しURLを出す
    python3 tools/1156_login_ichioshi.py state    # 今の状態をJSONで
    python3 tools/1156_login_ichioshi.py code XXX # ブラウザで出たコードを流し込む
    python3 tools/1156_login_ichioshi.py stop
"""
import io
import json
import os
import pty
import re
import select
import signal
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
DIR = os.path.join(STATUS, "1156")
STATE = os.path.join(DIR, "state.json")
CODE_IN = os.path.join(DIR, "code.txt")
RAW = os.path.join(DIR, "screen.txt")      # 端末に出た文字（鍵は伏せる）
PIDF = os.path.join(DIR, "runner.pid")
LOG = os.path.join(STATUS, "auth_keeper.log")

AUTH_FLAG = os.path.join(STATUS, "auth_expired.flag")
NO_LAUNCH = os.path.join(STATUS, "no_launch.flag")

TAMAGO = os.path.expanduser("~/.tamago")
TOKEN_PATH = os.path.join(TAMAGO, "claude_token")
MINTED_PATH = os.path.join(TAMAGO, "claude_token.minted")
USE_TOKEN = os.path.join(TAMAGO, "use_token")

TOKEN_RE = re.compile(r"sk-ant-oat01-[A-Za-z0-9_\-]{20,}")
URL_RE = re.compile(r"https://[^\s\"'<>]*(?:oauth/authorize|authorize\?)[^\s\"'<>]*")
LIMIT = 1800  # 30分で諦める


def claude_bin():
    p = os.path.expanduser("~/.local/bin/claude")
    if os.path.exists(p):
        return p
    for c in ("/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if os.path.exists(c):
            return c
    return "claude"


def log(msg):
    try:
        os.makedirs(STATUS, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s [1156] %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass


def mask(s):
    return TOKEN_RE.sub("sk-ant-oat01-«伏せた»", s)


def strip_ansi(s):
    s = re.sub(r"\x1b\][0-9;]*;;?", "", s)
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", s)


def put(**kw):
    os.makedirs(DIR, exist_ok=True)
    st = get()
    st.update(kw)
    st["at"] = time.strftime("%F %T")
    tmp = STATE + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(st, ensure_ascii=False, indent=1))
    os.replace(tmp, STATE)


def get():
    try:
        return json.load(io.open(STATE, encoding="utf-8"))
    except Exception:
        return {}


def probe(token):
    """本当に通るか1回だけ確かめる。鍵の中身は返さない。"""
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    try:
        r = subprocess.run([claude_bin(), "-p", "--model", "claude-sonnet-5",
                            "--output-format", "json", "1+1は？数字だけ"],
                           capture_output=True, text=True, timeout=180, env=env)
    except Exception as e:
        return False, "叩けなかった(%s)" % type(e).__name__
    out = (r.stdout or "") + (r.stderr or "")
    if "invalid" in out and "token" in out.lower():
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


def save_token(token):
    os.makedirs(TAMAGO, exist_ok=True)
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token + "\n")
    io.open(MINTED_PATH, "w", encoding="utf-8").write("%d\n" % int(time.time()))
    io.open(USE_TOKEN, "w", encoding="utf-8").write(
        "1156番が『実際に通ること』を確かめて立てた合図 %s\n" % time.strftime("%F %T"))


def run():
    """裏で setup-token を回す本体。"""
    os.makedirs(DIR, exist_ok=True)
    io.open(PIDF, "w").write("%d\n" % os.getpid())
    put(phase="starting", url="", note="setup-token を起動中", ok=None)
    for p in (CODE_IN, RAW):
        try:
            os.remove(p)
        except Exception:
            pass

    buf = ""
    pid, fd = pty.fork()
    if pid == 0:
        env = dict(os.environ)
        for k in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            env.pop(k, None)
        env["TERM"] = "xterm-256color"
        cb = claude_bin()
        os.execve(cb, [cb, "setup-token"], env)

    start = time.time()
    url_seen = ""
    token = ""
    try:
        while True:
            if time.time() - start > LIMIT:
                put(phase="timeout", note="30分たっても承認がありませんでした")
                log("失敗：30分たっても承認なし")
                break
            r, _, _ = select.select([fd], [], [], 0.5)
            if fd in r:
                try:
                    chunk = os.read(fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                buf += strip_ansi(chunk.decode("utf-8", "replace"))
                if len(buf) > 300000:
                    buf = buf[-150000:]
                try:
                    io.open(RAW, "w", encoding="utf-8").write(mask(buf[-8000:]))
                except Exception:
                    pass
                if not url_seen:
                    m = URL_RE.search(buf.replace("\n", ""))
                    if m:
                        # 端末の装飾(OSC 8 ハイパーリンク)で同じURLが2回くっついて出る。
                        # \x07 で切り、さらに「http が2回」出ていたら前半だけ採る。
                        u = m.group(0).split("\x07")[0]
                        i = u.find("https://", 8)
                        url_seen = u[:i] if i > 0 else u
                        put(phase="waiting_press", url=url_seen,
                            note="ブラウザで『承認(Authorize)』を1回押してください")
                        log("承認URLを出しました（押し待ち）")
                m = TOKEN_RE.findall(buf.replace("\n", "").replace(" ", ""))
                if m:
                    token = m[-1]
                    break
            # ブラウザで出たコードを外から流し込めるようにする
            if os.path.exists(CODE_IN):
                try:
                    code = io.open(CODE_IN, encoding="utf-8").read().strip()
                    os.remove(CODE_IN)
                    if code:
                        os.write(fd, (code + "\n").encode())
                        put(phase="code_sent", note="コードを流し込みました")
                        log("コードを流し込みました")
                except Exception:
                    pass
    finally:
        try:
            os.close(fd)
        except Exception:
            pass
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            os.waitpid(pid, 0)
        except Exception:
            pass

    if not token:
        put(phase="failed", ok=False, note="鍵を受け取れませんでした")
        log("失敗：鍵を拾えなかった")
        return 1

    put(phase="checking", note="受け取った鍵が本当に通るか確かめています")
    ok, why = probe(token)
    if not ok:
        put(phase="failed", ok=False, note="受け取った鍵で通りませんでした（%s）" % why)
        log("失敗：新しい鍵で通らない（%s）" % why)
        return 1

    save_token(token)
    clear_flags()
    put(phase="done", ok=True, url="", note="1年もつ固定の鍵に入れ替えました",
        token_len=len(token), minted=time.strftime("%F %T"))
    log("成功：1年もつ固定の鍵に入れ替えました（長さ%d）" % len(token))
    return 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "state"
    if cmd == "start":
        os.makedirs(DIR, exist_ok=True)
        # 二重起動しない
        st = get()
        try:
            old = int(io.open(PIDF).read().strip())
            os.kill(old, 0)
            if st.get("phase") in ("starting", "waiting_press", "code_sent", "checking"):
                print(json.dumps({"already": True, **st}, ensure_ascii=False))
                return 0
        except Exception:
            pass
        me = os.path.abspath(__file__)
        subprocess.Popen([sys.executable, me, "_run"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, start_new_session=True)
        for _ in range(120):
            time.sleep(0.5)
            st = get()
            if st.get("phase") in ("waiting_press", "failed", "done", "timeout"):
                break
        print(json.dumps(get(), ensure_ascii=False, indent=1))
        return 0
    if cmd == "_run":
        return run()
    if cmd == "state":
        print(json.dumps(get(), ensure_ascii=False, indent=1))
        return 0
    if cmd == "code":
        os.makedirs(DIR, exist_ok=True)
        io.open(CODE_IN, "w", encoding="utf-8").write(sys.argv[2].strip())
        print("ok")
        return 0
    if cmd == "stop":
        try:
            os.kill(int(io.open(PIDF).read().strip()), signal.SIGTERM)
        except Exception:
            pass
        put(phase="stopped", url="")
        print("ok")
        return 0
    print("start / state / code <コード> / stop")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
