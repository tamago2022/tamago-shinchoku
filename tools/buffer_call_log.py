#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Buffer APIを叩いた回数を1行ずつ数える係（1137番）。

なぜ要るか（2026-09-25 実測）:
  たまごさんは今日はじめてBufferを使い、出した投稿は01:58の1本だけ。
  なのに 24時間枠 250回 を使い切って 429 になっていた。
  犯人は **こちら側の自動便が同じAPIを1日に何百回も叩いていた** こと。
  叩いた跡がどこにも無かったので、犯人が分かるまでに時間がかかった。
  → 以後、**叩くたびに1行残す**。残り枠が分かるなら一緒に残す。

書き先: status/1135/buffer_call.jsonl（1行1回・追記のみ）
  {"at":"2026-09-25 05:30:00","who":"buffer_kagi_install","op":"verify",
   "http":429,"remaining":"0","limit":"250","reset":"1790352023","reset_jst":"..."}

★自前の言葉で包まない。生のHTTPコードとヘッダの値をそのまま入れる。
"""
import datetime
import io
import os

JST = datetime.timezone(datetime.timedelta(hours=9))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(REPO, "status", "1135", "buffer_call.jsonl")


def _jst(epoch):
    try:
        return datetime.datetime.fromtimestamp(
            int(epoch), JST).strftime("%F %T")
    except Exception:
        return ""


def rec(who, op, http=None, headers=None, note=""):
    """1回叩いたことを1行残す。ここで絶対に例外を投げない（本業を止めない）。"""
    import json
    h = {}
    try:
        if headers is not None:
            # urllib の HTTPMessage も requests の dict も同じ形で読む
            for k in ("x-ratelimit-limit", "x-ratelimit-remaining",
                      "x-ratelimit-reset", "retry-after"):
                v = headers.get(k) if hasattr(headers, "get") else None
                if v is not None:
                    h[k] = str(v)
    except Exception:
        pass
    line = {
        "at": datetime.datetime.now(JST).strftime("%F %T"),
        "who": who,
        "op": op,
        "http": http,
        "limit": h.get("x-ratelimit-limit"),
        "remaining": h.get("x-ratelimit-remaining"),
        "reset": h.get("x-ratelimit-reset"),
        "reset_jst": _jst(h.get("x-ratelimit-reset")) if h.get("x-ratelimit-reset") else "",
        "retry_after": h.get("retry-after"),
        "note": note,
    }
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with io.open(PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return line


def today_count(who=None):
    """今日（JST）何回叩いたか。数えるだけ。"""
    import json
    today = datetime.datetime.now(JST).strftime("%F")
    n = 0
    try:
        for ln in io.open(PATH, encoding="utf-8"):
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if not d.get("at", "").startswith(today):
                continue
            if who and d.get("who") != who:
                continue
            n += 1
    except Exception:
        pass
    return n


if __name__ == "__main__":
    import sys
    print("今日の叩いた回数:", today_count(sys.argv[1] if len(sys.argv) > 1 else None))
