#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""751番 手順1: ZENうんこ「干潟巨大モノリス」を16:9へ横伸ばし(outpaint)する。
fal-ai/nano-banana/edit を使用。上下は絶対に切らない・人物/太陽/モノリスの位置は変えない。
3モデル共通の元絵になるので1回だけ実行。"""
import os, json, time, base64, urllib.request, urllib.error

KEY_PATH = os.path.expanduser("~/.fal_key")
with open(KEY_PATH) as f:
    FAL_KEY = f.read().strip()

SRC = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/751-zen-beach/source_11_干潟巨大モノリス.png"
OUT_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/751-zen-beach"
os.makedirs(OUT_DIR, exist_ok=True)

MODEL = "fal-ai/nano-banana/edit"

PROMPT = (
    "Extend this photo horizontally to a 16:9 widescreen aspect ratio by adding more of the same "
    "tidal flat beach scenery ONLY on the right side of the image. Do NOT crop or remove any part of the top "
    "or bottom of the original image. Keep the giant stone monolith stack, the standing person, the sun, "
    "the misty sky, and the wet sand reflections exactly as they are, unchanged in size and position, in "
    "the same place as the original (do not recenter them). There must be exactly ONE sun in the entire "
    "image, in its original position near the left side — absolutely do NOT add a second sun or any "
    "duplicate light source anywhere in the newly generated area. Seamlessly blend the newly added right "
    "side area with matching wet sand, tide pools, soft mist, distant sea stacks, and the same warm sunset "
    "color palette so the extension is invisible."
)


def data_uri_for(path):
    with open(path, "rb") as f:
        b = f.read()
    b64 = base64.b64encode(b).decode("ascii")
    return f"data:image/png;base64,{b64}"


def post(url, payload):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
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
    uri = data_uri_for(SRC)
    payload = {
        "prompt": PROMPT,
        "image_urls": [uri],
        "aspect_ratio": "16:9",
        "num_images": 1,
    }
    try:
        r = post(f"https://queue.fal.run/{MODEL}", payload)
    except urllib.error.HTTPError as e:
        print(f"SUBMIT_FAIL: HTTP {e.code} {e.read().decode('utf-8')[:800]}")
        return
    print("submitted:", r.get("status"))
    status_url = r.get("status_url")
    response_url = r.get("response_url")
    start = time.time()
    while time.time() - start < 180:
        s = get(status_url)
        st = s.get("status")
        if st == "COMPLETED":
            data = get(response_url)
            imgs = data.get("images") or []
            if not imgs:
                print("NO_IMAGE:", json.dumps(data)[:800])
                return
            img = imgs[0]
            img_url = img.get("url")
            out_path = os.path.join(OUT_DIR, "16x9_widened_v2.png")
            download(img_url, out_path)
            print("DONE ->", out_path)
            print("size:", img.get("width"), img.get("height"))
            print("url:", img_url)
            with open(os.path.join(OUT_DIR, "_step1_result_v2.json"), "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return
        elif st in ("FAILED", "ERROR"):
            print("FAILED:", s)
            return
        time.sleep(3)
    print("TIMEOUT")


if __name__ == "__main__":
    main()
