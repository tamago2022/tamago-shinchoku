#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""テザリングの関所（2026-10-11・たまごさん「Wi-Fiが重すぎてテザリング中。通信量が限られる」）

テザリング中（Wi-Fi名が iPhone/Android 等、または iPhone の配る 172.20.10.x）は、
工場の大きな送受信を止め、Wi-Fi に戻ったら自動で再開する。心臓から1分おき。

  テザリング中に止めるもの：
    ・git push（tamago-shinchoku のまとめての push）→ 走っているものは止め、新しいものは
      .githooks/pre-push が status/public/tethering.json を見て出さない（Wi-Fiで自動再開）
    ・yt-dlp／rclone／ネットへ出る ffmpeg／1145_page.py（3000ページ取得）／朗読ループ tts_loop.py
      ／Playwright（kirikae_sokutei の測定1本だけは通す）→ SIGSTOP（Wi-Fiで SIGCONT）
    ・Google ドライブ → 終了（Wi-Fiで open -a で起動し直す）
  触らないもの：iCloud（システムの bird）。止め方がアプリ設定しか無いため、報告のみ。
  Wi-Fi 側：Google ドライブの送受信に上限（送信 500KB/s・受信 2000KB/s）をかけ、上りを使い切らせない。

  python3 tools/tethering_kanmon.py            # 判定して止める／戻す
  python3 tools/tethering_kanmon.py --self-test
  手動：status/tethering_force に on / off と書くと判定より優先（消せば自動判定）
"""
import json, os, re, signal, subprocess, sys, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(REPO, "status", "public", "tethering.json")
FORCE = os.path.join(REPO, "status", "tethering_force")
LOG = os.path.join(REPO, "status", "tethering.log")

TETHER_SSID = re.compile(r"iphone|android|pixel|galaxy|xperia|aquos|hotspot|テザリング|tether", re.I)
STOP_PAT = [
    re.compile(r"(^|/)yt-dlp(\s|$)|yt_dlp"),
    re.compile(r"(^|/)rclone\s"),
    re.compile(r"(^|/)ffmpeg\s.*https?://"),
    re.compile(r"tools/1145_page\.py"),
    re.compile(r"roudoku_enraku/tts_loop\.py"),
    re.compile(r"ms-playwright/"),
]
PUSH_PAT = re.compile(r"git .*tamago-shinchoku.* push |git-remote-https origin https://github\.com/tamago2022/tamago-shinchoku")
DRIVE_TX, DRIVE_RX = 500, 2000


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception:
        return ""


def is_tether(ssid, gw):
    return bool(ssid and TETHER_SSID.search(ssid)) or gw.startswith("172.20.10.")


def kansoku():
    ssid = ""
    for i in ("en0", "en1"):
        o = sh(["networksetup", "-getairportnetwork", i])
        if ":" in o and "not associated" not in o:
            ssid = o.split(":", 1)[1].strip()
            break
    gw = ""
    for l in sh(["route", "-n", "get", "default"]).splitlines():
        if "gateway:" in l:
            gw = l.split(":", 1)[1].strip()
    return ssid, gw


def procs():
    out = []
    for l in sh(["ps", "-axo", "pid=,ppid=,command="]).splitlines():
        p = l.strip().split(None, 2)
        if len(p) == 3:
            out.append((int(p[0]), int(p[1]), p[2]))
    return out


def ancestors_have(pid, table, word):
    par = {p: (pp, c) for p, pp, c in table}
    for _ in range(12):
        if pid not in par:
            return False
        pp, c = par[pid]
        if word in c:
            return True
        pid = pp
    return False


def load():
    try:
        return json.load(open(ST))
    except Exception:
        return {"tethering": False, "stopped": [], "drive_quit": False}


def save(d):
    os.makedirs(os.path.dirname(ST), exist_ok=True)
    d["at"] = time.strftime("%F %T")
    tmp = ST + ".tmp"
    json.dump(d, open(tmp, "w"), ensure_ascii=False, indent=1)
    os.replace(tmp, ST)


def log(s):
    with open(LOG, "a") as f:
        f.write("%s %s\n" % (time.strftime("%F %T"), s))


def drive_caps():
    for k, v in (("BandwidthTxKBPS", DRIVE_TX), ("BandwidthRxKBPS", DRIVE_RX)):
        sh(["defaults", "write", "com.google.drivefs.settings", k, "-int", str(v)])


def main():
    if "--self-test" in sys.argv:
        ok = (is_tether("iPhone (3)", "192.168.0.1") and is_tether("", "172.20.10.1")
              and not is_tether("Buffalo-G-1234", "192.168.11.1")
              and STOP_PAT[2].search("/usr/local/bin/ffmpeg -i https://x/y.m3u8 o.mp4")
              and not STOP_PAT[2].search("/usr/local/bin/ffmpeg -i a.mov b.mp4")
              and PUSH_PAT.search("/usr/bin/git -C /Users/mac/tamago/tamago-shinchoku -c x push origin HEAD:main"))
        print("SELFTEST", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    ssid, gw = kansoku()
    teth = is_tether(ssid, gw)
    try:
        f = open(FORCE).read().strip().lower()
        teth = {"on": True, "off": False}.get(f, teth)
    except Exception:
        pass
    d = load()
    d.update({"ssid": ssid, "gateway": gw})
    table = procs()
    me = os.getpid()

    if teth:
        if not d.get("tethering"):
            log("テザリングを検知（%s / %s）。工場の大きな送受信を止めます" % (ssid, gw))
        d["tethering"] = True
        have = {(s["pid"], s["cmd"]) for s in d.get("stopped", [])}
        for pid, _, cmd in table:
            if pid == me:
                continue
            if PUSH_PAT.search(cmd):
                try:
                    os.kill(pid, signal.SIGTERM); log("push を止めた %d %s" % (pid, cmd[:90]))
                except Exception:
                    pass
                continue
            if any(p.search(cmd) for p in STOP_PAT):
                if "ms-playwright/" in cmd and ancestors_have(pid, table, "kirikae_sokutei"):
                    continue
                if (pid, cmd) in have:
                    continue
                try:
                    os.kill(pid, signal.SIGSTOP)
                    d.setdefault("stopped", []).append({"pid": pid, "cmd": cmd})
                    log("一時停止 %d %s" % (pid, cmd[:90]))
                except Exception:
                    pass
        if any("Google Drive.app/Contents/MacOS/Google Drive" in c for _, _, c in table):
            sh(["pkill", "-x", "Google Drive"])
            d["drive_quit"] = True
            log("Google ドライブを終了（Wi-Fiで起動し直す）")
    else:
        if d.get("tethering"):
            log("Wi-Fi に戻った（%s）。止めたものを再開します" % ssid)
        alive = {(p, c) for p, _, c in table}
        for s in d.get("stopped", []):
            if (s["pid"], s["cmd"]) in alive:
                try:
                    os.kill(s["pid"], signal.SIGCONT); log("再開 %d" % s["pid"])
                except Exception:
                    pass
        drive_caps()
        if d.get("drive_quit"):
            sh(["open", "-g", "-a", "Google Drive"]); log("Google ドライブを起動し直した（上限 送%d/受%d KB/s）" % (DRIVE_TX, DRIVE_RX))
        d.update({"tethering": False, "stopped": [], "drive_quit": False})
    save(d)
    print(json.dumps({k: d[k] for k in ("tethering", "ssid", "gateway")}, ensure_ascii=False), len(d.get("stopped", [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
