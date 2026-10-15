#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""動画・音声の中間ファイルを、仕事が終わったら必ずしまう係（2026-10-16・たまごさん「使ったらしまう」）。

子セッションが動画・音声（ffmpeg・Whisper・yt-dlp・レンダ）の仕事で作った「途中の物」を、
2時間さわられていなければ消す。完成品（★最新・納品済み・mp4 の完成ファイル）には触らない。

  消すもの（名前で決め打ち＝作り直せるものだけ）
   ・フォルダ：_frames / frames_tmp / tmp_frames / _chunks / chunks_tmp / _tmp / _seg / segments_tmp / _render_tmp
   ・ファイル：*.part / *.ytdl / *.temp.* / *.tmp / ffmpeg2pass-*.log* / *_tmp.wav / *_tmp.mp4 / *.frag
  見る場所：~/howitholds・~/Documents/AI作業（.worktrees を除く）・/private/tmp・$TMPDIR
  見ない場所：壺と金庫・Vault・iCloud・ドライブ・HDD
仕事の回収（auto_launcher.harvest → status/worktree_taihi.go）と shimau.py から呼ばれる。
結果：status/public/chukan_shimau.json
逆テスト：python3 tools/chukan_shimau.py --self-test
"""
import fnmatch
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
PUB = os.path.join(REPO, "status", "public", "chukan_shimau.json")
AGE = 2 * 3600
DIRS = {"_frames", "frames_tmp", "tmp_frames", "_chunks", "chunks_tmp", "_tmp", "_seg", "segments_tmp", "_render_tmp"}
FILES = ("*.part", "*.ytdl", "*.temp.*", "*.tmp", "ffmpeg2pass-*.log*", "*_tmp.wav", "*_tmp.mp4", "*.frag")
FORBIDDEN = ("CloudStorage", "Mobile Documents", "iCloud", "Google Drive", "tamago_brain", "Vault", "金庫", "壺",
             "kinko", "/Volumes/", "★最新", "/.worktrees", "com.apple")


def newest(p):
    m = os.lstat(p).st_mtime
    if os.path.isdir(p) and not os.path.islink(p):
        for dp, dns, fns in os.walk(p):
            for x in dns + fns:
                try:
                    m = max(m, os.lstat(os.path.join(dp, x)).st_mtime)
                except Exception:
                    pass
    return m


def size(p):
    if os.path.isfile(p) or os.path.islink(p):
        return os.lstat(p).st_size
    t = 0
    for dp, _, fns in os.walk(p):
        for f in fns:
            try:
                t += os.lstat(os.path.join(dp, f)).st_size
            except Exception:
                pass
    return t


def scan(roots, age=AGE, dry=False, maxdepth=6):
    now = time.time()
    hit = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        base = root.rstrip("/").count("/")
        for dp, dns, fns in os.walk(root):
            if any(f in dp for f in FORBIDDEN) or dp.count("/") - base >= maxdepth:
                dns[:] = []
                continue
            for d in list(dns):
                p = os.path.join(dp, d)
                if d in DIRS and not os.path.islink(p):
                    dns.remove(d)
                    try:
                        if now - newest(p) > age:
                            hit.append(p)
                    except Exception:
                        pass
                elif d in (".worktrees", "node_modules", ".git"):
                    dns.remove(d)
            for f in fns:
                if any(fnmatch.fnmatch(f, pat) for pat in FILES):
                    p = os.path.join(dp, f)
                    try:
                        if now - os.lstat(p).st_mtime > age:
                            hit.append(p)
                    except Exception:
                        pass
    out = []
    for p in hit:
        if any(f in p for f in FORBIDDEN):
            continue
        b = size(p)
        if not dry:
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                try:
                    os.remove(p)
                except Exception:
                    continue
        out.append({"p": p.replace(HOME, "~"), "gb": round(b / 1e9, 3)})
    return out


def run(dry=False):
    roots = [HOME + "/howitholds", HOME + "/Documents/AI作業", "/private/tmp", tempfile.gettempdir()]
    out = scan(roots, dry=dry)
    res = {"at": time.strftime("%F %T"), "dry": dry, "count": len(out),
           "gb": round(sum(x["gb"] for x in out), 2), "removed": out[:200]}
    if not dry:
        os.makedirs(os.path.dirname(PUB), exist_ok=True)
        json.dump(res, open(PUB + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(PUB + ".tmp", PUB)
    return "%d個 %.2fGB" % (res["count"], res["gb"])


def self_test():
    d = tempfile.mkdtemp()
    old_t = time.time() - 5 * 3600
    mk = {"ep01/_frames/0001.png": old_t, "ep01/final.mp4": old_t, "ep01/a.part": old_t,
          "ep02/_frames/0001.png": time.time(), "金庫/_frames/x.png": old_t, "ep03/★最新_x_tmp.mp4": old_t}
    for rel, t in mk.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(b"x" * 1000)
        os.utime(p, (t, t))
    os.utime(os.path.join(d, "ep01/_frames"), (old_t, old_t))
    scan([d])
    ex = lambda r: os.path.exists(os.path.join(d, r))
    assert not ex("ep01/_frames") and not ex("ep01/a.part"), "古い中間物が残った"
    assert ex("ep01/final.mp4"), "完成品を消した"
    assert ex("ep02/_frames/0001.png"), "作業中の中間物を消した"
    assert ex("金庫/_frames/x.png") and ex("ep03/★最新_x_tmp.mp4"), "触らない物を消した"
    shutil.rmtree(d)
    print("self-test OK")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        print(run(dry="--dry" in sys.argv))
