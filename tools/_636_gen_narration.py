#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""636番: 日本の風景60秒動画の英語ナレーションをfal(ElevenLabs eleven-v3)で1本生成する。"""
import os, json, time, urllib.request, urllib.error

KEY_PATH = os.path.expanduser("~/.fal_key")
with open(KEY_PATH) as f:
    FAL_KEY = f.read().strip()

OUT_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/636-japan-60sec/audio"
os.makedirs(OUT_DIR, exist_ok=True)

MODEL = "fal-ai/elevenlabs/tts/eleven-v3"

SCRIPT = (
    "Mount Fuji last erupted in 1707. For three centuries now, it has simply watched. "
    "Each gate here was given by someone, one at a time, for centuries. "
    "Up to three thousand people cross this street at once, and almost no one collides. "
    "This bamboo grove has been tended by local farmers, by hand, for generations. "
    "This pavilion burned down in 1950. Five years later, it rose again in gold. "
    "At high tide, this gate seems to float. It has stood here since the eleven hundreds. "
    "These monkeys began soaking here in the 1960s, and the photos reached the whole world. "
    "These roofs were shaped to shed heavy snow. Some have stood for over a century. "
    "Over a thousand wild deer roam free here, long seen as messengers of the gods. "
    "Built in 1958, it stands a little taller than the tower in Paris that first inspired it. "
    "Farmers once grew lavender here for its oil. Now the fields themselves are why people come. "
    "Every country holds views like these, quietly waiting to be noticed. "
    "This one happens to be ours. We would love to see yours, too."
)


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


def main():
    print("文字数:", len(SCRIPT))
    r = post(f"https://queue.fal.run/{MODEL}", {"text": SCRIPT})
    print("submitted:", r.get("status"))
    status_url = r.get("status_url")
    start = time.time()
    while time.time() - start < 180:
        s = get(status_url)
        if s.get("status") == "COMPLETED":
            data = get(r.get("response_url"))
            print(json.dumps(data, ensure_ascii=False)[:500])
            audio = data.get("audio") or {}
            url = audio.get("url")
            if url:
                out_path = os.path.join(OUT_DIR, "narration_en.mp3")
                download(url, out_path)
                print("DONE ->", out_path)
            else:
                print("NO_AUDIO_URL", data)
            return
        elif s.get("status") in ("FAILED", "ERROR"):
            print("FAILED", s)
            return
        time.sleep(3)
    print("TIMEOUT")


if __name__ == "__main__":
    main()
