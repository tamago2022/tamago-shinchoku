#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""インスタURL → 動画ファイル（1行コマンド・2026-10-10・ワイちゃん変身動画の件で新設）

  python3 tools/insta_get.py https://www.instagram.com/reel/XXXXXXXX/
  python3 tools/insta_get.py --self-test

・Macで動けば直接、サンドボックス（Linux）なら status/mac_jobs 経由でMacに走らせる。
・道具：~/.tamago/bin/yt-dlp（GitHub公式の単体版 yt-dlp_macos。無ければ自動で取ってくる）。
  Mac標準の python3.9 + pip の yt-dlp(2025.10) は「ログインが要る」で落ちた。最新版の単体版で取れた（実測 2026-10-10）。
・保存先：~/.tamago/insta/<ID>.mp4（公開リポの外。他人の動画をGitHubへ写さないため）。
・ブラウザ・画面収録・クッキー読み出し（--cookies-from-browser はキーチェーンの許可が出る）は使わない。
・取れなかったら理由を1行で出して終了コード1。
"""
import os
import re
import shlex
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(REPO, "status", "mac_jobs")
URL_RE = re.compile(r"^https://(www\.)?instagram\.com/(reel|reels|p|tv)/[A-Za-z0-9_-]+/?(\?.*)?$")


def mac_script(url):
    q = shlex.quote(url)
    return "\n".join([
        "#!/bin/bash",
        "# insta_get.py：インスタURL→動画ファイル（読むだけ）",
        'Y="$HOME/.tamago/bin/yt-dlp"; OUT="$HOME/.tamago/insta"; mkdir -p "$HOME/.tamago/bin" "$OUT"',
        'if [ ! -x "$Y" ]; then curl -sL -m 120 -o "$Y.tmp" https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos && chmod +x "$Y.tmp" && mv "$Y.tmp" "$Y"; fi',
        # 週1回だけ自己更新（インスタ側の変更に追従するため）
        'if [ -n "$(find "$Y" -mtime +7 2>/dev/null)" ]; then "$Y" -U >/dev/null 2>&1; touch "$Y"; fi',
        '"$Y" --no-playlist -q --no-warnings -f "b[ext=mp4]/b" -o "$OUT/%(id)s.%(ext)s" --print after_move:filepath ' + q + ' 2>"$OUT/last_err.txt"',
        'rc=$?; if [ $rc -ne 0 ]; then echo "NG: $(grep -m1 ERROR "$OUT/last_err.txt" | cut -c1-200)"; fi; exit $rc',
        "",
    ])


def main():
    a = sys.argv[1:]
    if a and a[0] == "--self-test":
        ok = bool(URL_RE.match("https://www.instagram.com/reel/DeQAxSTNUBX/")) and not URL_RE.match("file:///etc/passwd")
        ok = ok and "yt-dlp" in mac_script("https://www.instagram.com/reel/A/")
        print("SELFTEST", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    if not a or not URL_RE.match(a[0]):
        print("使い方: python3 tools/insta_get.py https://www.instagram.com/reel/XXXX/")
        return 2
    script = mac_script(a[0])
    if sys.platform == "darwin":
        return subprocess.call(["bash", "-c", script])
    # サンドボックス → Macの心臓に走らせてもらう
    name = "insta_%s_%d" % (time.strftime("%H%M%S"), os.getpid())
    p = os.path.join(JOBS, "pending", name + ".sh")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p + ".tmp", "w", encoding="utf-8").write(script)
    os.replace(p + ".tmp", p)
    done = os.path.join(JOBS, "done", name + ".out")
    end = time.time() + 240
    while time.time() < end:
        if os.path.exists(done):
            time.sleep(1)
            out = open(done, encoding="utf-8", errors="ignore").read()
            lines = [l for l in out.splitlines() if l.endswith(".mp4") or l.startswith("NG:")]
            print("\n".join(lines) or out[-400:])
            return 0 if any(l.endswith(".mp4") for l in lines) else 1
        time.sleep(3)
    print("NG: Macが240秒で拾わなかった（後で %s を見る）" % done)
    return 1


if __name__ == "__main__":
    sys.exit(main())
