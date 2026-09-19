#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""919番 手順3補正: fal出力が1890x1080(1080pだが横が1920に30px足りない)だったため、
無料でできる単純リサイズ(cv2)で1920x1080ちょうどに揃える。追加課金なし。
引き伸ばし率は横方向のみ1920/1890=1.0159倍(見た目にはほぼ気づかないレベル)。"""
import cv2, sys, os

SRC_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/919-zen"
FILES = ["chashitsu_loop.mp4", "kuroihama_loop.mp4"]

for fn in FILES:
    src = os.path.join(SRC_DIR, fn)
    dst = os.path.join(SRC_DIR, fn.replace(".mp4", "_1920x1080.mp4"))
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(dst, fourcc, fps, (1920, 1080))
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        resized = cv2.resize(frame, (1920, 1080), interpolation=cv2.INTER_LANCZOS4)
        out.write(resized)
        n += 1
    cap.release()
    out.release()
    print(f"{fn}: {n} frames -> {dst}")
