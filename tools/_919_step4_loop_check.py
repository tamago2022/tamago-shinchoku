#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""919番 手順4: ループ検証を機械でやる（751番と同じ手法）。
- 最初のフレームと最後のフレームのRGB差(RMSE, 160x90に縮小)。継ぎ目の指標。
- 「往復度」= 前半を逆再生したフレーム列と後半のフレーム列を比較したRMSE。
  751番の実測(1.16/0.92/1.07)は「前半を逆再生して尻に繋いだだけ」だったケース。
  値が小さいほど逆再生でごまかしている疑いが強い。大きければ本物の前進ループの可能性が高い。
"""
import cv2, numpy as np, sys, json

def load_frames(path, size=(160, 90)):
    cap = cv2.VideoCapture(path)
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        small = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
        frames.append(small.astype(np.float32))
    cap.release()
    return frames

def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))

def analyze(path):
    frames = load_frames(path)
    n = len(frames)
    if n < 4:
        return {"path": path, "error": "too_few_frames", "n": n}
    first_last = rmse(frames[0], frames[-1])
    half = n // 2
    first_half = frames[:half]
    second_half = frames[n - half:]
    reversed_first_half = list(reversed(first_half))
    diffs = [rmse(a, b) for a, b in zip(reversed_first_half, second_half)]
    reversal_score = float(np.mean(diffs))
    return {
        "path": path,
        "n_frames": n,
        "first_last_rmse": round(first_last, 3),
        "reversal_score": round(reversal_score, 3),
    }

if __name__ == "__main__":
    results = [analyze(p) for p in sys.argv[1:]]
    print(json.dumps(results, ensure_ascii=False, indent=2))
