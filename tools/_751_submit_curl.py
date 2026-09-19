#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""751番: urllibのTLSハンドシェイクが2回連続タイムアウトしたため、curlへ経路を変えて
image-to-videoモデルへ投入する。base64ペイロードは一時ファイル、認証ヘッダも
一時ファイル経由でcurlへ渡す(コマンドラインにキーを出さない)。"""
import os, sys, json, base64, subprocess, tempfile

KEY_PATH = os.path.expanduser("~/.fal_key")
with open(KEY_PATH) as f:
    FAL_KEY = f.read().strip()

SRC = "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/751-zen-beach/16x9_widened_v2.png"

MOTION_PROMPT = (
    "Extremely subtle, gentle ambient motion only: thin mist drifts very slowly across the horizon and "
    "around the distant sea stacks, the wet sand and shallow tide water surface ripples very slightly, "
    "faintly reflecting the warm sunset light. The standing person, the sun, and the giant stone monolith "
    "stack remain completely still and unchanged. Static locked-off camera, absolutely no zoom, no pan, no "
    "camera movement. The landscape is barely breathing, extremely slow and subtle, calm and quiet."
)


def main():
    model = sys.argv[1]
    extra = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    image_field = sys.argv[3] if len(sys.argv) > 3 else "image_url"

    with open(SRC, "rb") as f:
        b = f.read()
    uri = "data:image/png;base64," + base64.b64encode(b).decode("ascii")
    payload = {image_field: uri, "prompt": MOTION_PROMPT}
    payload.update(extra)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as pf:
        json.dump(payload, pf)
        payload_path = pf.name
    out_path = "/tmp/751_submit_out.json"
    with tempfile.NamedTemporaryFile("w", suffix=".curlcfg", delete=False) as cf:
        cf.write(f'header = "Authorization: Key {FAL_KEY}"\n')
        cf.write('header = "Content-Type: application/json"\n')
        cf.write(f'url = "https://queue.fal.run/{model}"\n')
        cf.write(f'data = "@{payload_path}"\n')
        cf.write(f'output = "{out_path}"\n')
        cf.write('write-out = "HTTP:%{http_code}\\n"\n')
        cfg_path = cf.name

    cmd = ["curl", "-sS", "-m", "120", "-X", "POST", "-K", cfg_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout)
    print(r.stderr, file=sys.stderr)
    os.unlink(payload_path)
    os.unlink(cfg_path)
    if os.path.exists(out_path):
        with open(out_path) as f:
            print(f.read()[:2000])


if __name__ == "__main__":
    main()
