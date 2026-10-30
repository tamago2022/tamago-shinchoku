#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Suno MCP（ベータ）の見張り（2026-10-31・たまごさん「DispatchからSunoで曲を作れるようにしといて」）

公式（https://suno.com/mcp ・ help.suno.com/en/articles/14551425）の Claude Code 手順：
  claude mcp add --transport http suno https://api.suno.com/mcp   ← 10-31 05:00 に --scope user で登録済み
  サインインは Suno の OAuth（APIキーなし）。曲を作るとSunoのクレジットを使う。

この係がやること（Mac の上で。ブラウザは開かせない＝BROWSER と open を握りつぶす）：
  --signin  : `claude mcp login suno` を端末付きで回し、出てきた承認URLを status/suno_mcp/jotai.json に書く。
              たまごさんが押すまで待つ。期限切れで終わったら新しいURLを出し直す（最長 SIGNIN_HOURS 時間）。
              つながったら続けて --kakunin を走らせて終わる。二重に立たない（ロック）。
  --kakunin : つながったか（claude mcp get suno）を見て、claude -p に「読むだけの道具」で
              クレジット残高と1曲あたりの消費を確かめさせる。曲は作らない（作る系の道具は許さない）。
  --tick    : 心臓の相乗り用。つながっていない・係がいない → --signin を切り離して起こす。
  --self-test
結果：status/suno_mcp/jotai.json（公開しない status/ 直下・鍵の中身は書かない）。
片付け：終わったら ~/.tamago/suno_noopen と画面の控え（login_screen.txt）を自分で消す。
"""
import io
import json
import os
import pty
import re
import select
import shutil
import signal
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(REPO, "status", "suno_mcp")
JOTAI = os.path.join(ST, "jotai.json")
SCREEN = os.path.join(ST, "login_screen.txt")
LOCK = os.path.join(ST, "signin.lock")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
SHIM = os.path.expanduser("~/.tamago/suno_noopen")
CLAUDE = os.path.expanduser("~/.local/bin/claude")
NAME = "suno"
SIGNIN_HOURS = 72
URL_RE = re.compile(r"https://[^\s\"'\x1b<>]*(?:authorize|oauth)[^\s\"'\x1b<>]*")
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07|\x1b[()][A-Za-z0-9]")


def now():
    return time.strftime("%F %T")


def yomu():
    try:
        return json.load(io.open(JOTAI, encoding="utf-8"))
    except Exception:
        return {}


def kaku(**kw):
    os.makedirs(ST, exist_ok=True)
    d = yomu()
    d.update(kw)
    d["koushin"] = now()
    tmp = JOTAI + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
    os.replace(tmp, JOTAI)


def dispatch(msg):
    try:
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": now(), "type": "suno_mcp", "text": msg}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def strip_ansi(s):
    return ANSI.sub("", s).replace("\r", "")


def hirou_url(flat):
    """端末で折り返されたURLを繋ぎ直して最後の1本を返す。"""
    joined = re.sub(r"\n(?=[A-Za-z0-9%&=_\-./?:+~#]+)", "", flat)
    us = [u for u in URL_RE.findall(joined) if "code_challenge" in u or "redirect_uri" in u or "client_id" in u]
    return us[-1].rstrip(".,)") if us else ""


def shim_tsukuru():
    os.makedirs(SHIM, exist_ok=True)
    cap = os.path.join(ST, "open_capture.txt")
    for nm in ("open", "xdg-open", "browser"):
        p = os.path.join(SHIM, nm)
        io.open(p, "w", encoding="utf-8").write(
            '#!/bin/sh\necho "$@" >> %s\nexit 0\n' % cap)
        os.chmod(p, 0o755)
    return cap


def tsunagatta():
    """claude mcp get suno の Status で判定（✓ Connected なら True）。"""
    try:
        p = subprocess.run([CLAUDE, "mcp", "get", NAME], capture_output=True, text=True,
                           timeout=60, cwd=REPO)
        out = (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return None, "mcp get 失敗 %r" % (e,)
    st = ""
    for l in out.splitlines():
        if "Status:" in l:
            st = l.split("Status:", 1)[1].strip()
    return ("Connected" in st or "✓" in st), st or out.strip()[:200]


def lock_toru():
    os.makedirs(ST, exist_ok=True)
    try:
        if os.path.exists(LOCK):
            pid = int((io.open(LOCK).read().split() or ["0"])[0])
            try:
                os.kill(pid, 0)
                return False
            except Exception:
                pass
        io.open(LOCK, "w").write("%d %s\n" % (os.getpid(), now()))
        return True
    except Exception:
        return False


def login_ikkai(cap):
    """claude mcp login suno を1回。URLを書き、終わるまで待つ。戻り値＝(終わり方, 画面の最後)"""
    pid, mfd = pty.fork()
    if pid == 0:
        env = dict(os.environ)
        env["PATH"] = SHIM + ":" + env.get("PATH", "/usr/bin:/bin")
        env["BROWSER"] = os.path.join(SHIM, "browser")
        env["TERM"] = "xterm-256color"
        os.chdir(REPO)
        os.execve(CLAUDE, [CLAUDE, "mcp", "login", NAME], env)
        os._exit(127)
    buf, url, url_kouho, url_at, t0, last_dump, enter = "", "", "", 0.0, time.time(), 0, 0
    while True:
        try:
            r, _, _ = select.select([mfd], [], [], 1.0)
        except Exception:
            break
        if r:
            try:
                ch = os.read(mfd, 65536)
            except OSError:
                break
            if not ch:
                break
            buf = (buf + ch.decode("utf-8", "replace"))[-200000:]
        flat = strip_ansi(buf)
        t = time.time()
        if t - last_dump > 3:
            io.open(SCREEN, "w", encoding="utf-8").write(flat[-6000:])
            last_dump = t
        if enter < 3 and re.search(r"press enter|Enter to (open|continue)", flat, re.I) and not url:
            try:
                os.write(mfd, b"\r")
            except Exception:
                pass
            enter += 1
            time.sleep(1)
        u = hirou_url(flat)
        if not u and os.path.exists(cap):
            u = hirou_url(io.open(cap, encoding="utf-8", errors="ignore").read())
        if u and u != url:
            if u == url_kouho and t - url_at > 2.5:
                url = u
                kaku(jotai="承認待ち", url=url, url_deta=now(), url_pid=os.getpid())
                dispatch("Suno のサインイン（押すだけ）：%s" % url)
            elif u != url_kouho:
                url_kouho, url_at = u, t
        try:
            wp, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            wp = pid
        if wp == pid:
            break
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass
    try:
        os.waitpid(pid, 0)
    except Exception:
        pass
    flat = strip_ansi(buf)
    io.open(SCREEN, "w", encoding="utf-8").write(flat[-6000:])
    return round(time.time() - t0), flat[-600:]


def signin():
    if not lock_toru():
        return 0
    cap = shim_tsukuru()
    t_end = time.time() + SIGNIN_HOURS * 3600
    kaisuu = 0
    try:
        while time.time() < t_end:
            ok, st = tsunagatta()
            if ok:
                kaku(jotai="つながった", tsunagatta=now(), url="", status=st)
                dispatch("Suno MCP がつながりました。クレジットを確かめます。")
                kakunin()
                return 0
            kaisuu += 1
            try:
                os.remove(cap)
            except Exception:
                pass
            byou, owari = login_ikkai(cap)
            kaku(saigo_login={"kai": kaisuu, "byou": byou, "owari": owari[-300:], "at": now()})
            # 期限切れで終わったら出し直す。すぐ落ちる失敗が続くときは間をあける
            time.sleep(5 if byou > 60 else 120)
        kaku(jotai="期限切れ（%d時間押されず）" % SIGNIN_HOURS, url="")
        return 1
    finally:
        for p in (LOCK, SCREEN, os.path.join(ST, "open_capture.txt")):
            try:
                os.remove(p)
            except Exception:
                pass
        shutil.rmtree(SHIM, ignore_errors=True)


KAKUNIN_PROMPT = """Suno MCP（mcp__suno__* の道具）で、読むだけの確認をしてください。曲・音声は絶対に作らないでください。
1) 使える mcp__suno__ の道具の名前を全部、1行ずつ書く。
2) クレジット残高・プラン名を、残高を見る道具で確かめる（作る道具は呼ばない）。
3) 1曲作ると何クレジット減るかを、道具の説明・返り値に書いてあれば、その文言どおりに書く。書いていなければ「不明」と書く。推測で数字を作らない。
最後に次のJSONを1行だけ出す：
SUNO_KAKUNIN {"tools":[...],"plan":"...","credits":数字かnull,"per_song":"文言か不明","source":"どの道具の返り値か"}"""


def kakunin():
    ok, st = tsunagatta()
    if not ok:
        kaku(kakunin={"at": now(), "kekka": "まだつながっていない", "status": st})
        return 1
    # 作る系を通さないため、読むだけの道具名だけ許す。まず道具名を知る（道具は全部拒否で1回）
    env = dict(os.environ)
    try:
        p = subprocess.run([CLAUDE, "-p", "使える mcp__suno__ で始まる道具の名前だけを、1行1つで書いて。道具は呼ばないで。",
                            "--output-format", "text", "--disallowedTools", "mcp__suno"],
                           capture_output=True, text=True, timeout=170, cwd=REPO, env=env)
        names = sorted(set(re.findall(r"mcp__suno__[A-Za-z0-9_\-]+", p.stdout or "")))
    except Exception as e:
        names = []
        kaku(kakunin={"at": now(), "kekka": "道具名の取得に失敗 %r" % (e,)})
    yomu_dake = [n for n in names if re.search(r"credit|balance|plan|account|profile|me$|whoami|usage|billing|limit|info", n, re.I)
                 and not re.search(r"create|generate|make|song|cover|extend|remix|mashup|upload|speech|write|add|delete", n, re.I)]
    kekka = {"at": now(), "tools": names, "yurushita": yomu_dake}
    if yomu_dake:
        try:
            p = subprocess.run([CLAUDE, "-p", KAKUNIN_PROMPT, "--output-format", "text",
                                "--allowedTools", ",".join(yomu_dake),
                                "--disallowedTools", ",".join(n for n in names if n not in yomu_dake) or "Bash"],
                               capture_output=True, text=True, timeout=170, cwd=REPO, env=env)
            out = p.stdout or ""
            m = re.search(r"SUNO_KAKUNIN\s*(\{.*\})", out)
            kekka["kotae"] = json.loads(m.group(1)) if m else None
            kekka["text"] = out[-1500:]
        except Exception as e:
            kekka["err"] = repr(e)
    else:
        kekka["err"] = "残高を見る道具が名前で見分けられなかった（作る道具を呼ばないため止めた）"
    kaku(kakunin=kekka)
    k = kekka.get("kotae") or {}
    dispatch("Suno MCP 確認：プラン %s／残り %s クレジット／1曲 %s" % (
        k.get("plan", "?"), k.get("credits", "?"), k.get("per_song", "不明")))
    return 0


def tick():
    """心臓の相乗り：つながっていなくて係もいなければ、--signin を切り離して起こす。"""
    d = yomu()
    if d.get("jotai") == "つながった" and d.get("kakunin"):
        return 0
    if os.path.exists(LOCK):
        try:
            os.kill(int(io.open(LOCK).read().split()[0]), 0)
            return 0
        except Exception:
            pass
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "--signin"],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     cwd=REPO, start_new_session=True)
    return 0


def self_test():
    ok = True
    s = ("Please visit\r\nhttps://studio-api-prod.suno.com/api/v2/external/oauth/authorize?response_type=code&client_id=ab\n"
         "c&code_challenge=xyz&redirect_uri=http%3A%2F%2Flocalhost%3A5555%2Fcallback\n\nWaiting...")
    u = hirou_url(strip_ansi(s))
    ok &= u.startswith("https://studio-api-prod.suno.com/") and "client_id=abc" in u and u.endswith("callback")
    ok &= hirou_url("no url here") == ""
    ok &= strip_ansi("\x1b[32mhi\x1b[0m") == "hi"
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "--tick"
    sys.exit({"--signin": signin, "--kakunin": kakunin, "--tick": tick, "--self-test": self_test}.get(a, tick)())
