#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""783番: 読み聞かせ絵本・声3種類の聞き比べ用音声を生成する（桃太郎の冒頭・寝かしつけ用）。
上限20円承認済み（実際の見積もり合計は約4.4円）。
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

TEXT = (
    "むかしむかし、あるところに、おじいさんとおばあさんが住んでいました。\n"
    "おじいさんは山へしばかりに、おばあさんは川へせんたくに行きました。\n"
    "おばあさんが川でせんたくをしていると、どんぶらこ、どんぶらこと、\n"
    "大きな桃がながれてきました。"
)

JOBS = [
    {
        "name": "minimax_speech02hd",
        "label": "MiniMax Speech-02 HD (Wise_Woman・寝かしつけ調整)",
        "model": "fal-ai/minimax/speech-02-hd",
        "payload": {
            "text": TEXT,
            "voice_setting": {
                "voice_id": "Wise_Woman",
                "speed": 0.85,
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
        "name": "elevenlabs_eleven_v3",
        "label": "ElevenLabs eleven-v3 (Matilda・stability高め)",
        "model": "fal-ai/elevenlabs/tts/eleven-v3",
        "payload": {
            "text": TEXT,
            "voice": "Matilda",
            "stability": 0.75,
            "language_code": "ja",
            "apply_text_normalization": "auto",
        },
        "unit": "$0.10/1000文字",
        "unit_cost_usd_per_1k": 0.10,
    },
    {
        "name": "qwen_audio3_tts",
        "label": "Qwen Audio 3.0 TTS Flash (Cherry)",
        "model": "alibaba/qwen-audio-3-tts",
        "payload": {
            "text": TEXT,
            "voice": "Cherry",
            "language": "Japanese",
        },
        "unit": "$0.05/1000文字",
        "unit_cost_usd_per_1k": 0.05,
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
    with open(os.path.join(OUT_DIR, "results.json"), "w") as f:
        json.dump({"text": TEXT, "text_len": len(TEXT), "results": results}, f, ensure_ascii=False, indent=2)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
