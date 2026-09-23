#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""919番 手順1: ZEN 2枚（茶室・黒砂海岸）を16:9へ横伸ばし(outpaint)する。
751番(_751_step1_widen.py)と同じモデル・同じ地雷回避方針を踏襲する。
fal-ai/nano-banana/edit / $0.0398枚。"""
import os, sys, json, time, base64, urllib.request, urllib.error

# ★1034番【予算の栓】fal は1本が高い（動画1本30円・画像1枚6円／status/fal_cost_ledger.json）。
#   この使い捨ての口も、走り出す前に必ず栓を通す。上限0円なら1回も叩けない。
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__))))
try:
    import yosan as _yosan
    _ok, _why = _yosan.mitsumori("fal", 30.0, "%s を走らせる" % _os.path.basename(__file__))
    if not _ok:
        print(_why)
        raise SystemExit(1)
except ImportError as _e:
    print("予算の栓（tools/yosan.py）が読めませんでした: %s。お金の話なので止めます。" % _e)
    raise SystemExit(1)


KEY_PATH = os.path.expanduser("~/.fal_key")
with open(KEY_PATH) as f:
    FAL_KEY = f.read().strip()

SRC_DIR = "/Users/mac/Documents/AI作業/素材/ZEN_2026-09-17"
OUT_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/919-zen"
os.makedirs(OUT_DIR, exist_ok=True)

MODEL = "fal-ai/nano-banana/edit"

TARGETS = {
    "chashitsu": {
        "src": os.path.join(SRC_DIR, "18_ZEN_chashitsu.png"),
        "out": os.path.join(OUT_DIR, "chashitsu_16x9.png"),
        "prompt": (
            "Extend this photo horizontally to a 16:9 widescreen aspect ratio by adding more of the same "
            "tea room scenery ONLY on the left and right sides of the image, continuing the same tatami "
            "floor, walls, and room naturally outward. Do NOT crop or remove any part of the top or bottom "
            "of the original image — the full original vertical content must remain exactly as-is, centered "
            "in the frame, unchanged in size and position. Keep the round window, the stacked stone object, "
            "the cherry blossom branch, the floor shadows, and all lighting and colors exactly as they are, "
            "unchanged. Do NOT add any new objects, people, windows, or light sources in the newly generated "
            "area. Seamlessly blend the newly added left and right areas with matching tatami texture, wall "
            "material, and the same soft natural lighting so the extension is invisible."
        ),
    },
    "kuroihama": {
        "src": os.path.join(SRC_DIR, "22_ZEN_kuroihama.png"),
        "out": os.path.join(OUT_DIR, "kuroihama_16x9.png"),
        "prompt": (
            "Extend this photo horizontally to a 16:9 widescreen aspect ratio by adding more of the same "
            "black sand beach scenery ONLY on the left and right sides of the image, continuing the same "
            "black sand, waves, and cloudy sky naturally outward. Do NOT crop or remove any part of the top "
            "or bottom of the original image — the full original vertical content must remain exactly as-is, "
            "centered in the frame, unchanged in size and position. Keep the stacked stone object and the "
            "rock formations exactly as they are, unchanged in size, position, and shape. Do NOT add any new "
            "objects, people, or light sources in the newly generated area. Seamlessly blend the newly added "
            "left and right areas with matching black sand texture, wave patterns, and the same overcast sky "
            "color palette so the extension is invisible."
        ),
    },
}


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


def widen_one(name, cfg):
    uri = data_uri_for(cfg["src"])
    payload = {
        "prompt": cfg["prompt"],
        "image_urls": [uri],
        "aspect_ratio": "16:9",
        "num_images": 1,
    }
    print(f"--- {name}: submit ---")
    try:
        r = post(f"https://queue.fal.run/{MODEL}", payload)
    except urllib.error.HTTPError as e:
        print(f"SUBMIT_FAIL: HTTP {e.code} {e.read().decode('utf-8')[:800]}")
        return {"ok": False, "error": "submit_fail"}
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
                return {"ok": False, "error": "no_image"}
            img = imgs[0]
            img_url = img.get("url")
            download(img_url, cfg["out"])
            print(f"{name}: DONE -> {cfg['out']} size={img.get('width')}x{img.get('height')} url={img_url}")
            with open(cfg["out"] + ".json", "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return {"ok": True, "path": cfg["out"], "url": img_url,
                    "width": img.get("width"), "height": img.get("height")}
        elif st in ("FAILED", "ERROR"):
            print(f"{name}: FAILED:", s)
            return {"ok": False, "error": str(s)}
        time.sleep(4)
    print(f"{name}: TIMEOUT")
    return {"ok": False, "error": "timeout"}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    results = {}
    for name, cfg in TARGETS.items():
        if which != "all" and which != name:
            continue
        results[name] = widen_one(name, cfg)
    with open(os.path.join(OUT_DIR, "_step1_results.json"), "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
