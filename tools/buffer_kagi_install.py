#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bufferの鍵を「1回だけ受け取って、あとは二度と聞かない」形にしまう係。

たまごさん（2026-09-24）：
  「またなんかログインしてくださいとかいやだよ。毎回それだと困るんだよ。
    一回渡したものはちゃんと保管しようよ、その情報は。」

今日の事故：
  BufferはChrome側にセッションが無く（publish.buffer.com → auth.buffer.com/login）、
  鍵台帳にも Buffer の行が無かった。つまり **渡された記録がどこにも無い**。
  だから毎回「ログインして」に戻る。ここでそれを終わらせる。

やること（5分便から自動で呼ばれる。たまごさんはターミナルを開かない）：
  1. 下の DROPS のどれかに置かれたトークンを拾う
  2. api.buffer.com に1回だけ叩いて、本物か確かめる（ダメなら何も壊さない）
  3. ~/.tamago/keys/api_keys.env の BUFFER_ACCESS_TOKEN に書く（chmod 600）
  4. 置いてあった元ファイルを消す（平文を残さない）
  5. 伏せ字にしたログを status/kagi_daicho.log に1行だけ残す

★値は画面にもログにも出さない（先頭4文字＋末尾2文字だけ）。
★リポジトリの中には1文字も書かない。
"""
import io
import json
import os
import re
import stat
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TAMAGO = os.path.expanduser("~/.tamago")
KEYS = os.path.join(TAMAGO, "keys", "api_keys.env")
LOG = os.path.join(REPO, "status", "kagi_daicho.log")

# 受け取り口。★どれもリポジトリの外。拾ったら消す。
DROPS = [
    os.path.expanduser("~/Desktop/buffer_token.txt"),
    os.path.expanduser("~/Downloads/buffer_token.txt"),
    os.path.join(TAMAGO, "_drop", "buffer.txt"),
    # Cowork/Dispatch が書ける場所（たまごさんがチャットに貼ったときの経路）
    os.path.expanduser(
        "~/Library/Application Support/Claude/local-agent-mode-sessions"
    ),
]

API = "https://api.buffer.com"


def mask(v):
    if not v:
        return "(空)"
    return v[:4] + "…" + v[-2:] + "(%d文字)" % len(v)


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s [buffer_kagi_install] %s\n"
                    % (time.strftime("%F %T"), msg))
    except Exception:
        pass
    print(msg)


def find_drop():
    """置かれたトークンを探す。フォルダが来たら中の buffer_token.txt を掘る。"""
    for p in DROPS:
        if os.path.isfile(p):
            yield p
        elif os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for fn in files:
                    if fn == "buffer_token.txt":
                        yield os.path.join(root, fn)


def read_token(path):
    try:
        raw = io.open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return None
    # 行頭の BUFFER_ACCESS_TOKEN= も許す。空白・引用符は落とす。
    raw = raw.strip()
    # ★名前の言い間違いを吸収（1132番）。BUFFER_TOKEN でも BUFFER_ACCESS_TOKEN でも拾う。
    m = re.search(r"BUFFER(?:_ACCESS)?_TOKEN\s*=\s*(\S+)", raw)
    if m:
        raw = m.group(1)
    raw = raw.strip().strip('"').strip("'")
    # 1行だけ取る
    raw = raw.splitlines()[0].strip() if raw else ""
    return raw or None


def verify(token):
    """本物か1回だけ叩いて確かめる。通らない鍵は保管しない（嘘の台帳を作らない）。"""
    body = json.dumps({"query": "{ account { id } }"}).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer %s" % token,
                 "User-Agent": "tamago-buffer-kagi"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode())
        if d.get("errors"):
            return False, str(d["errors"])[:200]
        return True, "200 通った"
    except Exception as e:
        return False, "%s" % e


def put(token):
    os.makedirs(os.path.dirname(KEYS), exist_ok=True)
    lines = []
    if os.path.exists(KEYS):
        lines = io.open(KEYS, encoding="utf-8").read().splitlines()
    out, done = [], False
    for ln in lines:
        if ln.strip().startswith("BUFFER_ACCESS_TOKEN="):
            out.append("BUFFER_ACCESS_TOKEN=%s" % token)
            done = True
        else:
            out.append(ln)
    if not done:
        out.append("BUFFER_ACCESS_TOKEN=%s" % token)
    tmp = "%s.%d.tmp" % (KEYS, os.getpid())   # ★固定名の .tmp は使わない（既知の地雷）
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(out).rstrip() + "\n")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(tmp, KEYS)


def already_have():
    """★読み口は tools/kagi.py 1本だけ（1132番）。名前の揺れもそこで吸収する。"""
    sys.path.insert(0, HERE)
    import kagi
    return kagi.get("BUFFER_ACCESS_TOKEN")


def main():
    if not os.path.isdir(TAMAGO):
        # 鍵の置き場が見えない＝サンドボックス。判定を1つも書かない（969番の約束）。
        print("鍵の置き場(~/.tamago)が見えないので、何もせず退きました")
        return 3

    for path in find_drop():
        tok = read_token(path)
        if not tok:
            continue
        ok, why = verify(tok)
        if not ok:
            log("置かれた鍵 %s は通りませんでした（%s）。★元ファイルは消していません"
                % (mask(tok), why))
            return 2
        put(tok)
        try:
            os.remove(path)
        except Exception:
            pass
        log("Bufferの鍵を保管しました %s → ~/.tamago/keys/api_keys.env"
            " / 置いてあった平文は消しました" % mask(tok))
        return 0

    have = already_have()
    if have:
        # ★1135番：5分便が毎周回 verify() を叩いていて、BufferのAPIが429で閉じていた
        #   （2026-09-25 03:01〜、予約が1本も入れられなくなった）。
        #   鍵があるときの確認は**1日1回だけ**にする。鍵が新しく置かれた時は上の枝で毎回確かめる。
        stamp = os.path.join(TAMAGO, ".buffer_kagi_verify_stamp")
        today = time.strftime("%F")
        try:
            done = io.open(stamp, encoding="utf-8").read().strip()
        except Exception:
            done = ""
        if done == today:
            return 0
        ok, why = verify(have)
        log("Bufferの鍵は既にあります %s：%s" % (mask(have), why))
        if ok:
            try:
                with io.open(stamp, "w", encoding="utf-8") as f:
                    f.write(today)
            except Exception:
                pass
        return 0 if ok else 2

    log("Bufferの鍵はまだありません。publish.buffer.com/settings/api で1回だけ作って、"
        "~/Desktop/buffer_token.txt に貼って保存してください（あとは自動）")
    return 2


if __name__ == "__main__":
    sys.exit(main())
