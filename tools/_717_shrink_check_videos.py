#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
案件#717：share/check配下の1MB超のmp4/mp3をffmpegで圧縮し、その場（同じファイル名・拡張子）で置き換える。
確認ページの<video src>/<audio src>は変えずに済む（URLを壊さない）。

方針：
- 短尺(target<=1MB)を狙い、解像度を段階的に落としながらCRFエンコードを試す。
- 何段階か試して1MB以下に収まらなければ、そこで諦めて実測サイズをそのまま報告する
  （無理に壊れるまで潰さない＝実物を壊さない原則）。
"""
import os
import subprocess
import sys

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT = 1_000_000
TARGET = 950_000  # 安全マージン
SEARCH_DIR = os.path.join(REPO, "share", "check")


def find_targets():
    out = []
    for root, dirs, files in os.walk(SEARCH_DIR):
        for f in files:
            if f.lower().endswith((".mp4", ".mov", ".mp3")):
                p = os.path.join(root, f)
                try:
                    if os.path.getsize(p) > LIMIT:
                        out.append(p)
                except OSError:
                    pass
    return sorted(out)


def ffprobe_duration(p):
    r = subprocess.run([FFMPEG, "-i", p], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            hms = line.split(",")[0].split("Duration:")[1].strip()
            h, m, s = hms.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return None


def encode_mp4(src, dst, width, v_kbps, a_kbps):
    cmd = [
        FFMPEG, "-y", "-i", src,
        "-vf", "scale=%d:-2" % width,
        "-c:v", "libx264", "-preset", "medium", "-b:v", "%dk" % v_kbps,
        "-maxrate", "%dk" % int(v_kbps * 1.3), "-bufsize", "%dk" % int(v_kbps * 2),
        "-c:a", "aac", "-b:a", "%dk" % a_kbps, "-movflags", "+faststart",
        dst,
    ]
    subprocess.run(cmd, capture_output=True)


def encode_mp3(src, dst, kbps):
    cmd = [FFMPEG, "-y", "-i", src, "-c:a", "libmp3lame", "-b:a", "%dk" % kbps, dst]
    subprocess.run(cmd, capture_output=True)


def shrink_video(p):
    dur = ffprobe_duration(p) or 10.0
    tmp = p + ".tmp.mp4"
    # 総ビットレート予算(kbps) = TARGETバイト*8/1000 / 秒 から、音声ぶんを差し引く
    for width in (1280, 854, 640, 480):
        a_kbps = 64
        budget_kbps = (TARGET * 8 / 1000.0) / dur
        v_kbps = max(80, int(budget_kbps - a_kbps))
        encode_mp4(p, tmp, width, v_kbps, a_kbps)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            sz = os.path.getsize(tmp)
            if sz <= LIMIT:
                os.replace(tmp, p)
                return sz
    # 最終手段：480pの結果をそのまま採用（それでも収まらなければ実測値のまま置く）
    if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
        os.replace(tmp, p)
        return os.path.getsize(p)
    return os.path.getsize(p)


def shrink_mp3(p):
    dur = ffprobe_duration(p) or 10.0
    tmp = p + ".tmp.mp3"
    for kbps in (96, 64, 40, 24):
        encode_mp3(p, tmp, kbps)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0 and os.path.getsize(tmp) <= LIMIT:
            os.replace(tmp, p)
            return os.path.getsize(p)
    if os.path.exists(tmp):
        os.replace(tmp, p)
    return os.path.getsize(p)


def main():
    targets = find_targets()
    print("対象: %d件" % len(targets))
    ok, ng = 0, []
    for p in targets:
        before = os.path.getsize(p)
        try:
            if p.lower().endswith(".mp3"):
                after = shrink_mp3(p)
            else:
                after = shrink_video(p)
            status = "OK" if after <= LIMIT else "残"
            if after <= LIMIT:
                ok += 1
            else:
                ng.append((p, after))
            print("%s %9d -> %9d  %s" % (status, before, after, os.path.relpath(p, REPO)))
        except Exception as e:
            ng.append((p, str(e)))
            print("失敗", p, e)
    print("完了: %d/%d件がLIMIT以下に。残り%d件" % (ok, len(targets), len(ng)))
    for p, a in ng:
        print("  残:", p, a)


if __name__ == "__main__":
    sys.exit(main())
