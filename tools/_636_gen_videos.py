#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""636番: 12枚の静止画をfal(bytedance/seedance-2.0/mini/image-to-video)で
ごく微かに動く5秒動画に変換する。画像はbase64データURIで直接渡す(アップロード手順を省略)。"""
import os, json, time, base64, urllib.request, urllib.error

KEY_PATH = os.path.expanduser("~/.fal_key")
with open(KEY_PATH) as f:
    FAL_KEY = f.read().strip()

IMG_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/636-japan-60sec/img"
OUT_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/636-japan-60sec/video"
os.makedirs(OUT_DIR, exist_ok=True)

MODEL = "bytedance/seedance-2.0/mini/image-to-video"

MOTIONS = {
    "01_fuji": "extremely subtle drift of morning mist over the lake, gentle water ripple, static camera, calm",
    "02_fushimi": "very slow subtle camera drift forward through the torii gates, soft light flicker, calm",
    "03_shibuya": "motion blur of pedestrians walking, neon signs subtly flickering, static camera, busy but calm mood",
    "04_arashiyama": "bamboo stalks swaying gently in a light breeze, dappled light shifting softly, static camera",
    "05_kinkakuji": "very subtle ripple on the pond surface reflecting the pavilion, leaves gently trembling, static camera",
    "06_miyajima": "calm sea water gently lapping around the torii gate base, soft light shimmer, static camera",
    "07_jigokudani": "steam rising slowly from the hot spring, snow falling gently, monkeys breathing calmly, static camera",
    "08_shirakawago": "snow falling softly, warm window light flickering gently, static camera, quiet evening",
    "09_nara": "deer breathing calmly, a few leaves drifting down slowly, static camera, peaceful",
    "10_tokyotower": "city lights twinkling subtly, very slight haze drifting, static camera, calm dusk",
    "11_furano": "lavender fields swaying very gently in the wind, soft clouds drifting slowly, static camera",
    "12_okinawa": "gentle waves lapping the shore, sunlight sparkling softly on the water, static camera, tropical calm",
}

ORDER = ["01_fuji","02_fushimi","03_shibuya","04_arashiyama","05_kinkakuji","06_miyajima",
         "07_jigokudani","08_shirakawago","09_nara","10_tokyotower","11_furano","12_okinawa"]


def data_uri_for(path):
    ext = "jpeg"
    with open(path, "rb") as f:
        b = f.read()
    b64 = base64.b64encode(b).decode("ascii")
    return f"data:image/{ext};base64,{b64}"


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
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(path, "wb") as f:
            f.write(resp.read())


def main():
    jobs = {}
    for name in ORDER:
        img_path = os.path.join(IMG_DIR, f"{name}.jpg")
        if not os.path.exists(img_path):
            print(f"SKIP {name}: 元画像なし")
            continue
        uri = data_uri_for(img_path)
        payload = {
            "image_url": uri,
            "prompt": MOTIONS[name],
            "duration": "5",
        }
        try:
            r = post(f"https://queue.fal.run/{MODEL}", payload)
            jobs[name] = r
            print(f"submitted {name}: {r.get('status')}")
        except urllib.error.HTTPError as e:
            print(f"SUBMIT_FAIL {name}: HTTP {e.code} {e.read().decode('utf-8')[:300]}")
        except Exception as e:
            print(f"SUBMIT_FAIL {name}: {e}")
        time.sleep(0.8)

    results = {}
    pending = set(jobs.keys())
    start = time.time()
    while pending and time.time() - start < 900:
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
            st = s.get("status")
            if st == "COMPLETED":
                try:
                    data = get(r.get("response_url"))
                    vid = data.get("video") or {}
                    vid_url = vid.get("url")
                    if vid_url:
                        out_path = os.path.join(OUT_DIR, f"{name}.mp4")
                        download(vid_url, out_path)
                        results[name] = {"ok": True, "path": out_path, "url": vid_url}
                        print(f"DONE {name} -> {out_path}")
                    else:
                        results[name] = {"ok": False, "error": "no video url", "raw": data}
                        print(f"NO_VIDEO {name}: {json.dumps(data)[:300]}")
                except Exception as e:
                    results[name] = {"ok": False, "error": str(e)}
                    print(f"FETCH_ERR {name}: {e}")
                pending.discard(name)
            elif st in ("FAILED", "ERROR"):
                results[name] = {"ok": False, "error": s}
                print(f"FAILED {name}: {s}")
                pending.discard(name)
            else:
                pass
        if pending:
            time.sleep(6)

    for name in pending:
        results[name] = {"ok": False, "error": "timeout"}
        print(f"TIMEOUT {name}")

    with open(os.path.join(OUT_DIR, "_results.json"), "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    ok_count = sum(1 for v in results.values() if v.get("ok"))
    print(f"\n合計 {ok_count}/{len(ORDER)} 本成功")


if __name__ == "__main__":
    main()
