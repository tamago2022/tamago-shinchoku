#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ログイン手続きを「にせの端末」で抱えたまま待つ係（2026-09-05）。

たまごさんはターミナルを使わない。だからログインの手順をこちらで持つ。

分かったこと（実測）：
  - `claude setup-token` は**端末(TTY)が無いと何も出さずに即死する**（投げっぱなしでは何も起きない）
  - 端末を与えるとログインURLを出し、ブラウザで承認した**あとに出るコードを貼り戻すまで待つ**
  - こちらが待つ処理を工場の中に置くと心臓ごと固まる（07:03の事故）

そこで、この係を**工場の外に切り離して**常駐させる：
  1. ptyを作って `claude setup-token` を起動する
  2. 出てきたログインURLを status/auth_login_url.txt に書く（Dispatchがたまごさんへ渡す）
  3. status/auth_code.txt が置かれるのを待ち、中身をそのまま端末へ流し込む
  4. 終わったら後片付けして終了。10分で誰も来なければ諦めて終わる

工場の巡回・心臓はこの係を一切待たない。固まらない。
"""
import io
import os
import pty
import re
import select
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LOG = os.path.join(REPO, "status", "auth_login.log")
URL_FILE = os.path.join(REPO, "status", "auth_login_url.txt")
CODE_FILE = os.path.join(REPO, "status", "auth_code.txt")
DONE_FILE = os.path.join(REPO, "status", "auth_login_done.txt")
CLAUDE = os.path.expanduser("~/.local/bin/claude")
if not os.path.exists(CLAUDE):
    for c in ("/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if os.path.exists(c):
            CLAUDE = c
            break
LIMIT = 900  # 15分で諦める


def w(path, text):
    try:
        io.open(path, "w", encoding="utf-8").write(text)
    except Exception:
        pass


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def strip_ansi(s):
    s = re.sub(r"\x1b\][0-9;]*;;?", "", s)
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", s)


def main():
    for p in (URL_FILE, CODE_FILE, DONE_FILE):
        try:
            os.remove(p)
        except Exception:
            pass
    mode = sys.argv[1] if len(sys.argv) > 1 else "login"
    subprocess.run(["pkill", "-f", "setup-token"], capture_output=True)
    master, slave = pty.openpty()
    if mode == "setup-token":
        cmd = [CLAUDE, "setup-token"]
    else:
        # 本来のログイン。**キーチェーンの古い鍵を正しく上書きする**のはこちら。
        # setup-token は環境変数用のトークンを出すだけで、古い鍵が残ったままだと
        # CLIはそちらを見て「期限切れ」と言い続ける（2026-09-05に実測）。
        cmd = [CLAUDE]
    proc = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave,
                            start_new_session=True, close_fds=True)
    os.close(slave)
    log("ログイン係を started（pid %d）" % proc.pid)

    if mode != "setup-token":
        time.sleep(4)
        try:
            os.write(master, b"/login\r")
        except Exception:
            pass
    buf, t0, url_written, code_sent = "", time.time(), False, False
    while time.time() - t0 < LIMIT:
        if proc.poll() is not None:
            break
        r, _, _ = select.select([master], [], [], 1.0)
        if r:
            try:
                chunk = os.read(master, 4096)
            except Exception:
                break
            if not chunk:
                break
            buf += chunk.decode("utf-8", "ignore")
            clean = strip_ansi(buf)
            if not url_written:
                m = re.search(r"https://claude\.com/\S+?state=[A-Za-z0-9_\-]+", clean)
                if m:
                    w(URL_FILE, m.group(0))
                    url_written = True
                    log("ログインURLを書き出しました")
            try:
                with io.open(LOG, "a", encoding="utf-8") as f:
                    txt = strip_ansi(chunk.decode("utf-8", "ignore"))
                    txt = re.sub(r"sk-ant-oat01-[A-Za-z0-9_\-\s]{40,}", "（トークンは伏せました）", txt)
                    f.write(txt)
            except Exception:
                pass
        # 何度でも送れる入力箱（1行ずつ端末へ流す）。/login や コードはここを通す
        keys = os.path.join(REPO, "status", "auth_keys.txt")
        if os.path.exists(keys):
            try:
                lines = io.open(keys, encoding="utf-8").read()
                os.remove(keys)
                for ln in lines.splitlines():
                    os.write(master, (ln + "\r").encode("utf-8"))
                    time.sleep(0.4)
                log("入力を送りました（%d行）" % len(lines.splitlines()))
            except Exception as e:
                log("入力を送れませんでした: %s" % e)
        # たまごさんからコードが届いたら流し込む
        if not code_sent and os.path.exists(CODE_FILE):
            try:
                code = io.open(CODE_FILE, encoding="utf-8").read().strip()
            except Exception:
                code = ""
            if code:
                try:
                    os.write(master, (code + "\n").encode("utf-8"))
                    code_sent = True
                    log("コードを流し込みました")
                except Exception as e:
                    log("コードを流し込めませんでした: %s" % e)
        if code_sent and ("success" in buf.lower() or "saved" in buf.lower()):
            break

    # トークンを拾って安全な場所へ入れる（画面折り返しで空白・改行が混ざるので全部落とす）
    installed = False
    clean_all = strip_ansi(buf)
    squeezed = re.sub(r"\s+", "", clean_all)
    m = re.search(r"(sk-ant-oat01-[A-Za-z0-9_\-]{40,})", squeezed)
    if m:
        d = os.path.expanduser("~/.tamago")
        os.makedirs(d, exist_ok=True)
        tp = os.path.join(d, "claude_token")
        io.open(tp, "w", encoding="utf-8").write(m.group(1))
        os.chmod(tp, 0o600)
        installed = True
        log("トークンを ~/.tamago/claude_token へ入れました（%d文字）" % len(m.group(1)))

    ok = installed
    w(DONE_FILE, "ok" if ok else "ng")
    try:
        os.close(master)
    except Exception:
        pass
    if proc.poll() is None:
        try:
            proc.terminate()
        except Exception:
            pass
    log("ログイン係を終了（結果 %s）" % ("成功" if ok else "未完"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
