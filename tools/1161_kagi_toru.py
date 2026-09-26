#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1161番【鍵を取り直す係（承認はこちらで押す）】2026-09-26

心臓経由でMac上に常駐し、`claude setup-token` を端末付きで回す。
ブラウザは自動で開かせない（BROWSER=echo ＋ shimの open）。
OAuthのURLは status/1161_url.txt に出す。
承認コードは status/1161_code.txt に置かれたら流し込む。
取れた鍵は ~/.tamago/claude_token に保存し、実際に1本叩いて通ったときだけ
use_token を立て、auth_expired.flag / no_launch.flag / .hassha_stop を外す。
鍵の中身はログにも画面にも出さない（長さだけ）。
"""
import io, os, pty, re, select, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
URLF = os.path.join(ST, "1161_url.txt")
CODEF = os.path.join(ST, "1161_code.txt")
SCRF = os.path.join(ST, "1161_screen.txt")
LOGF = os.path.join(ST, "1161_toru.log")
LOCK = os.path.join(ST, "1161_toru.lock")
TAMAGO = os.path.expanduser("~/.tamago")
TOKEN = os.path.join(TAMAGO, "claude_token")
MINTED = os.path.join(TAMAGO, "claude_token.minted")
USE = os.path.join(TAMAGO, "use_token")
CLAUDE = os.path.expanduser("~/.local/bin/claude")
TOKEN_RE = re.compile(r"sk-ant-oat01-[A-Za-z0-9_\-]{20,}")
URL_RE = re.compile(r"https://claude\.ai/oauth/authorize\?[^\s\"'\x1b]+")
WAIT_CODE = 1500  # 25分


def log(m):
    try:
        with io.open(LOGF, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%F %T"), m))
    except Exception:
        pass


def strip_ansi(s):
    s = re.sub(r"\x1b\][0-9;]*;;?[^\x07\x1b]*(\x07|\x1b\\)?", "", s)
    s = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", s)
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)


def redact(s):
    return TOKEN_RE.sub("sk-ant-oat01-<KAKUSHITA>", s)


def dump(buf):
    try:
        with io.open(SCRF, "w", encoding="utf-8") as f:
            f.write(redact(strip_ansi(buf))[-20000:])
    except Exception:
        pass


def main():
    # 二重起動を止める
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        try:
            if time.time() - os.path.getmtime(LOCK) < 1800:
                log("既に走っているので降りる")
                return 0
        except Exception:
            pass
        try:
            os.remove(LOCK)
        except Exception:
            pass
        fd = os.open(LOCK, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)

    for p in (URLF, CODEF, SCRF):
        try:
            os.remove(p)
        except Exception:
            pass

    if not os.path.exists(CLAUDE):
        log("claude本体が無い: %s" % CLAUDE)
        return 1

    # ブラウザを開かせないための shim（open を握りつぶす）
    shim = os.path.join(TAMAGO, "noopen")
    os.makedirs(shim, exist_ok=True)
    op = os.path.join(shim, "open")
    with io.open(op, "w", encoding="utf-8") as f:
        f.write("#!/bin/sh\nexit 0\n")
    os.chmod(op, 0o755)

    log("setup-token を始める")
    pid, mfd = pty.fork()
    if pid == 0:
        env = dict(os.environ)
        env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        env["BROWSER"] = "echo"
        env["PATH"] = shim + ":" + env.get("PATH", "/usr/bin:/bin")
        env["TERM"] = "xterm-256color"
        env["CI"] = ""
        os.execve(CLAUDE, [CLAUDE, "setup-token"], env)
        os._exit(127)

    buf = ""
    token = ""
    url_written = False
    code_sent = False
    enter_sent = 0
    t0 = time.time()
    last_dump = 0
    while time.time() - t0 < WAIT_CODE:
        try:
            r, _, _ = select.select([mfd], [], [], 1.0)
        except Exception:
            break
        if r:
            try:
                chunk = os.read(mfd, 65536)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk.decode("utf-8", "replace")
            if len(buf) > 400000:
                buf = buf[-200000:]
        now = time.time()
        if now - last_dump > 3:
            dump(buf)
            last_dump = now
        flat = strip_ansi(buf)

        if not url_written:
            m = URL_RE.search(flat)
            if m:
                u = m.group(0).rstrip(".,)")
                with io.open(URLF, "w", encoding="utf-8") as f:
                    f.write(u + "\n")
                url_written = True
                log("OAuth URL を出した（len=%d）" % len(u))
        # 「Enterでブラウザを開く」で止まっているときは Enter を送る
        if not url_written and enter_sent < 3 and ("Press Enter" in flat or "press enter" in flat.lower()):
            try:
                os.write(mfd, b"\r")
            except Exception:
                pass
            enter_sent += 1
            log("Enterを送った(%d)" % enter_sent)
            time.sleep(1.0)

        if url_written and not code_sent and os.path.exists(CODEF):
            code = io.open(CODEF, encoding="utf-8").read().strip()
            if code:
                try:
                    os.write(mfd, (code + "\r").encode())
                    code_sent = True
                    log("コードを流し込んだ（len=%d）" % len(code))
                except Exception as e:
                    log("コード流し込み失敗 %r" % (e,))

        m = TOKEN_RE.search(flat)
        if m:
            token = m.group(0)
            log("鍵を拾った（len=%d）" % len(token))
            break
        try:
            done, _ = os.waitpid(pid, os.WNOHANG)
            if done:
                # 残りを読み切る
                for _ in range(20):
                    try:
                        r2, _, _ = select.select([mfd], [], [], 0.2)
                        if not r2:
                            break
                        c2 = os.read(mfd, 65536)
                        if not c2:
                            break
                        buf += c2.decode("utf-8", "replace")
                    except OSError:
                        break
                flat = strip_ansi(buf)
                m = TOKEN_RE.search(flat)
                if m:
                    token = m.group(0)
                log("setup-token が終了した token=%s" % ("あり" if token else "なし"))
                break
        except ChildProcessError:
            break

    dump(buf)
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass

    if not token:
        log("鍵が取れなかった")
        try:
            os.remove(LOCK)
        except Exception:
            pass
        return 2

    os.makedirs(TAMAGO, exist_ok=True)
    with io.open(TOKEN, "w", encoding="utf-8") as f:
        f.write(token + "\n")
    os.chmod(TOKEN, 0o600)
    with io.open(MINTED, "w", encoding="utf-8") as f:
        f.write(time.strftime("%F %T") + "\n")
    log("鍵を保存した len=%d" % len(token))

    # 実測：本当に1本通るか
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    ok = False
    try:
        p = subprocess.run([CLAUDE, "-p", "ping", "--model", "claude-3-5-haiku-20241022"],
                           capture_output=True, text=True, timeout=180, env=env, cwd=REPO)
        out = (p.stdout or "").strip()
        log("実測 rc=%s out=%r err=%r" % (p.returncode, out[:200], (p.stderr or "")[:300]))
        ok = (p.returncode == 0 and len(out) > 0)
    except subprocess.TimeoutExpired:
        log("実測 180秒で無応答")
    except Exception as e:
        log("実測 例外 %r" % (e,))

    if ok:
        with io.open(USE, "w", encoding="utf-8") as f:
            f.write(time.strftime("%F %T") + "\n")
        for p in (os.path.join(ST, "auth_expired.flag"),
                  os.path.join(ST, "no_launch.flag"),
                  os.path.join(ST, ".hassha_stop")):
            try:
                os.remove(p)
                log("外した: %s" % os.path.basename(p))
            except Exception:
                pass
        log("=== 鍵は生きている。発車を再開した ===")
    else:
        log("=== 鍵は取れたが1本通らなかった。use_tokenは立てない ===")
    try:
        os.remove(LOCK)
    except Exception:
        pass
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
