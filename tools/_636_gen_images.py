#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""636番: 日本の風景60秒動画・素材となる12枚の風景画像をfal(nano-banana)で生成する。
queueに12件まとめて投げてから並行でpollingすることで待ち時間を短縮する。"""
import os, json, time, urllib.request, urllib.error

KEY_PATH = os.path.expanduser("~/.fal_key")
with open(KEY_PATH) as f:
    FAL_KEY = f.read().strip()

OUT_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/636-japan-60sec/img"
os.makedirs(OUT_DIR, exist_ok=True)

MODEL = "fal-ai/nano-banana"

SCENES = [
    ("01_fuji", "Photorealistic wide landscape photo of Mount Fuji at sunrise, snow-capped peak, calm lake reflection in foreground, soft pink and gold sky, no people, cinematic quiet mood, 16:9 aspect ratio"),
    ("02_fushimi", "Photorealistic photo inside the vermilion torii gate tunnel of Fushimi Inari Shrine Kyoto, thousands of red gates receding into the distance, soft morning light, empty path, no people, 16:9 aspect ratio"),
    ("03_shibuya", "Photorealistic photo of Shibuya Crossing Tokyo at dusk, neon signs glowing, motion blur of countless pedestrians crossing, wet street reflections, cinematic, 16:9 aspect ratio"),
    ("04_arashiyama", "Photorealistic photo of Arashiyama Bamboo Grove Kyoto, towering green bamboo stalks on both sides of a narrow path, soft filtered sunlight, empty path, 16:9 aspect ratio"),
    ("05_kinkakuji", "Photorealistic photo of Kinkaku-ji golden pavilion Kyoto reflected perfectly in a still pond, surrounded by autumn trees, clear sky, no people, 16:9 aspect ratio"),
    ("06_miyajima", "Photorealistic photo of the floating red torii gate of Itsukushima Shrine Miyajima at high tide, calm sea, soft evening light, no people nearby, 16:9 aspect ratio"),
    ("07_jigokudani", "Photorealistic photo of Japanese snow monkeys relaxing in a steaming hot spring at Jigokudani Monkey Park, snow falling gently, misty atmosphere, 16:9 aspect ratio"),
    ("08_shirakawago", "Photorealistic photo of Shirakawa-go traditional steep thatched-roof gassho-zukuri houses covered in snow at dusk, warm lights glowing from windows, 16:9 aspect ratio"),
    ("09_nara", "Photorealistic photo of wild sika deer resting peacefully in Nara Park among orange autumn maple leaves, soft afternoon light, no people, 16:9 aspect ratio"),
    ("10_tokyotower", "Photorealistic photo of Tokyo Tower glowing orange at dusk, seen from a quiet rooftop, city lights sparkling below, clear sky, 16:9 aspect ratio"),
    ("11_furano", "Photorealistic photo of endless lavender fields in Furano Hokkaido under a blue sky with soft clouds, rolling hills, no people, 16:9 aspect ratio"),
    ("12_okinawa", "Photorealistic photo of a turquoise coral reef beach in Okinawa, clear shallow water over white sand, gentle waves, tropical calm, no people, 16:9 aspect ratio"),
]


def post(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
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
    jobs = {}
    for name, prompt in SCENES:
        try:
            r = post(f"https://queue.fal.run/{MODEL}", {
                "prompt": prompt,
                "aspect_ratio": "16:9",
            })
            jobs[name] = r
            print(f"submitted {name}: {r.get('status')}")
        except Exception as e:
            print(f"SUBMIT_FAIL {name}: {e}")
        time.sleep(0.5)

    results = {}
    pending = set(jobs.keys())
    start = time.time()
    while pending and time.time() - start < 600:
        for name in list(pending):
            r = jobs[name]
            status_url = r.get("status_url")
            if not status_url:
                pending.discard(name)
                continue
            try:
                s = get(status_url)
            except Exception as e:
                print(f"STATUS_ERR {name}: {e}")
                continue
            if s.get("status") == "COMPLETED":
                resp_url = r.get("response_url")
                data = get(resp_url)
                img = (data.get("images") or [{}])[0]
                img_url = img.get("url")
                if img_url:
                    out_path = os.path.join(OUT_DIR, f"{name}.jpg")
                    download(img_url, out_path)
                    results[name] = {"ok": True, "path": out_path, "url": img_url, "width": img.get("width"), "height": img.get("height")}
                    print(f"DONE {name} -> {out_path}")
                else:
                    results[name] = {"ok": False, "error": "no image url", "raw": data}
                    print(f"NO_IMAGE {name}: {data}")
                pending.discard(name)
            elif s.get("status") in ("FAILED", "ERROR"):
                results[name] = {"ok": False, "error": s}
                print(f"FAILED {name}: {s}")
                pending.discard(name)
        if pending:
            time.sleep(4)

    for name in pending:
        results[name] = {"ok": False, "error": "timeout"}

    with open(os.path.join(OUT_DIR, "_results.json"), "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    ok_count = sum(1 for v in results.values() if v.get("ok"))
    print(f"\n合計 {ok_count}/{len(SCENES)} 枚成功")


if __name__ == "__main__":
    main()
