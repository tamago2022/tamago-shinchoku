#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""空き容量の番人（2026-10-11・空き668MBの事故を受けて）。

たまごさんの指示（2026-10-11）：
  「心臓に空き容量の見張りを入れる。30GBを切ったら Dispatch に警告を出し、
    20GBを切ったら工場の新規発車を止める。」

心臓(heartbeat.sh)から約1分おきに呼ばれる。statvfs を1回読むだけ（0.01秒・0円）。
  ★2026-10-16 引き上げ（たまごさん「30GBを切ることは二度とないように」）：
  ・100GB未満 → Dispatch へ警告＋原因調査（tools/youryou_tantei.py）を自動で開始＋片付け（shimau.go）
  ・50GB未満 → status/no_launch.flag を立てる（auto_launcher.py が既に見て発車を止める）
  ・55GB以上に戻ったら、自分が立てた flag だけ外す（止める線と外す線を同じにするとバタつく）
  ・30GB未満 → 救急（tools/youryou_kyuukyuu.py＝作り直せるキャッシュだけ消す）を自動で1回起こす（6時間に1回まで）
目印は「空き容量の番人」。disk_guardian.py の目印「容量見張り」とは別の文字にしてある
（同じ文字を含むと、あちらが10GBで勝手に外してしまうため）。
  ・100GB未満 → 片付け係（tools/shimau.py＝場所ごとの上限 youryou_jougen を含む）を1時間に1回すぐ起こす（2026-10-16）
  ・空きの推移を10分おきに7日分 status/public/youryou_suii.json へ（進捗表 health.json の aki に写る）。
    24時間で5GB以上減っていたら Dispatch に「減り続けている」と知らせる（12時間に1回まで）
結果：status/public/youryou_mihari.json
"""
import io
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FLAG = os.path.join(REPO, "status", "no_launch.flag")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
STATE = os.path.join(REPO, "status", "youryou_mihari_state.json")
PUB = os.path.join(REPO, "status", "public", "youryou_mihari.json")
KYUUKYUU_GO = os.path.join(REPO, "status", "youryou_kyuukyuu.go")
SHIMAU_GO = os.path.join(REPO, "status", "shimau.go")
SUII = os.path.join(REPO, "status", "public", "youryou_suii.json")
SHIMAU_EVERY = 3600
SUII_EVERY = 600
HERU_EVERY = 12 * 3600
MARK = "空き容量の番人"

WARN_GB = 100     # 2026-10-16 たまごさん「30GBを切ることは二度とないように」→ 100GBで原因調査を自動開始
STOP_GB = 50      # 50GBで新規発車停止
RELEASE_GB = 55
KYUUKYUU_GB = 30  # 30GBで救急（作り直せるキャッシュ）
TANTEI_EVERY = 3 * 3600
WARN_EVERY = 2 * 3600
KYUUKYUU_EVERY = 6 * 3600


def free_gb():
    for p in ("/System/Volumes/Data", "/"):
        try:
            st = os.statvfs(p)
            return st.f_bavail * st.f_frsize / 1e9
        except Exception:
            continue
    return None


def load(p, d):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def save(p, o):
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with io.open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(o, f, ensure_ascii=False, indent=1)
        os.replace(p + ".tmp", p)
    except Exception:
        pass


def outbox(title, msg):
    try:
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"), "n": "youryou-mihari",
                                "type": "youryou_akai", "title": title, "message": msg},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass


def main():
    g = free_gb()
    if g is None:
        return
    now = time.time()
    st = load(STATE, {})
    band = "青" if g >= WARN_GB else ("黄" if g >= STOP_GB else "赤")

    # 30GB未満：警告（同じ帯は2時間に1回まで・帯が悪化したら即）
    if band != "青":
        if st.get("band") != band or now - st.get("warned_at", 0) > WARN_EVERY:
            outbox("Macの空き容量が%.1fGBです" % g,
                   ("100GBを切ったので原因調査（youryou_tantei）と片付け（shimau）を自動で始めました。" if band == "黄" else "50GBを切ったので新規発車を止めました。") +
                   "原因の測定は tools/youryou_kyuukyuu.py（status/youryou_kyuukyuu.json）。")
            st["warned_at"] = now

    # 20GB未満：発車を止める／22GB以上で自分の旗だけ外す
    if g < STOP_GB and not os.path.exists(FLAG):
        try:
            with io.open(FLAG, "w", encoding="utf-8") as f:
                f.write("%s：ディスク空き容量が%.1fGB（50GB未満）。新規発車を止めました（%s）。55GBに戻れば自動で外れます。\n"
                        % (MARK, g, time.strftime("%F %T")))
        except Exception:
            pass
    elif g >= RELEASE_GB and os.path.exists(FLAG):
        try:
            if MARK in io.open(FLAG, encoding="utf-8").read():
                os.remove(FLAG)
        except Exception:
            pass

    # 10GB未満：救急（作り直せるキャッシュだけ）を自動で1回
    if g < KYUUKYUU_GB and now - st.get("kyuukyuu_at", 0) > KYUUKYUU_EVERY:
        try:
            open(KYUUKYUU_GO, "w").close()
            st["kyuukyuu_at"] = now
        except Exception:
            pass

    # 2026-10-16 100GB未満：原因調査（探偵）を自動で始める（3時間に1回まで・心臓から切り離して走らせる）
    if g < WARN_GB and now - st.get("tantei_at", 0) > TANTEI_EVERY:
        try:
            import subprocess
            subprocess.Popen(["python3", os.path.join(HERE, "1144_hanareru.py"),
                              os.path.join(REPO, "status", "youryou_tantei_jidou.log"),
                              "python3", os.path.join(HERE, "youryou_tantei.py")])
            st["tantei_at"] = now
        except Exception:
            pass

    # 2026-10-16 100GB未満：片付け係をすぐ起こす（1時間に1回まで）
    if g < WARN_GB and now - st.get("shimau_at", 0) > SHIMAU_EVERY:
        try:
            open(SHIMAU_GO, "w").close()
            st["shimau_at"] = now
        except Exception:
            pass

    # 2026-10-16 推移（10分おき・7日分）と「24時間で5GB以上減った」知らせ
    su = load(SUII, {"points": []})
    pts = su.get("points", [])
    if not pts or now - pts[-1][0] >= SUII_EVERY:
        pts.append([int(now), round(g, 2)])
        pts = [x for x in pts if now - x[0] <= 7 * 86400]
        day = [x for x in pts if now - x[0] <= 86400]
        d24 = round(g - day[0][1], 2) if day else 0
        su = {"at": time.strftime("%F %T"), "free_gb": round(g, 2), "diff_24h_gb": d24,
              "min_7d_gb": min(x[1] for x in pts), "points": pts}
        save(SUII, su)
        if d24 <= -5 and now - st.get("heru_at", 0) > HERU_EVERY:
            outbox("Macの空きが24時間で%.1fGB減りました（今%.1fGB）" % (-d24, g),
                   "減り続けています。犯人は status/public/youryou_tantei.json（tools/youryou_tantei.py）で測れます。")
            st["heru_at"] = now

    st["band"] = band
    save(STATE, st)
    flag_mine = False
    try:
        flag_mine = os.path.exists(FLAG) and MARK in io.open(FLAG, encoding="utf-8").read()
    except Exception:
        pass
    save(PUB, {"at": time.strftime("%F %T"), "free_gb": round(g, 2), "band": band,
               "warn_gb": WARN_GB, "stop_gb": STOP_GB, "release_gb": RELEASE_GB,
               "launch_stopped_by_me": flag_mine})


if __name__ == "__main__":
    main()
