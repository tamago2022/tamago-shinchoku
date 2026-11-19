#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""動画に英語ラジオDJ型の字幕を焼き込み、縦1080x1920・無音のmp4にする（TikTok用）。
使い方: python3 tools/tiktok_caption.py <入力動画> <出力mp4> [<字幕フレームpng>]
音は消す（音源はTikTok側で付ける）。字幕は動画の長さを均等割りで切り替え。"""
import os, re, subprocess, sys, tempfile

FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
LINES = [
    "FROM JAPAN\nTODAY'S CITY POP",
    "MARIYA TAKEUCHI\n— PLASTIC LOVE (1984)",
    "One of Japan's\nmost beloved singer-songwriters",
    "Decades later,\nit went viral worldwide",
    "FULL SONG + MORE\n→ JOY RELIEF STATION",
]


def duration(p):
    r = subprocess.run(["ffmpeg", "-i", p], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


def main(src, dst, png=None):
    d = duration(src)
    seg = d / len(LINES)
    tmp = tempfile.mkdtemp()
    vf = ["scale=1080:1920:force_original_aspect_ratio=increase", "crop=1080:1920", "setsar=1"]
    for i, t in enumerate(LINES):
        f = os.path.join(tmp, "t%d.txt" % i)
        open(f, "w", encoding="utf-8").write(t)
        vf.append("drawtext=fontfile='%s':textfile='%s':fontsize=64:fontcolor=white:"
                  "shadowcolor=black@0.55:shadowx=3:shadowy=3:line_spacing=14:text_align=center:"
                  "x=(w-text_w)/2:y=h*0.70:enable='between(t,%.3f,%.3f)'" % (FONT, f, i * seg, (i + 1) * seg - 0.001))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-an", "-vf", ",".join(vf),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart", dst], check=True)
    if png:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.2f" % (seg * 1.5), "-i", dst,
                        "-frames:v", "1", png], check=True)
    r = subprocess.run(["ffmpeg", "-i", dst], capture_output=True, text=True).stderr
    print("duration %.2fs" % duration(dst), re.findall(r"\d{3,4}x\d{3,4}", r)[:1], "audio:", "Audio" in r)


if __name__ == "__main__":
    main(*sys.argv[1:4])
