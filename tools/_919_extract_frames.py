#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""919番: ゲート2(成果物検品)用に、動画から最初・中間・最後のフレームをPNGで抜き出す。"""
import cv2, sys, os

def extract(path, out_prefix):
    cap = cv2.VideoCapture(path)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    idxs = {"first": 0, "mid": n // 2, "last": n - 1}
    outs = {}
    for label, idx in idxs.items():
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        out_path = f"{out_prefix}_{label}.png"
        cv2.imwrite(out_path, frame)
        outs[label] = out_path
    cap.release()
    return outs

if __name__ == "__main__":
    src = sys.argv[1]
    prefix = sys.argv[2]
    print(extract(src, prefix))
