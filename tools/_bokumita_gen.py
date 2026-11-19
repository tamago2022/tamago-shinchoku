#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""『僕は見た、未来を待つ人々を』静止画9枚を fal(nano-banana) で作る。
費用メモ：status/bokumita/hiyou_memo.md（9枚で約54円・上限300円）。
作家名はプロンプトに入れない。特徴だけを言葉で指定する。
使い方: python3 tools/_bokumita_gen.py <出力dir> [名前...]   （名前を渡すとその分だけ作り直す）
"""
import sys as _sk_sys, os as _sk_os; _sk_sys.path.insert(0, _sk_os.path.dirname(_sk_os.path.abspath(__file__))); import saifu_kanmon as _sk; _sk.mon(__name__)  # ★2026-10-15 財布の関所：停止札があれば何も叩かず終わる
import os, sys, json, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ANKEN = "僕は見た、未来を待つ人々を"
YEN_PER = 6.0
MODEL = "fal-ai/nano-banana"

BASE = ("Black-and-white documentary street photograph of a contemporary Asian city, shot on medium-format "
        "film, silver gelatin print look, visible natural film grain, slightly soft imperfect focus, deep "
        "inky blacks and luminous highlights, strong contrast between light and shadow, hard backlight, "
        "architectural geometry, large areas of empty negative space, people appear small in the frame, "
        "quiet and still mood, unposed, candid, no text, no signs readable, no logos, no watermark, "
        "no color, 16:9. ")

# 室内の場面は「都市」を混ぜると街と室内の合成（二分割）になった（04・08 実測）→室内専用の土台
BASE_IN = ("A single continuous black-and-white photograph showing ONE scene only, the entire frame is the "
           "inside of one small room, nothing outside the room is visible except through its window. Not a "
           "collage, not a diptych, no split frame, no inset picture. Shot on medium-format film, silver "
           "gelatin print look, visible natural film grain, slightly soft imperfect focus, deep blacks, "
           "strong contrast between window light and shadow, large calm empty areas, candid and quiet, "
           "no text, no logos, no watermark, no color, 16:9. ")

SCENES = [
    ("01_machi", "Seen from high above: a narrow street between tall old buildings at early morning, a single "
                 "diagonal shaft of sunlight cuts across the pavement, one small figure stands waiting at the "
                 "edge of the light, everything else in deep shadow."),
    ("02_sanji", "Night, 3 a.m.: the facade of a large apartment block, a grid of dark windows, only one window "
                 "glows with a pale cold screen light, a tiny silhouette of a person sitting inside it."),
    ("03_himitsu", "A vast empty railway station hall at night, tall windows throwing long beams of light onto "
                   "the floor, one person sits alone on a long bench, face faintly lit from below by a phone, "
                   "head slightly bowed."),
    ("04_fude", "INTERIOR. An empty painter's studio, morning light from a single high window forms a sharp diagonal "
                "rectangle on the floor, a paintbrush laid down on a wooden table beside a blank canvas, "
                "dust floating in the light, no people."),
    ("05_ai", "A rain-wet narrow alley at dusk, reflections on the stones, a single person with an umbrella "
              "walking away into the backlight, steam and haze, their long shadow stretching toward the camera."),
    ("06_mirai", "The lobby of a modern glass office tower, enormous geometric shadows of the window frames fall "
                 "across the floor and walls, three small men in suits stand far apart, dwarfed by the "
                 "architecture, looking out of the glass."),
    ("07_shigoto", "A wide pedestrian crossing at morning rush hour photographed against the low sun, crowds "
                   "reduced to dark silhouettes with long shadows, in the middle one person stands still "
                   "holding a small cardboard box, everyone else in motion."),
    ("08_daidokoro", "INTERIOR. A small old apartment kitchen at sunrise, soft light through a small window and steam, "
                     "a mother at the stove with a frying pan, a small child standing beside her looking up, "
                     "both seen from behind as gentle silhouettes, warm and tender atmosphere."),
    ("09_asagohan", "Close view of a small kitchen table in morning window light: two plates, one fried egg "
                    "slightly burnt at the edges, two cups, chopsticks, crumbs, a chair pulled out, the light "
                    "falling softly across the table, intimate and calm, no people."),
]


def key():
    with open(os.path.expanduser("~/.fal_key")) as f:
        return f.read().strip()


def req(url, payload=None, k=None, timeout=30):
    h = {"Authorization": "Key " + k}
    data = None
    if payload is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    r = urllib.request.Request(url, data=data, headers=h, method="POST" if data else "GET")
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.read()


def main():
    out = sys.argv[1]
    want = set(sys.argv[2:])
    scenes = [s for s in SCENES if not want or s[0] in want]
    os.makedirs(out, exist_ok=True)
    import yosan
    ok, why = yosan.mitsumori("fal", YEN_PER * len(scenes), "%s 静止画%d枚" % (ANKEN, len(scenes)), anken=ANKEN)
    print(why)
    if not ok:
        raise SystemExit(1)
    k = key()
    jobs = {}
    for name, p in scenes:
        try:
            if p.startswith("INTERIOR. "):
                pr = BASE_IN + p[len("INTERIOR. "):]
            else:
                pr = BASE + p
            r = json.loads(req("https://queue.fal.run/" + MODEL, {"prompt": pr, "aspect_ratio": "16:9",
                                                                   "num_images": 1, "output_format": "png"}, k))
            jobs[name] = r
            print("submit", name, r.get("status"))
        except Exception as e:
            print("SUBMIT_FAIL", name, e)
    done = 0
    t0 = time.time()
    pend = set(jobs)
    while pend and time.time() - t0 < 900:
        for name in list(pend):
            try:
                s = json.loads(req(jobs[name]["status_url"], k=k))
            except Exception as e:
                print("STATUS_ERR", name, e)
                continue
            st = s.get("status")
            if st == "COMPLETED":
                d = json.loads(req(jobs[name]["response_url"], k=k))
                u = ((d.get("images") or [{}])[0]).get("url")
                if u:
                    ext = ".png" if ".png" in u else ".jpg"
                    with open(os.path.join(out, name + ext), "wb") as f:
                        f.write(req(u, k=k, timeout=90))
                    done += 1
                    print("DONE", name)
                else:
                    print("NOIMG", name, str(d)[:300])
                pend.discard(name)
            elif st in ("FAILED", "ERROR"):
                print("FAILED", name, s)
                pend.discard(name)
        if pend:
            time.sleep(4)
    yen = YEN_PER * done
    yosan.tsukatta("fal", yen, "%s 静止画%d枚" % (ANKEN, done), usd=round(0.039 * done, 3),
                   src="tools/_bokumita_gen.py", anken=ANKEN, model=MODEL, ryou="%d枚" % done)
    with open(os.path.join(out, "_cost.txt"), "a") as f:
        f.write("%s %d枚 %.0f円（推定）\n" % (time.strftime("%F %T"), done, yen))
    print("合計 %d/%d 枚・%.0f円（推定）" % (done, len(scenes), yen))


if __name__ == "__main__":
    main()
