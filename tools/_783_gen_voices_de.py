#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""783番 追加分: 読み聞かせ絵本の声D(渋い男性)・E(女の子)を1.0倍速で生成する。
既存A/B/Cと全く同じ桃太郎の冒頭116文字を使う（1文字も変えない）。
予算10円・上限20円承認済み（見積もり: 2本×1.74円=3.48円）。
"""
import json
import os
import time
import urllib.request

KEY_PATH = os.path.expanduser("~/.fal_key")
with open(KEY_PATH) as f:
    FAL_KEY = f.read().strip()

OUT_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/783-ehon-voice-compare"
os.makedirs(OUT_DIR, exist_ok=True)

# 既存783番と1文字も変えない台本
TEXT = (
    "むかしむかし、あるところに、おじいさんとおばあさんが住んでいました。\n"
    "おじいさんは山へしばかりに、おばあさんは川へせんたくに行きました。\n"
    "おばあさんが川でせんたくをしていると、どんぶらこ、どんぶらこと、\n"
    "大きな桃がながれてきました。"
)

JOBS = [
    {
        "name": "minimax_deep_voice_man",
        "label": "D：MiniMax Speech-02 HD（Deep_Voice_Man・渋い男性・1.0倍）",
        "model": "fal-ai/minimax/speech-02-hd",
        "payload": {
            "text": TEXT,
            "voice_setting": {
                "voice_id": "Deep_Voice_Man",
                "speed": 1.0,
                "vol": 1,
                "pitch": 0,
                "emotion": "neutral",
            },
            "language_boost": "Japanese",
            "output_format": "url",
        },
        "unit": "$0.10/1000文字",
        "unit_cost_usd_per_1k": 0.10,
    },
    {
        "name": "minimax_sweet_girl2",
        "label": "E：MiniMax Speech-02 HD（Sweet_Girl_2・女の子・1.0倍）",
        "model": "fal-ai/minimax/speech-02-hd",
        "payload": {
            "text": TEXT,
            "voice_setting": {
                "voice_id": "Sweet_Girl_2",
                "speed": 1.0,
                "vol": 1,
                "pitch": 0,
                "emotion": "neutral",
            },
            "language_boost": "Japanese",
            "output_format": "url",
        },
        "unit": "$0.10/1000文字",
        "unit_cost_usd_per_1k": 0.10,
    },
]


def post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Key {FAL_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download(url, path):
    req = urllib.request.Request(url, headers={"Authorization": f"Key {FAL_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        with open(path, "wb") as f:
            f.write(resp.read())


def run_job(job):
    print(f"=== {job['name']} ({job['model']}) ===")
    r = post(f"https://queue.fal.run/{job['model']}", job["payload"])
    status_url = r.get("status_url")
    response_url = r.get("response_url")
    if not status_url:
        print("SUBMIT_FAIL", r)
        return {"name": job["name"], "ok": False, "error": str(r)}
    start = time.time()
    while time.time() - start < 120:
        s = get(status_url)
        st = s.get("status")
        if st == "COMPLETED":
            data = get(response_url)
            audio = data.get("audio") or {}
            url = audio.get("url")
            if url:
                ext = ".mp3" if "mp3" in (audio.get("content_type") or "mp3") or url.endswith(".mp3") else os.path.splitext(url)[1] or ".mp3"
                out_path = os.path.join(OUT_DIR, f"{job['name']}{ext}")
                download(url, out_path)
                dur = data.get("duration_ms") or (audio.get("duration") and audio["duration"] * 1000)
                print("DONE ->", out_path, "duration_ms=", dur)
                return {
                    "name": job["name"], "label": job["label"], "model": job["model"],
                    "ok": True, "out_path": out_path, "duration_ms": dur,
                    "source_url": url, "unit": job["unit"],
                }
            print("NO_AUDIO_URL", data)
            return {"name": job["name"], "ok": False, "error": "no audio url", "raw": data}
        if st in ("FAILED", "ERROR"):
            print("FAILED", s)
            return {"name": job["name"], "ok": False, "error": str(s)}
        time.sleep(3)
    print("TIMEOUT")
    return {"name": job["name"], "ok": False, "error": "timeout"}


def main():
    print("文字数:", len(TEXT))
    results = []
    for job in JOBS:
        results.append(run_job(job))
    out_json = os.path.join(OUT_DIR, "results_de.json")
    with open(out_json, "w") as f:
        json.dump({"text": TEXT, "text_len": len(TEXT), "results": results}, f, ensure_ascii=False, indent=2)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
