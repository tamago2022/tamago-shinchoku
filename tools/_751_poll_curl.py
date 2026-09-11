#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""751番: curlでキューをポーリングし、完了したら動画をダウンロードする。"""
import os, sys, json, time, subprocess, tempfile

KEY_PATH = os.path.expanduser("~/.fal_key")
with open(KEY_PATH) as f:
    FAL_KEY = f.read().strip()


def curl_get(url, out_path=None):
    with tempfile.NamedTemporaryFile("w", suffix=".curlcfg", delete=False) as cf:
        cf.write(f'header = "Authorization: Key {FAL_KEY}"\n')
        cf.write(f'url = "{url}"\n')
        if out_path:
            cf.write(f'output = "{out_path}"\n')
        else:
            cf.write('output = "/tmp/751_poll_body.json"\n')
        cfg_path = cf.name
    cmd = ["curl", "-sS", "-m", "60", "-K", cfg_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(cfg_path)
    if out_path:
        return None
    with open("/tmp/751_poll_body.json") as f:
        return json.load(f)


def main():
    status_url = sys.argv[1]
    response_url = sys.argv[2]
    out_path = sys.argv[3]
    start = time.time()
    while time.time() - start < 600:
        s = curl_get(status_url)
        st = s.get("status")
        print(time.strftime("%H:%M:%S"), st)
        if st == "COMPLETED":
            data = curl_get(response_url)
            vid = data.get("video") or {}
            vid_url = vid.get("url")
            if not vid_url:
                print("NO_VIDEO:", json.dumps(data)[:1000])
                sys.exit(1)
            curl_get(vid_url, out_path=out_path)
            print("DONE ->", out_path)
            print("url:", vid_url)
            with open(out_path + ".json", "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return
        elif st in ("FAILED", "ERROR"):
            print("FAILED:", s)
            sys.exit(1)
        time.sleep(6)
    print("TIMEOUT")
    sys.exit(1)


if __name__ == "__main__":
    main()
