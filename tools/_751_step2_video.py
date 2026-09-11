#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""751番 手順2: 16x9_widened_v2.png を3モデルで「微かに動く」動画にする。
3本とも同じ動きプロンプトを使う(公平な比較のため)。1モデルずつ実行して確認する。"""
import os, sys, json, time, base64, urllib.request, urllib.error

KEY_PATH = os.path.expanduser("~/.fal_key")
with open(KEY_PATH) as f:
    FAL_KEY = f.read().strip()

SRC = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/751-zen-beach/16x9_widened_v2.png"
OUT_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/751-zen-beach"
os.makedirs(OUT_DIR, exist_ok=True)

MOTION_PROMPT = (
    "Extremely subtle, gentle ambient motion only: thin mist drifts very slowly across the horizon and "
    "around the distant sea stacks, the wet sand and shallow tide water surface ripples very slightly, "
    "faintly reflecting the warm sunset light. The standing person, the sun, and the giant stone monolith "
    "stack remain completely still and unchanged. Static locked-off camera, absolutely no zoom, no pan, no "
    "camera movement. The landscape is barely breathing, extremely slow and subtle, calm and quiet."
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


def run(model, out_name, extra_payload=None, image_field="image_url"):
    uri = data_uri()
    payload = {image_field: uri, "prompt": MOTION_PROMPT}
    if extra_payload:
        payload.update(extra_payload)
    print(f"--- {model} ---")
    try:
        r = post(f"https://queue.fal.run/{model}", payload)
    except urllib.error.HTTPError as e:
        print(f"SUBMIT_FAIL: HTTP {e.code} {e.read().decode('utf-8')[:800]}")
        return {"ok": False, "error": "submit_fail"}
    print("submitted:", r.get("status"))
    status_url = r.get("status_url")
    response_url = r.get("response_url")
    start = time.time()
    while time.time() - start < 600:
        try:
            s = get(status_url)
        except Exception as e:
            print("STATUS_ERR:", e)
            time.sleep(5)
            continue
        st = s.get("status")
        if st == "COMPLETED":
            data = get(response_url)
            vid = data.get("video") or {}
            vid_url = vid.get("url")
            if not vid_url:
                print("NO_VIDEO:", json.dumps(data)[:800])
                return {"ok": False, "error": "no_video", "raw": data}
            out_path = os.path.join(OUT_DIR, out_name)
            download(vid_url, out_path)
            print("DONE ->", out_path, "url:", vid_url)
            return {"ok": True, "path": out_path, "url": vid_url, "raw": data}
        elif st in ("FAILED", "ERROR"):
            print("FAILED:", s)
            return {"ok": False, "error": s}
        time.sleep(5)
    print("TIMEOUT")
    return {"ok": False, "error": "timeout"}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    results = {}
    if which in ("all", "ltx-fast"):
        results["ltx-fast"] = run("lightricks/ltx-2.5/image-to-video/fast", "video_ltx_fast.mp4")
    if which in ("all", "ltx-distilled"):
        results["ltx-distilled"] = run("fal-ai/ltx-video-13b-distilled/image-to-video", "video_ltx_distilled.mp4")
    if which in ("all", "seedance"):
        results["seedance"] = run("bytedance/seedance-2.0/mini/image-to-video", "video_seedance.mp4", extra_payload={"duration": "5"})
    with open(os.path.join(OUT_DIR, f"_step2_result_{which}.json"), "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    main()
