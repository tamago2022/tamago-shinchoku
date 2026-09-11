#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""771番: ltx-2.5 fast で「もやが一方向に流れ続け、戻らない」海辺を1本だけ生成する。
元絵は751番と同じ 16x9_widened_v2.png を再利用(作り直さない)。
レスポンスヘッダー・本文を全部記録し、実費を示す手がかりが無いか確認する。"""
import os, json, time, base64, urllib.request, urllib.error, datetime

KEY_PATH = os.path.expanduser("~/.fal_key")
with open(KEY_PATH) as f:
    FAL_KEY = f.read().strip()

SRC = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/751-zen-beach/16x9_widened_v2.png"
OUT_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/771-zen-beach-loop"
os.makedirs(OUT_DIR, exist_ok=True)

MODEL = "lightricks/ltx-2.5/image-to-video/fast"

MOTION_PROMPT = (
    "Static locked-off camera, absolutely no zoom, no pan, no camera movement whatsoever, the framing "
    "never changes. Thin mist drifts continuously and steadily in ONE direction only, slowly from left to "
    "right across the horizon and around the distant sea stacks -- the mist must never reverse direction, "
    "never drift backward, it only keeps moving forward the entire time, like a slow steady breeze. Far in "
    "the background, gentle waves roll in slowly with soft rolling motion; the water near the shore and in "
    "the foreground stays calm and almost still, no foreground wave motion, no glossy or artificial looking "
    "water. The standing person remains almost completely still, only an extremely subtle natural body sway "
    "from breathing, no walking, no gestures. The sun and the giant stone monolith stack remain completely "
    "still and unchanged, exact same position and size throughout. The first frame and the last frame of "
    "this video should look nearly identical to each other, so the clip can loop seamlessly with a "
    "crossfade. Calm, quiet, extremely slow and subtle ambient motion throughout, nothing sudden."
)


def data_uri():
    with open(SRC, "rb") as f:
        b = f.read()
    return "data:image/png;base64," + base64.b64encode(b).decode("ascii")


def post(url, payload):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8")), dict(resp.getheaders())


def get(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Key {FAL_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8")), dict(resp.getheaders())


def download(url, path):
    req = urllib.request.Request(url, headers={"Authorization": f"Key {FAL_KEY}"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(path, "wb") as f:
            f.write(resp.read())


def main():
    t0 = datetime.datetime.now().isoformat()
    uri = data_uri()
    payload = {"image_url": uri, "prompt": MOTION_PROMPT}
    print("=== SUBMIT", t0, MODEL, "===")
    try:
        r, submit_headers = post(f"https://queue.fal.run/{MODEL}", payload)
    except urllib.error.HTTPError as e:
        print("SUBMIT_FAIL:", e.code, e.read().decode("utf-8")[:800])
        return
    print("submitted:", r.get("status"))
    status_url = r.get("status_url")
    response_url = r.get("response_url")
    start = time.time()
    all_headers_seen = {"submit": submit_headers}
    while time.time() - start < 600:
        try:
            s, status_headers = get(status_url)
        except Exception as e:
            print("STATUS_ERR:", e)
            time.sleep(5)
            continue
        st = s.get("status")
        if st == "COMPLETED":
            data, response_headers = get(response_url)
            all_headers_seen["status_final"] = status_headers
            all_headers_seen["response"] = response_headers
            vid = data.get("video") or {}
            vid_url = vid.get("url")
            t1 = datetime.datetime.now().isoformat()
            if not vid_url:
                print("NO_VIDEO:", json.dumps(data)[:800])
                return
            out_path = os.path.join(OUT_DIR, "video_ltx_fast_771.mp4")
            download(vid_url, out_path)
            print("DONE ->", out_path, "url:", vid_url)
            result = {
                "n": 771, "model": MODEL, "started_at": t0, "completed_at": t1,
                "video": vid, "video_url": vid_url, "local_path": out_path,
                "headers": all_headers_seen, "raw_response": data,
            }
            with open(os.path.join(OUT_DIR, "_771_result.json"), "w") as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)
            print(json.dumps({"duration": vid.get("duration"), "width": vid.get("width"),
                               "height": vid.get("height"), "file_size": vid.get("file_size")},
                              ensure_ascii=False))
            return
        elif st in ("FAILED", "ERROR"):
            print("FAILED:", s)
            return
        time.sleep(5)
    print("TIMEOUT")


if __name__ == "__main__":
    main()
