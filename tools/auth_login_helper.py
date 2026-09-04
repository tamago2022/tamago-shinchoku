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
    subprocess.run(["pkill", "-f", "setup-token"], capture_output=True)
    master, slave = pty.openpty()
    proc = subprocess.Popen([CLAUDE, "setup-token"], stdin=slave, stdout=slave, stderr=slave,
                            start_new_session=True, close_fds=True)
    os.close(slave)
    log("ログイン係を started（pid %d）" % proc.pid)

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
                    f.write(strip_ansi(chunk.decode("utf-8", "ignore")))
            except Exception:
                pass
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

    ok = code_sent and proc.poll() is not None and proc.returncode == 0
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
