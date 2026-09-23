#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""919番 手順2: 16:9拡張済み画像2枚から、minimax/h3-max-turbo/image-to-video で
1080p・5秒のループ動画を作る。image_url と end_image_url に同じ画像を入れて
逆再生に頼らないループにする（発注前検品PASS済みプロンプトをそのまま使う）。"""
import os, sys, json, time, urllib.request, urllib.error

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

OUT_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/919-zen"
os.makedirs(OUT_DIR, exist_ok=True)

MODEL = "minimax/h3-max-turbo/image-to-video"

COMMON = (
    "camera is completely motionless, locked off on a tripod for the entire clip: "
    "zero pan, zero tilt, zero zoom, zero push-in, zero dolly, zero orbit, zero "
    "parallax, zero handheld shake, zero rack focus. framing is pixel-identical "
    "in every single frame from first to last.\n\n"
    "the motion forms one seamless forward loop: everything moves in a single "
    "forward direction only and returns naturally to its starting state by the "
    "final frame, so the last frame matches the first frame perfectly. the clip "
    "must never play backwards, never rewind, and never mirror or repeat its "
    "first half to fake the ending — the return to the start state is achieved "
    "purely by continuing the natural forward motion, not by reversing it. "
    "even though the start image and end image are the identical picture, do "
    "NOT take the shortcut of playing forward then reversing the same motion "
    "backward to get back to it — that shortcut is strictly forbidden. instead, "
    "the motion must complete one full natural forward cycle (for example: mist "
    "or waves advance all the way through their motion and settle back into the "
    "same resting shape by moving forward the whole time, never by rewinding).\n\n"
    "photorealistic, no added objects, no added people, no text, no watermark."
)

TARGETS = {
    "chashitsu": {
        "image_url": "https://v3b.fal.media/files/b/0aaab8a3/BhtbK5ECjt_0t4a9LS566_S2EwFqUk.png",
        "out": os.path.join(OUT_DIR, "chashitsu_loop.mp4"),
        "prompt": COMMON + "\n\n" + (
            "Only the green foliage visible outside the round window sways very gently, "
            "as if in a faint breeze — a slow, small, continuous drift that returns to "
            "its starting position. Everything else is completely still: the stacked "
            "stone object, the tatami and wooden floor, the shadows on the floor, "
            "the cherry blossom branch, and the walls do not move or change shape. "
            "Light and color stay constant throughout."
        ),
    },
    "kuroihama": {
        "image_url": "https://v3b.fal.media/files/b/0aaab8aa/y_CYNAd8fTqqcicSyb2Xd_dbP67uyq.png",
        "out": os.path.join(OUT_DIR, "kuroihama_loop.mp4"),
        "prompt": COMMON + "\n\n" + (
            "Waves roll in toward the shore and recede in one continuous natural cycle, "
            "and the clouds drift slowly in a single direction across the sky, completing "
            "one cycle by the final frame. The stacked stone object, the rock formations, "
            "and the black sand beach itself remain completely still and do not change "
            "shape, size, or position. Foam and spray behave naturally; water never "
            "flows backwards."
        ),
    },
}


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


def gen_one(name, cfg):
    payload = {
        "prompt": cfg["prompt"],
        "image_url": cfg["image_url"],
        "end_image_url": cfg["image_url"],
        "resolution": "1080P",
        "duration": 5,
        "prompt_expansion_mode": "disabled",
    }
    print(f"--- {name}: submit ---")
    try:
        r = post(f"https://queue.fal.run/{MODEL}", payload)
    except urllib.error.HTTPError as e:
        print(f"SUBMIT_FAIL: HTTP {e.code} {e.read().decode('utf-8')[:1500]}")
        return {"ok": False, "error": "submit_fail"}
    status_url = r.get("status_url")
    response_url = r.get("response_url")
    start = time.time()
    while time.time() - start < 280:
        s = get(status_url)
        st = s.get("status")
        if st == "COMPLETED":
            data = get(response_url)
            video = data.get("video") or {}
            v_url = video.get("url")
            if not v_url:
                print("NO_VIDEO:", json.dumps(data)[:1000])
                return {"ok": False, "error": "no_video", "raw": data}
            download(v_url, cfg["out"])
            print(f"{name}: DONE -> {cfg['out']} url={v_url}")
            with open(cfg["out"] + ".json", "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return {"ok": True, "path": cfg["out"], "url": v_url}
        elif st in ("FAILED", "ERROR"):
            print(f"{name}: FAILED:", s)
            return {"ok": False, "error": str(s)}
        time.sleep(5)
    print(f"{name}: TIMEOUT")
    return {"ok": False, "error": "timeout"}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    results = {}
    for name, cfg in TARGETS.items():
        if which != "all" and which != name:
            continue
        results[name] = gen_one(name, cfg)
    with open(os.path.join(OUT_DIR, "_step2_results.json"), "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
